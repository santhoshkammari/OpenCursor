# OpenCursor

OpenCursor is an AI coding assistant with a Gradio web interface.

## Features

- Chat with an AI coding agent in autonomous or interactive mode
- Direct LLM chat without tools
- File context management (add, drop, clear)
- Repository mapping
- Focus on specific files
- Workspace directory selection

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

To start the Gradio web interface:

```bash
python code_agent/src/gradio_ui.py
```

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