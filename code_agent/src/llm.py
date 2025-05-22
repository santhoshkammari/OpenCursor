import ollama
from ollama import ChatResponse
from typing import Dict, Any, List, Tuple, Optional


class LLMClient:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434"):
        """
        Initialize an LLM client using Ollama.

        Args:
            model_name (str): The name of the Ollama model to use.
            host (str): The host URL for the Ollama API.
        """
        self.model_name = model_name
        self.client = ollama.AsyncClient(host=host)
        self.messages = []
    
    def add_message(self, role: str, content: str, name: Optional[str] = None):
        """
        Add a message to the conversation history.

        Args:
            role (str): The role of the message sender (user, assistant, tool).
            content (str): The content of the message.
            name (Optional[str]): The name of the tool when role is 'tool'.
        """
        message = {"role": role, "content": content}
        if name and role == "tool":
            message["name"] = name
        self.messages.append(message)
    
    
    async def chat(self, user_message: str, tools: List[Dict[str, Any]] = None, system_message: Optional[str] = None) -> ChatResponse:
        """
        Send a message to the LLM.

        Args:
            user_message (str): The user's message.
            tools (List[Dict]): List of tool schemas to provide to the model.
            system_message (Optional[str]): Optional system message to guide the model.

        Returns:
            ChatResponse: The response from the model.
        """
        # Add system message if provided and no messages exist yet
        if system_message and not self.messages:
            self.add_message("system", system_message)
        
        # Add user message to conversation
        self.add_message("user", user_message)
        
        # Send to LLM
        response: ChatResponse = await self.client.chat(
            self.model_name,
            messages=self.messages,
            tools=tools if tools else None,
        )
        
        # Add assistant response to conversation
        self.add_message("assistant", response.message.content)
        
        return response 