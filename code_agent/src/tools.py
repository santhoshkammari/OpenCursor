import asyncio
import os
import re
import json
import aiohttp
import subprocess
from typing import Callable, Dict, Any, Optional
from difflib import unified_diff
from rich.console import Console

from .llm import LLMClient
from .tool_playwright_search import register_playwright_search_tool


class Tools:
    def __init__(self, workspace_root: str = None):
        """Initialize tools with the workspace root directory."""
        self.workspace_root = workspace_root or os.getcwd()
        self.available_functions = {}
        self.tools = []

    async def process_tool_calls(self, tool_calls, llm_client:LLMClient):
        """
        Process tool calls from the LLM.
        
        Args:
            tool_calls (list): List of tool calls from the LLM
            llm_client: The LLM client to add tool results to
            
        Returns:
            list: Results of the tool calls
        """
        results = []
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            function_args = tool_call['function']['arguments']
            
            # Get the function
            if function_name in self.available_functions:
                function = self.available_functions[function_name]
                
                try:
                    # Check if the function is async
                    if asyncio.iscoroutinefunction(function):
                        result = await function(**function_args)
                    else:
                        result = function(**function_args)
                        
                    # Add the result to the LLM client
                    llm_client.add_message(role="tool", content=result, name=function_name)
                    results.append(result)
                except Exception as e:
                    error_message = f"Error executing {function_name}: {str(e)}"
                    llm_client.add_message(role="tool", content=error_message, name=function_name)
                    results.append(error_message)
            else:
                error_message = f"Function {function_name} not found"
                llm_client.add_message(role="tool", content=error_message, name=function_name)
                results.append(error_message)
        
        return results

    def register_all_tools(self):
        """
        Register all available tools for use with the LLM.
        This is a convenience method to register all tool categories at once.
        """
        # File operations
        self.register_file_tools()
        
        # Terminal operations
        self.register_terminal_tools()
        
        # Semantic understanding
        self.register_semantic_tools()
        
        # Math tools
        self.register_math_tools()
        
        
        return self.tools

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

    def run_git_diff(self, file_path: str) -> str:
        """
        Run git diff for a specific file to show changes.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            str: Git diff output or error message
        """
        try:
            # Check if file is in a git repository
            result = subprocess.run(
                ['git', 'ls-files', '--error-unmatch', file_path], 
                cwd=self.workspace_root,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # File is not tracked by git
                return "File is not tracked by git."
            
            # Run git diff
            diff_result = subprocess.run(
                ['git', 'diff', file_path], 
                cwd=self.workspace_root,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if diff_result.returncode != 0:
                return f"Error running git diff: {diff_result.stderr}"
            
            if not diff_result.stdout.strip():
                return "No changes detected by git."
            
            return diff_result.stdout
        except Exception as e:
            return f"Error running git diff: {str(e)}"

    def register_file_tools(self):
        """Register file operation tools."""
        
        def read_file(target_file: str, offset: int = 0, limit: int = None, should_read_entire_file: bool = False) -> str:
            """
            Read the contents of a file.
            
            Args:
                target_file (str): Path to the file to read
                offset (int): Line to start reading from (0-indexed)
                limit (int): Maximum number of lines to read
                should_read_entire_file (bool): Whether to read the entire file ignoring offset and limit
                
            Returns:
                str: The file contents
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if should_read_entire_file:
                        return f.read()
                    
                    lines = f.readlines()
                
                # Apply offset and limit
                start_idx = max(0, offset)
                end_idx = len(lines) if limit is None else min(start_idx + limit, len(lines))
                
                # Include summary of lines outside the range
                result = []
                if start_idx > 0:
                    result.append(f"[Lines 1-{start_idx} omitted]")
                
                result.append(''.join(lines[start_idx:end_idx]))
                
                if end_idx < len(lines):
                    result.append(f"[Lines {end_idx+1}-{len(lines)} omitted]")
                
                return '\n'.join(result)
            except Exception as e:
                return f"Error reading file: {str(e)}"
        
        def edit_file(target_file: str, code_edit: str, instructions: str = "") -> str:
            """
            Edit a file with the specified code changes.
            
            Args:
                target_file (str): Path to the file to edit
                code_edit (str): The code edits to apply
                instructions (str): Instructions for applying the edit
                
            Returns:
                str: Result of the operation
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Check if file exists
                file_exists = os.path.isfile(file_path)
                
                # Record git state before edit
                before_git_state = self.run_git_diff(file_path) if file_exists else ""
                
                if file_exists:
                    # Read existing content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    
                    # Here we would apply a more sophisticated diff algorithm
                    # For now, we'll just replace the entire content
                    new_content = code_edit
                else:
                    # Create new file
                    existing_content = ""
                    new_content = code_edit
                
                # Write the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Get git diff after edit
                after_git_state = self.run_git_diff(file_path)
                
                action = "Updated" if file_exists else "Created"
                result = f"{action} file: {target_file}\nInstructions applied: {instructions}"
                
                # Add git diff if available and changed
                if after_git_state and after_git_state != "No changes detected by git." and after_git_state != "File is not tracked by git.":
                    result += f"\n\n[Git Diff]\n{after_git_state}"
                else:
                    # If git diff is not available, show a simple diff
                    if existing_content != new_content:
                        result += "\n\n[Changes Made]\n"
                        # Show a simple line-by-line diff of changes
                        diff = unified_diff(
                            existing_content.splitlines(keepends=True),
                            new_content.splitlines(keepends=True),
                            fromfile=f'a/{target_file}',
                            tofile=f'b/{target_file}'
                        )
                        diff_text = ''.join(diff)
                        if diff_text:
                            result += diff_text
                
                return result
                
            except Exception as e:
                return f"Error editing file: {str(e)}"
        
        def list_dir(directory: str = ".",explanation:str="") -> str:
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
        
        # Register file tools
        self.register_function(read_file)
        self.register_function(edit_file)
        self.register_function(list_dir)
        
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
        
        def delete_file(target_file: str, explanation: str = "") -> str:
            """
            Delete a file.
            
            Args:
                target_file (str): Path to the file to delete
                explanation (str): Explanation for why the file is being deleted
                
            Returns:
                str: Result of the operation
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                if os.path.exists(file_path):
                    # Ask for confirmation
                    console = Console()
                    console.print(f"[yellow]WARNING: About to delete file: {target_file}[/yellow]")
                    if explanation:
                        console.print(f"Reason: {explanation}")
                    
                    confirmation = input("Are you sure you want to delete this file? (y/n): ").strip().lower()
                    
                    if confirmation == 'y' or confirmation == 'yes':
                        os.remove(file_path)
                        return f"Deleted file: {target_file}"
                    else:
                        return f"File deletion cancelled: {target_file}"
                else:
                    return f"File not found: {target_file}"
            except Exception as e:
                return f"Error deleting file: {str(e)}"
        
        def search_replace(file_path: str, old_string: str, new_string: str) -> str:
            """
            Search and replace text in a file.
            
            Args:
                file_path (str): Path to the file
                old_string (str): Text to replace
                new_string (str): New text
                
            Returns:
                str: Result of the operation
            """
            full_path = os.path.join(self.workspace_root, file_path) if not os.path.isabs(file_path) else file_path
            
            try:
                if not os.path.exists(full_path):
                    return f"Error: File {file_path} not found"
                    
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if old_string not in content:
                    return f"Error: Could not find the specified text in {file_path}"
                    
                # Count occurrences
                occurrences = content.count(old_string)
                if occurrences > 1:
                    return f"Error: Found {occurrences} occurrences of the text. Please provide more context to make the match unique."
                
                # Record git state before edit
                before_git_state = self.run_git_diff(file_path)
                
                # Replace the text
                new_content = content.replace(old_string, new_string)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Get git diff after edit
                after_git_state = self.run_git_diff(file_path)
                
                result = f"Successfully replaced text in {file_path}"
                
                # Add git diff if available and changed
                if after_git_state and after_git_state != "No changes detected by git." and after_git_state != "File is not tracked by git.":
                    result += f"\n\n[Git Diff]\n{after_git_state}"
                else:
                    # If git diff is not available, show a simple diff
                    result += "\n\n[Changes Made]\n"
                    # Show a simple line-by-line diff of changes
                    diff = unified_diff(
                        content.splitlines(keepends=True),
                        new_content.splitlines(keepends=True),
                        fromfile=f'a/{file_path}',
                        tofile=f'b/{file_path}'
                    )
                    diff_text = ''.join(diff)
                    if diff_text:
                        result += diff_text
                
                return result
                
            except Exception as e:
                return f"Error performing search and replace: {str(e)}"
        
        # Register file operation tools
        self.register_function(read_file)
        self.register_function(edit_file)
        self.register_function(list_dir)
        self.register_function(search_files)
        self.register_function(delete_file)
        self.register_function(search_replace)

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
                # Use the workspace_root as the cwd for command execution
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=True,
                    cwd=self.workspace_root  # Set the working directory to workspace_root
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

    def register_semantic_tools(self):
        """Register semantic search tools for code understanding."""
        
        def semantic_search(query: str) -> str:
            """
            Run a semantic search on the codebase.
            
            Args:
                query (str): The natural language query to search for
                
            Returns:
                str: Matching code snippets or files
            """
            results = []
            
            try:
                # This is a simplified implementation
                # In a real system, you would use an embedding model and vector DB
                
                # For now, we'll do a simple keyword search in key files
                for root, dirs, files in os.walk(self.workspace_root):
                    # Skip hidden directories and dependencies
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                    
                    for file in files:
                        if file.endswith(('.py', '.js', '.java', '.cpp', '.c', '.h', '.md', '.jsx', '.ts', '.tsx')):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                # Simple check for query terms
                                query_terms = query.lower().split()
                                content_lower = content.lower()
                                
                                match_count = sum(1 for term in query_terms if term in content_lower)
                                
                                if match_count >= max(1, len(query_terms) // 3):
                                    # Extract a relevant snippet
                                    lines = content.split('\n')
                                    best_line = 0
                                    best_score = 0
                                    
                                    for i, line in enumerate(lines):
                                        line_lower = line.lower()
                                        score = sum(1 for term in query_terms if term in line_lower)
                                        if score > best_score:
                                            best_score = score
                                            best_line = i
                                    
                                    # Extract a window of code around the best matching line
                                    start = max(0, best_line - 5)
                                    end = min(len(lines), best_line + 10)
                                    snippet = '\n'.join(lines[start:end])
                                    
                                    results.append({
                                        'path': rel_path,
                                        'score': match_count + (best_score * 0.5),  # Weight both file and line matches
                                        'snippet': snippet,
                                        'start_line': start + 1,
                                        'end_line': end
                                    })
                            except:
                                # Skip files we can't read
                                pass
                
                # Sort by score
                results.sort(key=lambda x: x['score'], reverse=True)
                
                if results:
                    formatted_results = []
                    for i, result in enumerate(results[:5]):  # Limit to top 5 results
                        formatted_results.append(
                            f"File: {result['path']} (lines {result['start_line']}-{result['end_line']})\n```\n{result['snippet']}\n```\n"
                        )
                    return "\n".join(formatted_results)
                else:
                    return f"No semantic matches found for '{query}'"
                    
            except Exception as e:
                return f"Error during semantic search: {str(e)}"
        
        def codebase_search(query: str, target_directories: list = None, explanation: str = "") -> str:
            """
            Find code snippets from the codebase relevant to the search query.
            
            Args:
                query (str): The search query to find relevant code
                target_directories (list): Optional list of directories to search in
                explanation (str): Explanation for why the search is being performed
                
            Returns:
                str: Relevant code snippets
            """
            results = []
            
            try:
                # Define search directories
                search_dirs = []
                if target_directories:
                    for dir_pattern in target_directories:
                        import glob
                        matched_dirs = glob.glob(os.path.join(self.workspace_root, dir_pattern))
                        search_dirs.extend(matched_dirs)
                else:
                    search_dirs = [self.workspace_root]
                
                # Search through all directories
                for search_dir in search_dirs:
                    for root, dirs, files in os.walk(search_dir):
                        # Skip hidden directories and dependencies
                        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'dist', '__pycache__']]
                        
                        for file in files:
                            # Skip hidden and binary files
                            if file.startswith('.') or file.endswith(('.exe', '.bin', '.pyc', '.pyo')):
                                continue
                                
                            # Focus on code files
                            if not file.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.md', '.json')):
                                continue
                                
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            
                            try:
                                # Skip large files
                                if os.path.getsize(file_path) > 1024 * 1024:  # 1MB
                                    continue
                                    
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                # Search for query terms
                                query_terms = query.lower().split()
                                content_lower = content.lower()
                                
                                # Try to find the most relevant section of the file
                                lines = content.split('\n')
                                matches = []
                                
                                for i, line in enumerate(lines):
                                    line_lower = line.lower()
                                    score = sum(1 for term in query_terms if term in line_lower)
                                    if score > 0:
                                        matches.append((i, score))
                                
                                if matches:
                                    # Group matches that are close together
                                    groups = []
                                    current_group = [matches[0]]
                                    
                                    for i in range(1, len(matches)):
                                        if matches[i][0] - current_group[-1][0] <= 5:  # If lines are within 5 lines
                                            current_group.append(matches[i])
                                        else:
                                            groups.append(current_group)
                                            current_group = [matches[i]]
                                    
                                    groups.append(current_group)
                                    
                                    # Find the group with highest score
                                    best_group = max(groups, key=lambda g: sum(m[1] for m in g))
                                    
                                    # Extract a window around this group
                                    start_line = max(0, best_group[0][0] - 5)
                                    end_line = min(len(lines), best_group[-1][0] + 5)
                                    
                                    snippet = '\n'.join(lines[start_line:end_line])
                                    score = sum(m[1] for m in best_group)
                                    
                                    results.append({
                                        'path': rel_path,
                                        'score': score,
                                        'snippet': snippet,
                                        'start_line': start_line + 1,
                                        'end_line': end_line
                                    })
                            except:
                                # Skip files we can't read
                                pass
                
                # Sort by relevance score
                results.sort(key=lambda x: x['score'], reverse=True)
                
                if results:
                    formatted_results = []
                    for result in results[:5]:  # Limit to top 5 results
                        formatted_results.append(
                            f"File: {result['path']} (lines {result['start_line']}-{result['end_line']})\n```\n{result['snippet']}\n```\n"
                        )
                    return "\n".join(formatted_results)
                else:
                    return f"No relevant code found for: {query}"
                    
            except Exception as e:
                return f"Error during codebase search: {str(e)}"

        def reapply(target_file: str) -> str:
            """
            Reapply the last edit to the specified file with a smarter model.
            
            Args:
                target_file (str): Path to the file to reapply edits to
                
            Returns:
                str: Result of the operation
            """
            return f"Function 'reapply' called for file {target_file}. This is a stub implementation. In a full implementation, this would use a more capable model to apply complex edits to the file."
        
        def list_code_usages(symbol_name: str, file_paths: list = None) -> str:
            """
            Find usages of a symbol (function, class, variable) in the codebase.
            
            Args:
                symbol_name (str): Name of the symbol to find
                file_paths (list): Optional list of files to search in
                
            Returns:
                str: Matching usages
            """
            results = []
            
            try:
                search_paths = []
                if file_paths:
                    for path in file_paths:
                        file_path = os.path.join(self.workspace_root, path) if not os.path.isabs(path) else path
                        search_paths.append(file_path)
                else:
                    # Search all code files
                    for root, dirs, files in os.walk(self.workspace_root):
                        for file in files:
                            if file.endswith(('.py', '.js', '.java', '.cpp', '.c', '.h')):
                                search_paths.append(os.path.join(root, file))
                
                for file_path in search_paths:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        rel_path = os.path.relpath(file_path, self.workspace_root)
                        
                        for i, line in enumerate(lines):
                            if symbol_name in line:
                                # Check if it's a real symbol, not part of another word
                                stripped_line = line.strip()
                                # This is a very simplified check
                                if re.search(r'\b' + re.escape(symbol_name) + r'\b', stripped_line):
                                    context_start = max(0, i - 2)
                                    context_end = min(len(lines), i + 3)
                                    
                                    context = ''.join(lines[context_start:context_end])
                                    results.append(f"File: {rel_path}, Line {i+1}\n```\n{context}\n```")
                    except Exception as e:
                        # Skip files we can't read
                        pass
                
                return "\n".join(results) if results else f"No usages found for symbol '{symbol_name}'"
                
            except Exception as e:
                return f"Error finding usages: {str(e)}"

        # Register the functions
        self.register_function(semantic_search)
        self.register_function(codebase_search)
        self.register_function(reapply)
        self.register_function(list_code_usages)
