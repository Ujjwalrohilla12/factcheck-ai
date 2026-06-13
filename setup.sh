#!/bin/bash

# FactCheck AI Setup Script
# This script automates the setup process for local development

set -e

echo "🚀 FactCheck AI Setup"
echo "===================="
echo ""

# Check Python version
echo "✓ Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "  Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "✓ Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "✓ Upgrading pip..."
pip install --upgrade pip > /dev/null

# Install dependencies
echo "✓ Installing dependencies..."
pip install -r requirements.txt > /dev/null

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "✓ Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys:"
    echo "   - OPENAI_API_KEY"
    echo "   - TAVILY_API_KEY"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. Run: streamlit run app.py"
echo "3. Open http://localhost:8501 in your browser"
echo ""
