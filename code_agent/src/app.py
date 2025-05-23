#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
import time
from typing import List, Dict, Optional, Set, Union
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich import box
from rich.markdown import Markdown
from rich.theme import Theme
from rich.style import Style as RichStyle

# Add prompt_toolkit imports
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle

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

# Custom orange theme color
ORANGE_COLOR = "#FF8C69"

# Custom completers for OpenCursor
class CommandCompleter(Completer):
    """Completer for OpenCursor commands"""
    def __init__(self, commands):
        self.commands = commands
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Complete commands that start with /
        if text.startswith('/'):
            word = text.lstrip('/')
            for command in self.commands:
                cmd = command.lstrip('/')
                if cmd.startswith(word):
                    # Return the full command with the / prefix
                    yield Completion(
                        text=cmd,
                        start_position=-len(word),
                        display=command,  # Show the full command with / in the dropdown
                        style='class:command'
                    )

class FileCompleter(Completer):
    """Completer for file paths with fuzzy matching"""
    def __init__(self, workspace_root):
        self.workspace_root = Path(workspace_root)
        # Cache files to avoid scanning the filesystem on every keystroke
        self._cached_files = None
        self._last_cache_time = 0
    
    def _get_all_files(self):
        """Get all files in the workspace with cache support"""
        current_time = time.time()
        # Refresh cache every 5 seconds
        if self._cached_files is None or (current_time - self._last_cache_time) > 5:
            all_files = []
            for root, dirs, files in os.walk(self.workspace_root):
                # Skip hidden directories and __pycache__
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                for file in files:
                    if not file.startswith('.'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.workspace_root)
                        all_files.append(rel_path)
            
            self._cached_files = all_files
            self._last_cache_time = current_time
        
        return self._cached_files
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        # Complete file paths that start with @
        if text.startswith('@'):
            path_text = text[1:]  # Remove @ for path completion
            
            # Get all files in the workspace
            all_files = self._get_all_files()
            
            # Filter files based on input
            matches = []
            for file_path in all_files:
                # Different matching strategies
                if not path_text:
                    # Show all files if no input
                    matches.append((0, file_path))
                elif path_text.lower() in file_path.lower():
                    # Simple substring match
                    match_pos = file_path.lower().find(path_text.lower())
                    matches.append((match_pos, file_path))
                elif all(c.lower() in file_path.lower() for c in path_text):
                    # Fuzzy match - all characters appear in order
                    matches.append((100, file_path))  # Lower priority
            
            # Sort by match position and then by path length
            matches.sort(key=lambda x: (x[0], len(x[1])))
            
            # Limit results
            for _, file_path in matches[:20]:
                yield Completion(
                    text=file_path,
                    start_position=-len(path_text),
                    display=file_path,
                    style='class:file'
                )

class OpenCursorCompleter(Completer):
    """Combined completer for OpenCursor"""
    def __init__(self, commands, workspace_root):
        self.command_completer = CommandCompleter(commands)
        self.file_completer = FileCompleter(workspace_root)
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        if text.startswith('/'):
            # Handle command completions
            yield from self.command_completer.get_completions(document, complete_event)
        elif text.startswith('@'):
            # Handle file completions
            yield from self.file_completer.get_completions(document, complete_event)
        elif not text:
            # If no text yet, suggest both prefixes
            yield Completion(
                text='/',
                start_position=0,
                display='/ (command)',
                style='class:command'
            )
            yield Completion(
                text='@',
                start_position=0,
                display='@ (file)',
                style='class:file'
            )

