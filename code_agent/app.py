import asyncio
from typing import Dict, Any, List, Tuple, Optional

from .llm import LLMClient
from .tools import Tools


class CodeAgent:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434"):
        """
        Initialize a CodeAgent that can use tools and execute tool calls.

        Args:
            model_name (str): The name of the Ollama model to use.
            host (str): The host URL for the Ollama API.
        """
        self.llm_client = LLMClient(model_name=model_name, host=host)
        self.tools_manager = Tools()
        self.register_tools()
    
    def register_tools(self):
        """Register all available tools."""
        self.tools_manager.register_file_tools()
        self.tools_manager.register_terminal_tools()
        self.tools_manager.register_math_tools()
    
    async def process_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """
        Process tool calls from the model response.

        Args:
            tool_calls: List of tool calls from the model.

        Returns:
            List[Tuple[str, str]]: List of (tool_name, tool_output) pairs.
        """
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            
            if function := self.tools_manager.available_functions.get(function_name):
                try:
                    # Parse the arguments
                    args = tool_call['function']['arguments']
                    
                    # Call the function
                    print(f"Calling function: {function_name}")
                    print(f"Arguments: {args}")
                    
                    output = function(**args)
                    print(f"Function output: {output}")
                    
                    # Add the result to the conversation
                    self.llm_client.add_message("tool", str(output), name=function_name)
                    results.append((function_name, str(output)))
                    
                except Exception as e:
                    error_message = f"Error executing {function_name}: {str(e)}"
                    print(error_message)
                    self.llm_client.add_message("tool", error_message, name=function_name)
                    results.append((function_name, error_message))
            else:
                error_message = f"Function {function_name} not found"
                print(error_message)
                self.llm_client.add_message("tool", error_message, name=function_name)
                results.append((function_name, error_message))
                
        return results
    
    async def chat(self, user_message: str, system_message: Optional[str] = None) -> str:
        """
        Send a message to the LLM and process any tool calls.

        Args:
            user_message (str): The user's message.
            system_message (Optional[str]): Optional system message to guide the model.

        Returns:
            str: The final response from the model.
        """
        # Send to LLM
        response = await self.llm_client.chat(
            user_message=user_message,
            tools=self.tools_manager.tools,
            system_message=system_message
        )
        
        # Process tool calls if any
        if response.message.tool_calls:
            await self.process_tool_calls(response.message.tool_calls)
            
            # Get final response with tool results
            final_response = await self.llm_client.chat(
                user_message="",  # Empty message to just get the next response
                tools=None  # No tools for the final response
            )
            
            return final_response.message.content
        
        return response.message.content


async def demo():
    """Example usage of the CodeAgent."""
    # Create the agent
    agent = CodeAgent()
    
    # System prompt to guide the agent
    system_prompt = """
    You are CodeAgent, an AI coding assistant. You can help with:
    1. Answering coding questions
    2. Creating or modifying files
    3. Running terminal commands
    4. Searching for code in files
    
    Use your tools wisely to help the user with their coding tasks.
    """
    
    # Test with a math calculation
    print("\n=== Testing math calculation ===")
    response = await agent.chat("What is 3 + 4?", system_message=system_prompt)
    print("Final response:", response)
    
    # Test with a file operation
    print("\n=== Testing file operation ===")
    response = await agent.chat("Create a simple Python file that prints 'Hello World'")
    print("Final response:", response)
    
    # Test with a directory listing
    print("\n=== Testing directory listing ===")
    response = await agent.chat("List the files in the current directory")
    print("Final response:", response)


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\nGoodbye!")
