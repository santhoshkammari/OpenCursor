import asyncio
import os
import re
from typing import Callable, Dict, Any, Optional


class Tools:
    def __init__(self, workspace_root: str = None):
        """Initialize tools with the workspace root directory."""
        self.workspace_root = workspace_root or os.getcwd()
        self.available_functions = {}
        self.tools = []

    def register_function(self, func: Callable, custom_schema: Optional[Dict[str, Any]] = None):
        """
        Register a function as an available tool.

        Args:
            func (Callable): The function to register.
            custom_schema (Optional[Dict]): Optional custom schema for the function.
        """
        import inspect
        
        function_name = func.__name__
        self.available_functions[function_name] = func
        
        if custom_schema:
            self.tools.append(custom_schema)
        else:
            # Create tool schema from function's docstring and type hints
            schema = {
                'type': 'function',
                'function': {
                    'name': function_name,
                    'description': func.__doc__ or f"Execute {function_name}",
                    'parameters': {
                        'type': 'object',
                        'required': [],
                        'properties': {}
                    }
                }
            }
            
            # Try to extract parameter info from type hints
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param.annotation is not inspect.Parameter.empty:
                    param_type = "string"
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    
                    schema['function']['parameters']['properties'][param_name] = {
                        'type': param_type,
                        'description': f"Parameter {param_name}"
                    }
                    
                    # Add to required if no default value
                    if param.default is inspect.Parameter.empty:
                        schema['function']['parameters']['required'].append(param_name)
            
            self.tools.append(schema)

    def register_file_tools(self):
        """Register file operation tools."""
        
        def read_file(target_file: str, start_line: int = 1, end_line: int = None) -> str:
            """
            Read the contents of a file.
            
            Args:
                target_file (str): Path to the file to read
                start_line (int): Line to start reading from (1-indexed)
                end_line (int): Line to end reading at (1-indexed, inclusive)
                
            Returns:
                str: The file contents
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Adjust for 1-indexing
                start_idx = max(0, start_line - 1)
                end_idx = len(lines) if end_line is None else min(end_line, len(lines))
                
                return ''.join(lines[start_idx:end_idx])
            except Exception as e:
                return f"Error reading file: {str(e)}"
        
        def edit_file(target_file: str, code_edit: str) -> str:
            """
            Edit a file with the specified code changes.
            
            Args:
                target_file (str): Path to the file to edit
                code_edit (str): The code edits to apply
                
            Returns:
                str: Result of the operation
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Check if file exists
                file_exists = os.path.isfile(file_path)
                
                if file_exists:
                    # Read existing content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    
                    # Apply edits - this is a simplified implementation
                    # In a real system, you'd need more sophisticated diff handling
                    new_content = code_edit
                else:
                    # Create new file
                    new_content = code_edit
                
                # Write the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                action = "Updated" if file_exists else "Created"
                return f"{action} file: {target_file}"
                
            except Exception as e:
                return f"Error editing file: {str(e)}"
        
        def list_dir(directory: str = ".") -> str:
            """
            List contents of a directory.
            
            Args:
                directory (str): Path to directory to list
                
            Returns:
                str: Directory contents
            """
            dir_path = os.path.join(self.workspace_root, directory) if not os.path.isabs(directory) else directory
            
            try:
                items = os.listdir(dir_path)
                result = []
                
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    item_type = "[dir] " if os.path.isdir(item_path) else "[file]"
                    size = os.path.getsize(item_path) if os.path.isfile(item_path) else ""
                    size_str = f"({size}B)" if size else ""
                    result.append(f"{item_type} {item} {size_str}")
                
                return "\n".join(result)
            except Exception as e:
                return f"Error listing directory: {str(e)}"
        
        def search_files(query: str, file_pattern: str = "*") -> str:
            """
            Search for files matching a pattern.
            
            Args:
                query (str): Text to search for
                file_pattern (str): File pattern to match
                
            Returns:
                str: Search results
            """
            results = []
            
            try:
                for root, dirs, files in os.walk(self.workspace_root):
                    for file in files:
                        if file_pattern == "*" or re.match(file_pattern, file):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    
                                if query.lower() in content.lower():
                                    results.append(f"Found in: {rel_path}")
                            except:
                                # Skip files we can't read
                                pass
                
                if results:
                    return "\n".join(results)
                else:
                    return f"No matches found for '{query}'"
            except Exception as e:
                return f"Error searching files: {str(e)}"
        
        def delete_file(target_file: str) -> str:
            """
            Delete a file.
            
            Args:
                target_file (str): Path to the file to delete
                
            Returns:
                str: Result of the operation
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return f"Deleted file: {target_file}"
                else:
                    return f"File not found: {target_file}"
            except Exception as e:
                return f"Error deleting file: {str(e)}"
        
        # Register file operation tools
        self.register_function(read_file)
        self.register_function(edit_file)
        self.register_function(list_dir)
        self.register_function(search_files)
        self.register_function(delete_file)

    def register_terminal_tools(self):
        """Register terminal command execution tools."""
        
        async def run_terminal_cmd(command: str, is_background: bool = False) -> str:
            """
            Run a terminal command.
            
            Args:
                command (str): The command to run
                is_background (bool): Whether to run in background
                
            Returns:
                str: Command output
            """
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=True
                )
                
                if is_background:
                    # Don't wait for process to complete
                    return f"Running command in background: {command}"
                
                stdout, stderr = await process.communicate()
                
                result = stdout.decode().strip()
                error = stderr.decode().strip()
                
                if error:
                    return f"Command output:\n{result}\n\nErrors:\n{error}"
                
                return f"Command output:\n{result}"
                
            except Exception as e:
                return f"Error executing command: {str(e)}"
        
        # Register as async function
        self.available_functions["run_terminal_cmd"] = run_terminal_cmd
        
        # Create schema manually since it's an async function
        schema = {
            'type': 'function',
            'function': {
                'name': 'run_terminal_cmd',
                'description': 'Run a terminal command',
                'parameters': {
                    'type': 'object',
                    'required': ['command'],
                    'properties': {
                        'command': {
                            'type': 'string',
                            'description': 'The command to run'
                        },
                        'is_background': {
                            'type': 'boolean',
                            'description': 'Whether to run in background'
                        }
                    }
                }
            }
        }
        
        self.tools.append(schema)

    def register_math_tools(self):
        """Register built-in math tools."""
        
        def add_two_numbers(a: int, b: int) -> int:
            """
            Add two numbers.

            Args:
                a (int): The first number
                b (int): The second number

            Returns:
                int: The sum of the two numbers
            """
            return a + b
        
        def subtract_two_numbers(a: int, b: int) -> int:
            """Subtract two numbers"""
            return a - b
        
        # Register the functions
        self.register_function(add_two_numbers)
        self.register_function(subtract_two_numbers) 