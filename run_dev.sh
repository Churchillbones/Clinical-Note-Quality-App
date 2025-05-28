#!/bin/bash

# Development runner script

echo "Starting Clinical Note Quality Assessment in development mode..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Please copy .env.example to .env and configure your Azure OpenAI credentials."
    echo "cp .env.example .env"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Run Flask in development mode
export FLASK_ENV=development
export FLASK_DEBUG=True

echo "Starting Flask application on http://localhost:5000"
python app.py 