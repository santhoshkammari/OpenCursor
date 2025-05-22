#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
from typing import List, Dict, Optional, Set
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich import box
from rich.markdown import Markdown

from code_agent.src.agent import CodeAgent

# ASCII Art for OPENCURSOR
OPENCURSOR_LOGO = """
  ____  _____  ______ _   _  _____ _    _ _____   _____  ____  _____  
 / __ \|  __ \|  ____| \ | |/ ____| |  | |  __ \ / ____|/ __ \|  __ \ 
| |  | | |__) | |__  |  \| | |    | |  | | |__) | (___ | |  | | |__) |
| |  | |  ___/|  __| | . ` | |    | |  | |  _  / \___ \| |  | |  _  / 
| |__| | |    | |____| |\  | |____| |__| | | \ \ ____) | |__| | | \ \ 
 \____/|_|    |______|_| \_|\_____|\____/|_|  \_\_____/ \____/|_|  \_\\
                                                                      
"""

class OpenCursorApp:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", workspace_path: Optional[str] = None):
        # Use provided workspace path or current working directory
        self.current_workspace = Path(workspace_path).resolve() if workspace_path else Path.cwd()
        
        # Initialize agent with current workspace
        self.agent = CodeAgent(model_name=model_name, host=host, workspace_root=str(self.current_workspace))
        self.console = Console()
        
        # Chat context management
        self.files_in_context: Set[Path] = set()
        self.chat_history: List[Dict[str, str]] = []
        
        # Available commands
        self.commands = [
            "/agent", "/chat", "/add", "/drop", "/clear", 
            "/help", "/exit", "/repomap", "/focus", "/interactive"
        ]
        
        # Output storage
        self.last_output = ""

    def print_logo(self):
        """Print the OpenCursor logo"""
        self.console.print(f"[bold blue]{OPENCURSOR_LOGO}[/bold blue]")
        
    def print_help(self):
        """Print help information"""
        table = Table(title="OpenCursor Commands", box=box.ROUNDED)
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")
        
        table.add_row("/agent <message>", "Send a message to the agent (autonomous mode)")
        table.add_row("/interactive <message>", "Send a message to the agent (interactive mode)")
        table.add_row("/chat <message>", "Chat with the LLM directly (no tools)")
        table.add_row("/add <filepath>", "Add a file to the chat context")
        table.add_row("/drop <filepath>", "Remove a file from the chat context")
        table.add_row("/clear", "Clear all files from the chat context")
        table.add_row("/repomap", "Show a map of the repository")
        table.add_row("/focus <filepath>", "Focus on a specific file")
        table.add_row("/help", "Show this help message")
        table.add_row("/exit", "Exit the application")
        
        self.console.print(table)
        
        # Add information about agent modes
        agent_modes = Table(title="Agent Modes", box=box.ROUNDED)
        agent_modes.add_column("Mode", style="cyan")
        agent_modes.add_column("Description", style="green")
        
        agent_modes.add_row("Autonomous (default)", "Agent works step-by-step without user interaction")
        agent_modes.add_row("Interactive", "Agent performs one tool call at a time, waiting for user input")
        
        self.console.print(agent_modes)
        
    def show_files_in_context(self):
        """Show files currently in context"""
        if not self.files_in_context:
            self.console.print("[red]No files in context[/red]")
            return
            
        table = Table(title="Files in Context", box=box.SIMPLE)
        table.add_column("File", style="green")
        
        for file_path in sorted(self.files_in_context):
            table.add_row(str(file_path.relative_to(self.current_workspace)))
            
        self.console.print(table)
        
    def add_file_to_context(self, file_path: str):
        """Add a file to the chat context"""
        path = Path(file_path).resolve()
        if path.exists() and path.is_file():
            self.files_in_context.add(path)
            self.console.print(f"[green]Added {path} to context[/green]")
        else:
            self.console.print(f"[red]File not found: {file_path}[/red]")
    
    def drop_file_from_context(self, file_path: str):
        """Remove a file from the chat context"""
        path = Path(file_path).resolve()
        if path in self.files_in_context:
            self.files_in_context.remove(path)
            self.console.print(f"[green]Removed {path} from context[/green]")
        else:
            self.console.print(f"[red]File not in context: {file_path}[/red]")
    
    def clear_context(self):
        """Clear all files from the chat context"""
        self.files_in_context.clear()
        self.console.print("[green]Cleared all files from context[/green]")
    
    def generate_repo_map(self):
        """Generate a map of the repository"""
        self.console.print("[bold]REPOSITORY MAP:[/bold]")
        
        # Get all files in the current directory recursively
        all_files = []
        for root, dirs, files in os.walk(self.current_workspace):
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for file in files:
                if not file.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, file), self.current_workspace)
                    all_files.append(rel_path)
        
        # Sort and format files
        table = Table(box=box.SIMPLE)
        table.add_column("File", style="green")
        table.add_column("Status", style="cyan")
        
        for file in sorted(all_files):
            if any(Path(file).resolve() == f for f in self.files_in_context):
                table.add_row(file, "in context")
            else:
                table.add_row(file, "")
                
        self.console.print(table)
    
    async def process_command(self, command: str, args: str) -> bool:
        """Process a command and return whether to continue running"""
        if command == "/exit":
            return False
        elif command == "/help":
            self.print_help()
        elif command == "/agent":
            response = await self.agent(args)
            self.console.print(Panel(response, title="Agent Response", border_style="green"))
            self.last_output = response
        elif command == "/chat":
            self.console.print("[yellow]Chatting with LLM...[/yellow]")
            # Direct chat with LLM without tools
            response = await self.agent.llm_client.chat(user_message=args, tools=None)
            self.console.print(Panel(response.message.content, title="LLM Response", border_style="blue"))
            self.last_output = response.message.content
        elif command == "/add":
            self.add_file_to_context(args)
        elif command == "/drop":
            self.drop_file_from_context(args)
        elif command == "/clear":
            self.clear_context()
        elif command == "/repomap":
            self.generate_repo_map()
        elif command == "/focus":
            if os.path.exists(args):
                self.add_file_to_context(args)
                self.console.print(f"[green]Focusing on {args}[/green]")
                try:
                    with open(args, 'r') as f:
                        content = f.read()
                    
                    # Determine syntax highlighting based on file extension
                    extension = os.path.splitext(args)[1].lstrip('.')
                    syntax = Syntax(content, extension or "text", line_numbers=True)
                    self.console.print(Panel(syntax, title=f"File: {args}", border_style="cyan"))
                except Exception as e:
                    self.console.print(f"[red]Error reading file: {e}[/red]")
            else:
                self.console.print(f"[red]File not found: {args}[/red]")
        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
        
        return True
    
    async def run(self, initial_query: Optional[str] = None):
        """Run the application"""
        # Show the logo and welcome message
        self.print_logo()
        self.console.print("[bold green]Welcome to OpenCursor![/bold green] Type [bold]/help[/bold] for available commands.")
        self.console.print("[bold cyan]NEW:[/bold cyan] OpenCursor now features an autonomous agent mode (default) that works step-by-step without user interaction.")
        self.console.print(f"[bold cyan]Using workspace:[/bold cyan] {self.current_workspace}")
        
        running = True
        while running:
            try:
                # Show files in context
                self.show_files_in_context()
                
                # Get user input
                user_input = initial_query if initial_query else Prompt.ask("[bold cyan]OpenCursor>[/bold cyan]")
                initial_query = None  # Reset after first use
                
                # Parse command
                if user_input.startswith('/'):
                    parts = user_input.split(' ', 1)
                    command = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    running = await self.process_command(command, args)
                else:
                    # Default to autonomous agent if no command specified
                    response = await self.agent(user_input)
                    self.console.print(Panel(response, title="Agent Response", border_style="green"))
                    self.last_output = response
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Exiting...[/yellow]")
                running = False
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
        
        self.console.print("[bold green]Thank you for using OpenCursor![/bold green]")

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OpenCursor - An AI-powered code assistant")
    parser.add_argument("-m", "--model", default="qwen3_14b_q6k:latest", help="Model name to use")
    parser.add_argument("--host", default="http://192.168.170.76:11434", help="Ollama host URL")
    parser.add_argument("-w", "--workspace", help="Path to workspace directory")
    parser.add_argument("-q", "--query", default=None, help="Initial query to process")
    args = parser.parse_args()
    
    console = Console()
    console.print("[bold green]Starting OpenCursor...[/bold green]")
    
    # Create and run the app with parsed arguments
    app = OpenCursorApp(
        model_name=args.model,
        host=args.host,
        workspace_path=args.workspace
    )
    await app.run(initial_query=args.query)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Console().print("\n[bold red]Goodbye![/bold red]")
