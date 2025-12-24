#!/usr/bin/env python3
"""
Universal Client Installation Script
Works on Windows, Linux, macOS
"""

import os
import sys
import platform
import subprocess
import json
from pathlib import Path

def detect_platform():
    """Detect current platform"""
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system == 'darwin':
        return 'macos'
    elif system == 'linux':
        # Check for Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                if 'raspberry pi' in f.read().lower():
                    return 'raspberry_pi'
        except:
            pass
        return 'linux'
    return 'unknown'

def install_dependencies():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    
    requirements = [
        'psutil>=5.9.0',
        'python-socketio>=5.0.0',
        'requests>=2.28.0'
    ]
    
    # Platform-specific requirements
    platform_name = detect_platform()
    
    if platform_name == 'windows':
        requirements.append('pywin32>=300')
    elif platform_name == 'macos':
        # macOS might need additional packages
        pass
    elif platform_name == 'raspberry_pi':
        requirements.append('RPi.GPIO')
    
    # Install packages
    for package in requirements:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")

def create_configuration():
    """Create client configuration file"""
    print("\nCreating configuration...")
    
    config = {
        "server_url": input("Enter monitoring server URL (e.g., http://192.168.1.100:8080): "),
        "client_name": platform.node(),
        "update_interval": 10,
        "log_level": "INFO"
    }
    
    config_path = Path('client_config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Configuration saved to {config_path}")

def setup_autostart():
    """Setup auto-start based on platform"""
    platform_name = detect_platform()
    
    print(f"\nSetting up auto-start for {platform_name}...")
    
    if platform_name == 'windows':
        # Windows Task Scheduler
        script_path = os.path.abspath('universal_client.py')
        task_name = "InternetCafeMonitor"
        
        command = f'''
        schtasks /create /tn "{task_name}" /tr "{sys.executable} {script_path}" /sc onlogon /rl highest /f
        '''
        
        try:
            subprocess.run(command, shell=True, check=True)
            print("✓ Created Windows Task Scheduler entry")
        except subprocess.CalledProcessError:
            print("✗ Failed to create auto-start entry")
    
    elif platform_name in ['linux', 'raspberry_pi']:
        # Systemd service for Linux
        service_content = f'''[Unit]
Description=Universal Monitoring Client
After=network.target

[Service]
Type=simple
User={os.getenv('USER')}
ExecStart={sys.executable} {os.path.abspath('universal_client.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''
        
        service_path = '/etc/systemd/system/universal-monitor.service'
        
        try:
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            subprocess.run(['sudo', 'systemctl', 'enable', 'universal-monitor'], check=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'universal-monitor'], check=True)
            
            print("✓ Created and started systemd service")
        except:
            print("✗ Failed to create systemd service (may need sudo)")
    
    elif platform_name == 'macos':
        # LaunchAgent for macOS
        agent_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.internetcafe.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{os.path.abspath('universal_client.py')}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
'''
        
        agent_path = os.path.expanduser('~/Library/LaunchAgents/com.internetcafe.monitor.plist')
        
        try:
            with open(agent_path, 'w') as f:
                f.write(agent_content)
            
            subprocess.run(['launchctl', 'load', agent_path], check=True)
            print("✓ Created LaunchAgent")
        except:
            print("✗ Failed to create LaunchAgent")

def main():
    """Main installation routine"""
    print("=" * 50)
    print("Universal Monitoring Client Installer")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        sys.exit(1)
    
    # Install dependencies
    install_dependencies()
    
    # Create configuration
    create_configuration()
    
    # Setup auto-start
    setup_choice = input("\nSetup auto-start? (y/n): ").lower()
    if setup_choice == 'y':
        setup_autostart()
    
    print("\n" + "=" * 50)
    print("Installation Complete!")
    print("\nTo start the client manually:")
    print(f"  {sys.executable} universal_client.py")
    print("\nTo edit configuration:")
    print("  Edit client_config.json")
    print("=" * 50)

if __name__ == '__main__':
    main()