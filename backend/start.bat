@echo off
chcp 65001 >nul
echo 🚀 Starting Integration Server...

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

echo 📦 Installing dependencies...
pip install -r requirements.txt

if not exist .env (
    echo ⚠️  .env file not found! Copying from .env.example...
    copy .env.example .env
    echo 📝 Please edit .env file and add your API keys before restarting.
    pause
    exit /b 1
)

echo 🗄️  Initializing database...
python -c "import asyncio; from database import init_db; asyncio.run(init_db())"

echo ✅ Starting server on http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
