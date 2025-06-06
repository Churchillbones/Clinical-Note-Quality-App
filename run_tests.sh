#!/bin/bash

# Test runner script

echo "Running Clinical Note Quality Assessment test suite..."

# Activate virtual environment
source venv/bin/activate

# Run tests with coverage
echo "Running pytest with coverage..."
pytest tests/ --cov=grading --cov-report=term-missing --cov-report=html -v

echo ""
echo "Test results:"
echo "- Coverage report: htmlcov/index.html"
echo "- Detailed results above" 