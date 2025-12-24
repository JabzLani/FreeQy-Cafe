#!/usr/bin/env python3
"""
Universal Cross-Platform Monitoring Client
Works on Windows, Linux, macOS, iOS (via Pythonista), and Raspberry Pi
"""

import asyncio
import json
import logging
import os
import platform
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import socket
import subprocess

# Platform-specific imports with fallbacks
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Install with: pip install psutil")

try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    print("Warning: socketio not available. Install with: pip install python-socketio")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlatformDetector:
    """Detect and handle platform-specific features"""
    
    @staticmethod
    def detect_platform() -> str:
        """Detect current platform"""
        system = platform.system().lower()
        
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'macos'
        elif system == 'linux':
            # Check if Raspberry Pi
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    if 'raspberry pi' in f.read().lower():
                        return 'raspberry_pi'
            except:
                pass
            
            # Check for Android
            if 'android' in platform.platform().lower():
                return 'android'
            
            return 'linux'
        else:
            return 'unknown'
    
    @staticmethod
    def get_mac_address() -> str:
        """Get MAC address"""
        try:
            if platform.system() == 'Windows':
                output = subprocess.check_output('getmac', shell=True).decode()
                for line in output.split('\n'):
                    if 'Device' not in line and len(line.strip()) > 0:
                        return line.split()[0]
            else:
                import uuid
                return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                               for elements in range(0, 8*6, 8)][::-1])
        except:
            pass
        return '00:00:00:00:00:00'
    
    @staticmethod
    def get_unique_id() -> str:
        """Generate a unique client ID"""
        # Try to use MAC address
        mac = PlatformDetector.get_mac_address()
        if mac != '00:00:00:00:00:00':
            return hashlib.md5(mac.encode()).hexdigest()
        
        # Fallback to hostname + platform
        hostname = socket.gethostname()
        platform_name = PlatformDetector.detect_platform()
        return hashlib.md5(f"{hostname}_{platform_name}".encode()).hexdigest()

