#!/bin/bash
# Quick Test Setup Script for User Authentication Tests

echo "=============================================="
echo "AI Roosters - User Authentication Test Setup"
echo "=============================================="

# Ensure we're in the right directory
if [ ! -d "Testing" ]; then
    echo "Error: Testing directory not found. Please run from project root."
    exit 1
fi

# Create test directory structure
echo "Creating User test directory structure..."
mkdir -p Testing/User/unit
mkdir -p Testing/User/behavioral

# Create __init__.py files
echo "Creating Python package files..."
touch Testing/User/__init__.py
touch Testing/User/unit/__init__.py
touch Testing/User/behavioral/__init__.py

echo "Test directory structure created at Testing/User/"
echo ""
echo "Structure:"
echo "Testing/User/"
echo "├── conftest.py"
echo "├── pytest.ini"
echo "├── test_requirements.txt"
echo "├── unit/"
echo "│   ├── test_security.py"
echo "│   └── test_user_model.py"
echo "└── behavioral/"
echo "    └── test_auth_endpoints.py"
echo ""

# Check if in Testing/User directory
if [ -f "test_requirements.txt" ]; then
    echo "Installing test dependencies..."
    pip install -r test_requirements.txt
    echo ""
fi

echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
echo "To run tests:"
echo "  cd Testing/User"
echo "  pytest                     # Run all User tests"
echo "  pytest -v                  # Verbose output"
echo "  pytest --cov=app           # With coverage"
echo "  pytest unit/               # Only unit tests"
echo "  pytest behavioral/         # Only behavioral tests"
echo ""
echo "For more info, see Testing/User/README.md"
echo ""
