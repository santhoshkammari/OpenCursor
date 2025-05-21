# OpenCursor

A terminal-based code agent with a nice UI built using prompt_toolkit.

## Features

- Interactive terminal UI with prompt_toolkit
- Agent mode for code assistance with tools
- Chat mode for direct LLM interaction
- File context management (add/drop files)
- Repository mapping
- Command history

## Commands

- `/agent <message>` - Send a message to the agent (with tools)
- `/chat <message>` - Chat with the LLM directly (no tools)
- `/add <filepath>` - Add a file to the chat context
- `/drop <filepath>` - Remove a file from the chat context
- `/clear` - Clear all files from the chat context
- `/repomap` - Show a map of the repository
- `/focus <filepath>` - Focus on a specific file
- `/help` - Show help message
- `/exit` - Exit the application

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m code_agent.app
```

By default, OpenCursor uses the Ollama API with the qwen3_14b_q6k model. You can modify the model and host in the app.py file.