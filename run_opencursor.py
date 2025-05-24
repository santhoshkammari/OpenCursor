#!/usr/bin/env python3
"""
A wrapper script that runs OpenCursor while suppressing telemetry and initialization logs.
This provides a clean terminal interface without any unwanted log messages.
"""
import os
import sys
import argparse
import asyncio

# Set environment variables to disable all telemetry and logging
os.environ["TELEMETRY_ENABLED"] = "0"
os.environ["SENTENCE_TRANSFORMERS_TELEMETRY"] = "0"
os.environ["BROWSER_USE_TELEMETRY"] = "0"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

def parse_args():
    """Parse command line arguments and return them in a format suitable for OpenCursor"""
    parser = argparse.ArgumentParser(description="OpenCursor - An AI-powered code assistant")
    parser.add_argument("-m", "--model", default="qwen3_14b_q6k:latest", help="Model name to use")
    parser.add_argument("--host", default="http://192.168.170.76:11434", help="Ollama host URL")
    parser.add_argument("-w", "--workspace", help="Path to workspace directory")
    parser.add_argument("-q", "--query", default=None, help="Initial query to process")
    return parser.parse_args()

def main():
    # Parse arguments
    args = parse_args()
    
    # Save original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Temporarily redirect stdout and stderr to /dev/null during initialization
    null_fd = open(os.devnull, 'w')
    sys.stdout = null_fd
    sys.stderr = null_fd

    try:
        # Import the app and code agent modules (after stdout is redirected)
        from code_agent.src.app import OpenCursorApp
        
        # Restore original stdout/stderr before running the app
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # Create and run the app with parsed arguments
        app = OpenCursorApp(
            model_name=args.model,
            host=args.host,
            workspace_path=args.workspace
        )
        asyncio.run(app.run(initial_query=args.query))
    except Exception as e:
        # Restore original stdout/stderr in case of exception
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print(f"Error: {e}")
    finally:
        # Close the /dev/null file descriptor
        null_fd.close()

if __name__ == "__main__":
    main() 