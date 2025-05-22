import asyncio
from typing import Dict, Any, List, Tuple, Optional

from .llm import LLMClient
from .tools import Tools
from .prompts import SYSTEM_PROMPT, AUTONOMOUS_AGENT_PROMPT
from .register_tools import register_additional_tools

# Add interactive prompt
INTERACTIVE_AGENT_PROMPT = """
You are an interactive AI coding agent that works step-by-step with the user. You will be given a task and must complete it one step at a time, waiting for user approval between steps.

1. Analyze the task and suggest the next step
2. Wait for user approval before executing any tool
3. After each tool use, explain the result and suggest the next step
4. Continue until the task is complete

<important>
- Suggest ONE tool call at a time
- Wait for user approval before proceeding
- Explain your reasoning clearly
- Be methodical and thorough
</important>

<available_tools>
1. File operations:
   - read_file(target_file, start_line, end_line) - Read contents of a file
   - edit_file(target_file, code_edit) - Edit or create a file
   - list_dir(directory) - List contents of a directory
   - delete_file(target_file) - Delete a file

2. Code analysis:
   - grep_search(query, include_pattern, is_regexp) - Search for text patterns in files
   - file_search(query) - Search for files by name pattern
   - semantic_search(query) - Search for semantically relevant code

3. Terminal:
   - run_terminal_cmd(command, is_background) - Run a terminal command

4. Web tools:
   - web_search_playwright(search_term, search_provider) - Search the web using Playwright (preferred)
   - web_search(search_term) - Search the web (fallback if Playwright search fails)
   - fetch_webpage(urls, query) - Fetch contents from web pages
</available_tools>
"""

class CodeAgent:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", workspace_root: str = None):
        """
        Initialize a CodeAgent that can use tools and execute tool calls.

        Args:
            model_name (str): The name of the Ollama model to use.
            host (str): The host URL for the Ollama API.
            workspace_root (str): The root directory of the workspace.
        """
        self.llm_client = LLMClient(model_name=model_name, host=host)
        self.tools_manager = Tools(workspace_root=workspace_root)
        self.register_tools()
        self.max_iterations = 25

    def register_tools(self):
        """Register all available tools."""
        # Use the convenient method to register all tools
        self.tools_manager.register_all_tools()
        
        # Register additional tools
        register_additional_tools(self.tools_manager)

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
        self.llm_client.add_message("system", AUTONOMOUS_AGENT_PROMPT)
        
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
                # Log tool calls with simplified names
                tool_calls_info = []
                for tc in response.message.tool_calls:
                    name = tc['function']['name']
                    # Simplify tool names for display
                    if name == 'read_file':
                        tool_calls_info.append("Reading file...")
                    elif name == 'list_dir':
                        tool_calls_info.append("Listing directory...")
                    elif name == 'edit_file':
                        tool_calls_info.append("Editing file...")
                    elif name == 'grep_search':
                        tool_calls_info.append("Searching code...")
                    elif name == 'file_search':
                        tool_calls_info.append("Finding files...")
                    elif name == 'semantic_search':
                        tool_calls_info.append("Semantic search...")
                    elif name == 'run_terminal_cmd':
                        tool_calls_info.append("Running command...")
                    else:
                        tool_calls_info.append(f"{name}...")
                
                execution_log.append(f"Step {i+1}: {', '.join(tool_calls_info)}")
                
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