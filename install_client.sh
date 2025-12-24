#!/bin/bash
# Installation script for Raspberry Pi client

echo "Installing Internet Cafe Monitoring Client..."

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv lm-sensors

# Install Python packages
pip3 install --upgrade pip
pip3 install psutil python-socketio requests

# Create systemd service
sudo tee /etc/systemd/system/cafe-monitor.service > /dev/null << EOF
[Unit]
Description=Internet Cafe Monitoring Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/pi_client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable cafe-monitor
sudo systemctl start cafe-monitor

echo "Client installation complete!"
echo "Edit /home/pi/pi_client.py to set your server IP address"