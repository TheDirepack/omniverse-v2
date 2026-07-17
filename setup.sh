#!/bin/bash
set -e

echo "🚀 Omniverse V2 Setup"
echo "====================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Create virtual environment if not exists
if [ ! -d "backend/.venv" ] && [ ! -d "backend/venv" ]; then
    echo "${CYAN}Creating Python virtual environment...${NC}"
    python3 -m venv backend/.venv
fi

echo "${CYAN}Activating virtual environment...${NC}"
source backend/.venv/bin/activate || source backend/venv/bin/activate

echo "${BLUE}Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -q -r requirements.txt
pip install -q -r requirements-dev.txt

echo "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Check .env.local
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local from example..."
    cp .env.example .env.local
else
    echo ".env.local already exists."
fi
echo ""

echo "${GREEN}✅ Setup complete!${NC}"
echo "Run './run.sh' to start the application."
