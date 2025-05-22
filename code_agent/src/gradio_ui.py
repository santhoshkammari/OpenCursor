#!/usr/bin/env python3
import os
import asyncio
import gradio as gr
from pathlib import Path
from typing import List, Dict, Set, Optional

from code_agent.src.agent import CodeAgent

class OpenCursorGradioUI:
    def __init__(self, model_name: str = "qwen3_14b_q6k:latest", host: str = "http://192.168.170.76:11434"):
        self.agent = CodeAgent(model_name=model_name, host=host)
        
        # Chat context management
        self.files_in_context: Set[Path] = set()
        self.chat_history: List[List[str]] = []
        self.current_workspace = Path.cwd()
        
        # Available commands/tools
        self.available_tools = [
            "agent (autonomous)", 
            "agent (interactive)", 
            "chat (LLM only)", 
            "add file", 
            "drop file", 
            "clear context", 
            "repo map", 
            "focus on file"
        ]

    def add_file_to_context(self, file_path: str) -> str:
        """Add a file to the chat context"""
        path = Path(file_path).resolve()
        if path.exists() and path.is_file():
            self.files_in_context.add(path)
            return f"Added {path} to context"
        else:
            return f"File not found: {file_path}"
    
    def drop_file_from_context(self, file_path: str) -> str:
        """Remove a file from the chat context"""
        path = Path(file_path).resolve()
        if path in self.files_in_context:
            self.files_in_context.remove(path)
            return f"Removed {path} from context"
        else:
            return f"File not in context: {file_path}"
    
    def clear_context(self) -> str:
        """Clear all files from the chat context"""
        self.files_in_context.clear()
        return "Cleared all files from context"
    
    def generate_repo_map(self, workspace_path: str = None) -> str:
        """Generate a map of the repository"""
        if workspace_path and os.path.isdir(workspace_path):
            self.current_workspace = Path(workspace_path).resolve()
        
        result = "REPOSITORY MAP:\n\n"
        
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
                result += f"✓ {file} (in context)\n"
            else:
                result += f"  {file}\n"
                
        return result
    
    def get_file_content(self, file_path: str) -> str:
        """Get the content of a file"""
        try:
            path = Path(file_path).resolve()
            if path.exists() and path.is_file():
                with open(path, 'r') as f:
                    content = f.read()
                return f"FILE: {file_path}\n\n{content}"
            else:
                return f"File not found: {file_path}"
        except Exception as e:
            return f"Error reading file: {e}"
    
    def get_files_in_context(self) -> str:
        """Get the list of files in context"""
        if not self.files_in_context:
            return "No files in context"
            
        result = "FILES IN CONTEXT:\n"
        for file_path in sorted(self.files_in_context):
            result += f"- {file_path.relative_to(self.current_workspace)}\n"
            
        return result
    
    async def process_message(self, message: str, tool: str, workspace_path: str) -> str:
        """Process a message with the selected tool"""
        # Update workspace if provided
        if workspace_path and os.path.isdir(workspace_path):
            self.current_workspace = Path(workspace_path).resolve()
            os.chdir(self.current_workspace)
        
        # Handle tool selection
        if tool == "agent (autonomous)":
            response = await self.agent(message)
            return response
        elif tool == "agent (interactive)":
            response = await self.agent(f"/interactive {message}")
            return response
        elif tool == "chat (LLM only)":
            response = await self.agent.llm_client.chat(user_message=message, tools=None)
            return response.message.content
        elif tool == "add file":
            return self.add_file_to_context(message)
        elif tool == "drop file":
            return self.drop_file_from_context(message)
        elif tool == "clear context":
            return self.clear_context()
        elif tool == "repo map":
            return self.generate_repo_map()
        elif tool == "focus on file":
            self.add_file_to_context(message)
            return self.get_file_content(message)
        else:
            return f"Unknown tool: {tool}"
    
    def update_chat(self, message: str, tool: str, workspace_path: str, history: List[List[str]]):
        """Update the chat with user message and bot response"""
        if not message.strip():
            return history
        
        # Process the message asynchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop for the thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            loop = new_loop
        
        response = loop.run_until_complete(self.process_message(message, tool, workspace_path))
        
        # Update history with the new message format
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        return history
    
    def build_interface(self):
        """Build the Gradio interface"""
        with gr.Blocks(title="OpenCursor", theme=gr.themes.Soft()) as interface:
            gr.Markdown("# 🖱️ OpenCursor")
            gr.Markdown("An AI coding assistant with various tools and capabilities.")
            
            with gr.Row():
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(
                        label="Chat History",
                        height=500,
                        show_copy_button=True,
                        type="messages"
                    )
                    
                    with gr.Row():
                        message = gr.Textbox(
                            label="Message",
                            placeholder="Type your message here...",
                            lines=2,
                            show_copy_button=True
                        )
                        tool = gr.Dropdown(
                            label="Tool",
                            choices=self.available_tools,
                            value="agent (autonomous)"
                        )
                    
                    with gr.Row():
                        workspace = gr.Textbox(
                            label="Workspace Path",
                            placeholder="Enter directory path to work with (default: current directory)",
                            value=str(self.current_workspace)
                        )
                        submit = gr.Button("Submit", variant="primary")
                
                with gr.Column(scale=1):
                    context_info = gr.Textbox(
                        label="Context Information",
                        value=self.get_files_in_context(),
                        lines=15,
                        interactive=False
                    )
                    
                    update_context = gr.Button("Update Context")
                    clear_button = gr.Button("Clear Chat")
            
            submit.click(
                fn=self.update_chat,
                inputs=[message, tool, workspace, chatbot],
                outputs=[chatbot],
                queue=True,
            ).then(
                lambda: "",
                None,
                message,
                queue=False,
            )
            
            update_context.click(
                fn=lambda: self.get_files_in_context(),
                inputs=[],
                outputs=[context_info]
            )
            
            clear_button.click(lambda: None, None, chatbot)
            
            # Also submit on Enter key
            message.submit(
                fn=self.update_chat,
                inputs=[message, tool, workspace, chatbot],
                outputs=[chatbot],
                queue=True,
            ).then(
                lambda: "",
                None,
                message,
                queue=False,
            )
            
        return interface
    
    def launch(self, *args, **kwargs):
        """Launch the Gradio interface"""
        interface = self.build_interface()
        interface.launch(*args, **kwargs)

def main():
    """Main entry point"""
    # Parse command line arguments for model and host (could be expanded)
    model_name = "qwen3_14b_q6k:latest"
    host = "http://192.168.170.76:11434"
    
    # Create and run the app
    app = OpenCursorGradioUI(model_name=model_name, host=host)
    app.launch(share=False,server_name="0.0.0.0")

if __name__ == "__main__":
    main() 