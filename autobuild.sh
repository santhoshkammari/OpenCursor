#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting automated build and publish process...${NC}"

# Update version (requires python and toml)
echo -e "\n${GREEN}1. Updating version...${NC}"
python3 - << EOF
import toml

# Read the file
with open('pyproject.toml', 'r') as f:
    content = toml.load(f)

# Update version
current = content['tool']['poetry']['version']
parts = current.split('.')
parts[-1] = str(int(parts[-1]) + 1)
new_version = '.'.join(parts)
content['tool']['poetry']['version'] = new_version

# Write back
with open('pyproject.toml', 'w') as f:
    toml.dump(content, f)

print(f"Version updated: {current} -> {new_version}")
EOF

# Build package
echo -e "\n${GREEN}2. Building package...${NC}"
poetry build

# Publish package
echo -e "\n${GREEN}3. Publishing package...${NC}"
poetry publish

# Wait for PyPI
echo -e "\n${GREEN}Waiting for PyPI to process the new version...${NC}"
sleep 2

# Update local installation
echo -e "\n${GREEN}4. Updating local installation...${NC}"
uv pip install -U opencursor

echo -e "\n${BLUE}Process completed successfully!${NC}"

echo -e "\n${GREEN}Waiting for PyPI to process the new version...${NC}"
sleep 2
# Update local installation
echo -e "\n${GREEN}4. Updating local installation...${NC}"
uv pip install -U opencursor

echo -e "\n${BLUE}Process completed successfully!${NC}"