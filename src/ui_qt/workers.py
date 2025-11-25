from PySide6.QtCore import QObject, Signal, QRunnable, Slot
import requests
import urllib3

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    finished = Signal(object)  # Data returned from the task
    error = Signal(str)        # Error message if failed
    start = Signal()           # Emitted when task starts

class FetchAlertsWorker(QRunnable):
    """
    Worker thread to fetch alerts from the printer.
    """
    def __init__(self, ip_address):
        super().__init__()
        self.ip = ip_address
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        Execute the fetch operation.
        """
        self.signals.start.emit()
        url = f"https://{self.ip}/cdm/alert/v1/alerts"
        
        try:
            # Short timeout to prevent hanging indefinitely
            response = requests.get(url, verify=False, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            # Ensure we return a list
            if isinstance(data, dict):
                # Check common wrapper keys
                if 'alerts' in data:
                    data = data['alerts']
                elif 'elements' in data:
                    data = data['elements']
                else:
                    data = [data] # Wrap single object in list
            
            self.signals.finished.emit(data)
            
        except requests.exceptions.Timeout:
            self.signals.error.emit("Connection timed out. Check IP address.")
        except requests.exceptions.ConnectionError:
            self.signals.error.emit("Failed to connect to printer.")
        except Exception as e:
            self.signals.error.emit(f"Error fetching alerts: {str(e)}")

class FetchTelemetryWorker(QRunnable):
    """
    Worker thread to fetch telemetry from the printer.
    """
    def __init__(self, ip_address):
        super().__init__()
        self.ip = ip_address
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.start.emit()
        # Common telemetry endpoint (this might vary by printer type)
        url = f"https://{self.ip}/cdm/system/v1/telemetry/events"
        
        try:
            response = requests.get(url, verify=False, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            # Ensure list format
            if isinstance(data, dict) and 'events' in data:
                data = data['events']
            elif isinstance(data, dict):
                data = [data]
                
            self.signals.finished.emit(data)
            
        except Exception as e:
            self.signals.error.emit(f"Error fetching telemetry: {str(e)}")

class FetchCDMWorker(QRunnable):
    """
    Worker thread to fetch CDM data from multiple endpoints.
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
            url = f"https://{self.ip}/{endpoint}"
            try:
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                results[endpoint] = response.text
            except Exception as e:
                results[endpoint] = f"Error: {str(e)}"
                errors.append(f"{endpoint}: {str(e)}")

        self.signals.finished.emit(results)
        if errors:
            # We don't want to fail the whole batch if some fail, 
            # but we might want to notify about errors.
            # For now, we'll just let the finished signal carry the error strings in the results.
            pass
