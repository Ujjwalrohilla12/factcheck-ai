@echo off
REM FactCheck AI Setup Script for Windows

echo ==============================
echo FactCheck AI Setup
echo ==============================
echo.

REM Check Python
echo Checking Python installation...
python --version
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip > nul

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt > nul

REM Check if .env exists
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo.
    echo Warning: Please edit .env and add your API keys:
    echo   - OPENAI_API_KEY
    echo   - TAVILY_API_KEY
)

echo.
echo ==============================
echo Setup complete!
echo.
echo Next steps:
echo 1. Edit .env and add your API keys
echo 2. Run: streamlit run app.py
echo 3. Open http://localhost:8501 in your browser
echo.
pause
