#!/usr/bin/env python3
import asyncio
from rich.console import Console
from rich.theme import Theme
from rich.style import Style as RichStyle

from code_agent.src.app import main

# Custom orange theme color
ORANGE_COLOR = "#FF8C69"

def entry_point():
    """Non-async entry point for the package that runs the async main function"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        custom_theme = Theme({"orange": RichStyle(color=ORANGE_COLOR)})
        Console(theme=custom_theme).print(f"\n[orange bold]Goodbye![/orange bold]")

if __name__ == "__main__":
    entry_point() 