class OpenCursorApp:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", workspace_path: Optional[str] = None):
        # Use provided workspace path or current working directory
        self.current_workspace = Path(workspace_path).resolve() if workspace_path else Path.cwd()
        
        # Initialize agent with current workspace
        self.agent = CodeAgent(model_name=model_name, host=host, workspace_root=str(self.current_workspace))
        
        # Create custom theme with orange accent color
        custom_theme = Theme({
            "info": RichStyle(color="cyan"),
            "warning": RichStyle(color="yellow"),
            "error": RichStyle(color="red"),
            "success": RichStyle(color="green"),
            "orange": RichStyle(color=ORANGE_COLOR),
            "orange.border": RichStyle(color=ORANGE_COLOR),
            "orange.title": RichStyle(color=ORANGE_COLOR, bold=True),
        })
        
        # Initialize console with custom theme and full width
        self.console = Console(theme=custom_theme, width=None)
        
        # Create custom box styles
        self.orange_box_rounded = box.ROUNDED
        self.orange_box_simple = box.SIMPLE
        
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
        self.tool_results = []  # Store recent tool results
        
        # Current mode (default is "OpenCursor")
        self.current_mode = "OpenCursor"
        
        # Define prompt styles
        self.style = Style.from_dict({
            'command': '#00FFFF bold',  # Cyan for commands
            'file': '#00FF00',          # Green for files
            'prompt': '#FFFFFF bold',   # White bold for prompt
        })
        
        # Create key bindings
        kb = KeyBindings()
        
        @kb.add('c-space')
        def _(event):
            """Toggle completion or select next completion with Ctrl+Space"""
            buff = event.app.current_buffer
            if buff.complete_state:
                buff.complete_next()
            else:
                buff.start_completion(select_first=False)
        
        @kb.add('c-n')
        def _(event):
            """Navigate to next completion with Ctrl+N"""
            buff = event.app.current_buffer
            if buff.complete_state:
                buff.complete_next()
        
        @kb.add('c-p')
        def _(event):
            """Navigate to previous completion with Ctrl+P"""
            buff = event.app.current_buffer
            if buff.complete_state:
                buff.complete_previous()
        
        # Initialize prompt_toolkit session
        self.completer = OpenCursorCompleter(self.commands, self.current_workspace)
        self.history = InMemoryHistory()
        self.session = PromptSession(
            history=self.history,
            style=self.style,
            completer=self.completer,
            complete_while_typing=True,
            complete_in_thread=True,  # Process completions in a separate thread
            enable_history_search=True,
            complete_style=CompleteStyle.MULTI_COLUMN,  # Show completions in a dropdown
            key_bindings=kb
        )

    def print_logo(self):
        """Print the OpenCursor logo"""
        self.console.print(f"[{ORANGE_COLOR}]{OPENCURSOR_LOGO}[/{ORANGE_COLOR}]")
        
    def print_help(self):
        """Print help information"""
        table = Table(title=f"[{ORANGE_COLOR} bold]OpenCursor Commands[/{ORANGE_COLOR} bold]", box=box.ROUNDED, border_style=ORANGE_COLOR)
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
        agent_modes = Table(title=f"[{ORANGE_COLOR} bold]Agent Modes[/{ORANGE_COLOR} bold]", box=box.ROUNDED, border_style=ORANGE_COLOR)
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
            
        table = Table(title=f"[{ORANGE_COLOR} bold]Files in Context[/{ORANGE_COLOR} bold]", box=box.SIMPLE, border_style=ORANGE_COLOR)
        table.add_column("File", style="green")
        
        for file_path in sorted(self.files_in_context):
            table.add_row(str(file_path.relative_to(self.current_workspace)))
            
        self.console.print(table)
    
    def display_tool_results(self):
        """Display recent tool results in a nice format"""
        if not self.tool_results:
            return
            
        # Create a panel to display tool results
        table = Table(box=box.ROUNDED, title=f"[{ORANGE_COLOR} bold]Recent Tool Results[/{ORANGE_COLOR} bold]", expand=True, border_style=ORANGE_COLOR)
        table.add_column("Tool", style="cyan")
        table.add_column("Result", style="white")
        
        for tool_name, result in self.tool_results[-5:]:  # Show last 5 results
            # Format the result based on tool type
            if tool_name == "web_search":
                # Create a nested table for web search results
                web_results = self._format_web_search_results(result)
                table.add_row(tool_name, web_results)
            elif tool_name in ["read_file", "edit_file", "grep_search", "codebase_search"]:
                # For code-related results, use syntax highlighting where possible
                if "```" in result:
                    # Extract code blocks and format them
                    formatted_result = self._format_code_blocks(result)
                    table.add_row(tool_name, formatted_result)
                else:
                    table.add_row(tool_name, result)
            else:
                # Default formatting for other tools
                table.add_row(tool_name, result)
        
        self.console.print(table)
        
    def _format_web_search_results(self, result: str) -> str:
        """Format web search results into a nested table"""
        lines = result.strip().split('\n')
        
        # Create a nested table for web results
        web_table = Table(box=None, expand=True)
        web_table.add_column("Result", style="white")
        
        current_result = []
        for line in lines:
            if line.strip() == "":
                if current_result:
                    web_table.add_row("\n".join(current_result))
                    current_result = []
            else:
                current_result.append(line)
                
        # Add the last result if any
        if current_result:
            web_table.add_row("\n".join(current_result))
            
        return web_table
        
    def _format_code_blocks(self, result: str) -> str:
        """Format code blocks with syntax highlighting"""
        parts = result.split("```")
        formatted_parts = []
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Regular text
                formatted_parts.append(part)
            else:
                # Code block
                lang_and_code = part.split("\n", 1)
                if len(lang_and_code) > 1:
                    lang = lang_and_code[0].strip()
                    code = lang_and_code[1]
                    syntax = Syntax(code, lang, theme="monokai", line_numbers=True)
                    formatted_parts.append(syntax)
                else:
                    # If no language specified
                    syntax = Syntax(part, "text", theme="monokai")
                    formatted_parts.append(syntax)
                    
        return formatted_parts
        
    def add_file_to_context(self, file_path: str):
        """Add a file to the chat context"""
        path = Path(file_path).resolve()
        if path.exists() and path.is_file():
            self.files_in_context.add(path)
            self.console.print(f"[success]Added {path} to context[/success]")
        else:
            self.console.print(f"[error]File not found: {file_path}[/error]")
    
    def drop_file_from_context(self, file_path: str):
        """Remove a file from the chat context"""
        path = Path(file_path).resolve()
        if path in self.files_in_context:
            self.files_in_context.remove(path)
            self.console.print(f"[success]Removed {path} from context[/success]")
        else:
            self.console.print(f"[error]File not in context: {file_path}[/error]")
    
    def clear_context(self):
        """Clear all files from the chat context"""
        self.files_in_context.clear()
        self.console.print("[success]Cleared all files from context[/success]")
    
    def generate_repo_map(self):
        """Generate a map of the repository"""
        self.console.print(f"[{ORANGE_COLOR} bold]REPOSITORY MAP:[/{ORANGE_COLOR} bold]")
        
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
        table = Table(box=box.SIMPLE, expand=True, border_style=ORANGE_COLOR)
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
            self.console.print("[info]Agent working...[/info]")
            response = await self.agent(args)
            self.console.print(Panel(response, title=f"[{ORANGE_COLOR} bold]Agent Response[/{ORANGE_COLOR} bold]", border_style=ORANGE_COLOR, expand=True))
            self.last_output = response
            
            # Display tool results after agent response
            self.display_tool_results()
        elif command == "/interactive":
            self.console.print("[info]Interactive mode...[/info]")
            # Interactive mode with the agent
            response = await self.agent.interactive(args)
            self.console.print(Panel(response, title=f"[{ORANGE_COLOR} bold]Interactive Response[/{ORANGE_COLOR} bold]", border_style=ORANGE_COLOR, expand=True))
            self.last_output = response
            
            # Display tool results after agent response
            self.display_tool_results()
        elif command == "/chat":
            self.console.print("[info]Chatting...[/info]")
            # Direct chat with LLM without tools
            response = await self.agent.llm_client.chat(user_message=args, tools=None)
            self.console.print(Panel(response.message.content, title=f"[{ORANGE_COLOR} bold]LLM Response[/{ORANGE_COLOR} bold]", border_style=ORANGE_COLOR, expand=True))
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
                self.console.print(f"[success]Focusing on {args}[/success]")
                try:
                    with open(args, 'r') as f:
                        content = f.read()
                    
                    # Determine syntax highlighting based on file extension
                    extension = os.path.splitext(args)[1].lstrip('.')
                    syntax = Syntax(content, extension or "text", line_numbers=True, theme="monokai")
                    self.console.print(Panel(syntax, title=f"[{ORANGE_COLOR} bold]File: {args}[/{ORANGE_COLOR} bold]", border_style=ORANGE_COLOR, expand=True))
                except Exception as e:
                    self.console.print(f"[error]Error reading file: {e}[/error]")
            else:
                self.console.print(f"[error]File not found: {args}[/error]")
        else:
            self.console.print(f"[error]Unknown command: {command}[/error]")
        
        return True
    
    async def run(self, initial_query: Optional[str] = None):
        """Run the application"""
        # Show the logo and welcome message
        self.print_logo()
        self.console.print("[bold green]Welcome to OpenCursor![/bold green] Type [bold]/help[/bold] for available commands.")
        self.console.print(f"[bold cyan]Using workspace:[/bold cyan] {self.current_workspace}")
        
        # Hook into agent's tool processing to capture tool results
        original_process_tool_calls = self.agent.tools_manager.process_tool_calls
        
        async def process_tool_calls_with_capture(*args, **kwargs):
            results = await original_process_tool_calls(*args, **kwargs)
            
            # Capture tool results for display
            tool_calls = args[0]  # First argument is tool_calls list
            for i, tool_call in enumerate(tool_calls):
                if i < len(results):
                    function_name = tool_call['function']['name']
                    result = results[i]
                    self.tool_results.append((function_name, result))
            
            return results
            
        # Replace the method with our wrapped version
        self.agent.tools_manager.process_tool_calls = process_tool_calls_with_capture
        
        running = True
        while running:
            try:
                # Show files in context
                self.show_files_in_context()
                
                # Get user input with prompt_toolkit
                if initial_query:
                    user_input = initial_query
                    initial_query = None  # Reset after first use
                else:
                    # We need to run this in a separate thread since prompt_toolkit is blocking
                    prompt_message = f"{self.current_mode}> "
                    
                    # Use the prompt_toolkit session directly with proper styling
                    user_input = await asyncio.to_thread(
                        lambda: self.session.prompt(
                            prompt_message,
                            # Don't override the completer settings that are already in the session
                        )
                    )
                
                # Handle @ file references
                if user_input.startswith('@'):
                    file_path = user_input[1:]
                    self.add_file_to_context(file_path)
                    continue
                
                # Parse command
                if user_input.startswith('/'):
                    parts = user_input.split(' ', 1)
                    command = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    
                    # Update mode based on command
                    if command == "/agent":
                        self.current_mode = "Agent"
                    elif command == "/chat":
                        self.current_mode = "Chat"
                    elif command == "/interactive":
                        self.current_mode = "Interactive"
                    
                    running = await self.process_command(command, args)
                else:
                    # Default to autonomous agent if no command specified
                    self.current_mode = "Agent"
                    response = await self.agent(user_input)
                    self.console.print(Panel(response, title=f"[{ORANGE_COLOR} bold]Agent Response[/{ORANGE_COLOR} bold]", border_style=ORANGE_COLOR, expand=True))
                    self.last_output = response
                    
                    # Display tool results after agent response
                    self.display_tool_results()
                    
            except KeyboardInterrupt:
                self.console.print("\n[warning]Exiting...[/warning]")
                running = False
            except Exception as e:
                self.console.print(f"[error]Error:[/error] {str(e)}")
        
        self.console.print(f"[{ORANGE_COLOR} bold]Thank you for using OpenCursor![/{ORANGE_COLOR} bold]")

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OpenCursor - An AI-powered code assistant")
    parser.add_argument("-m", "--model", default="qwen3_14b_q6k:latest", help="Model name to use")
    parser.add_argument("--host", default="http://192.168.170.76:11434", help="Ollama host URL")
    parser.add_argument("-w", "--workspace", help="Path to workspace directory")
    parser.add_argument("-q", "--query", default=None, help="Initial query to process")
    args = parser.parse_args()
    
    # Create custom theme with orange accent color
    custom_theme = Theme({
        "info": RichStyle(color="cyan"),
        "warning": RichStyle(color="yellow"),
        "error": RichStyle(color="red"),
        "success": RichStyle(color="green"),
        "orange": RichStyle(color=ORANGE_COLOR),
    })
    
    console = Console(theme=custom_theme, width=None)
    
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
        custom_theme = Theme({"orange": RichStyle(color=ORANGE_COLOR)})
        Console(theme=custom_theme).print(f"\n[orange bold]Goodbye![/orange bold]")

# Add a non-async entry point for the package
def entry_point():
    """Non-async entry point for the package"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        custom_theme = Theme({"orange": RichStyle(color=ORANGE_COLOR)})
        Console(theme=custom_theme).print(f"\n[orange bold]Goodbye![/orange bold]")
