import asyncio
from typing import Dict, Any, List, Tuple, Optional


from .llm import LLMClient
from .tools import Tools
from .prompts import SYSTEM_PROMPT, AUTONOMOUS_AGENT_PROMPT, INTERACTIVE_AGENT_PROMPT
from .tool_playwright_search import register_playwright_search_tool



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
                # Process each tool call and show real-time feedback
                for tc in response.message.tool_calls:
                    name = tc['function']['name']
                    args = tc['function']['arguments']
                    
                    # Display explanation if available
                    if 'explanation' in args and args['explanation']:
                        print(f"{args['explanation']}...")
                    
                    # Display what tool is being used with relevant info
                    if name == 'read_file':
                        target_file = args.get('target_file', '')
                        print(f"Reading file: {target_file}")
                    elif name == 'list_dir':
                        path = args.get('relative_workspace_path', '')
                        print(f"Listing directory: {path}")
                    elif name == 'edit_file':
                        target_file = args.get('target_file', '')
                        print(f"Editing file: {target_file}")
                    elif name == 'grep_search':
                        query = args.get('query', '')
                        print(f"Searching code for: {query}")
                    elif name == 'file_search':
                        query = args.get('query', '')
                        print(f"Finding files matching: {query}")
                    elif name == 'codebase_search':
                        query = args.get('query', '')
                        print(f"Semantic search for: {query}")
                    elif name == 'run_terminal_cmd':
                        cmd = args.get('command', '')
                        print(f"Running command: {cmd}")
                    else:
                        print(f"Using {name}...")
                    
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