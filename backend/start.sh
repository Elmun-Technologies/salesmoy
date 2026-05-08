#!/bin/bash

# Sales Doctor ↔ MoySklad Integration Server Startup Script

echo "🚀 Starting Integration Server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found! Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file and add your API keys before restarting."
    exit 1
fi

# Initialize database
echo "🗄️  Initializing database..."
python -c "import asyncio; from database import init_db; asyncio.run(init_db())"

# Start server
echo "✅ Starting server on http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
