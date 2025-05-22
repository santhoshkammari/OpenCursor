import asyncio
from code_agent.src.agent import CodeAgent


async def demo():
    """Example usage of the CodeAgent."""
    # Create the agent
    agent = CodeAgent()

    # Test with a file operation
    print("\n=== Testing file operation ===")
    response = await agent("Create a simple Python file that prints 'Hello World'")
    print("Final response:", response)

    # Test with a directory listing
    print("\n=== Testing directory listing ===")
    response = await agent("List the files in the current directory")
    print("Final response:", response)

    # Test reading a file
    print("\n=== Testing file read ===")
    response = await agent("Read the contents of the file 'hello.py'")
    print("Final response:", response)

    # Test editing a file
    print("\n=== Testing file edit ===")
    response = await agent("Edit the file 'hello.py' to print 'Hello, CodeAgent!'")
    print("Final response:", response)

    # Test searching for text in files
    print("\n=== Testing file search ===")
    response = await agent("Search for the text 'Hello' in all files")
    print("Final response:", response)

    # Test deleting a file
    print("\n=== Testing file delete ===")
    response = await agent("Delete the file 'hello.py'")
    print("Final response:", response)

    # Test running a terminal command
    print("\n=== Testing terminal command ===")
    response = await agent("Run the command 'echo Terminal test' in the terminal")
    print("Final response:", response)

    # Test math tools
    print("\n=== Testing math add ===")
    response = await agent("Add 7 and 5")
    print("Final response:", response)
    print("\n=== Testing math subtract ===")
    response = await agent("Subtract 3 from 10")
    print("Final response:", response)

    # Test semantic search
    print("\n=== Testing semantic search ===")
    response = await agent("Find code related to 'asyncio' usage")
    print("Final response:", response)

    # Test code usage search
    print("\n=== Testing code usage search ===")
    response = await agent("Find usages of the symbol 'CodeAgent'")
    print("Final response:", response)

    # Test web search
    print("\n=== Testing web search ===")
    response = await agent("Search the web for 'Python asyncio tutorial'")
    print("Final response:", response)

    # Test fetch webpage
    print("\n=== Testing fetch webpage ===")
    response = await agent("Fetch the webpage content from 'https://www.python.org/'")
    print("Final response:", response)

    # Test file search by name
    print("\n=== Testing file search by name ===")
    response = await agent("Find files with 'app' in the name")
    print("Final response:", response)

    # Test grep search
    print("\n=== Testing grep search ===")
    response = await agent("Find all lines containing 'import' in Python files")
    print("Final response:", response)

    # Test get errors (simulated)
    print("\n=== Testing get errors ===")
    response = await agent("Check for errors in the file 'app.py'")
    print("Final response:", response)


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\nGoodbye!")
