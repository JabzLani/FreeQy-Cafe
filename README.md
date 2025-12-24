# FreeQy Café - Universal Monitoring System

A cross-platform internet café monitoring system that works on Windows, Linux, macOS, Raspberry Pi, Android, and iOS devices.

## Features

- **Universal Client Support**: Monitor devices across all major platforms
- **Real-time Monitoring**: Track CPU, memory, disk, network, and GPU usage
- **Session Management**: Start/end user sessions with automatic cost calculation
- **Application Tracking**: Monitor which applications are being used
- **Web Dashboard**: Modern, responsive dashboard for managing all clients
- **Alerts**: Automatic alerts for high resource usage
- **Multi-platform**: Works on Windows, macOS, Linux, Raspberry Pi, Android, and iOS

## Quick Start

### Server Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the monitoring server:
```bash
python universal_monitoring_server.py
```

3. Access the dashboard at `http://localhost:8080`

### Client Setup

#### Windows/macOS/Linux
```bash
python install_universal_client.py
```

#### Raspberry Pi
```bash
bash setup.sh
```

#### Android (Termux)
```bash
bash android_client.sh
```

#### iOS (Pythonista)
Run `ios_client.py` in Pythonista app

## Configuration

Edit `config/universal_config.json` to customize:
- Server host and port
- Session rates
- Alert thresholds
- Database settings

## Architecture

- **Server**: Python asyncio + aiohttp + Socket.IO
- **Database**: SQLite
- **Frontend**: HTML + Bootstrap + Chart.js
- **Communication**: WebSocket (Socket.IO) for real-time updates

## License

MIT License

## Author

JabzLani
