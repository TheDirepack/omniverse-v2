#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Starting Omniverse V2 Environment Setup..."

# 1. Backend Setup
echo "📦 Setting up Backend..."
cd "$BASE_DIR/backend"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing backend dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 2. Frontend Setup
echo "📦 Setting up Frontend..."
cd "$BASE_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# 3. Environment Configuration
echo "⚙️ Configuring environment..."
cd "$BASE_DIR/backend"
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local template..."
    cat <<EOF > .env.local
GEMINI_API_KEY=your_key_here
DATABASE_URL=omniverse.db
PORT=8000
EOF
    echo "⚠️  PLEASE EDIT backend/.env.local and add your GEMINI_API_KEY"
else
    echo ".env.local already exists."
fi

echo "✅ Setup complete!"
echo "Run './run.sh' to start the application."
