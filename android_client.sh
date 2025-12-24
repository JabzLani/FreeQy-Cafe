#!/data/data/com.termux/files/usr/bin/bash
# Android client setup for Termux

echo "Setting up Android monitoring client..."

# Update packages
pkg update -y
pkg upgrade -y

# Install Python and dependencies
pkg install -y python python-pip
pip install --upgrade pip

# Install required Python packages
pip install psutil python-socketio requests

# Create client directory
mkdir -p ~/.cafe_monitor
cd ~/.cafe_monitor

# Download client script
curl -O https://your-server.com/clients/android_client.py

# Create configuration
cat > config.json << EOF
{
    "server_url": "http://your-server-ip:8080",
    "client_name": "Android-$(getprop ro.product.model)",
    "update_interval": 15,
    "log_level": "INFO"
}
EOF

# Create startup script
cat > start_monitor.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/.cafe_monitor
python android_client.py
EOF

chmod +x start_monitor.sh

echo "Android client setup complete!"
echo "To start: cd ~/.cafe_monitor && python android_client.py"