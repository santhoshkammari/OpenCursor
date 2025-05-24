from code_agent.src.agent import CodeAgent


# def edit_file(target_file: str, code_edit: str, instructions: str = "") -> str:

def test_edit_tool():
    agent = CodeAgent()
    agent.register_tools()
    args = {
        "target_file": "test_edit.py",
        "code_edit": """// ... existing code ...
def multiply(a, b):
    '''Multiply two numbers and return the result.

    Args:
        a (int or float): The first number.
        b (int or float): The second number.

    Returns:
        int or float: The product of a and b.
    '''
    return a * b""",
        "instructions": "Add a print statement to the file"
    }
    result = agent.tools_manager.available_functions['edit_file'](**args)
    print(result)


if __name__ == "__main__":
    test_edit_tool()
