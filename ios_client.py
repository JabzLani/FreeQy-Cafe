# iOS Monitoring Client (Pythonista compatible)
import json
import platform
import time
import requests
from datetime import datetime

class IOSMonitor:
    def __init__(self, server_url):
        self.server_url = server_url
        self.client_id = self.get_device_id()
        self.session = requests.Session()
        
    def get_device_id(self):
        """Get unique device identifier for iOS"""
        import uuid
        return str(uuid.getnode())
    
    def get_device_info(self):
        """Get iOS device information"""
        return {
            'platform': 'ios',
            'hostname': platform.node(),
            'os_version': platform.release(),
            'model': platform.machine()
        }
    
    def get_basic_resources(self):
        """Get basic resource info (iOS has limited access)"""
        import memory
        try:
            mem_info = memory.memory_info()
            memory_percent = (mem_info.used / mem_info.total) * 100
        except:
            memory_percent = 0
        
        return {
            'cpu_percent': 0,  # Not accessible on iOS
            'memory_percent': memory_percent,
            'battery_percent': self.get_battery_level(),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_battery_level(self):
        """Get battery level if available"""
        try:
            from objc_util import ObjCClass
            device = ObjCClass('UIDevice').currentDevice()
            device.setBatteryMonitoringEnabled_(True)
            level = device.batteryLevel()
            return int(level * 100)
        except:
            return 100
    
    def send_update(self):
        """Send update to server"""
        data = {
            'client_id': self.client_id,
            'device_info': self.get_device_info(),
            'resources': self.get_basic_resources()
        }
        
        try:
            response = self.session.post(
                f"{self.server_url}/api/v1/ios_update",
                json=data,
                timeout=10
            )
            return response.json()
        except Exception as e:
            print(f"Error sending update: {e}")
            return None
    
    def run(self):
        """Main monitoring loop"""
        print(f"iOS Monitor starting for device: {self.client_id}")
        
        # Register with server
        register_data = {
            'client_id': self.client_id,
            **self.get_device_info()
        }
        
        try:
            response = self.session.post(
                f"{self.server_url}/api/v1/register",
                json=register_data
            )
            print(f"Registration response: {response.json()}")
        except:
            print("Failed to register with server")
        
        # Monitoring loop
        while True:
            result = self.send_update()
            if result:
                print(f"Update sent: {datetime.now()}")
            
            time.sleep(30)  # Send updates every 30 seconds

if __name__ == '__main__':
    # Load configuration
    try:
        with open('ios_config.json', 'r') as f:
            config = json.load(f)
            server_url = config['server_url']
    except:
        server_url = 'http://your-server-ip:8080'
    
    monitor = IOSMonitor(server_url)
    monitor.run()