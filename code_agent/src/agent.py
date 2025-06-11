import asyncio
from typing import Dict, Any, List, Tuple, Optional
from rich.console import Console
from rich.text import Text
from rich.style import Style
import time

from .llm import LLMClient
from .tools import Tools
from .prompts import SYSTEM_PROMPT, AUTONOMOUS_AGENT_PROMPT, INTERACTIVE_AGENT_PROMPT
from .tool_playwright import register_playwright_search_tool



class CodeAgent:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", workspace_root: str = None, system_prompt: Optional[str] = None, num_ctx: int = 2048, no_think: bool = True):
        """
        Initialize a CodeAgent that can use tools and execute tool calls.

        Args:
            model_name (str): The name of the Ollama model to use.
            host (str): The host URL for the Ollama API.
            workspace_root (str): The root directory of the workspace.
            system_prompt (Optional[str]): Optional custom system prompt to use.
            num_ctx (int): Context window size for the model.
            no_think (bool): Whether to use no-thinking mode (adds /no_think tag). Default is True.
        """
        self.llm_client = LLMClient(model_name=model_name, host=host, num_ctx=num_ctx, no_think=no_think)
        self.tools_manager = Tools(workspace_root=workspace_root)
        self.register_tools()
        self.max_iterations = 100
        self.model_name = model_name
        self.custom_system_prompt = system_prompt
        
        # Initialize nostalgic console for tool displays
        self.console = Console()
        
        # Nostalgic tool icons and symbols
        self.tool_icons = {
            'read_file': '📂',
            'list_dir': '📁', 
            'edit_file': '✏️',
            'grep_search': '🔍',
            'file_search': '🗂️',
            'codebase_search': '🔎',
            'run_terminal_cmd': '⚡',
            'web_search': '🌐',
            'default': '⚙️'
        }
        
        # Retro ASCII symbols for different states
        self.retro_symbols = {
            'working': '▓▓▒▒░░',
            'complete': '███',
            'error': '▄▄▄',
            'dots': ['◐', '◓', '◑', '◒'],
            'loading': ['|', '/', '-', '\\'],
        }

    def register_tools(self):
        """Register all available tools."""
        # Use the convenient method to register all tools
        self.tools_manager.register_all_tools()
        
        # Register additional tools
        register_playwright_search_tool(self.tools_manager)

    async def __call__(self, user_message: str) -> str:
        """
        Send a message to the LLM and process any tool calls.

        Args:
            user_message (str): The user's message.
            system_message (Optional[str]): Optional system message to guide the model.

        Returns:
            str: The final response from the model.
        """
        return await self.autonomous_mode(user_message)
    
    async def interactive(self, user_message: str) -> str:
        """
        Process a user message in interactive mode (one tool call at a time).
        
        Args:
            user_message (str): The user's message.
            
        Returns:
            str: The final response from the model.
        """
        # Reset the conversation
        self.llm_client.messages = []
        
        # Set the system prompt to interactive agent mode
        if self.custom_system_prompt:
            # Use custom system prompt if provided
            self.llm_client.add_message("system", self.custom_system_prompt)
        else:
            # Use default interactive agent prompt
            self.llm_client.add_message("system", INTERACTIVE_AGENT_PROMPT)
        
        # Add the initial user message
        self.llm_client.add_message("user", f"Task: {user_message}")
        
        # Get the initial response
        response = await self.llm_client.chat(
            user_message="",  # Empty message to just get the next response
            tools=self.tools_manager.tools
        )
        
        # Return the initial plan
        return response.message.content

    async def autonomous_mode(self, user_message: str) -> str:
        """
        Process a user message in autonomous mode (multiple tool calls in sequence).
        
        Args:
            user_message (str): The user's message.
            
        Returns:
            str: The final response from the model.
        """
        # Reset the conversation
        self.llm_client.messages = []
        
        # Set the system prompt to autonomous agent mode
        if self.custom_system_prompt:
            # Use custom system prompt if provided
            self.llm_client.add_message("system", self.custom_system_prompt)
        else:
            # Use default system prompt
            system_prompt = SYSTEM_PROMPT.replace("<|user_workspace_path|>", str(self.tools_manager.workspace_root))
            self.llm_client.add_message("system", system_prompt)
        
        # Add the initial user message
        self.llm_client.add_message("user", f"Task: {user_message}")
        
        # Keep a log of iterations and actions taken
        execution_log = []
        
        # Main agent loop
        for i in range(self.max_iterations):
            # Get the LLM response with available tools
            response = await self.llm_client.chat(
                user_message="",  # Empty message to just get the next response
                tools=self.tools_manager.tools
            )
            
            # Process tool calls if any
            if response.message.tool_calls:
                # Process each tool call and show nostalgic feedback
                for tc in response.message.tool_calls:
                    name = tc['function']['name']
                    args = tc['function']['arguments']
                    
                    # Display nostalgic tool call indicator
                    self._show_nostalgic_tool_call(name, args)
                    
                    # Brief nostalgic pause for that retro feel
                    time.sleep(0.1)
                    
                    # Log for execution summary
                    tool_info = f"{name}"
                    if name == 'read_file':
                        tool_info = f"Reading {args.get('target_file', '')}"
                    elif name == 'list_dir':
                        tool_info = f"Listing {args.get('relative_workspace_path', '')}"
                    elif name == 'edit_file':
                        tool_info = f"Editing {args.get('target_file', '')}"
                    
                    execution_log.append(f"Step {i+1}: {tool_info}")
                
                # Process tool calls
                await self.tools_manager.process_tool_calls(response.message.tool_calls, self.llm_client)
            else:
                # If no tool calls, the agent is done
                # Log the final message
                execution_log.append(f"Step {i+1}: Final response")
                
                # If there's content in the message, this is the final response
                if response.message.content.strip():
                    # Add execution log to the response
                    execution_summary = "\n".join(execution_log)
                    return f"{response.message.content}\n\n[Execution Summary]\n{execution_summary}"
                else:
                    # No content, ask for a final response
                    print("Generating final summary...")
                    final_response = await self.llm_client.chat(
                        user_message="Now that you've completed the task, provide a summary of what you've done.",
                        tools=None
                    )
                    
                    # Add execution log to the response
                    execution_summary = "\n".join(execution_log)
                    return f"{final_response.message.content}\n\n[Execution Summary]\n{execution_summary}"
        
        # If we reach here, we've hit the iteration limit
        execution_summary = "\n".join(execution_log)
        return f"I've reached the maximum number of steps ({self.max_iterations}) without completing the task. Here's what I've done so far:\n\n[Execution Summary]\n{execution_summary}"
    
    def _show_nostalgic_tool_call(self, tool_name: str, args: dict):
        """Display nostalgic tool call with retro styling"""
        # Get the appropriate icon
        icon = self.tool_icons.get(tool_name, self.tool_icons['default'])
        
        # Create nostalgic styled text
        tool_text = Text()
        tool_text.append("• ", style="#FFB000")  # Amber bullet
        tool_text.append(f"{icon} ", style="#00FFFF")  # Cyan icon
        
        # Format tool-specific messages with retro style
        if tool_name == 'read_file':
            target_file = args.get('target_file', '')
            tool_text.append("READING FILE: ", style="#00FF41 bold")
            tool_text.append(f"{target_file}", style="#F0F0F0")
        elif tool_name == 'list_dir':
            path = args.get('relative_workspace_path', '')
            tool_text.append("LISTING DIR: ", style="#00FF41 bold")
            tool_text.append(f"{path}", style="#F0F0F0")
        elif tool_name == 'edit_file':
            target_file = args.get('target_file', '')
            tool_text.append("EDITING FILE: ", style="#00FF41 bold")
            tool_text.append(f"{target_file}", style="#F0F0F0")
        elif tool_name == 'grep_search':
            query = args.get('query', '')
            tool_text.append("CODE SEARCH: ", style="#00FF41 bold")
            tool_text.append(f"{query}", style="#F0F0F0")
        elif tool_name == 'file_search':
            query = args.get('query', '')
            tool_text.append("FILE SEARCH: ", style="#00FF41 bold")
            tool_text.append(f"{query}", style="#F0F0F0")
        elif tool_name == 'codebase_search':
            query = args.get('query', '')
            tool_text.append("SEMANTIC SEARCH: ", style="#00FF41 bold")
            tool_text.append(f"{query}", style="#F0F0F0")
        elif tool_name == 'run_terminal_cmd':
            cmd = args.get('command', '')
            tool_text.append("TERMINAL CMD: ", style="#00FF41 bold")
            tool_text.append(f"{cmd}", style="#F0F0F0")
        elif tool_name == 'web_search':
            search_term = args.get('search_term', '')
            tool_text.append("WEB SEARCH: ", style="#00FF41 bold")
            tool_text.append(f"{search_term}", style="#F0F0F0")
        else:
            tool_text.append(f"USING {tool_name.upper()}", style="#00FF41 bold")
        
        # Add explanation if available
        if 'explanation' in args and args['explanation']:
            tool_text.append(f" >> {args['explanation']}", style="#FFB000 dim")
        
        # Add retro loading dots
        tool_text.append(" ", style="")
        for dot in self.retro_symbols['dots'][:2]:
            tool_text.append(dot, style="#00FFFF dim")
        
        self.console.print(tool_text)