#!/usr/bin/env python3
"""
Universal Internet Cafe Monitoring Server
Supports Windows, Linux, macOS, and Raspberry Pi clients
"""

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from aiohttp import web
import socketio
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Platform types
class Platform(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    RASPBERRY_PI = "raspberry_pi"
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"

# Client status
class ClientStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"

@dataclass
class ClientInfo:
    client_id: str
    platform: Platform
    hostname: str
    ip_address: str
    mac_address: str
    os_version: str
    last_seen: datetime
    status: ClientStatus
    session_id: Optional[str] = None
    user_name: Optional[str] = None
    total_uptime: int = 0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class UniversalMonitoringServer:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp', 
            cors_allowed_origins='*',
            ping_timeout=60,
            ping_interval=25
        )
        self.app = web.Application()
        self.sio.attach(self.app)
        
        # Store connected clients
        self.clients: Dict[str, ClientInfo] = {}
        self.client_sessions: Dict[str, str] = {}  # client_id -> session_id
        
        # Initialize database
        self.init_database()
        
        # Setup routes and handlers
        self.setup_routes()
        self.setup_socket_handlers()
        
        # Background tasks
        self.background_tasks = []
        
    def init_database(self):
        """Initialize SQLite database with cross-platform support"""
        conn = sqlite3.connect('universal_monitoring.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Create clients table with platform info
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                hostname TEXT NOT NULL,
                ip_address TEXT,
                mac_address TEXT,
                os_version TEXT,
                last_seen TIMESTAMP,
                status TEXT,
                total_uptime INTEGER DEFAULT 0,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                client_id TEXT,
                user_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration INTEGER,
                cost REAL,
                notes TEXT,
                FOREIGN KEY (client_id) REFERENCES clients (client_id)
            )
        ''')
        
        # Create resource usage table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                timestamp TIMESTAMP,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                network_rx_mbps REAL,
                network_tx_mbps REAL,
                gpu_usage REAL,
                battery_percent REAL,
                screen_on BOOLEAN,
                processes_count INTEGER,
                FOREIGN KEY (client_id) REFERENCES clients (client_id)
            )
        ''')
        
        # Create application usage table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS application_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                client_id TEXT,
                app_name TEXT,
                app_path TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                FOREIGN KEY (client_id) REFERENCES clients (client_id)
            )
        ''')
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                timestamp TIMESTAMP,
                acknowledged BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (client_id) REFERENCES clients (client_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def setup_routes(self):
        """Setup HTTP routes for REST API"""
        routes = web.RouteTableDef()
        
        @routes.get('/')
        async def index(request):
            return web.FileResponse('./templates/dashboard.html')
        
        @routes.get('/api/v1/clients')
        async def get_clients(request):
            """Get all clients with filtering"""
            platform = request.query.get('platform')
            status = request.query.get('status')
            
            conn = sqlite3.connect('universal_monitoring.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM clients"
            params = []
            conditions = []
            
            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY last_seen DESC"
            cursor.execute(query, params)
            clients = cursor.fetchall()
            conn.close()
            
            return web.json_response({
                'clients': [dict(client) for client in clients]
            })
        
        @routes.get('/api/v1/clients/{client_id}')
        async def get_client(request):
            """Get specific client details"""
            client_id = request.match_info['client_id']
            
            conn = sqlite3.connect('universal_monitoring.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM clients WHERE client_id = ?', (client_id,))
            client = cursor.fetchone()
            
            if not client:
                conn.close()
                return web.json_response({'error': 'Client not found'}, status=404)
            
            # Get recent resource usage
            cursor.execute('''
                SELECT * FROM resource_usage 
                WHERE client_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 100
            ''', (client_id,))
            resources = cursor.fetchall()
            
            # Get active session
            cursor.execute('''
                SELECT * FROM sessions 
                WHERE client_id = ? AND end_time IS NULL
                ORDER BY start_time DESC 
                LIMIT 1
            ''', (client_id,))
            session = cursor.fetchone()
            
            conn.close()
            
            return web.json_response({
                'client': dict(client),
                'recent_resources': [dict(r) for r in resources],
                'active_session': dict(session) if session else None
            })
        
        @routes.post('/api/v1/sessions')
        async def create_session(request):
            """Start a new session"""
            data = await request.json()
            client_id = data.get('client_id')
            user_name = data.get('user_name', 'Guest')
            session_type = data.get('type', 'regular')
            
            if not client_id:
                return web.json_response({'error': 'client_id required'}, status=400)
            
            session_id = hashlib.md5(f"{client_id}{datetime.now().timestamp()}".encode()).hexdigest()
            
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            # Check if client exists
            cursor.execute('SELECT client_id FROM clients WHERE client_id = ?', (client_id,))
            if not cursor.fetchone():
                conn.close()
                return web.json_response({'error': 'Client not registered'}, status=404)
            
            # Create session
            cursor.execute('''
                INSERT INTO sessions (session_id, client_id, user_name, start_time, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, client_id, user_name, datetime.now(), f"Type: {session_type}"))
            
            # Update client status
            cursor.execute('''
                UPDATE clients SET status = ? WHERE client_id = ?
            ''', ('busy', client_id))
            
            conn.commit()
            conn.close()
            
            # Update in-memory state
            if client_id in self.clients:
                self.clients[client_id].status = ClientStatus.BUSY
                self.clients[client_id].session_id = session_id
                self.clients[client_id].user_name = user_name
            
            # Broadcast session start
            await self.sio.emit('session_started', {
                'session_id': session_id,
                'client_id': client_id,
                'user_name': user_name
            })
            
            return web.json_response({
                'success': True,
                'session_id': session_id,
                'message': 'Session started'
            })
        
        @routes.put('/api/v1/sessions/{session_id}')
        async def end_session(request):
            """End a session"""
            session_id = request.match_info['session_id']
            data = await request.json()
            notes = data.get('notes', '')
            
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            # Get session details
            cursor.execute('''
                SELECT client_id, start_time FROM sessions 
                WHERE session_id = ? AND end_time IS NULL
            ''', (session_id,))
            session = cursor.fetchone()
            
            if not session:
                conn.close()
                return web.json_response({'error': 'Session not found or already ended'}, status=404)
            
            client_id, start_time = session
            end_time = datetime.now()
            duration = int((end_time - datetime.fromisoformat(start_time)).total_seconds())
            
            # Calculate cost based on duration (configurable rate)
            cost_per_hour = 1.50  # Default rate
            cost = round(duration / 3600 * cost_per_hour, 2)
            
            # Update session
            cursor.execute('''
                UPDATE sessions 
                SET end_time = ?, duration = ?, cost = ?, notes = notes || ?
                WHERE session_id = ?
            ''', (end_time, duration, cost, f"\n{notes}", session_id))
            
            # Update client status
            cursor.execute('''
                UPDATE clients SET status = ? WHERE client_id = ?
            ''', ('online', client_id))
            
            conn.commit()
            conn.close()
            
            # Update in-memory state
            if client_id in self.clients:
                self.clients[client_id].status = ClientStatus.ONLINE
                self.clients[client_id].session_id = None
            
            # Broadcast session end
            await self.sio.emit('session_ended', {
                'session_id': session_id,
                'client_id': client_id,
                'duration': duration,
                'cost': cost
            })
            
            return web.json_response({
                'success': True,
                'duration': duration,
                'cost': cost,
                'message': 'Session ended'
            })
        
        @routes.get('/api/v1/stats')
        async def get_stats(request):
            """Get overall statistics"""
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            # Platform distribution
            cursor.execute('''
                SELECT platform, COUNT(*) as count 
                FROM clients 
                GROUP BY platform
            ''')
            platform_dist = cursor.fetchall()
            
            # Today's revenue
            today = datetime.now().date()
            cursor.execute('''
                SELECT SUM(cost) FROM sessions 
                WHERE DATE(start_time) = ?
            ''', (today,))
            today_revenue = cursor.fetchone()[0] or 0
            
            # Active sessions count
            cursor.execute('''
                SELECT COUNT(*) FROM sessions 
                WHERE end_time IS NULL
            ''')
            active_sessions = cursor.fetchone()[0]
            
            # Online clients count
            cursor.execute('''
                SELECT COUNT(*) FROM clients 
                WHERE status = 'online' OR status = 'busy'
            ''')
            online_clients = cursor.fetchone()[0]
            
            conn.close()
            
            return web.json_response({
                'platform_distribution': dict(platform_dist),
                'today_revenue': today_revenue,
                'active_sessions': active_sessions,
                'online_clients': online_clients,
                'total_clients': len(self.clients)
            })
        
        @routes.get('/api/v1/reports/daily')
        async def daily_report(request):
            """Generate daily report"""
            date_str = request.query.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            conn = sqlite3.connect('universal_monitoring.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    s.session_id,
                    s.client_id,
                    c.hostname,
                    c.platform,
                    s.user_name,
                    s.start_time,
                    s.end_time,
                    s.duration,
                    s.cost
                FROM sessions s
                JOIN clients c ON s.client_id = c.client_id
                WHERE DATE(s.start_time) = ?
                ORDER BY s.start_time DESC
            ''', (date_str,))
            
            sessions = cursor.fetchall()
            
            cursor.execute('''
                SELECT 
                    strftime('%H', timestamp) as hour,
                    AVG(cpu_percent) as avg_cpu,
                    AVG(memory_percent) as avg_memory,
                    COUNT(DISTINCT client_id) as active_clients
                FROM resource_usage
                WHERE DATE(timestamp) = ?
                GROUP BY strftime('%H', timestamp)
            ''', (date_str,))
            
            hourly_stats = cursor.fetchall()
            
            conn.close()
            
            return web.json_response({
                'date': date_str,
                'sessions': [dict(s) for s in sessions],
                'hourly_stats': [dict(h) for h in hourly_stats],
                'total_sessions': len(sessions),
                'total_revenue': sum(s['cost'] or 0 for s in sessions)
            })
        
        self.app.router.add_routes(routes)
        self.app.router.add_static('/static', 'static')
        self.app.router.add_static('/assets', 'assets')
    
    def setup_socket_handlers(self):
        """Setup Socket.IO event handlers"""
        
        @self.sio.event
        async def connect(sid, environ):
            logger.info(f"Client connected via Socket.IO: {sid}")
        
        @self.sio.event
        async def client_register(sid, data):
            """Register a new client"""
            client_id = data.get('client_id')
            platform_str = data.get('platform', 'unknown')
            
            try:
                platform = Platform(platform_str.lower())
            except ValueError:
                platform = Platform.UNKNOWN
            
            client_info = ClientInfo(
                client_id=client_id,
                platform=platform,
                hostname=data.get('hostname', 'Unknown'),
                ip_address=environ.get('REMOTE_ADDR', 'unknown'),
                mac_address=data.get('mac_address', ''),
                os_version=data.get('os_version', ''),
                last_seen=datetime.now(),
                status=ClientStatus.ONLINE,
                tags=data.get('tags', [])
            )
            
            # Store in memory
            self.clients[client_id] = client_info
            self.client_sessions[sid] = client_id
            
            # Store in database
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO clients 
                (client_id, platform, hostname, ip_address, mac_address, 
                 os_version, last_seen, status, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client_id,
                platform.value,
                client_info.hostname,
                client_info.ip_address,
                client_info.mac_address,
                client_info.os_version,
                client_info.last_seen,
                client_info.status.value,
                json.dumps(client_info.tags)
            ))
            
            conn.commit()
            conn.close()
            
            # Broadcast to all connected dashboards
            await self.sio.emit('client_registered', {
                'client_id': client_id,
                'platform': platform.value,
                'hostname': client_info.hostname,
                'status': client_info.status.value
            })
            
            logger.info(f"Client registered: {client_id} ({platform.value})")
            
            return {'status': 'registered', 'client_id': client_id}
        
        @self.sio.event
        async def resource_update(sid, data):
            """Handle resource updates from clients"""
            client_id = data.get('client_id')
            
            if client_id not in self.clients:
                return {'error': 'Client not registered'}
            
            # Update client last seen
            self.clients[client_id].last_seen = datetime.now()
            
            # Store resource data in database
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO resource_usage 
                (client_id, timestamp, cpu_percent, memory_percent, 
                 disk_percent, network_rx_mbps, network_tx_mbps,
                 gpu_usage, battery_percent, screen_on, processes_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client_id,
                datetime.now(),
                data.get('cpu_percent', 0),
                data.get('memory_percent', 0),
                data.get('disk_percent', 0),
                data.get('network_rx_mbps', 0),
                data.get('network_tx_mbps', 0),
                data.get('gpu_usage', 0),
                data.get('battery_percent', 100),
                data.get('screen_on', True),
                data.get('processes_count', 0)
            ))
            
            # Update client last seen in database
            cursor.execute('''
                UPDATE clients 
                SET last_seen = ?, status = ?
                WHERE client_id = ?
            ''', (datetime.now(), 'online', client_id))
            
            conn.commit()
            conn.close()
            
            # Check for alerts (high resource usage, etc.)
            await self.check_alerts(client_id, data)
            
            # Broadcast update to dashboards
            await self.sio.emit('resource_updated', {
                'client_id': client_id,
                'resources': data,
                'timestamp': datetime.now().isoformat()
            })
            
            return {'status': 'updated'}
        
        @self.sio.event
        async def application_usage(sid, data):
            """Handle application usage data"""
            client_id = data.get('client_id')
            session_id = data.get('session_id')
            
            if not session_id and client_id in self.clients:
                session_id = self.clients[client_id].session_id
            
            if not session_id:
                return {'error': 'No active session'}
            
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            for app in data.get('applications', []):
                cursor.execute('''
                    INSERT INTO application_usage 
                    (session_id, client_id, app_name, app_path, start_time, duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    client_id,
                    app.get('name'),
                    app.get('path'),
                    datetime.fromisoformat(app.get('start_time')),
                    app.get('duration', 0)
                ))
            
            conn.commit()
            conn.close()
            
            return {'status': 'logged'}
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnect"""
            if sid in self.client_sessions:
                client_id = self.client_sessions[sid]
                
                if client_id in self.clients:
                    self.clients[client_id].status = ClientStatus.OFFLINE
                    
                    # Update database
                    conn = sqlite3.connect('universal_monitoring.db')
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE clients 
                        SET status = ?, last_seen = ?
                        WHERE client_id = ?
                    ''', ('offline', datetime.now(), client_id))
                    conn.commit()
                    conn.close()
                    
                    # Broadcast to dashboards
                    await self.sio.emit('client_disconnected', {
                        'client_id': client_id,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.info(f"Client disconnected: {client_id}")
                
                del self.client_sessions[sid]
    
    async def check_alerts(self, client_id: str, resources: dict):
        """Check for alert conditions"""
        alerts = []
        
        # High CPU usage alert
        if resources.get('cpu_percent', 0) > 90:
            alerts.append({
                'type': 'high_cpu',
                'severity': 'warning',
                'message': f'CPU usage is {resources["cpu_percent"]}%'
            })
        
        # High memory usage alert
        if resources.get('memory_percent', 0) > 90:
            alerts.append({
                'type': 'high_memory',
                'severity': 'warning',
                'message': f'Memory usage is {resources["memory_percent"]}%'
            })
        
        # Low disk space alert
        if resources.get('disk_percent', 0) > 90:
            alerts.append({
                'type': 'low_disk',
                'severity': 'critical',
                'message': f'Disk usage is {resources["disk_percent"]}%'
            })
        
        # Save alerts to database and broadcast
        if alerts:
            conn = sqlite3.connect('universal_monitoring.db')
            cursor = conn.cursor()
            
            for alert in alerts:
                cursor.execute('''
                    INSERT INTO alerts 
                    (client_id, alert_type, severity, message, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    client_id,
                    alert['type'],
                    alert['severity'],
                    alert['message'],
                    datetime.now()
                ))
            
            conn.commit()
            conn.close()
            
            # Broadcast alerts
            for alert in alerts:
                await self.sio.emit('alert', {
                    'client_id': client_id,
                    **alert,
                    'timestamp': datetime.now().isoformat()
                })
    
    async def cleanup_old_data(self):
        """Clean up old data periodically"""
        while True:
            await asyncio.sleep(3600)  # Run every hour
            
            try:
                conn = sqlite3.connect('universal_monitoring.db')
                cursor = conn.cursor()
                
                # Delete resource usage older than 7 days
                cutoff = datetime.now() - timedelta(days=7)
                cursor.execute('''
                    DELETE FROM resource_usage 
                    WHERE timestamp < ?
                ''', (cutoff,))
                
                # Delete old alerts
                cursor.execute('''
                    DELETE FROM alerts 
                    WHERE timestamp < ? AND acknowledged = TRUE
                ''', (cutoff,))
                
                conn.commit()
                conn.close()
                
                logger.info("Cleaned up old data")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    
    async def health_check_clients(self):
        """Periodically check client health"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            now = datetime.now()
            offline_clients = []
            
            for client_id, client in list(self.clients.items()):
                if (now - client.last_seen) > timedelta(minutes=10):
                    client.status = ClientStatus.OFFLINE
                    offline_clients.append(client_id)
                    
                    # Update database
                    conn = sqlite3.connect('universal_monitoring.db')
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE clients 
                        SET status = ?
                        WHERE client_id = ?
                    ''', ('offline', client_id))
                    conn.commit()
                    conn.close()
            
            if offline_clients:
                logger.warning(f"Marked as offline: {offline_clients}")

async def main():
    """Main server entry point"""
    server = UniversalMonitoringServer()
    
    # Start background tasks
    server.background_tasks = [
        asyncio.create_task(server.cleanup_old_data()),
        asyncio.create_task(server.health_check_clients())
    ]
    
    # Start web server
    runner = web.AppRunner(server.app)
    await runner.setup()
    
    # Allow configuration of host/port via environment variables
    host = '0.0.0.0'
    port = 8080
    
    site = web.TCPSite(runner, host, port)
    
    logger.info(f"Universal Monitoring Server starting on http://{host}:{port}")
    
    try:
        await site.start()
        await asyncio.Event().wait()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())