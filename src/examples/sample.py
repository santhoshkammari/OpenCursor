import asyncio
from src.codeagent.agent import CodeAgent


async def demo():
    """Example usage of the CodeAgent."""
    # Create the agent
    agent = CodeAgent()

    # Test with a file operation
    print("\n=== Testing file operation ===")
    response = await agent("Create a simple Python file that prints 'Hello World'")
    print("Final response:", response)


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\nGoodbye!")
