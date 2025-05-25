import asyncio
import os
import re
import json
import aiohttp
import subprocess
from typing import Callable, Dict, Any, Optional
from difflib import unified_diff
from rich.console import Console
from sentence_transformers import SentenceTransformer
from fuzzywuzzy import fuzz

from .llm import LLMClient
from .tool_playwright import register_playwright_search_tool
from .tool_browser import register_browser_search_tools
from liteauto.parselite import parse


class Tools:
    def __init__(self, workspace_root: str = None):
        """Initialize tools with the workspace root directory."""
        self.workspace_root = workspace_root or os.getcwd()
        self.available_functions = {}
        self.tools = []
        self.model = SentenceTransformer('all-MiniLM-L6-v2',trust_remote_code=True)

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
                        
                    # Convert result to string if it's not already a string
                    if isinstance(result,int):
                        result = str(result)
                    if isinstance(result, list):
                        result = "\n".join(result)
                        
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
        
        # Browser search tools
        register_playwright_search_tool(self)
        register_browser_search_tools(self)
        
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
        
        def read_file(target_file: str, start_line_one_indexed: int = 1, end_line_one_indexed_inclusive: int = None, should_read_entire_file: bool = False, explanation: str = "") -> str:
            """
            Read the contents of a file. The output of this tool call will be the 1-indexed file contents from start_line_one_indexed to end_line_one_indexed_inclusive, together with a summary of the lines outside start_line_one_indexed and end_line_one_indexed_inclusive.
            Note that this call can view at most 250 lines at a time and 200 lines minimum.
            
            Args:
                target_file (str): Path to the file to read
                start_line_one_indexed (int): The one-indexed line number to start reading from (inclusive)
                end_line_one_indexed_inclusive (int): The one-indexed line number to end reading at (inclusive)
                should_read_entire_file (bool): Whether to read the entire file
                explanation (str): One sentence explanation as to why this tool is being used
                
            Returns:
                str: The file contents
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if should_read_entire_file:
                        content = f.read()
                        return f"Requested to read the entire file.\nContents of {target_file}, lines 1-{content.count(os.linesep) + 1} (entire file):\n```\n{content}\n```"
                    
                    lines = f.readlines()
                
                # Apply start and end line indices (convert from 1-indexed to 0-indexed)
                start_idx = max(0, start_line_one_indexed - 1)
                if end_line_one_indexed_inclusive is None:
                    # If end line is not specified, limit to start + 250 lines or the end of file
                    end_idx = min(start_idx + 250, len(lines))
                else:
                    end_idx = min(end_line_one_indexed_inclusive - 1, len(lines) - 1)
                    # Enforce maximum of 250 lines
                    if end_idx - start_idx + 1 > 250:
                        end_idx = start_idx + 250 - 1
                
                # Ensure reading at least 200 lines if available
                if end_idx - start_idx + 1 < 200 and len(lines) >= 200:
                    end_idx = min(start_idx + 200 - 1, len(lines) - 1)
                
                # Include summary of lines outside the range
                result = []
                if start_idx > 0:
                    result.append(f"[Lines 1-{start_idx} omitted]")
                
                selected_content = ''.join(lines[start_idx:end_idx+1])
                
                # Display the range we're actually returning
                start_line = start_idx + 1  # Convert back to 1-indexed
                end_line = end_idx + 1      # Convert back to 1-indexed
                
                if len(lines) > end_idx + 1:
                    result.append(selected_content)
                    result.append(f"[Lines {end_line+1}-{len(lines)} omitted]")
                    return f"Requested to read lines {start_line_one_indexed}-{end_line_one_indexed_inclusive if end_line_one_indexed_inclusive is not None else ''}, but returning lines {start_line}-{end_line} to comply with line limits.\nContents of {target_file}, lines {start_line}-{end_line}:\n```\n{''.join(result)}\n```"
                else:
                    result.append(selected_content)
                    return f"Requested to read lines {start_line_one_indexed}-{end_line_one_indexed_inclusive if end_line_one_indexed_inclusive is not None else ''}, but returning lines {start_line}-{end_line} to give more context.\nContents of {target_file}, lines {start_line}-{end_line}:\n```\n{''.join(result)}\n```"
            except Exception as e:
                return f"Error reading file: {str(e)}"
        
        def python_edit_file(target_file: str, code_edit: str, instructions: str = "") -> str:
            """
            USE THIS TOOL FOR PYTHON FILES ONLY!
            
            Use this tool to propose an edit to an existing Python file or create a new Python file.
            This will be read by a less intelligent model which will quickly apply the edit. You should make it clear what the edit is, while also minimizing the unchanged code you write.
            When writing the edit, you should specify each edit in sequence, with the special comment # ... existing code ... to represent unchanged code in between edited lines.
            
            For example:
            # ... existing code ...
            FIRST_EDIT
            # ... existing code ...
            SECOND_EDIT
            # ... existing code ...
            THIRD_EDIT
            # ... existing code ...
            
            You should still bias towards repeating as few lines of the original file as possible to convey the change.
            But, each edit should contain sufficient context of unchanged lines around the code you're editing to resolve ambiguity.
            DO NOT omit spans of pre-existing code (or comments) without using the # ... existing code ... comment to indicate its absence. If you omit the existing code comment, the model may inadvertently delete these lines.
            Make sure it is clear what the edit should be, and where it should be applied.
            
            For non-Python files (like .md, .txt, .sh, etc.), use text_file_edit instead.
            
            You should specify the following arguments before the others: [target_file]
            """
            file_path = os.path.join(self.workspace_root, target_file) if not os.path.isabs(target_file) else target_file

            ## print params nicely in table format using rich
            console = Console()
            console.print(f"[cyan]{instructions} in {target_file}[/cyan]")
            
            # Show code edit in a styled panel with filename as title
            from rich.panel import Panel
            from rich.markdown import Markdown
            
            # Create markdown with syntax highlighting
            markdown = Markdown(f"```\n{code_edit}\n```")
            # Display in panel with filename as title
            console.print(Panel(markdown, title=f"[bold]{target_file}[/bold]", border_style="green"))
            


            
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
                    
                    # Determine the appropriate comment marker based on file extension
                    ext = os.path.splitext(target_file)[1].lower()
                    comment_marker = "// ... existing code ..."  # Default for most languages
                    
                    # Adjust comment marker based on file extension
                    if ext in ['.py', '.sh', '.bash', '.rb']:
                        comment_marker = "// ... existing code ..."
                    elif ext in ['.html', '.xml']:
                        comment_marker = "<!-- ... existing code ... -->"
                    elif ext in ['.lua', '.hs']:
                        comment_marker = "-- ... existing code ..."
                    

                    
                    # Split existing content into lines for embedding
                    existing_lines = existing_content.splitlines()
                    
                    # Generate embeddings for each line of the existing content
                    existing_embeddings = self.model.encode(existing_lines)
                    
                    # Split the code edit into segments based on the comment marker
                    edit_segments = code_edit.split(comment_marker)
                    
                    # Initialize the new content
                    new_content_lines = []
                    current_line_idx = 0
                    
                    # Process each segment
                    for i, segment in enumerate(edit_segments):
                        if i == 0 and segment.strip() == "":
                            # Skip empty first segment
                            continue
                            
                        # Clean the segment and split into lines
                        segment_lines = segment.strip().splitlines()
                        
                        if not segment_lines:
                            continue
                            
                        # Get the first line of the segment for matching
                        anchor_line = segment_lines[0].strip()
                        
                        if i > 0:  # Not the first segment, need to find insertion point
                            # Create embedding for anchor line
                            anchor_embedding = self.model.encode([anchor_line])[0]
                            
                            # Calculate similarity with all existing lines
                            import numpy as np
                            similarities = np.dot(existing_embeddings, anchor_embedding)
                            
                            # Find the best match after the current position
                            best_match_idx = -1
                            best_score = -1
                            
                            for idx in range(current_line_idx, len(existing_lines)):
                                if similarities[idx] > best_score:
                                    best_score = similarities[idx]
                                    best_match_idx = idx
                            
                            # If good match found, add lines up to that point
                            if best_match_idx > current_line_idx and best_score > 0.7:
                                new_content_lines.extend(existing_lines[current_line_idx:best_match_idx])
                                current_line_idx = best_match_idx
                        
                        # Add the segment lines to the output
                        new_content_lines.extend(segment_lines)
                        
                        # Update current line index by finding where segment ends in original
                        if len(segment_lines) > 0:
                            last_line = segment_lines[-1].strip()
                            last_embedding = self.model.encode([last_line])[0]
                            
                            # Calculate similarity for the last line
                            similarities = np.dot(existing_embeddings, last_embedding)
                            
                            # Find best match for the last line
                            best_idx = -1
                            best_score = -1
                            
                            for idx in range(current_line_idx, len(existing_lines)):
                                if similarities[idx] > best_score:
                                    best_score = similarities[idx]
                                    best_idx = idx
                            
                            if best_idx >= 0 and best_score > 0.7:
                                current_line_idx = best_idx + 1
                    
                    # Add any remaining lines from the original file
                    if current_line_idx < len(existing_lines):
                        new_content_lines.extend(existing_lines[current_line_idx:])
                    
                    # Join the lines back into content
                    new_content = '\n'.join(new_content_lines)
                        
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
                            # Format the diff with syntax highlighting using triple backticks
                            result += f"```diff\n{diff_text}\n```"
                
                return result
                
            except Exception as e:
                return f"Error editing file: {str(e)}"
        
        def list_dir(directory: str = ".",explanation:str="") -> str:
            """
            List the contents of a directory. The quick tool to use for discovery, before using more targeted tools like semantic search or file reading. 
            Useful to try to understand the file structure before diving deeper into specific files. 
            Can be used to explore the codebase
            
            Args:
                directory (str): Path to directory to list
                explanation (str): One sentence explanation as to why this tool is being used
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
        self.register_function(python_edit_file)
        self.register_function(list_dir)
        
        def file_search(query: str, explanation: str = "") -> str:
            """
            Fast file search based on fuzzy matching against file path. Use if you know part of the file path but don't know where it's located exactly. 
            Response will be capped to 10 results. Make your query more specific if need to filter results further.
            
            Args:
                query (str): Fuzzy filename to search for
                explanation (str): One sentence explanation as to why this tool is being used, and how it contributes to the goal
                
            Returns:
                str: Search results
            """
            try:
                from fuzzywuzzy import fuzz
            except ImportError:
                return "Error: fuzzywuzzy library is not installed. Please install it with 'pip install fuzzywuzzy python-Levenshtein'."
                
            results = []
            
            try:
                # Get all files in workspace
                all_files = []
                for root, dirs, files in os.walk(self.workspace_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, self.workspace_root)
                        all_files.append(rel_path)
                
                # Calculate fuzzy match scores
                scored_files = []
                for file_path in all_files:
                    # Use token_set_ratio for better partial matching regardless of word order
                    score = fuzz.token_set_ratio(query.lower(), file_path.lower())
                    # Boost score if the query appears as a substring
                    if query.lower() in file_path.lower():
                        score += 20
                    scored_files.append((file_path, score))
                
                # Sort by score in descending order
                scored_files.sort(key=lambda x: x[1], reverse=True)
                
                # Take top 10 results with a minimum score threshold
                results = [file for file, score in scored_files[:10] if score > 50]
                
                if results:
                    return "\n".join(results)
                else:
                    return f"No files found matching '{query}'"
            except Exception as e:
                return f"Error searching files: {str(e)}"
        
        def delete_file(target_file: str, explanation: str = "") -> str:
            """
            Deletes a file at the specified path. The operation will fail gracefully if:
            - The file doesn't exist
            - The operation is rejected for security reasons
            - The file cannot be deleted
            
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
                        # Format the diff with syntax highlighting using triple backticks
                        result += f"```diff\n{diff_text}\n```"
                
                return result
                
            except Exception as e:
                return f"Error performing search and replace: {str(e)}"
        
        def text_file_edit(file: str, old_str: str, new_str: str, sudo: bool = False) -> str:
            """
            USE THIS TOOL FOR TEXT-BASED FILES ONLY (.md, .txt, .sh, .json, .yaml, etc.)!
            
            Replace specified string in a non-Python text file. Use for updating content in text-based files or fixing errors in non-Python code.
            
            Args:
                file (str): Path of the file to perform replacement on
                old_str (str): Original string to be replaced
                new_str (str): New string to replace with
                sudo (bool): Whether to use sudo privileges
                
            Returns:
                str: Result of the operation
            """
            file_path = os.path.join(self.workspace_root, file) if not os.path.isabs(file) else file
            
            try:
                # Check if file exists
                if not os.path.exists(file_path):
                    return f"Error: File {file} not found"
                
                # Check if file is a Python file (this tool is for non-Python files)
                if file_path.endswith('.py'):
                    return f"Error: This tool is intended for non-Python files like .md, .txt, .sh. For Python files, use python_edit_file instead."
                
                # Check file extension to ensure it's a text file
                allowed_extensions = ['.md', '.txt', '.sh', '.bash', '.json', '.yml', '.yaml', '.html', '.css', '.js', '.jsx', '.ts', '.tsx', '.xml', '.csv']
                if not any(file_path.endswith(ext) for ext in allowed_extensions) and '.' in os.path.basename(file_path):
                    return f"Warning: File {file} may not be a text file. Proceeding anyway, but be cautious."
                
                # Read the file content
                if sudo:
                    # Use sudo to read the file
                    read_cmd = ['sudo', 'cat', file_path]
                    read_result = subprocess.run(
                        read_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if read_result.returncode != 0:
                        return f"Error reading file with sudo: {read_result.stderr}"
                    
                    content = read_result.stdout
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # Check if the string exists in the file
                if old_str not in content:
                    return f"Error: String '{old_str}' not found in {file}"
                
                # Count occurrences
                occurrences = content.count(old_str)
                
                # Replace the string
                new_content = content.replace(old_str, new_str)
                
                # Write the modified content back to the file
                if sudo:
                    # Use a temporary file and sudo to write
                    temp_file = f"{file_path}.temp"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    # Move the temp file to the original with sudo
                    write_cmd = ['sudo', 'mv', temp_file, file_path]
                    write_result = subprocess.run(
                        write_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if write_result.returncode != 0:
                        return f"Error writing file with sudo: {write_result.stderr}"
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                
                # Show a diff of the changes
                diff = unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f'a/{file}',
                    tofile=f'b/{file}'
                )
                diff_text = ''.join(diff)
                
                result = f"Successfully replaced {occurrences} occurrence(s) of the specified string in {file}"
                
                if diff_text:
                    result += f"\n\n[Changes Made]\n```diff\n{diff_text}\n```"
                
                return result
                
            except Exception as e:
                return f"Error performing text file replacement: {str(e)}"
        
        # Register file operation tools
        self.register_function(read_file)
        self.register_function(list_dir)
        self.register_function(file_search)
        self.register_function(delete_file)
        self.register_function(search_replace)
        self.register_function(text_file_edit)

    def register_terminal_tools(self):
        """Register terminal command execution tools."""
        
        async def run_terminal_cmd(command: str, is_background: bool = False, require_user_approval: bool = True, explanation: str = "") -> str:
            """
            PROPOSE a command to run on behalf of the user.
            If you have this tool, note that you DO have the ability to run commands directly on the USER's system.
            Note that the user will have to approve the command before it is executed.
            The user may reject it if it is not to their liking, or may modify the command before approving it. If they do change it, take those changes into account.
            The actual command will NOT execute until the user approves it. The user may not approve it immediately. Do NOT assume the command has started running.
            If the step is WAITING for user approval, it has NOT started running.
            In using these tools, adhere to the following guidelines:
            1. Based on the contents of the conversation, you will be told if you are in the same shell as a previous step or a different shell.
            2. If in a new shell, you should cd to the appropriate directory and do necessary setup in addition to running the command.
            3. If in the same shell, the state will persist (eg. if you cd in one step, that cwd is persisted next time you invoke this tool).
            4. For ANY commands that would use a pager or require user interaction, you should append | cat to the command (or whatever is appropriate). Otherwise, the command will break. You MUST do this for: git, less, head, tail, more, etc.
            5. For commands that are long running/expected to run indefinitely until interruption, please run them in the background. To run jobs in the background, set is_background to true rather than changing the details of the command.
            6. Dont include any newlines in the command.
            
            Args:
                command (str): The terminal command to execute
                is_background (bool): Whether to run in background
                require_user_approval (bool): Whether the user must approve the command before it is executed. Only set this to false if the command is safe and if it matches the user's requirements for commands that should be executed automatically.
                explanation (str): One sentence explanation as to why this command needs to be run and how it contributes to the goal
                
            Returns:
                str: Command output
            """
            try:
                # If user approval is required, ask for confirmation
                if require_user_approval:
                    console = Console()
                    console.print(f"[yellow]Command to be executed:[/yellow] {command}")
                    if explanation:
                        console.print(f"[cyan]Reason:[/cyan] {explanation}")
                    
                    if is_background:
                        console.print("[cyan]This command will run in the background[/cyan]")
                    
                    confirmation = input("Do you approve this command? (y/n): ").strip().lower()
                    
                    if confirmation != 'y' and confirmation != 'yes':
                        return "Command execution cancelled by user"
                
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
                'description': 'PROPOSE a command to run on behalf of the user.\nIf you have this tool, note that you DO have the ability to run commands directly on the USER\'s system.\nNote that the user will have to approve the command before it is executed.\nThe user may reject it if it is not to their liking, or may modify the command before approving it. If they do change it, take those changes into account.\nThe actual command will NOT execute until the user approves it. The user may not approve it immediately. Do NOT assume the command has started running.\nIf the step is WAITING for user approval, it has NOT started running.\nIn using these tools, adhere to the following guidelines:\n1. Based on the contents of the conversation, you will be told if you are in the same shell as a previous step or a different shell.\n2. If in a new shell, you should cd to the appropriate directory and do necessary setup in addition to running the command.\n3. If in the same shell, the state will persist (eg. if you cd in one step, that cwd is persisted next time you invoke this tool).\n4. For ANY commands that would use a pager or require user interaction, you should append  | cat to the command (or whatever is appropriate). Otherwise, the command will break. You MUST do this for: git, less, head, tail, more, etc.\n5. For commands that are long running/expected to run indefinitely until interruption, please run them in the background. To run jobs in the background, set is_background to true rather than changing the details of the command.\n6. Dont include any newlines in the command.',
                'parameters': {
                    'type': 'object',
                    'required': ['command', 'is_background', 'require_user_approval'],
                    'properties': {
                        'command': {
                            'type': 'string',
                            'description': 'The terminal command to execute'
                        },
                        'is_background': {
                            'type': 'boolean',
                            'description': 'Whether the command should be run in the background'
                        },
                        'require_user_approval': {
                            'type': 'boolean',
                            'description': 'Whether the user must approve the command before it is executed. Only set this to false if the command is safe and if it matches the user\'s requirements for commands that should be executed automatically.'
                        },
                        'explanation': {
                            'type': 'string',
                            'description': 'One sentence explanation as to why this command needs to be run and how it contributes to the goal'
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
        
        async def fetch_webpage(urls: list, explanation: str = "") -> str:
            """
            Fetch contents from web pages.
            
            Args:
                urls (list): List of URLs to fetch content from , For single url have single element list
                explanation (str): Explanation for why the content is being fetched
                
            Returns:
                str: Formatted web page content
            """
            try:
                from liteauto.parselite import aparse
                results = await aparse(urls)
                
                # Format the results
                formatted_output = []
                if isinstance(results, list):
                    for result in results:
                        formatted_output.append(f"URL: {result.url}\n\nContent:\n{result.content[:2000]}...")
                        formatted_output.append("-" * 50)
                else:
                    formatted_output.append(f"URL: {results.url}\n\nContent:\n{results.content[:2000]}...")
                
                return "\n".join(formatted_output)
            except Exception as e:
                return f"Error fetching web page content: {str(e)}"
        
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
            Find snippets of code from the codebase most relevant to the search query.
            This is a semantic search tool, so the query should ask for something semantically matching what is needed.
            If it makes sense to only search in particular directories, please specify them in the target_directories field.
            Unless there is a clear reason to use your own search query, please just reuse the user's exact query with their wording.
            Their exact wording/phrasing can often be helpful for the semantic search query. Keeping the same exact question format can also be helpful.
            
            Args:
                query (str): The search query to find relevant code. You should reuse the user's exact query with their wording unless there is a clear reason not to.
                target_directories (list): Optional list of directories to search in (glob patterns for directories to search over)
                explanation (str): One sentence explanation as to why this tool is being used, and how it contributes to the goal.
                
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
                        # Format according to required code citation format: ```startLine:endLine:filepath
                        formatted_results.append(
                            f"```{result['start_line']}:{result['end_line']}:{result['path']}\n{result['snippet']}\n```\n"
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

        def diff_history(explanation: str = "") -> str:
            """
            Retrieve the history of recent changes made to files in the workspace. 
            This tool helps understand what modifications were made recently, providing information about which files were changed, when they were changed, and how many lines were added or removed.
            Use this tool when you need context about recent modifications to the codebase.
            
            Args:
                explanation (str): One sentence explanation as to why this tool is being used
                
            Returns:
                str: Recent change history
            """
            try:
                # Run git log with stat to get recent changes
                result = subprocess.run(
                    ['git', 'log', '--stat', '--pretty=format:%h - %an, %ar : %s', '-n', '10'],
                    cwd=self.workspace_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    # Try to determine if this is a git repository
                    git_check = subprocess.run(
                        ['git', 'rev-parse', '--is-inside-work-tree'],
                        cwd=self.workspace_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if git_check.returncode != 0:
                        return "The workspace is not a git repository. Cannot retrieve change history."
                    else:
                        return f"Error retrieving git history: {result.stderr}"
                
                if not result.stdout.strip():
                    return "No recent changes found in the git history."
                
                return f"Recent changes in the repository:\n\n{result.stdout}"
                
            except Exception as e:
                return f"Error retrieving change history: {str(e)}"

        def grep_search(query: str, include_pattern: str = None, exclude_pattern: str = None, case_sensitive: bool = False, explanation: str = "") -> str:
            """
            Fast text-based regex search that finds exact pattern matches within files or directories.
            
            This is best for finding exact text matches or regex patterns.
            More precise than semantic search for finding specific strings or patterns.
            This is preferred over semantic search when we know the exact symbol/function name/etc. to search in some set of directories/file types.
            
            Args:
                query (str): The regex pattern to search for
                include_pattern (str): Glob pattern for files to include (e.g. '*.ts' for TypeScript files)
                exclude_pattern (str): Glob pattern for files to exclude
                case_sensitive (bool): Whether the search should be case sensitive
                explanation (str): One sentence explanation as to why this tool is being used
                
            Returns:
                str: Search results
            """
            try:
                # Build the ripgrep command
                cmd = ['rg', '--line-number']
                
                # Add case sensitivity option
                if not case_sensitive:
                    cmd.append('--ignore-case')
                
                # Add include pattern if provided
                if include_pattern:
                    cmd.extend(['--glob', include_pattern])
                
                # Add exclude pattern if provided
                if exclude_pattern:
                    cmd.extend(['--glob', f'!{exclude_pattern}'])
                
                # Add max count to avoid overwhelming output
                cmd.extend(['--max-count', '50'])
                
                # Add the search pattern and path
                cmd.append(query)
                cmd.append(self.workspace_root)
                
                # Run the command
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0 and result.returncode != 1:  # rg returns 1 when no matches found
                    # Check if ripgrep is installed
                    check_rg = subprocess.run(
                        ['which', 'rg'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if check_rg.returncode != 0:
                        return "Error: ripgrep (rg) is not installed. Please install it to use this tool."
                    else:
                        return f"Error executing grep search: {result.stderr}"
                
                if not result.stdout.strip():
                    return f"No matches found for pattern: {query}"
                
                # Format the results
                relative_paths = []
                for line in result.stdout.splitlines():
                    parts = line.split(':', 2)
                    if len(parts) >= 2:
                        # Convert absolute path to relative path
                        abs_path = parts[0]
                        rel_path = os.path.relpath(abs_path, self.workspace_root)
                        line = f"{rel_path}:{parts[1]}" + (f":{parts[2]}" if len(parts) > 2 else "")
                    relative_paths.append(line)
                
                return f"Search results for pattern '{query}':\n\n" + "\n".join(relative_paths)
                
            except Exception as e:
                return f"Error performing grep search: {str(e)}"

        # Register the functions
        self.register_function(fetch_webpage)
        self.register_function(semantic_search)
        self.register_function(codebase_search)
        self.register_function(reapply)
        self.register_function(list_code_usages)
        self.register_function(diff_history)
        self.register_function(grep_search)