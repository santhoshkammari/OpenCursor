from difflib import unified_diff
import os
from code_agent.src.agent import CodeAgent


# def edit_file(target_file: str, code_edit: str, instructions: str = "") -> str:


def edit_file(target_file: str, code_edit: str, instructions: str = "") -> str:
            """
            Edit a file with the specified code changes.
            
            This will be read by a less intelligent model, which will quickly apply the edit. You should make it clear what the edit is, while also minimizing the unchanged code you write.
            When writing the edit, you should specify each edit in sequence, with the special comment // ... existing code ... to represent unchanged code in between edited lines.
            
            You should still bias towards repeating as few lines of the original file as possible to convey the change.
            But, each edit should contain sufficient context of unchanged lines around the code you're editing to resolve ambiguity.
            DO NOT omit spans of pre-existing code (or comments) without using the // ... existing code ... comment to indicate its absence. If you omit the existing code comment, the model may inadvertently delete these lines.
            
            Args:
                target_file (str): Path to the file to edit
                code_edit (str): The code edits to apply
                instructions (str): Instructions for applying the edit
                
            Returns:
                str: Result of the operation
            """
            file_path = "/home/ntlpt59/MAIN/Personal/OpenCursor/test_edit.py"

            ## print params nicely in table format using rich
            from rich.console import Console
            console = Console()
            console.print(f"[cyan]Target File:[/cyan] {target_file}")
            console.print(f"[cyan]Code Edit:[/cyan] {code_edit}")
            console.print(f"[cyan]Instructions:[/cyan] {instructions}")
            print('************')
            print('************')
            print('************')
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Check if file exists
                file_exists = os.path.isfile(file_path)
                
                
                if file_exists:
                    # Read existing content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                    
                    # Determine the appropriate comment marker based on file extension
                    ext = os.path.splitext(target_file)[1].lower()
                    comment_marker = "// ... existing code ..."  # Default for most languages
                    
                    # Adjust comment marker based on file extension
                    if ext in ['.py', '.sh', '.bash', '.rb']:
                        comment_marker = "# ... existing code ..."
                    elif ext in ['.html', '.xml']:
                        comment_marker = "<!-- ... existing code ... -->"
                    elif ext in ['.lua', '.hs']:
                        comment_marker = "-- ... existing code ..."
                    
                    # Import sentence-transformers for embeddings
                    from sentence_transformers import SentenceTransformer
                    
                    # Load the embedding model
                    model = SentenceTransformer('all-MiniLM-L6-v2',trust_remote_code=True)
                    
                    # Split existing content into lines for embedding
                    existing_lines = existing_content.splitlines()
                    
                    # Generate embeddings for each line of the existing content
                    existing_embeddings = model.encode(existing_lines)
                    
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
                            anchor_embedding = model.encode([anchor_line])[0]
                            
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
                            last_embedding = model.encode([last_line])[0]
                            
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
                
                action = "Updated" if file_exists else "Created"
                result = f"{action} file: {target_file}\nInstructions applied: {instructions}"
                
                return result
                
            except Exception as e:
                return f"Error editing file: {str(e)}"
            
def test_edit_tool():
    agent = CodeAgent()
    agent.register_tools()
    args = {
        "target_file": "test_edit.py",
        "code_edit": """# ... existing code ...
def multiply(a, b):
    """Multiply two numbers and return the result."""
    return a * b
        "instructions": "Add a print statement to the file"
    }
    print(agent.tools_manager.available_functions.keys())
    result =edit_file(**args)
    print(result)


if __name__ == "__main__":
    test_edit_tool()