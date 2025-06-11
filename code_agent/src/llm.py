import time
import ollama
from ollama import ChatResponse
from typing import Dict, Any, List, Tuple, Optional
import sys
import asyncio
from rich.console import Console
from rich.text import Text
from rich.style import Style

import tiktoken


class LLMClient:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434", num_ctx: int = 2048, no_think: bool = True):
        """
        Initialize an LLM client using Ollama.

        Args:
            model_name (str): The name of the Ollama model to use.
            host (str): The host URL for the Ollama API.
            num_ctx (int): Context window size for the model.
            no_think (bool): Whether to use no-thinking mode (adds /no_think tag). Default is True.
        """
        self.model_name = model_name
        self.client = ollama.AsyncClient(host=host)
        self.messages = []
        self.num_ctx = num_ctx
        self.no_think = no_think
        
        # Check if model supports thinking (models like deepseek-r1, qwen-qwq, etc.)
        self.supports_thinking = any(keyword in model_name.lower() for keyword in ['deepseek', 'qwq', 'r1', 'think'])
        
        # Initialize nostalgic console for streaming
        self.console = Console()
        self.nostalgic_chars = ['░', '▒', '▓', '█']
        self.thinking_dots = ['.', '··', '···', '····', '·····', '····', '···', '··']
        self.thinking_index = 0
    
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
    
    
    async def chat(self, user_message: str, tools: List[Dict[str, Any]] = None, system_message: Optional[str] = None, stream: bool = True) -> ChatResponse:
        """
        Send a message to the LLM.

        Args:
            user_message (str): The user's message.
            tools (List[Dict]): List of tool schemas to provide to the model.
            system_message (Optional[str]): Optional system message to guide the model.
            stream (bool): Whether to stream the response or not.

        Returns:
            ChatResponse: The response from the model.
        """
        # Add system message if provided and no messages exist yet
        if system_message and not self.messages:
            sys_content = system_message + " /no_think" if self.no_think else system_message
            self.add_message("system", sys_content)
        
        # Add user message to conversation (only if not empty)
        if user_message.strip():
            user_content = user_message + " /no_think" if self.no_think else user_message
            self.add_message("user", user_content)
        
        if stream:
            # Stream the response
            complete_content = ""
            tool_calls = []
            thinking_content = ""
            
            # Prepare chat options
            chat_options = {
                'model': self.model_name,
                'messages': self.messages,
                'tools': tools if tools else None,
                'stream': True,
                'options': {'num_ctx': self.num_ctx}
            }
            
            # Add thinking support for compatible models
            if self.supports_thinking and not tools:  # Don't use thinking when tools are available
                chat_options['options'].update({'think': True})
            
            async for chunk in await self.client.chat(**chat_options):
                # Check if chunk has message content
                if chunk.message.content:
                    complete_content += chunk.message.content
                    # Nostalgic streaming display with green retro effect
                    self._nostalgic_stream_text(chunk.message.content)
                
                # Check for thinking content (if supported)
                if hasattr(chunk.message, 'thinking') and chunk.message.thinking:
                    thinking_content += chunk.message.thinking
                
                # Check for tool calls
                if chunk.message.tool_calls:
                    tool_calls.extend(chunk.message.tool_calls)
            
            # Print newline after streaming is done with nostalgic effect
            if complete_content:
                self._nostalgic_stream_complete()
            
            # Create a ChatResponse-like object with the complete content
            class StreamResponse:
                def __init__(self, content, tool_calls, thinking=None):
                    self.message = type('obj', (object,), {
                        'content': content,
                        'tool_calls': tool_calls
                    })()
                    if thinking:
                        self.thinking = thinking
            
            response = StreamResponse(complete_content, tool_calls, thinking_content if thinking_content else None)
        else:
            # Non-streaming response
            chat_options = {
                'model': self.model_name,
                'messages': self.messages,
                'tools': tools if tools else None,
                'options': {'num_ctx': self.num_ctx}
            }
            
            # Add thinking support for compatible models
            if self.supports_thinking and not tools:  # Don't use thinking when tools are available
                chat_options['options'].update({'think': True})
            
            response: ChatResponse = await self.client.chat(**chat_options)

        # Add assistant response to conversation
        self.add_message("assistant", response.message.content)
        
        return response
    
    def _nostalgic_stream_text(self, text: str):
        """Stream text with nostalgic green terminal effect"""
        nostalgic_text = Text(text, style="#00FF41")  # Matrix green
        self.console.print(nostalgic_text, end="")
    
    def _nostalgic_stream_complete(self):
        """Complete streaming with nostalgic effect"""
        self.console.print()  # New line
        # Optional: Add a brief pause for that old terminal feel
        time.sleep(0.05)
    
    def _nostalgic_thinking_indicator(self):
        """Show nostalgic thinking indicator"""
        dots = self.thinking_dots[self.thinking_index % len(self.thinking_dots)]
        thinking_text = Text(f"\r[THINKING{dots}]", style="#00FF41 dim")
        self.console.print(thinking_text, end="")
        self.thinking_index += 1 