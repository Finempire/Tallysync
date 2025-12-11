# TallySync Desktop Connector

This application bridges your local TallyPrime installation with the TallySync SaaS platform.

## Requirements

- Windows 10 or later
- TallyPrime with ODBC Server enabled (port 9000)
- Python 3.10+ (for source installation)

## Installation

### Option 1: Using Pre-built Executable (Recommended)
1. Download `TallySyncConnector.exe` from your TallySync dashboard
2. Run the installer
3. Configure with your API key from Settings > Tally Connection

### Option 2: From Source
```bash
pip install -r requirements.txt
python connector.py --config config.ini
```

## Configuration

1. Copy `config.example.ini` to `config.ini`
2. Update `api_key` with your key from TallySync dashboard
3. Verify Tally settings (default: localhost:9000)

## TallyPrime Setup

1. Open TallyPrime
2. Go to **F12 > Advanced Configuration**
3. Enable **ODBC Server** (Yes)
4. Set **Port** to 9000
5. Restart TallyPrime

## Testing Connection

```bash
python connector.py --test
```

## Running as Windows Service

Use NSSM (Non-Sucking Service Manager):
```bash
nssm install TallySyncConnector "C:\TallySync\connector.exe"
nssm start TallySyncConnector
```

## Troubleshooting

- **Cannot connect to Tally**: Ensure TallyPrime is running with ODBC enabled
- **API errors**: Verify your API key in config.ini
- **Firewall issues**: Allow connector.exe through Windows Firewall
