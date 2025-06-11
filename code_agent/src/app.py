#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
import time
import subprocess
import logging
from typing import List, Dict, Optional, Set, Union
from pathlib import Path

# Configure logging to suppress INFO messages
logging.basicConfig(level=logging.WARNING)

# Silence standard library loggers
for logger_name in ["asyncio", "urllib", "urllib3", "filelock"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Explicitly silence specific loggers that are producing unwanted output
for logger_name in ["telemetry", "sentence_transformers.SentenceTransformer"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

import rich
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
from rich.console import Group

# Add prompt_toolkit imports
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle

from code_agent.src.agent import CodeAgent

import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"

OPENCURSOR_LOGO_V1 = """
  ____  _____  ______ _   _  _____ _    _ _____   _____  ____  _____  
 / __ \|  __ \|  ____| \ | |/ ____| |  | |  __ \ / ____|/ __ \|  __ \ 
| |  | | |__) | |__  |  \| | |    | |  | | |__) | (___ | |  | | |__) |
| |  | |  ___/|  __| | . ` | |    | |  | |  _  / \___ \| |  | |  _  / 
| |__| | |    | |____| |\  | |____| |__| | | \ \ ____) | |__| | | \ \ 
 \____/|_|    |______|_| \_|\_____|\____/|_|  \_\_____/ \____/|_|  \_\\
                                                                      
"""

OPENCURSOR_LOGO = """
 ██████╗ ██████╗ ███████╗███╗   ██╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║
██║   ██║██████╔╝█████╗  ██╔██╗ ██║
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║
╚██████╔╝██║     ███████╗██║ ╚████║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝
                                   
 ██████╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ 
██╔════╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗
██║     ██║   ██║██████╔╝███████╗██║   ██║██████╔╝
██║     ██║   ██║██╔══██╗╚════██║██║   ██║██╔══██╗
╚██████╗╚██████╔╝██║  ██║███████║╚██████╔╝██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝
"""

# Claude-inspired theme colors
CLAUDE_PRIMARY = "#E67E50"    # Warm coral/orange from Claude branding
CLAUDE_SECONDARY = "#D4A574"  # Warm beige/tan
CLAUDE_ACCENT = "#B8956A"     # Deeper warm tone
CLAUDE_SUCCESS = "#7B9E3F"    # Natural green
CLAUDE_INFO = "#5B8AA6"       # Calm blue
CLAUDE_WARNING = "#D49C3D"    # Warm amber
CLAUDE_ERROR = "#C85450"      # Warm red
CLAUDE_TEXT = "#2C2B29"       # Warm dark text
CLAUDE_BACKGROUND = "#F5F5F2" # Warm off-white background

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
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", workspace_path: Optional[str] = None, system_prompt: Optional[str] = None, num_ctx: int = 2048, no_think: bool = True):
        # Use provided workspace path or current working directory
        self.current_workspace = Path(workspace_path).resolve() if workspace_path else Path.cwd()
        
        # Ensure logs are silenced
        logging.getLogger().setLevel(logging.WARNING)
        
        # Initialize agent with current workspace
        self.agent = CodeAgent(model_name=model_name, host=host, workspace_root=str(self.current_workspace), system_prompt=system_prompt, num_ctx=num_ctx, no_think=no_think)
        
        # Create Claude-inspired theme
        custom_theme = Theme({
            "info": RichStyle(color=CLAUDE_INFO),
            "warning": RichStyle(color=CLAUDE_WARNING),
            "error": RichStyle(color=CLAUDE_ERROR),
            "success": RichStyle(color=CLAUDE_SUCCESS),
            "primary": RichStyle(color=CLAUDE_PRIMARY),
            "primary.border": RichStyle(color=CLAUDE_PRIMARY),
            "primary.title": RichStyle(color=CLAUDE_PRIMARY, bold=True),
            "claude.thinking": RichStyle(color=CLAUDE_ACCENT, dim=True),
            "claude.streaming": RichStyle(color=CLAUDE_SUCCESS),
            "claude.tool": RichStyle(color=CLAUDE_WARNING),
            "claude.border": RichStyle(color=CLAUDE_SECONDARY),
            "claude.text": RichStyle(color=CLAUDE_TEXT),
        })
        
        # Initialize console with custom theme and full width
        self.console = Console(theme=custom_theme, width=None)
        
        # Create custom box styles for Claude aesthetic
        self.claude_box_rounded = box.ROUNDED
        self.claude_box_simple = box.SIMPLE
        
        # Chat context management
        self.files_in_context: Set[Path] = set()
        self.chat_history: List[Dict[str, str]] = []
        
        # Available commands
        self.commands = [
            "/agent", "/chat", "/add", "/drop", "/clear", 
            "/help", "/exit", "/repomap", "/focus", "/interactive", "/diff"
        ]
        
        # Output storage
        self.last_output = ""
        self.tool_results = []  # Store recent tool results
        
        # Current mode (default is "OpenCursor")
        self.current_mode = "Agent"
        
        # Define Claude-inspired prompt styles
        self.style = Style.from_dict({
            'command': f'{CLAUDE_PRIMARY} bold',     # Claude primary for commands
            'file': f'{CLAUDE_SUCCESS}',             # Natural green for files
            'prompt': f'{CLAUDE_WARNING} bold',      # Warm amber for prompt
            'ansigreen': f'{CLAUDE_SUCCESS} bold',   # Natural green bold
            'text': f'{CLAUDE_TEXT}',                # Warm dark text
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
        self.console.print(f"[{CLAUDE_PRIMARY}]{OPENCURSOR_LOGO}[/{CLAUDE_PRIMARY}]")
        
    def print_help(self):
        """Print help information"""
        table = Table(title=f"[{CLAUDE_PRIMARY} bold]OpenCursor Commands[/{CLAUDE_PRIMARY} bold]", box=box.ROUNDED, border_style=CLAUDE_PRIMARY)
        table.add_column("Command", style="primary")
        table.add_column("Description", style="claude.text")
        
        table.add_row("/agent <message>", "Send a message to the agent (autonomous mode)")
        table.add_row("/interactive <message>", "Send a message to the agent (interactive mode)")
        table.add_row("/chat <message>", "Chat with the LLM directly (no tools)")
        table.add_row("/add <filepath>", "Add a file to the chat context")
        table.add_row("/drop <filepath>", "Remove a file from the chat context")
        table.add_row("/clear", "Clear all files from the chat context")
        table.add_row("/repomap", "Show a map of the repository")
        table.add_row("/focus <filepath>", "Focus on a specific file")
        table.add_row("/diff <filepath>", "Show git diff for a file with syntax highlighting")
        table.add_row("/help", "Show this help message")
        table.add_row("/exit", "Exit the application")
        
        self.console.print(table)
        
        # Add information about agent modes
        agent_modes = Table(title=f"[{CLAUDE_PRIMARY} bold]Agent Modes[/{CLAUDE_PRIMARY} bold]", box=box.ROUNDED, border_style=CLAUDE_PRIMARY)
        agent_modes.add_column("Mode", style="primary")
        agent_modes.add_column("Description", style="claude.text")
        
        agent_modes.add_row("Autonomous (default)", "Agent works step-by-step without user interaction")
        agent_modes.add_row("Interactive", "Agent performs one tool call at a time, waiting for user input")
        
        self.console.print(agent_modes)
        
        # Add information about code block format
        code_formats = Table(title=f"[{CLAUDE_PRIMARY} bold]Code Block Formats[/{CLAUDE_PRIMARY} bold]", box=box.ROUNDED, border_style=CLAUDE_PRIMARY)
        code_formats.add_column("Format", style="primary")
        code_formats.add_column("Description", style="claude.text")
        
        code_formats.add_row("```language:filepath", "Code with syntax highlighting for language and file path")
        code_formats.add_row("```startLine:endLine:filepath", "Code with line numbers and file path")
        code_formats.add_row("```language:startLine:endLine:filepath", "Code with language, line numbers, and file path")
        
        self.console.print(code_formats)
        
    def show_files_in_context(self):
        """Show files currently in context"""
        if not self.files_in_context:
            # Create an empty panel instead of text message
            empty_panel = Panel(
                "No files in context yet. Use [bold]@filename[/bold] or [bold]/add filename[/bold] to add files.",
                title=f"[{CLAUDE_PRIMARY} bold]Files in Context[/{CLAUDE_PRIMARY} bold]",
                border_style=CLAUDE_PRIMARY,
                box=box.ROUNDED
            )
            self.console.print(empty_panel)
            return
            
        # Create a table for files in context
        table = Table(box=box.SIMPLE, border_style=CLAUDE_PRIMARY)
        table.add_column("File", style="success")
        
        for file_path in sorted(self.files_in_context):
            table.add_row(str(file_path.relative_to(self.current_workspace)))
        
        # Wrap the table in a panel
        files_panel = Panel(
            table,
            title=f"[{CLAUDE_PRIMARY} bold]Files in Context[/{CLAUDE_PRIMARY} bold]",
            border_style=CLAUDE_PRIMARY,
            box=box.ROUNDED
        )
        self.console.print(files_panel)
    
    def _format_search_results(self, result: str) -> str:
        """Format search results into Markdown format"""
        try:
            # Try to parse as JSON if possible
            import json
            data = json.loads(result)
            
            markdown_content = ""
            
            # Handle query information if present
            if isinstance(data, dict) and "query" in data:
                markdown_content += f"**Query:** {data['query']}\n\n"
            
            # Handle results array
            results = []
            if isinstance(data, dict) and "results" in data:
                results = data["results"]
            elif isinstance(data, list):
                results = data
                
            # Format each result
            for item in results:
                if isinstance(item, dict):
                    title = item.get("title", "").strip()
                    url = item.get("url", "")
                    description = item.get("description", "")
                    
                    # Extract domain from URL
                    import re
                    domain = ""
                    if url:
                        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                        domain = domain_match.group(1) if domain_match else url
                    
                    # Format the description
                    desc_preview = ""
                    if description:
                        desc_preview = description[:50].strip() + "..."
                        desc_preview = " ".join(desc_preview.split()).strip()

                    try:
                        desc_preview_2 = url.split(".com")[1]
                    except:
                        desc_preview_2 = ""
                    
                    # Create citation entry
                    if url:
                        markdown_content += f"- [{domain}]({url}) {title or desc_preview or desc_preview_2}\n"
                    else:
                        markdown_content += f"- {title or desc_preview}\n"
            
            return Markdown(markdown_content.strip())
        except:
            # Fallback for non-JSON content
            lines = result.strip().split('\n')
            markdown_content = ""
            
            for line in lines:
                line = line.strip()
                if line:
                    markdown_content += f"- {line}\n"
                    
            return Markdown(markdown_content.strip())

    def display_tool_results(self):
        """Display recent tool results in a nice format"""
        if not self.tool_results:
            return
            
        # Create a panel to display tool results
        table = Table(box=box.ROUNDED, title=f"[{CLAUDE_PRIMARY} bold]Recent Tool Results[/{CLAUDE_PRIMARY} bold]", expand=True, border_style=CLAUDE_PRIMARY)
        table.add_column("Tool", style="primary")
        table.add_column("Result", style="claude.text")
        
        for tool_name, result in self.tool_results[-5:]:  # Show last 5 results
            # Format the result based on tool type
            if tool_name == "web_search":
                # Create a nested table for web search results
                web_results = self._format_web_search_results(result)
                table.add_row(tool_name, web_results)
            elif tool_name == "fetch_webpage":
                fetch_webpage_results = self._format_fetch_webpage_results(result)
                table.add_row(tool_name, fetch_webpage_results)
            elif tool_name in ["search_in_docs_with_keyboard_shortcut", "search_in_docs_with_dom_element"]:
                search_results = self._format_search_results(result)
                table.add_row(tool_name, search_results)
            elif tool_name in ["read_file", "edit_file", "grep_search", "codebase_search"]:
                # For code-related results, use syntax highlighting where possible
                if "```" in result:
                    # Extract code blocks and format them
                    formatted_result = self._format_code_blocks(result)
                    table.add_row(tool_name, str(formatted_result))
                else:
                    table.add_row(tool_name, result)
            else:
                # Default formatting for other tools
                table.add_row(tool_name, result)
        
        # Add execution summary if available
        if hasattr(self, 'execution_summary') and self.execution_summary:
            summary_panel = Panel(
                Markdown(self.execution_summary),
                title=f"[{CLAUDE_PRIMARY} bold]Execution Summary[/{CLAUDE_PRIMARY} bold]",
                border_style=CLAUDE_PRIMARY,
                box=box.ROUNDED
            )
            
            # Create a group with both the table and summary panel
            result_group = Group(table, summary_panel)
            self.console.print(result_group)
        else:
            self.console.print(table)
        
    def _format_fetch_webpage_results(self, result: str) -> str:
        """Format fetch webpage results into a nested table"""
        # Create markdown content for results
        markdown_content = ""
        
        # Split the result by URL entries
        url_entries = result.split("URL: ")[1:]
        
        for entry in url_entries:
            if "Content:" in entry:
                url, content = entry.split("Content:", 1)
                url = url.strip()
                content = content.strip()
                
                # Extract domain from URL
                import re
                domain = re.search(r'https?://(?:www\.)?([^/]+)', url)
                domain = domain.group(1) if domain else url
                
                # Take just a snippet of the content (first 25 chars)
                content_preview = content[:25].strip() + "..."
                content_preview = " ".join(content_preview.split())
                
                # Format as citation style: "content_preview (domain)"
                citation = f"- [{domain}]({url}) {content_preview}\n"
                markdown_content += citation
        
        return Markdown(markdown_content.strip())
        
    def _format_web_search_results(self, result: str) -> str:
        """Format web search results into a nice table"""
        import re
        
        # Extract search term
        search_term_match = re.search(r"Search results for: (.+?)$", result.strip().split('\n')[0])
        search_term = search_term_match.group(1) if search_term_match else "Unknown query"
        
        # Extract search results using regex
        pattern = r"(\d+)\. (.+?)\n\s+URL: (.+?)\n(?:\s+Description: (.+?)\n)?\n"
        matches = re.findall(pattern, result, re.DOTALL)
        
        # Create a table for search results
        from rich.table import Table
        
        table = Table(box=box.ROUNDED,title=f"[bold]Search results for: {search_term}[/bold]", expand=True, border_style=CLAUDE_PRIMARY)

        table.add_column("#", style="info", no_wrap=True)
        table.add_column("Title", style="success")
        table.add_column("Description", style="warning")
        
        # Add rows to the table
        for match in matches:
            index, title, url, description = match
            description = description or "No description available"
            # Make title clickable with embedded URL
            clickable_title = f"[link={url}]{title}[/link]"
            table.add_row(index, clickable_title, description)
            
        return table
        
    def _display_file_with_location(self, file_path: str, content: str, start_line: int = 1, end_line: Optional[int] = None):
        """
        Display file content with location information
        
        Args:
            file_path: Path to the file
            content: Content of the file
            start_line: Starting line number
            end_line: Ending line number
        """
        # Determine syntax highlighting based on file extension
        extension = os.path.splitext(file_path)[1].lstrip('.')
        
        # Create the title with location information
        location_info = f"{start_line}"
        if end_line:
            location_info += f":{end_line}"
        title = f"[{CLAUDE_PRIMARY} bold]File: {file_path} (Lines {location_info})[/{CLAUDE_PRIMARY} bold]"
        
        # Create syntax object with highlighting
        syntax = Syntax(content, extension or "text", theme="monokai", line_numbers=True, 
                        start_line=start_line, highlight_lines=set(range(start_line, (end_line or start_line) + 1)))
        
        # Display in a panel
        self.console.print(Panel(syntax, title=title, border_style=CLAUDE_PRIMARY, expand=True))
        
    def _format_code_blocks(self, result: str) -> str:
        """Format code blocks with syntax highlighting and file location information"""
        parts = result.split("```")
        formatted_parts = []
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Regular text
                formatted_parts.append(part)
            else:
                # Code block
                # Check if there's a file path specified with line numbers (format: language:start_line:end_line:filepath or start_line:end_line:filepath)
                file_path = None
                start_line = 1
                end_line = None
                lang = "text"  # Default language
                code = part
                
                first_line = part.split("\n", 1)[0].strip() if "\n" in part else part.strip()
                
                # Handle format with line numbers like ```python:10:20:path/to/file.py or ```10:20:path/to/file.py
                if first_line.count(':') >= 2 and any(c.isdigit() for c in first_line.split(':', 1)[0]):
                    components = first_line.split(':')
                    
                    if components[0].isdigit():
                        # Format: ```line:line:filepath
                        try:
                            start_line = int(components[0])
                            end_line = int(components[1]) if len(components) > 2 else start_line
                            file_path = ':'.join(components[2:]) if len(components) > 2 else None
                            lang = self.extension_to_language(file_path) if file_path else "text"
                        except ValueError:
                            pass
                    else:
                        # Format: ```language:line:line:filepath
                        try:
                            lang = components[0]
                            start_line = int(components[1])
                            end_line = int(components[2]) if len(components) > 3 else start_line
                            file_path = ':'.join(components[3:]) if len(components) > 3 else None
                        except ValueError:
                            pass
                    
                    # Extract the code (everything after the first line)
                    if "\n" in part:
                        code = part.split("\n", 1)[1]
                
                # Handle format like ```python:path/to/file.py or ```path/to/file.py
                elif ":" in first_line:
                    lang_and_path = first_line.split(":", 1)
                    
                    if len(lang_and_path) > 1:
                        lang = lang_and_path[0]
                        file_path = lang_and_path[1]
                        # Extract the code (everything after the first line)
                        if "\n" in part:
                            code = part.split("\n", 1)[1]
                
                # Handle standard markdown code blocks
                elif "\n" in part:
                    lang_and_code = part.split("\n", 1)
                    lang = lang_and_code[0].strip()
                    code = lang_and_code[1]
                
                # Create syntax object with highlighting
                syntax = Syntax(
                    code, 
                    lang, 
                    theme="monokai", 
                    line_numbers=True,
                    start_line=start_line,
                    highlight_lines=set(range(start_line, (end_line or start_line) + 1)) if start_line != 1 else None
                )
                
                # If we have a file path, add it to a panel title
                if file_path:
                    from rich.panel import Panel
                    location_info = f"{start_line}"
                    if end_line and end_line != start_line:
                        location_info += f":{end_line}"
                        
                    panel = Panel(
                        syntax,
                        title=f"[{CLAUDE_PRIMARY} bold]File: {file_path} (Lines {location_info})[/{CLAUDE_PRIMARY} bold]",
                        border_style=CLAUDE_PRIMARY
                    )
                    formatted_parts.append(panel)
                else:
                    formatted_parts.append(syntax)
                    
        return formatted_parts
        
    def _split_response_with_think(self, response: str):
        """Split response into think section and regular response"""
        # Check if response contains <think> tags
        if "<think>" in response and "</think>" in response:
            # Extract think content
            think_start = response.find("<think>") + len("<think>")
            think_end = response.find("</think>")
            think_content = response[think_start:think_end].strip()
            
            # Extract regular response (everything after </think>)
            regular_response = response[think_end + len("</think>"):].strip()
            
            # Create Claude-inspired thinking panel with warm styling
            think_panel = Panel(
                Markdown(think_content),  # Use Markdown for better formatting
                title=f"[{CLAUDE_ACCENT} bold]⚡ THINKING PROCESS ⚡[/{CLAUDE_ACCENT} bold]",
                border_style=CLAUDE_ACCENT,
                box=box.ROUNDED
            )
            
            # If there's an execution summary, split it out too
            self.execution_summary = ""
            if "[Execution Summary]" in regular_response:
                summary_start = regular_response.find("[Execution Summary]")
                self.execution_summary = regular_response[summary_start:].strip()
                regular_response = regular_response[:summary_start].strip()
            
            # Create Claude-inspired response panel
            response_panel = Panel(
                Markdown(regular_response),  # Use Markdown for better formatting
                border_style=CLAUDE_INFO,
                title=f"[{CLAUDE_INFO} bold]✨ RESPONSE ✨[/{CLAUDE_INFO} bold]",
                box=box.ROUNDED
            )
            
            # Create a group with just the thinking and response panels
            # from rich.console import Group
            # return Group(think_panel, response_panel)
            return Markdown(regular_response)

        
        else:
            # Check for execution summary in regular response
            self.execution_summary = ""
            if "[Execution Summary]" in response:
                summary_start = response.find("[Execution Summary]")
                self.execution_summary = response[summary_start:].strip()
                response = response[:summary_start].strip()
            
            # Return the original response if no think tags
            return Markdown(response)  # Use Markdown for better formatting
        
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
        self.console.print(f"[{CLAUDE_PRIMARY} bold]REPOSITORY MAP:[/{CLAUDE_PRIMARY} bold]")
        
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
        table = Table(box=box.SIMPLE, expand=True, border_style=CLAUDE_PRIMARY)
        table.add_column("File", style="success")
        table.add_column("Status", style="info")
        
        for file in sorted(all_files):
            if any(Path(file).resolve() == f for f in self.files_in_context):
                table.add_row(file, "in context")
            else:
                table.add_row(file, "")
                
        self.console.print(table)
    
    def _display_diff(self, file_path: str):
        """Display git diff for a file with syntax highlighting"""
        try:
            # Check if the file exists
            full_path = Path(file_path).resolve()
            if not full_path.exists():
                self.console.print(f"[error]File not found: {file_path}[/error]")
                return
                
            # Get git diff
            try:
                # Check if file is in a git repository
                result = subprocess.run(
                    ['git', 'ls-files', '--error-unmatch', str(full_path)], 
                    cwd=self.current_workspace,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    # File is not tracked by git
                    self.console.print("[warning]File is not tracked by git.[/warning]")
                    return
                
                # Run git diff
                diff_result = subprocess.run(
                    ['git', 'diff', str(full_path)], 
                    cwd=self.current_workspace,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if diff_result.returncode != 0:
                    self.console.print(f"[error]Error running git diff: {diff_result.stderr}[/error]")
                    return
                
                diff_text = diff_result.stdout.strip()
                if not diff_text:
                    self.console.print("[info]No changes detected by git.[/info]")
                    return
                
                # Display the diff with syntax highlighting
                syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
                self.console.print(Panel(
                    syntax,
                    title=f"[{CLAUDE_PRIMARY} bold]Git Diff: {file_path}[/{CLAUDE_PRIMARY} bold]",
                    border_style=CLAUDE_PRIMARY,
                    expand=True
                ))
                
            except Exception as e:
                self.console.print(f"[error]Error running git diff: {str(e)}[/error]")
                
        except Exception as e:
            self.console.print(f"[error]Error: {str(e)}[/error]")
            
    async def process_command(self, command: str, args: str) -> bool:
        """Process a command and return whether to continue running"""
        if command == "/exit":
            return False
        elif command == "/help":
            self.print_help()
        elif command == "/agent":
            self.console.print("[info]Agent working...[/info]")
            response = await self.agent(args)
            
            # Process response to split think and regular content
            processed_response = self._split_response_with_think(response)
            
            # Display tool results first
            self.display_tool_results()
            
            # Display the processed response in a Claude-style panel
            self.console.print(Panel(
                processed_response,
                title=f"[{CLAUDE_SUCCESS} bold]🤖 AGENT RESPONSE 🤖[/{CLAUDE_SUCCESS} bold]", 
                border_style=CLAUDE_SUCCESS, 
                expand=True,
                box=box.ROUNDED
            ))
                
            self.last_output = response
        elif command == "/interactive":
            self.console.print("[info]Interactive mode...[/info]")
            # Interactive mode with the agent
            response = await self.agent.interactive(args)
            
            # Process response to split think and regular content
            processed_response = self._split_response_with_think(response)
            
            # Display tool results first
            self.display_tool_results()
            
            # Display the processed response in a Claude-style panel
            self.console.print(Panel(
                processed_response,
                title=f"[{CLAUDE_WARNING} bold]⚡ INTERACTIVE RESPONSE ⚡[/{CLAUDE_WARNING} bold]", 
                border_style=CLAUDE_WARNING, 
                expand=True,
                box=box.ROUNDED
            ))
                
            self.last_output = response
        elif command == "/chat":
            self.console.print("[info]Chatting...[/info]")
            # Direct chat with LLM without tools
            response = await self.agent.llm_client.chat(user_message=args, tools=None)
            self.console.print(Panel(response.message.content, title=f"[{CLAUDE_PRIMARY} bold]LLM Response[/{CLAUDE_PRIMARY} bold]", border_style=CLAUDE_PRIMARY, expand=True))
            self.last_output = response.message.content
        elif command == "/add":
            self.add_file_to_context(args)
        elif command == "/drop":
            self.drop_file_from_context(args)
        elif command == "/clear":
            self.clear_context()
        elif command == "/repomap":
            self.generate_repo_map()
        elif command == "/diff":
            self._display_diff(args)
        elif command == "/focus":
            if os.path.exists(args):
                self.add_file_to_context(args)
                self.console.print(f"[success]Focusing on {args}[/success]")
                try:
                    with open(args, 'r') as f:
                        content = f.read()
                    
                    # Use the new display method for better visualization
                    self._display_file_with_location(args, content)
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
        
        # Create a welcome panel with system information
        system_info = []
        system_info.append(f"*Workspace:* {self.current_workspace}")
        system_info.append(f"*OS:* {os.uname().sysname} {os.uname().release}")
        system_info.append(f"*Model:* {self.agent.model_name}")
        
        welcome_panel = Panel(
            Group(
                Markdown("**Welcome to OpenCursor!** Type `/help` for available commands."),
                Markdown("\n".join(system_info))
            ),
            title=f"[{CLAUDE_PRIMARY} bold]System Information[/{CLAUDE_PRIMARY} bold]",
            border_style=CLAUDE_PRIMARY,
            box=box.ROUNDED
        )
        
        self.console.print(welcome_panel)
        
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
        
        # Initialize execution summary
        self.execution_summary = ""
        
        running = True
        while running:
            # try:
            # Show files in context
            self.show_files_in_context()
            
            # Get user input with prompt_toolkit
            if initial_query:
                user_input = initial_query
                initial_query = None  # Reset after first use
            else:
                # Create a styled input panel title
                prompt_message = f"{self.current_mode}> "
                
                # Display Claude-style input separator
                self.console.print(f"[{CLAUDE_WARNING} bold]{'─' * 18} ENTER COMMAND {'─' * 18}[/{CLAUDE_WARNING} bold]")
                
                # Use Claude-style prompt styling
                user_input = await asyncio.to_thread(
                    lambda: self.session.prompt(
                        HTML(f"<ansigreen><b>[{self.current_mode.upper()}]></b></ansigreen> "),
                    )
                )

                # Clear the previous line to make the UI cleaner
                self.console.print("")
            
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
                
                # Process response to split think and regular content
                processed_response = self._split_response_with_think(response)
                
                # Display tool results first
                self.display_tool_results()
                
                # Display the processed response in a Claude-style panel
                self.console.print(Panel(
                    processed_response,
                    title=f"[{CLAUDE_SUCCESS} bold]🤖 AGENT RESPONSE 🤖[/{CLAUDE_SUCCESS} bold]", 
                    border_style=CLAUDE_SUCCESS, 
                    expand=True,
                    box=box.ROUNDED
                ))
                    
                self.last_output = response
                    
            # except KeyboardInterrupt:
            #     self.console.print("\n[warning]Exiting...[/warning]")
            #     running = False
            # except Exception as e:
            #     self.console.print(f"[error]Error:[/error] {str(e)}")
        
        self.console.print(f"[{CLAUDE_PRIMARY} bold]Thank you for using OpenCursor![/{CLAUDE_PRIMARY} bold]")

    def extension_to_language(self, file_path):
        """Convert file extension to language name for syntax highlighting"""
        if not file_path:
            return "text"
        
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".sh": "bash",
            ".bash": "bash",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "cpp",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".sql": "sql",
            ".diff": "diff",
            ".gitignore": "gitignore",
        }
        
        ext = os.path.splitext(file_path)[1].lower()
        return ext_map.get(ext, "text")

async def main():
    """Main entry point"""

    # Disable all third-party library logs for a clean terminal
    logging.getLogger().setLevel(logging.WARNING)
    # Silence specific verbose loggers
    for module in ["httpx", "urllib3", "httpcore", "telemetry", 
                  "sentence_transformers", "filelock", "huggingface", 
                  "transformers", "torch"]:
        if logging.getLogger(module):
            logging.getLogger(module).setLevel(logging.ERROR)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OpenCursor - An AI-powered code assistant")
    parser.add_argument("-m", "--model", default="qwen3_14b_q6k:latest", help="Model name to use (default: qwen3_14b_q6k:latest)")
    parser.add_argument("--host", default="http://192.168.170.76:11434", help="Ollama host URL (default: http://192.168.170.76:11434)")
    parser.add_argument("-w", "--workspace", help="Path to workspace directory")
    parser.add_argument("-q", "--query", default=None, help="Initial query to process")
    parser.add_argument("--thinking", action="store_true", help="Enable thinking process in responses (disabled by default)")
    parser.add_argument("--num-ctx", type=int, default=2048, help="Context window size (default: 2048)")
    args = parser.parse_args()
    
    # Create custom theme with Claude-inspired colors
    custom_theme = Theme({
        "info": RichStyle(color=CLAUDE_INFO),
        "warning": RichStyle(color=CLAUDE_WARNING),
        "error": RichStyle(color=CLAUDE_ERROR),
        "success": RichStyle(color=CLAUDE_SUCCESS),
        "primary": RichStyle(color=CLAUDE_PRIMARY),
    })
    
    console = Console(theme=custom_theme, width=None)
    
    # Create and run the app with parsed arguments
    app = OpenCursorApp(
        model_name=args.model,
        host=args.host,
        workspace_path=args.workspace,
        system_prompt=None,
        num_ctx=args.num_ctx,
        no_think=not args.thinking  # Invert logic: no_think by default, thinking only when flag is passed
    )
    await app.run(initial_query=args.query)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        custom_theme = Theme({"primary": RichStyle(color=CLAUDE_PRIMARY)})
        Console(theme=custom_theme).print(f"\n[primary bold]Goodbye![/primary bold]")

# Add a non-async entry point for the package
def entry_point():
    """Non-async entry point for the package"""
    try:
        # Disable all third-party library logs for a clean terminal
        logging.getLogger().setLevel(logging.WARNING)
        # Silence specific verbose loggers
        for module in ["httpx", "urllib3", "httpcore", "telemetry", 
                      "sentence_transformers", "filelock", "huggingface", 
                      "transformers", "torch"]:
            if logging.getLogger(module):
                logging.getLogger(module).setLevel(logging.ERROR)
                
        asyncio.run(main())
    except KeyboardInterrupt:
        custom_theme = Theme({"primary": RichStyle(color=CLAUDE_PRIMARY)})
        Console(theme=custom_theme).print(f"\n[primary bold]Goodbye![/primary bold]")
