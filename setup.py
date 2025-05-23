#!/usr/bin/env python3
from setuptools import setup

# This file is only needed for pip installation compatibility
# The actual package configuration is in pyproject.toml

setup(
    name="opencursor",
    version="0.1.0",
    packages=["code_agent", "code_agent.src"],
    entry_points={
        "console_scripts": [
            "opencursor=code_agent.cli:main",
        ],
    },
) 