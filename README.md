# OpenCursor

An AI-powered code agent for workspace operations.

## Features

- Chat with an AI coding agent in autonomous or interactive mode
- Direct LLM chat without tools
- File context management (add, drop, clear)
- Repository mapping
- Focus on specific files
- Workspace directory selection

## Installation

### Using Poetry (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/opencursor.git
cd opencursor

# Install with Poetry
poetry install
```

### Using pip

```bash
pip install git+https://github.com/yourusername/opencursor.git
```

## Usage

Once installed, you can use OpenCursor from the command line:

```bash
# Basic usage
opencursor -q "Create a simple Flask app"

# Specify a workspace directory
opencursor -w /path/to/workspace -q "Fix the bug in app.py"

# Use a different model
opencursor -m "gpt-4" -q "Refactor the authentication module"

# Run in interactive mode
opencursor -i -q "Create a React component"
```

### Command-line Options

- `-w, --workspace`: Path to the workspace directory (default: current directory)
- `-q, --query`: Query to process (required)
- `-m, --model`: LLM model to use (default: qwen3_14b_q6k:latest)
- `-H, --host`: Ollama API host URL (default: http://192.168.170.76:11434)
- `-i, --interactive`: Run in interactive mode (one tool call at a time)

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/opencursor.git
cd opencursor

# Install dependencies
poetry install

# Run tests
poetry run pytest
```

### Project Structure

```
opencursor/
├── code_agent/
│   ├── src/
│   │   ├── agent.py      # Main agent implementation
│   │   ├── llm.py        # LLM client
│   │   ├── prompts.py    # System prompts
│   │   ├── tools.py      # Tool implementations
│   │   └── ...
│   ├── cli.py            # Command-line interface
│   └── __init__.py
├── tests/
├── pyproject.toml
└── README.md
```

## License

MIT

### UI Components

- **Chat History**: Shows the conversation between you and the AI
- **Message Input**: Type your messages here
- **Tool Selection**: Choose which tool to use for processing your message
- **Workspace Path**: Set the directory to work with
- **Context Information**: Shows which files are currently in context
- **Update Context**: Refreshes the context information
- **Clear Chat**: Clears the chat history

### Available Tools

- **agent (autonomous)**: Agent works step-by-step without user interaction
- **agent (interactive)**: Agent performs one tool call at a time, waiting for user input
- **chat (LLM only)**: Chat with the LLM directly without using tools
- **add file**: Add a file to the context (provide file path in message)
- **drop file**: Remove a file from the context (provide file path in message)
- **clear context**: Remove all files from the context
- **repo map**: Show the files in the current workspace
- **focus on file**: Add a file to context and show its contents

## Customization

You can modify the model and host settings in the `main()` function of `gradio_ui.py`.