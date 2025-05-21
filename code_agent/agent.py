import asyncio
from typing import Dict, Any, List, Tuple, Optional

from code_agent.llm import LLMClient
from code_agent.tools import Tools
from code_agent.prompts import SYSTEM_PROMPT


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
        self.tools_manager.register_semantic_tools()
        self.tools_manager.register_web_tools()
        self.tools_manager.register_code_analysis_tools()

    async def __call__(self, user_message: str) -> str:
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
            system_message=SYSTEM_PROMPT
        )

        # Process tool calls if any
        if response.message.tool_calls:
            await self.tools_manager.process_tool_calls(response.message.tool_calls, self.llm_client)

            # Get final response with tool results
            final_response = await self.llm_client.chat(
                user_message="",  # Empty message to just get the next response
                tools=None  # No tools for the final response
            )

            return final_response.message.content

        return response.message.content