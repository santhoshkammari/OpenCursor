import asyncio
import os
import re
import json
import aiohttp
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
                    for file in files:
                        if file.endswith(('.py', '.js', '.java', '.cpp', '.c', '.h', '.md')):
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
                                    
                                    results.append(f"File: {rel_path}\n```\n{snippet}\n```\n")
                            except:
                                # Skip files we can't read
                                pass
                
                if results:
                    return "\n".join(results[:5])  # Limit to top 5 results
                else:
                    return f"No semantic matches found for '{query}'"
                    
            except Exception as e:
                return f"Error during semantic search: {str(e)}"
        
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
                                    results.append(f"File: {rel_path}, Line {i+1}\n```\n{context}```\n")
                    except:
                        # Skip files we can't read
                        pass
                
                if results:
                    return "\n".join(results[:10])  # Limit to top 10 results
                else:
                    return f"No usages found for '{symbol_name}'"
                    
            except Exception as e:
                return f"Error finding code usages: {str(e)}"
        
        # Register semantic tools
        self.register_function(semantic_search)
        self.register_function(list_code_usages)
    
    def register_web_tools(self):
        """Register web search and web fetching tools."""
        
        async def web_search(search_term: str) -> str:
            """
            Search the web for information.
            
            Args:
                search_term (str): The search query
                
            Returns:
                str: Search results (simulated)
            """
            # This is a stub implementation
            # In a real implementation, you would use a search API
            return f"Simulated web search results for: {search_term}\n\n" + \
                   "1. Example result 1\n" + \
                   "2. Example result 2\n" + \
                   "3. Example result 3\n\n" + \
                   "Note: This is a simulated response. Implement a real search API integration for actual results."
        
        async def fetch_webpage(urls: list, query: str = None) -> str:
            """
            Fetch contents from web pages.
            
            Args:
                urls (list): List of URLs to fetch
                query (str): Optional query to filter content
                
            Returns:
                str: Webpage contents (simulated)
            """
            # This is a stub implementation
            # In a real implementation, you would use HTTP requests to fetch webpage content
            results = []
            
            for url in urls:
                results.append(f"Simulated content from {url}:\n\n" + 
                               "This is simulated webpage content.\n" +
                               "In a real implementation, the actual webpage would be fetched and parsed.\n")
            
            return "\n\n".join(results)
        
        # Register web tools as async functions
        self.available_functions["web_search"] = web_search
        self.available_functions["fetch_webpage"] = fetch_webpage
        
        # Create schemas manually
        web_search_schema = {
            'type': 'function',
            'function': {
                'name': 'web_search',
                'description': 'Search the web for information',
                'parameters': {
                    'type': 'object',
                    'required': ['search_term'],
                    'properties': {
                        'search_term': {
                            'type': 'string',
                            'description': 'The search query'
                        }
                    }
                }
            }
        }
        
        fetch_webpage_schema = {
            'type': 'function',
            'function': {
                'name': 'fetch_webpage',
                'description': 'Fetch contents from web pages',
                'parameters': {
                    'type': 'object',
                    'required': ['urls'],
                    'properties': {
                        'urls': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of URLs to fetch'
                        },
                        'query': {
                            'type': 'string',
                            'description': 'Optional query to filter content'
                        }
                    }
                }
            }
        }
        
        self.tools.append(web_search_schema)
        self.tools.append(fetch_webpage_schema)
    
    def register_code_analysis_tools(self):
        """Register code analysis tools."""
        
        def file_search(query: str) -> str:
            """
            Search for files by name pattern.
            
            Args:
                query (str): The filename pattern to search for
                
            Returns:
                str: Matching files
            """
            results = []
            
            try:
                for root, dirs, files in os.walk(self.workspace_root):
                    for file in files:
                        if query.lower() in file.lower():
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            results.append(rel_path)
                
                if results:
                    return "Matching files:\n" + "\n".join(results[:20])  # Limit to 20 results
                else:
                    return f"No files matching '{query}' found"
                    
            except Exception as e:
                return f"Error searching for files: {str(e)}"
        
        def grep_search(query: str, include_pattern: str = None, is_regexp: bool = False) -> str:
            """
            Search for text patterns in files.
            
            Args:
                query (str): The text pattern to search for
                include_pattern (str): Optional glob pattern to filter files
                is_regexp (bool): Whether the query is a regular expression
                
            Returns:
                str: Matching lines
            """
            results = []
            
            try:
                for root, dirs, files in os.walk(self.workspace_root):
                    for file in files:
                        # Skip binary files and large files
                        if file.endswith(('.exe', '.bin', '.obj', '.dll', '.so')):
                            continue
                            
                        file_path = os.path.join(root, file)
                        
                        # Check include pattern if provided
                        if include_pattern:
                            import fnmatch
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            if not fnmatch.fnmatch(rel_path, include_pattern):
                                continue
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                            
                            rel_path = os.path.relpath(file_path, self.workspace_root)
                            
                            for i, line in enumerate(lines):
                                match = False
                                if is_regexp:
                                    try:
                                        if re.search(query, line):
                                            match = True
                                    except:
                                        # Invalid regex
                                        pass
                                else:
                                    if query in line:
                                        match = True
                                
                                if match:
                                    results.append(f"{rel_path}:{i+1}: {line.strip()}")
                        except:
                            # Skip files we can't read
                            pass
                
                if results:
                    return "\n".join(results[:20])  # Limit to 20 results
                else:
                    return f"No matches found for '{query}'"
                    
            except Exception as e:
                return f"Error during grep search: {str(e)}"
        
        def get_errors(file_paths: list) -> str:
            """
            Get any compile or lint errors in code files.
            
            Args:
                file_paths (list): List of files to check for errors
                
            Returns:
                str: Error messages if any
            """
            # This is a stub implementation
            # In a real implementation, you would run linters or compilers
            
            return "No errors found in the specified files.\n\n" + \
                   "Note: This is a simulated response. For actual error checking, implement integration with linters or compilers."
        
        # Register code analysis tools
        self.register_function(file_search)
        self.register_function(grep_search)
        self.register_function(get_errors)

    async def process_tool_calls(self, tool_calls: list, llm_client) -> list:
        """
        Process tool calls from the model response.

        Args:
            tool_calls (list): List of tool calls from the model.
            llm_client: The LLMClient instance to add messages to.

        Returns:
            list: List of (tool_name, tool_output) pairs.
        """
        results = []
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            function = self.available_functions.get(function_name)
            
            if function:
                try:
                    args = tool_call['function']['arguments']
                    # Convert string args to dict if needed
                    if isinstance(args, str):
                        args = json.loads(args)
                    
                    print(f"Calling function: {function_name}")
                    print(f"Arguments: {args}")
                    
                    # Check if the function is async
                    import inspect
                    if inspect.iscoroutinefunction(function):
                        output = await function(**args)
                    else:
                        output = function(**args)
                    
                    # For read_file, don't print the entire output to terminal
                    if function_name == "read_file":
                        target_file = args.get("target_file", "")
                        start_line = args.get("start_line", 1)
                        end_line = args.get("end_line", None)
                        if end_line:
                            line_count = end_line - start_line + 1
                        else:
                            # Estimate line count from output
                            line_count = output.count('\n') + 1
                        print(f"Function output: Read {line_count} lines from {target_file}")
                    else:
                        print(f"Function output: {output}")
                    
                    llm_client.add_message("tool", str(output), name=function_name)
                    results.append((function_name, str(output)))
                except Exception as e:
                    error_message = f"Error executing {function_name}: {str(e)}"
                    print(error_message)
                    llm_client.add_message("tool", error_message, name=function_name)
                    results.append((function_name, error_message))
            else:
                error_message = f"Function {function_name} not found"
                print(error_message)
                llm_client.add_message("tool", error_message, name=function_name)
                results.append((function_name, error_message))
        return results 