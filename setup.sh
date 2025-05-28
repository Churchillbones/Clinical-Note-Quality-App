#!/bin/bash

# Clinical Note Quality Assessment Setup Script

echo "Setting up Clinical Note Quality Assessment application..."

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directory structure..."
mkdir -p grading
mkdir -p templates
mkdir -p tests

echo "Setup complete!"
echo ""
echo "To run the application:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Set environment variables (see .env.example)"
echo "3. Run the application: python app.py"
echo ""
echo "To run tests:"
echo "pytest tests/" 