#!/usr/bin/env python3
import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import the code_agent package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from code_agent.src.agent import CodeAgent

async def main():
    """Test the autonomous agent mode"""
    print("Testing OpenCursor Autonomous Agent Mode")
    print("---------------------------------------")
    
    # Create the agent
    agent = CodeAgent()
    
    # Example tasks to test
    tasks = [
        "Create a simple Python function that calculates the factorial of a number and save it to a file called factorial.py",
        "Find all Python files in the current directory and count how many lines they have in total",
        "Create a simple web server using Flask that serves a 'Hello World' page",
    ]
    
    # Let the user choose a task or enter their own
    print("Choose a task to test or enter your own:")
    for i, task in enumerate(tasks):
        print(f"{i+1}. {task}")
    print("4. Enter your own task")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == "4":
        task = input("Enter your task: ")
    else:
        try:
            task_index = int(choice) - 1
            if 0 <= task_index < len(tasks):
                task = tasks[task_index]
            else:
                print("Invalid choice, using the first task")
                task = tasks[0]
        except ValueError:
            print("Invalid choice, using the first task")
            task = tasks[0]
    
    print(f"\nExecuting task: {task}\n")
    
    # Run the agent
    response = await agent(task)
    
    # Print the response
    print("\nAgent Response:")
    print("---------------")
    print(response)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...") 