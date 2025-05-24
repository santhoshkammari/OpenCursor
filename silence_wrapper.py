#!/usr/bin/env python3
"""
Wrapper script that redirects stdout/stderr temporarily to silence telemetry messages.
"""
import os
import sys
import subprocess

# Set environment variables to disable all telemetry and logging
os.environ["TELEMETRY_ENABLED"] = "0"
os.environ["SENTENCE_TRANSFORMERS_TELEMETRY"] = "0"
os.environ["BROWSER_USE_TELEMETRY"] = "0"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

# Save original stdout/stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Temporarily redirect stdout and stderr to /dev/null to capture the initialization output
null_fd = open(os.devnull, 'w')
sys.stdout = null_fd
sys.stderr = null_fd

try:
    # Import necessary modules
    import asyncio
    from code_agent.src.app import main
    
    # Restore original stdout/stderr
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    
    # Run the app with original command line arguments
    asyncio.run(main())
except Exception as e:
    # Restore original stdout/stderr in case of exception
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    print(f"Error: {e}")
finally:
    # Close the /dev/null file descriptor
    null_fd.close() 