class ResourceMonitor:
    """Monitor system resources across platforms"""
    
    def __init__(self):
        self.platform = PlatformDetector.detect_platform()
        self.last_net_io = None
        
    def get_cpu_usage(self) -> float:
        """Get CPU usage percentage"""
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            return psutil.cpu_percent(interval=1)
        except:
            return 0.0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage"""
        if not PSUTIL_AVAILABLE:
            return {'percent': 0.0, 'total_mb': 0, 'available_mb': 0}
        
        try:
            memory = psutil.virtual_memory()
            return {
                'percent': memory.percent,
                'total_mb': memory.total // (1024 * 1024),
                'available_mb': memory.available // (1024 * 1024),
                'used_mb': memory.used // (1024 * 1024)
            }
        except:
            return {'percent': 0.0, 'total_mb': 0, 'available_mb': 0}
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage"""
        if not PSUTIL_AVAILABLE:
            return {'percent': 0.0, 'total_gb': 0, 'free_gb': 0}
        
        try:
            disk = psutil.disk_usage('/')
            return {
                'percent': disk.percent,
                'total_gb': disk.total // (1024**3),
                'free_gb': disk.free // (1024**3),
                'used_gb': disk.used // (1024**3)
            }
        except:
            return {'percent': 0.0, 'total_gb': 0, 'free_gb': 0}
    
    def get_network_usage(self) -> Dict[str, float]:
        """Get network usage in Mbps"""
        if not PSUTIL_AVAILABLE:
            return {'rx_mbps': 0.0, 'tx_mbps': 0.0}
        
        try:
            net_io = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_net_io:
                time_diff = current_time - self.last_net_io['time']
                bytes_rx = net_io.bytes_recv - self.last_net_io['bytes_recv']
                bytes_tx = net_io.bytes_sent - self.last_net_io['bytes_sent']
                
                rx_mbps = (bytes_rx * 8) / (time_diff * 1_000_000)  # Convert to Mbps
                tx_mbps = (bytes_tx * 8) / (time_diff * 1_000_000)  # Convert to Mbps
            else:
                rx_mbps = tx_mbps = 0.0
            
            self.last_net_io = {
                'bytes_recv': net_io.bytes_recv,
                'bytes_sent': net_io.bytes_sent,
                'time': current_time
            }
            
            return {'rx_mbps': rx_mbps, 'tx_mbps': tx_mbps}
        except:
            return {'rx_mbps': 0.0, 'tx_mbps': 0.0}
    
    def get_gpu_usage(self) -> Optional[float]:
        """Get GPU usage if available"""
        if self.platform == 'windows':
            # Try to get NVIDIA GPU usage
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                pynvml.nvmlShutdown()
                return util.gpu
            except:
                pass
        
        elif self.platform in ['linux', 'raspberry_pi']:
            # Try to get GPU usage from various sources
            try:
                # For NVIDIA on Linux
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return float(result.stdout.strip())
            except:
                pass
        
        return None
    
    def get_temperature(self) -> Optional[float]:
        """Get system temperature if available"""
        if self.platform == 'raspberry_pi':
            try:
                # Raspberry Pi temperature
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000.0
                return temp
            except:
                pass
        
        elif self.platform == 'linux':
            try:
                # Try to get temperature from sensors
                result = subprocess.run(['sensors'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse output for temperature
                    for line in result.stdout.split('\n'):
                        if 'Core' in line and '°C' in line:
                            try:
                                temp_str = line.split('+')[1].split('°C')[0]
                                return float(temp_str)
                            except:
                                pass
            except:
                pass
        
        return None
    
    def get_battery_info(self) -> Dict[str, Any]:
        """Get battery information"""
        if not PSUTIL_AVAILABLE:
            return {'percent': 100, 'plugged': True}
        
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {
                    'percent': battery.percent,
                    'plugged': battery.power_plugged,
                    'time_left': battery.secsleft if battery.secsleft != -1 else None
                }
        except:
            pass
        
        return {'percent': 100, 'plugged': True}
    
    def get_running_processes(self) -> List[Dict[str, Any]]:
        """Get list of running processes"""
        if not PSUTIL_AVAILABLE:
            return []
        
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'user': info['username'],
                        'cpu': info['cpu_percent'],
                        'memory': info['memory_percent']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except:
            pass
        
        # Sort by CPU usage and limit to top 10
        processes.sort(key=lambda x: x.get('cpu', 0), reverse=True)
        return processes[:10]
    
    def get_all_resources(self) -> Dict[str, Any]:
        """Get all resource information"""
        memory = self.get_memory_usage()
        disk = self.get_disk_usage()
        network = self.get_network_usage()
        battery = self.get_battery_info()
        
        resources = {
            'cpu_percent': self.get_cpu_usage(),
            'memory_percent': memory.get('percent', 0),
            'memory_total_mb': memory.get('total_mb', 0),
            'memory_used_mb': memory.get('used_mb', 0),
            'disk_percent': disk.get('percent', 0),
            'disk_total_gb': disk.get('total_gb', 0),
            'disk_free_gb': disk.get('free_gb', 0),
            'network_rx_mbps': network.get('rx_mbps', 0),
            'network_tx_mbps': network.get('tx_mbps', 0),
            'battery_percent': battery.get('percent', 100),
            'battery_plugged': battery.get('plugged', True),
            'processes_count': len(self.get_running_processes()),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add GPU usage if available
        gpu_usage = self.get_gpu_usage()
        if gpu_usage is not None:
            resources['gpu_usage'] = gpu_usage
        
        # Add temperature if available
        temperature = self.get_temperature()
        if temperature is not None:
            resources['temperature'] = temperature
        
        return resources

class ApplicationTracker:
    """Track application usage"""
    
    def __init__(self):
        self.active_apps = {}
        self.app_history = []
        
    def track_application(self, app_name: str, app_path: str = ''):
        """Track when an application is active"""
        current_time = datetime.now()
        
        if app_name not in self.active_apps:
            # New application started
            self.active_apps[app_name] = {
                'path': app_path,
                'start_time': current_time,
                'last_active': current_time
            }
        else:
            # Update last active time
            self.active_apps[app_name]['last_active'] = current_time
        
        # Clean up inactive apps (not active for 5 minutes)
        inactive_apps = []
        for name, info in self.active_apps.items():
            if (current_time - info['last_active']).total_seconds() > 300:
                inactive_apps.append(name)
        
        for name in inactive_apps:
            self._log_application_usage(name)
    
    def _log_application_usage(self, app_name: str):
        """Log application usage duration"""
        if app_name in self.active_apps:
            app_info = self.active_apps[app_name]
            duration = (app_info['last_active'] - app_info['start_time']).total_seconds()
            
            self.app_history.append({
                'name': app_name,
                'path': app_info['path'],
                'start_time': app_info['start_time'].isoformat(),
                'end_time': app_info['last_active'].isoformat(),
                'duration': duration
            })
            
            del self.active_apps[app_name]
    
    def get_active_applications(self) -> List[Dict[str, Any]]:
        """Get currently active applications"""
        current_time = datetime.now()
        active_apps = []
        
        for name, info in self.active_apps.items():
            active_apps.append({
                'name': name,
                'path': info['path'],
                'start_time': info['start_time'].isoformat(),
                'duration': (current_time - info['start_time']).total_seconds()
            })
        
        return active_apps
    
    def get_application_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent application usage history"""
        return self.app_history[-limit:]

class UniversalMonitoringClient:
    """Main client class for cross-platform monitoring"""
    
    def __init__(self, server_url: str = 'http://localhost:8080'):
        if not SOCKETIO_AVAILABLE:
            raise ImportError("socketio package is required. Install with: pip install python-socketio")
        
        self.server_url = server_url
        self.sio = socketio.AsyncClient()
        self.resource_monitor = ResourceMonitor()
        self.app_tracker = ApplicationTracker()
        
        # Client identification
        self.client_id = PlatformDetector.get_unique_id()
        self.platform = PlatformDetector.detect_platform()
        self.hostname = socket.gethostname()
        self.mac_address = PlatformDetector.get_mac_address()
        
        # Session management
        self.session_id = None
        self.user_name = None
        self.is_monitoring = False
        
        # Setup event handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup Socket.IO event handlers"""
        
        @self.sio.event
        async def connect():
            logger.info(f"Connected to monitoring server: {self.server_url}")
            
            # Register with server
            await self.sio.emit('client_register', {
                'client_id': self.client_id,
                'platform': self.platform,
                'hostname': self.hostname,
                'mac_address': self.mac_address,
                'os_version': platform.platform(),
                'tags': [self.platform, socket.gethostname()]
            })
        
        @self.sio.event
        async def disconnect():
            logger.warning("Disconnected from monitoring server")
            self.is_monitoring = False
        
        @self.sio.event
        async def session_started(data):
            """Handle session start from server"""
            self.session_id = data.get('session_id')
            self.user_name = data.get('user_name', 'Guest')
            logger.info(f"Session started: {self.session_id} for {self.user_name}")
            
            # Start application tracking for this session
            self.start_application_tracking()
            
            return {'status': 'session_started'}
        
        @self.sio.event
        async def session_ended(data):
            """Handle session end from server"""
            logger.info(f"Session ended: {self.session_id}")
            
            # Stop application tracking
            self.stop_application_tracking()
            
            # Send final application usage data
            await self.send_application_usage()
            
            self.session_id = None
            self.user_name = None
            
            return {'status': 'session_ended'}
        
        @self.sio.event
        async def command(data):
            """Handle commands from server"""
            command_type = data.get('type')
            
            if command_type == 'shutdown':
                logger.info("Received shutdown command")
                # You could implement graceful shutdown here
                return {'status': 'shutting_down'}
            
            elif command_type == 'restart':
                logger.info("Received restart command")
                return {'status': 'restarting'}
            
            elif command_type == 'lock':
                logger.info("Received lock command")
                return {'status': 'locked'}
            
            elif command_type == 'message':
                message = data.get('message', '')
                logger.info(f"Message from server: {message}")
                return {'status': 'message_received'}
    
    def detect_foreground_application(self) -> Optional[str]:
        """Detect foreground/active application (platform-specific)"""
        current_platform = self.platform
        
        try:
            if current_platform == 'windows':
                import win32gui
                import win32process
                
                hwnd = win32gui.GetForegroundWindow()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                
                if PSUTIL_AVAILABLE:
                    process = psutil.Process(pid)
                    return process.name()
            
            elif current_platform == 'macos':
                # macOS - use AppleScript
                script = '''
                tell application "System Events"
                    set frontApp to name of first application process whose frontmost is true
                    return frontApp
                end tell
                '''
                result = subprocess.run(['osascript', '-e', script], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            
            elif current_platform in ['linux', 'raspberry_pi']:
                # Linux - try various methods
                try:
                    # Try using wmctrl
                    result = subprocess.run(['wmctrl', '-lp'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        # Parse output to find active window
                        for line in result.stdout.split('\n'):
                            if 'active' in line.lower():
                                parts = line.split()
                                if len(parts) > 3:
                                    pid = parts[2]
                                    if PSUTIL_AVAILABLE:
                                        process = psutil.Process(int(pid))
                                        return process.name()
                except:
                    pass
        except:
            pass
        
        return None
    
    def start_application_tracking(self):
        """Start tracking application usage"""
        self.is_monitoring = True
        
        async def track_applications():
            while self.is_monitoring and self.session_id:
                try:
                    app_name = self.detect_foreground_application()
                    if app_name:
                        self.app_tracker.track_application(app_name)
                    
                    # Send application usage every 30 seconds
                    await asyncio.sleep(30)
                    await self.send_application_usage()
                    
                except Exception as e:
                    logger.error(f"Error tracking applications: {e}")
                    await asyncio.sleep(5)
        
        # Start tracking in background
        asyncio.create_task(track_applications())
    
    def stop_application_tracking(self):
        """Stop tracking application usage"""
        self.is_monitoring = False
        
        # Log all active applications
        for app_name in list(self.app_tracker.active_apps.keys()):
            self.app_tracker._log_application_usage(app_name)
    
    async def send_application_usage(self):
        """Send application usage data to server"""
        if not self.session_id:
            return
        
        active_apps = self.app_tracker.get_active_applications()
        
        if active_apps:
            await self.sio.emit('application_usage', {
                'client_id': self.client_id,
                'session_id': self.session_id,
                'applications': active_apps
            })
    
    async def send_resource_update(self):
        """Periodically send resource updates to server"""
        while True:
            try:
                if self.sio.connected:
                    resources = self.resource_monitor.get_all_resources()
                    
                    await self.sio.emit('resource_update', {
                        'client_id': self.client_id,
                        'session_id': self.session_id,
                        **resources
                    })
                    
                    logger.debug(f"Sent resource update: CPU={resources['cpu_percent']}%")
                
            except Exception as e:
                logger.error(f"Error sending resource update: {e}")
            
            await asyncio.sleep(10)  # Send updates every 10 seconds
    
    async def start(self):
        """Start the monitoring client"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to server (attempt {attempt + 1}/{max_retries})...")
                
                await self.sio.connect(self.server_url)
                
                # Start resource update task
                asyncio.create_task(self.send_resource_update())
                
                logger.info(f"Client started: {self.client_id} ({self.platform})")
                logger.info(f"Hostname: {self.hostname}")
                logger.info(f"MAC Address: {self.mac_address}")
                
                # Keep client running
                await asyncio.Event().wait()
                break
                
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Max retries reached. Exiting.")
                    break

# Platform-specific implementations

class WindowsClient(UniversalMonitoringClient):
    """Windows-specific client enhancements"""
    
    def __init__(self, server_url: str):
        super().__init__(server_url)
        
        # Windows-specific initialization
        try:
            import win32api
            import win32con
            self.windows_available = True
        except ImportError:
            self.windows_available = False
            logger.warning("pywin32 not available. Install with: pip install pywin32")
    
    async def lock_workstation(self):
        """Lock Windows workstation"""
        if self.windows_available:
            import win32api
            win32api.LockWorkStation()
            return True
        return False

class MacOSClient(UniversalMonitoringClient):
    """macOS-specific client enhancements"""
    
    def __init__(self, server_url: str):
        super().__init__(server_url)
    
    async def lock_screen(self):
        """Lock macOS screen"""
        try:
            subprocess.run(['pmset', 'displaysleepnow'])
            return True
        except:
            return False

class LinuxClient(UniversalMonitoringClient):
    """Linux-specific client enhancements"""
    
    def __init__(self, server_url: str):
        super().__init__(server_url)
    
    async def lock_screen(self):
        """Lock Linux screen"""
        try:
            # Try different lock commands
            commands = [
                ['gnome-screensaver-command', '-l'],  # GNOME
                ['dm-tool', 'lock'],  # LightDM
                ['xlock'],  # xlock
                ['xscreensaver-command', '-lock']  # XScreenSaver
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0:
                    return True
        except:
            pass
        return False

class IOSClient:
    """iOS client using Pythonista or similar"""
    # Note: iOS has restrictions on background execution
    # This would need to be adapted for iOS limitations
    
    @staticmethod
    def is_jailbroken():
        """Check if iOS device is jailbroken"""
        return os.path.exists('/Applications/Cydia.app')
    
    @staticmethod
    def get_ios_info():
        """Get iOS device information"""
        import platform
        return {
            'model': platform.machine(),
            'version': platform.release(),
            'system': platform.system()
        }

# Configuration helper
def load_config():
    """Load configuration from file or environment"""
    config = {
        'server_url': os.getenv('MONITORING_SERVER', 'http://localhost:8080'),
        'client_name': os.getenv('CLIENT_NAME', socket.gethostname()),
        'update_interval': int(os.getenv('UPDATE_INTERVAL', '10')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Try to load from config file
    config_file = 'client_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
    
    return config

async def main():
    """Main entry point"""
    config = load_config()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, config['log_level']))
    
    logger.info("Starting Universal Monitoring Client")
    logger.info(f"Platform: {PlatformDetector.detect_platform()}")
    logger.info(f"Server URL: {config['server_url']}")
    
    # Create appropriate client for platform
    platform = PlatformDetector.detect_platform()
    
    if platform == 'windows':
        client = WindowsClient(config['server_url'])
    elif platform == 'macos':
        client = MacOSClient(config['server_url'])
    elif platform in ['linux', 'raspberry_pi']:
        client = LinuxClient(config['server_url'])
    else:
        client = UniversalMonitoringClient(config['server_url'])
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Client shutting down...")
    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # Check dependencies
    if not PSUTIL_AVAILABLE:
        print("Warning: psutil is not installed. Resource monitoring will be limited.")
        print("Install with: pip install psutil")
    
    if not SOCKETIO_AVAILABLE:
        print("Error: python-socketio is required.")
        print("Install with: pip install python-socketio")
        sys.exit(1)
    
    # Import hashlib (should always be available)
    import hashlib
    
    # Run the client
    asyncio.run(main())