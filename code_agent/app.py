#!/usr/bin/env python3
import os
import sys
import asyncio
from typing import List, Dict, Optional, Set
from pathlib import Path

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FormattedTextControl
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers import MarkdownLexer

from code_agent.agent import CodeAgent
from code_agent.llm import LLMClient

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
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434"):
        self.agent = CodeAgent(model_name=model_name, host=host)
        self.history_file = os.path.expanduser("~/.opencursor_history")
        self.session = PromptSession(history=FileHistory(self.history_file))
        
        # Chat context management
        self.files_in_context: Set[Path] = set()
        self.chat_history: List[Dict[str, str]] = []
        self.current_workspace = Path.cwd()
        
        # Command completions
        self.commands = [
            "/agent", "/chat", "/add", "/drop", "/clear", 
            "/help", "/exit", "/repomap", "/focus"
        ]
        self.command_completer = WordCompleter(self.commands)
        
        # Create key bindings
        self.kb = KeyBindings()
        
        # Status message
        self.status_message = ""
        self.output_text = ""
        
        # Initialize the UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the terminal UI"""
        style = Style.from_dict({
            'status': 'bg:#333333 #ffffff',
            'command-line': 'bg:#000000 #ffffff',
            'output-area': 'bg:#101010 #00ff00',
            'header': 'bg:#000080 #ffffff bold',
        })
        
        # Header with logo and status
        self.header_control = FormattedTextControl(HTML(f"<header>{OPENCURSOR_LOGO}</header>"))
        header = Window(content=self.header_control, height=8)
        
        # Status bar
        self.status_control = FormattedTextControl(lambda: f"Status: {self.status_message}")
        status_bar = Window(content=self.status_control, height=1, style="class:status")
        
        # Output area
        self.output_control = FormattedTextControl(lambda: self.output_text)
        output_area = Window(content=self.output_control, wrap_lines=True, style="class:output-area")
        
        # Files in context area
        self.files_control = FormattedTextControl(lambda: self.format_files_in_context())
        files_area = Window(content=self.files_control, width=30, style="class:status")
        
        # Main layout
        self.layout = Layout(
            HSplit([
                header,
                VSplit([
                    output_area,
                    files_area,
                ]),
                status_bar,
            ])
        )
        
        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            style=style,
            mouse_support=True,
        )
    
    def format_files_in_context(self) -> str:
        """Format the list of files in context for display"""
        if not self.files_in_context:
            return "No files in context"
        
        result = "FILES IN CONTEXT:\n"
        for file_path in sorted(self.files_in_context):
            result += f"- {file_path.relative_to(self.current_workspace)}\n"
        return result
    
    def update_status(self, message: str):
        """Update the status message"""
        self.status_message = message
        self.app.invalidate()
    
    def update_output(self, text: str):
        """Update the output text area"""
        self.output_text = text
        self.app.invalidate()
    
    def add_file_to_context(self, file_path: str):
        """Add a file to the chat context"""
        path = Path(file_path).resolve()
        if path.exists() and path.is_file():
            self.files_in_context.add(path)
            self.update_status(f"Added {path} to context")
        else:
            self.update_status(f"File not found: {file_path}")
    
    def drop_file_from_context(self, file_path: str):
        """Remove a file from the chat context"""
        path = Path(file_path).resolve()
        if path in self.files_in_context:
            self.files_in_context.remove(path)
            self.update_status(f"Removed {path} from context")
        else:
            self.update_status(f"File not in context: {file_path}")
    
    def clear_context(self):
        """Clear all files from the chat context"""
        self.files_in_context.clear()
        self.update_status("Cleared all files from context")
    
    def generate_repo_map(self):
        """Generate a map of the repository"""
        repo_map = "REPOSITORY MAP:\n"
        
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
        for file in sorted(all_files):
            if any(Path(file).resolve() == f for f in self.files_in_context):
                repo_map += f"* {file} (in context)\n"
            else:
                repo_map += f"- {file}\n"
        
        return repo_map
    
    async def process_command(self, command: str, args: str) -> bool:
        """Process a command and return whether to continue running"""
        if command == "/exit":
            return False
        elif command == "/help":
            help_text = """
            OPENCURSOR COMMANDS:
            /agent <message> - Send a message to the agent (with tools)
            /chat <message> - Chat with the LLM directly (no tools)
            /add <filepath> - Add a file to the chat context
            /drop <filepath> - Remove a file from the chat context
            /clear - Clear all files from the chat context
            /repomap - Show a map of the repository
            /focus <filepath> - Focus on a specific file
            /help - Show this help message
            /exit - Exit the application
            """
            self.update_output(help_text)
        elif command == "/agent":
            self.update_status("Processing with agent...")
            response = await self.agent(args)
            self.update_output(response)
            self.update_status("Agent response received")
        elif command == "/chat":
            self.update_status("Chatting with LLM...")
            # Direct chat with LLM without tools
            response = await self.agent.llm_client.chat(user_message=args, tools=None)
            self.update_output(response.message.content)
            self.update_status("LLM response received")
        elif command == "/add":
            self.add_file_to_context(args)
        elif command == "/drop":
            self.drop_file_from_context(args)
        elif command == "/clear":
            self.clear_context()
        elif command == "/repomap":
            repo_map = self.generate_repo_map()
            self.update_output(repo_map)
        elif command == "/focus":
            if os.path.exists(args):
                self.add_file_to_context(args)
                self.update_status(f"Focusing on {args}")
                try:
                    with open(args, 'r') as f:
                        content = f.read()
                    self.update_output(f"File: {args}\n\n{content}")
                except Exception as e:
                    self.update_status(f"Error reading file: {e}")
            else:
                self.update_status(f"File not found: {args}")
        else:
            self.update_status(f"Unknown command: {command}")
        
        return True
    
    async def run(self):
        """Run the application"""
        # Show the logo and welcome message
        welcome_message = f"{OPENCURSOR_LOGO}\nWelcome to OpenCursor! Type /help for available commands."
        self.update_output(welcome_message)
        self.update_status("Ready")
        
        # Start the application in the background
        with self.app.session():
            running = True
            while running:
                try:
                    # Get user input
                    user_input = await self.session.prompt_async(
                        "OpenCursor> ", 
                        completer=self.command_completer
                    )
                    
                    # Parse command
                    if user_input.startswith('/'):
                        parts = user_input.split(' ', 1)
                        command = parts[0].lower()
                        args = parts[1] if len(parts) > 1 else ""
                        running = await self.process_command(command, args)
                    else:
                        # Default to agent if no command specified
                        self.update_status("Processing with agent...")
                        response = await self.agent(user_input)
                        self.update_output(response)
                        self.update_status("Agent response received")
                        
                except KeyboardInterrupt:
                    running = False
                except Exception as e:
                    self.update_status(f"Error: {str(e)}")
        
        print("Thank you for using OpenCursor!")

async def main():
    """Main entry point"""
    print(OPENCURSOR_LOGO)
    print("Starting OpenCursor...")
    
    # Parse command line arguments for model and host
    model_name = "qwen3_14b_q6k:latest"
    host = "http://192.168.170.76:11434"
    
    # Create and run the app
    app = OpenCursorApp(model_name=model_name, host=host)
    await app.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
