"""
TallySync Desktop Connector
Bridges the SaaS platform with TallyPrime on localhost:9000
"""
import os
import sys
import json
import time
import uuid
import logging
import requests
import threading
from datetime import datetime
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET

# Configuration
CONFIG_FILE = "connector_config.json"
DEFAULT_CONFIG = {
    "api_url": "https://app.tallysync.com/api/v1",
    "tally_host": "localhost",
    "tally_port": 9000,
    "poll_interval": 5,
    "retry_attempts": 3,
    "log_level": "INFO"
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('connector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TallyConnector:
    """Handles communication with TallyPrime"""
    
    def __init__(self, host: str = "localhost", port: int = 9000):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
    
    def is_tally_running(self) -> bool:
        """Check if Tally is running and accepting connections"""
        try:
            # Simple request to check Tally status
            test_xml = """<ENVELOPE>
                <HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>List of Companies</ID></HEADER>
                <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
            </ENVELOPE>"""
            response = requests.post(self.base_url, data=test_xml, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_companies(self) -> list:
        """Get list of companies from Tally"""
        xml_request = """<ENVELOPE>
            <HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>List of Companies</ID></HEADER>
            <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
        </ENVELOPE>"""
        
        try:
            response = requests.post(self.base_url, data=xml_request, timeout=30)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                companies = []
                for company in root.findall('.//COMPANY'):
                    name = company.find('NAME')
                    if name is not None:
                        companies.append(name.text)
                return companies
        except Exception as e:
            logger.error(f"Failed to get companies: {e}")
        return []
    
    def send_xml(self, xml_data: str) -> Dict[str, Any]:
        """Send XML request to Tally and parse response"""
        try:
            start_time = time.time()
            response = requests.post(
                self.base_url,
                data=xml_data.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=60
            )
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = {
                'success': False,
                'status_code': response.status_code,
                'response_xml': response.text,
                'duration_ms': duration_ms,
                'error': None,
                'tally_guid': None
            }
            
            if response.status_code == 200:
                result = self._parse_tally_response(response.text, result)
            else:
                result['error'] = f"HTTP {response.status_code}"
            
            return result
            
        except requests.Timeout:
            return {'success': False, 'error': 'Request timeout', 'duration_ms': 60000}
        except requests.ConnectionError:
            return {'success': False, 'error': 'Tally not reachable', 'duration_ms': 0}
        except Exception as e:
            return {'success': False, 'error': str(e), 'duration_ms': 0}
    
    def _parse_tally_response(self, xml_text: str, result: dict) -> dict:
        """Parse Tally XML response for success/error"""
        try:
            root = ET.fromstring(xml_text)
            
            # Check for LINEERROR
            line_error = root.find('.//LINEERROR')
            if line_error is not None and line_error.text:
                result['error'] = line_error.text
                return result
            
            # Check import result
            import_result = root.find('.//IMPORTRESULT')
            if import_result is not None:
                created = import_result.find('CREATED')
                altered = import_result.find('ALTERED')
                errors = import_result.find('ERRORS')
                
                if errors is not None and int(errors.text or 0) > 0:
                    result['error'] = f"Tally reported {errors.text} errors"
                elif (created is not None and int(created.text or 0) > 0) or \
                     (altered is not None and int(altered.text or 0) > 0):
                    result['success'] = True
            
            # Extract GUID if available
            guid = root.find('.//GUID')
            if guid is not None:
                result['tally_guid'] = guid.text
            
            # Check for general success indicators
            if 'CREATED' in xml_text or 'ALTERED' in xml_text:
                if not result.get('error'):
                    result['success'] = True
            
        except ET.ParseError as e:
            result['error'] = f"XML parse error: {e}"
        
        return result


class SaaSClient:
    """Handles communication with TallySync SaaS API"""
    
    def __init__(self, api_url: str, api_key: str, connector_id: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.connector_id = connector_id
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-Connector-ID': connector_id
        })
    
    def send_heartbeat(self, tally_connected: bool, companies: list = None) -> bool:
        """Send heartbeat to SaaS"""
        try:
            response = self.session.post(
                f"{self.api_url}/tally/heartbeat/",
                json={
                    'connector_id': self.connector_id,
                    'tally_connected': tally_connected,
                    'companies': companies or [],
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return False
    
    def get_pending_operations(self) -> list:
        """Fetch pending operations from SaaS"""
        try:
            response = self.session.get(
                f"{self.api_url}/tally/pending-operations/",
                params={'connector_id': self.connector_id}
            )
            if response.status_code == 200:
                return response.json().get('operations', [])
        except Exception as e:
            logger.error(f"Failed to get pending operations: {e}")
        return []
    
    def report_operation_result(self, operation_id: str, result: dict) -> bool:
        """Report operation result back to SaaS"""
        try:
            response = self.session.post(
                f"{self.api_url}/tally/operation-result/",
                json={
                    'operation_id': operation_id,
                    'connector_id': self.connector_id,
                    'success': result.get('success', False),
                    'error_message': result.get('error'),
                    'response_xml': result.get('response_xml', ''),
                    'tally_guid': result.get('tally_guid'),
                    'duration_ms': result.get('duration_ms', 0)
                }
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to report result: {e}")
            return False


class DesktopConnector:
    """Main connector application"""
    
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config = self._load_config(config_path)
        self.connector_id = self._get_or_create_connector_id()
        self.running = False
        
        self.tally = TallyConnector(
            self.config.get('tally_host', 'localhost'),
            self.config.get('tally_port', 9000)
        )
        
        self.saas = None  # Initialized after authentication
        
        logger.setLevel(getattr(logging, self.config.get('log_level', 'INFO')))
    
    def _load_config(self, path: str) -> dict:
        """Load configuration from file"""
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        return DEFAULT_CONFIG.copy()
    
    def _save_config(self, path: str = CONFIG_FILE):
        """Save configuration to file"""
        with open(path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _get_or_create_connector_id(self) -> str:
        """Get existing or create new connector ID"""
        connector_id = self.config.get('connector_id')
        if not connector_id:
            connector_id = str(uuid.uuid4())
            self.config['connector_id'] = connector_id
            self._save_config()
        return connector_id
    
    def authenticate(self, api_key: str) -> bool:
        """Authenticate with SaaS using API key"""
        self.config['api_key'] = api_key
        self._save_config()
        
        self.saas = SaaSClient(
            self.config['api_url'],
            api_key,
            self.connector_id
        )
        
        # Test connection with heartbeat
        tally_running = self.tally.is_tally_running()
        companies = self.tally.get_companies() if tally_running else []
        
        if self.saas.send_heartbeat(tally_running, companies):
            logger.info("Successfully authenticated with TallySync")
            return True
        
        logger.error("Authentication failed")
        return False
    
    def process_operation(self, operation: dict) -> dict:
        """Process a single operation"""
        op_id = operation.get('id')
        op_type = operation.get('operation_type')
        xml_data = operation.get('request_xml')
        
        logger.info(f"Processing operation {op_id}: {op_type}")
        
        if not xml_data:
            return {'success': False, 'error': 'No XML data provided'}
        
        # Send to Tally
        result = self.tally.send_xml(xml_data)
        
        if result['success']:
            logger.info(f"Operation {op_id} completed successfully")
        else:
            logger.error(f"Operation {op_id} failed: {result.get('error')}")
        
        return result
    
    def run_poll_loop(self):
        """Main polling loop"""
        self.running = True
        poll_interval = self.config.get('poll_interval', 5)
        heartbeat_counter = 0
        
        logger.info(f"Starting poll loop (interval: {poll_interval}s)")
        
        while self.running:
            try:
                # Check Tally status
                tally_running = self.tally.is_tally_running()
                
                # Send heartbeat every 6 polls (30 seconds with 5s interval)
                heartbeat_counter += 1
                if heartbeat_counter >= 6:
                    companies = self.tally.get_companies() if tally_running else []
                    self.saas.send_heartbeat(tally_running, companies)
                    heartbeat_counter = 0
                
                if not tally_running:
                    logger.warning("Tally not running, waiting...")
                    time.sleep(poll_interval)
                    continue
                
                # Get pending operations
                operations = self.saas.get_pending_operations()
                
                for operation in operations:
                    result = self.process_operation(operation)
                    self.saas.report_operation_result(operation['id'], result)
                
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
                self.running = False
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                time.sleep(poll_interval)
        
        logger.info("Poll loop stopped")
    
    def stop(self):
        """Stop the connector"""
        self.running = False


class ConnectorGUI:
    """Simple GUI for the connector (using tkinter)"""
    
    def __init__(self):
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
            self.tk = tk
            self.ttk = ttk
            self.messagebox = messagebox
            self.has_gui = True
        except ImportError:
            self.has_gui = False
            logger.warning("tkinter not available, running in console mode")
    
    def run(self, connector: DesktopConnector):
        if not self.has_gui:
            self._run_console(connector)
            return
        
        self._run_gui(connector)
    
    def _run_console(self, connector: DesktopConnector):
        """Run in console mode"""
        print("\n" + "="*50)
        print("TallySync Desktop Connector")
        print("="*50 + "\n")
        
        api_key = connector.config.get('api_key') or input("Enter API Key: ")
        
        if connector.authenticate(api_key):
            print("\n✓ Connected to TallySync")
            print("Press Ctrl+C to stop\n")
            connector.run_poll_loop()
        else:
            print("✗ Authentication failed")
    
    def _run_gui(self, connector: DesktopConnector):
        """Run with GUI"""
        tk = self.tk
        ttk = self.ttk
        
        root = tk.Tk()
        root.title("TallySync Desktop Connector")
        root.geometry("500x400")
        root.resizable(False, False)
        
        # Status frame
        status_frame = ttk.LabelFrame(root, text="Status", padding=10)
        status_frame.pack(fill='x', padx=10, pady=10)
        
        tally_status = ttk.Label(status_frame, text="Tally: Checking...")
        tally_status.pack(anchor='w')
        
        saas_status = ttk.Label(status_frame, text="TallySync: Not connected")
        saas_status.pack(anchor='w')
        
        # API Key frame
        auth_frame = ttk.LabelFrame(root, text="Authentication", padding=10)
        auth_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(auth_frame, text="API Key:").pack(anchor='w')
        api_key_var = tk.StringVar(value=connector.config.get('api_key', ''))
        api_key_entry = ttk.Entry(auth_frame, textvariable=api_key_var, show='*', width=50)
        api_key_entry.pack(fill='x', pady=5)
        
        def connect():
            if connector.authenticate(api_key_var.get()):
                saas_status.config(text="TallySync: Connected ✓", foreground='green')
                connect_btn.config(state='disabled')
                start_btn.config(state='normal')
                self.messagebox.showinfo("Success", "Connected to TallySync!")
            else:
                self.messagebox.showerror("Error", "Authentication failed")
        
        connect_btn = ttk.Button(auth_frame, text="Connect", command=connect)
        connect_btn.pack(pady=5)
        
        # Control frame
        control_frame = ttk.LabelFrame(root, text="Sync Control", padding=10)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        sync_running = tk.BooleanVar(value=False)
        
        def start_sync():
            sync_running.set(True)
            start_btn.config(state='disabled')
            stop_btn.config(state='normal')
            threading.Thread(target=connector.run_poll_loop, daemon=True).start()
        
        def stop_sync():
            connector.stop()
            sync_running.set(False)
            start_btn.config(state='normal')
            stop_btn.config(state='disabled')
        
        start_btn = ttk.Button(control_frame, text="Start Sync", command=start_sync, state='disabled')
        start_btn.pack(side='left', padx=5)
        
        stop_btn = ttk.Button(control_frame, text="Stop Sync", command=stop_sync, state='disabled')
        stop_btn.pack(side='left', padx=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(root, text="Activity Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        log_text = tk.Text(log_frame, height=8, state='disabled')
        log_text.pack(fill='both', expand=True)
        
        # Update status periodically
        def update_status():
            tally_running = connector.tally.is_tally_running()
            if tally_running:
                tally_status.config(text="Tally: Running ✓", foreground='green')
            else:
                tally_status.config(text="Tally: Not running ✗", foreground='red')
            root.after(5000, update_status)
        
        update_status()
        root.mainloop()


def main():
    """Main entry point"""
    connector = DesktopConnector()
    gui = ConnectorGUI()
    gui.run(connector)


if __name__ == '__main__':
    main()
