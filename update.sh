#!/bin/bash

# NavienRS485 Project Update Script
# This script updates the NavienRS485 wallpad controller components

PROJECT_NAME="NavienRS485"
MAIN_DIR="Navien485"

echo "=== $PROJECT_NAME Update Script ==="

# Check if we're in the correct directory
if [ ! -d "./$MAIN_DIR" ]; then
    echo "Error: $MAIN_DIR directory not found!"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Function to check if git repository exists
check_git_repo() {
    if [ ! -d ".git" ]; then
        echo "Warning: Not a git repository. Initializing..."
        git init
        git add .
        git commit -m "Initial commit for $PROJECT_NAME"
    fi
}

# Function to update dependencies
update_dependencies() {
    echo "Checking for Python dependencies..."
    if [ -f "requirements.txt" ]; then
        echo "Installing Python requirements..."
        pip install -r requirements.txt
    fi
    
    if [ -f "$MAIN_DIR/requirements.txt" ]; then
        echo "Installing $MAIN_DIR requirements..."
        pip install -r $MAIN_DIR/requirements.txt
    fi
}

# Function to validate config
validate_config() {
    echo "Validating configuration files..."
    if [ -f "$MAIN_DIR/config.json" ]; then
        python -m json.tool $MAIN_DIR/config.json > /dev/null
        if [ $? -eq 0 ]; then
            echo "✓ config.json is valid"
        else
            echo "✗ config.json has syntax errors"
            exit 1
        fi
    else
        echo "Warning: config.json not found in $MAIN_DIR/"
    fi
}

# Function to build Docker image if Dockerfile exists
build_docker() {
    if [ -f "$MAIN_DIR/Dockerfile" ]; then
        echo "Building Docker image..."
        docker build -t navien-rs485:latest $MAIN_DIR/
        if [ $? -eq 0 ]; then
            echo "✓ Docker image built successfully"
        else
            echo "✗ Docker build failed"
            exit 1
        fi
    fi
}

# Main execution
echo "Starting update process..."

check_git_repo
validate_config
update_dependencies
build_docker

echo ""
echo "=== Update Complete ==="
echo "NavienRS485 project has been updated successfully!"
echo ""
echo "Next steps:"
echo "1. Review configuration in $MAIN_DIR/config.json"
echo "2. Test the wallpad connection"
echo "3. Deploy to your Home Assistant setup"

