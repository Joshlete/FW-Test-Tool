from PySide6.QtCore import QObject, Signal, QRunnable, Slot
import requests
import xml.etree.ElementTree as ET
import urllib3
from src.utils.ssh_telemetry import TelemetryManager

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal(object)  # Data returned from the task
    error = Signal(str)        # Error message if failed
    start = Signal()           # Emitted when task starts

class FetchSiriusAlertsWorker(QRunnable):
    """
    Worker thread to fetch and parse Sirius alerts from ProductStatusDyn.xml.
    """
    def __init__(self, ip_address):
        super().__init__()
        self.ip = ip_address
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.start.emit()
        url = f"http://{self.ip}/DevMgmt/ProductStatusDyn.xml"
        
        try:
            response = requests.get(url, verify=False, timeout=10)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.text)
            alerts = []
            
            # Namespace map for XML elements
            ns = {
                'psdyn': 'http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31',
                'ad': 'http://www.hp.com/schemas/imaging/con/ledm/alertdetails/2007/10/31',
                'locid': 'http://www.hp.com/schemas/imaging/con/ledm/localizationids/2007/10/31'
            }

            # Find all alerts in the AlertTable
            for alert in root.findall('.//psdyn:AlertTable/psdyn:Alert', ns):
                details = alert.find('ad:AlertDetails', ns)
                color = details.findtext('ad:AlertDetailsMarkerColor', namespaces=ns, default='') if details else ''
                
                if color == "CyanMagentaYellow":
                    color = "Tri-Color"
                
                # Map to common alert structure used by AlertsWidget/AlertCard
                alerts.append({
                    'id': alert.findtext('ad:ProductStatusAlertID', namespaces=ns, default=''),
                    'stringId': alert.findtext('locid:StringId', namespaces=ns, default=''),
                    'category': color if color else 'General', # Use color as category/consumable type
                    'severity': alert.findtext('ad:Severity', namespaces=ns, default='info'),
                    'priority': alert.findtext('ad:AlertPriority', namespaces=ns, default=''),
                    # Store extra fields if needed for context
                    'raw_color': color
                })
            
            self.signals.finished.emit(alerts)
            
        except Exception as e:
            self.signals.error.emit(f"Error fetching Sirius alerts: {str(e)}")

class FetchSiriusLEDMWorker(QRunnable):
    """
    Worker thread to fetch LEDM data from multiple endpoints.
    """
    def __init__(self, ip_address, endpoints):
        super().__init__()
        self.ip = ip_address
        self.endpoints = endpoints
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.start.emit()
        results = {}
        errors = []

        for endpoint in self.endpoints:
            # Ensure endpoint starts with slash or handle it
            path = endpoint if endpoint.startswith('/') else f"/{endpoint}"
            url = f"http://{self.ip}{path}"
            
            try:
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                results[endpoint] = response.text
            except Exception as e:
                results[endpoint] = f"Error: {str(e)}"
                errors.append(f"{endpoint}: {str(e)}")

        self.signals.finished.emit(results)

class FetchSiriusTelemetryWorker(QRunnable):
    """
    Worker thread to fetch telemetry using the Universal TelemetryManager.
    This runs the blocking connect/fetch loop of the existing manager in a thread.
    """
    def __init__(self, ip_address, telemetry_manager):
        super().__init__()
        self.ip = ip_address
        self.mgr = telemetry_manager
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.start.emit()
        try:
            # Update IP if changed
            if self.mgr.ip != self.ip:
                self.mgr.ip = self.ip
                self.mgr.disconnect()
            
            # Ensure connected
            if not self.mgr.ssh_client:
                self.mgr.connect()
                
            # Fetch data
            self.mgr.fetch_telemetry()
            
            # Return the raw file_data list from the manager
            self.signals.finished.emit(self.mgr.file_data)
            
        except Exception as e:
            self.signals.error.emit(f"Error fetching Sirius telemetry: {str(e)}")

