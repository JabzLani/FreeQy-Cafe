#!/bin/bash
# Installation script for Internet Cafe Monitoring System

echo "Setting up Internet Cafe Monitoring System..."

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv sqlite3

# Create directories
mkdir -p logs
mkdir -p static/js
mkdir -p templates

# Setup Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
python3 -c "from monitoring_server import init_database; init_database()"

echo "Setup complete!"
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  python3 monitoring_server.py"
echo ""
echo "To configure Raspberry Pi clients:"
echo " 1. Copy pi_client.py to each Raspberry Pi"
echo " 2. Update server URL in pi_client.py"
echo " 3. Run: python3 pi_client.py"