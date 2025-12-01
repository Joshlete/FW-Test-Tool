import json
import paramiko
from typing import List, Dict
import re

class TelemetryManager:
    def __init__(self, ip: str):
        self.ip = ip
        self.ssh_client = None
        self.file_data = []
        
    def connect(self) -> None:
        """Establish SSH connection to the device"""
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.ip, username='root', password='myroot', timeout=5)

    def disconnect(self) -> None:
        """Properly close SSH connection"""
        print("DEBUG: Disconnecting SSH client")
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
        self.file_data = []

    def update_ip(self, new_ip: str) -> None:
        """Update IP address and reset connection"""
        if self.ip != new_ip:
            self.disconnect()
            self.ip = new_ip

    def fetch_telemetry(self) -> List[Dict]:
        """Fetch and parse telemetry data from device using bulk remote operation"""
        if not self.ssh_client:
            raise ConnectionError("Not connected to device")

        # Single command to get all file contents with markers
        bulk_command = (
            "cd /mnt/encfs/cdm_eventing/supply/ && "
            "for f in event_*; do "
            "echo '===FILE_START==='; "
            "echo \"$f\"; "
            "cat \"$f\"; "
            "echo '===FILE_END==='; "
            "done"
        )
        
        # Execute single command to get all data
        stdin, stdout, stderr = self.ssh_client.exec_command(bulk_command)
        bulk_output = stdout.read().decode('utf-8').strip()
        
        # Handle empty response case
        if not bulk_output:
            self.file_data = []
            return self.file_data

        # Split output into individual files using markers
        file_blocks = re.split(r'===FILE_START===\n(.*?)\n(.*?)===FILE_END===', 
                              bulk_output, flags=re.DOTALL)
        
        self.file_data = []
        for i in range(0, len(file_blocks)-1, 3):
            # Handle potential empty blocks from split
            if i+2 >= len(file_blocks):
                continue
                
            filename = file_blocks[i+1].strip()
            content = file_blocks[i+2].strip()

            # Skip empty content blocks
            if not content:
                continue
                
            try:
                data = json.loads(content)
                self.file_data.append({
                    'filename': filename,
                    'sequenceNumber': data.get('sequenceNumber', ''),
                    'color': data.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', ''),
                    'reasons': data.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', []),
                    'trigger': data.get('eventDetail', {}).get('notificationTrigger', 'Unknown'),
                    'raw_data': data
                })
            except json.JSONDecodeError as e:
                print(f"Failed to parse {filename}: {str(e)}")
                self.file_data.append({
                    'filename': filename,
                    'error': f"Invalid JSON: {str(e)}"
                })
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                self.file_data.append({
                    'filename': filename,
                    'error': str(e)
                })

        self.file_data.sort(key=lambda x: int(x.get('sequenceNumber', 0)), reverse=True)
        return self.file_data

    def get_telemetry_data(self) -> List[Dict]:
        """Get cached telemetry data"""
        return self.file_data

    def save_telemetry_file(self, index: int, save_path: str) -> None:
        """Save specific telemetry file to local path"""
        if index < 0 or index >= len(self.file_data):
            raise IndexError("Invalid telemetry index")
            
        file_info = self.file_data[index]
        with open(save_path, 'w') as f:
            pretty = json.dumps(file_info['raw_data'], indent=4)
            if not pretty.endswith('\n'):
                pretty += '\n'
            f.write('\t' + pretty.replace('\n', '\n\t'))

    def delete_telemetry_file(self, index: int) -> None:
        """Delete specific telemetry file from device"""
        if index < 0 or index >= len(self.file_data):
            raise IndexError("Invalid telemetry index")
            
        # Get filename from our stored data
        filename = self.file_data[index]['filename']
        
        # Use filename for actual deletion command
        stdin, stdout, stderr = self.ssh_client.exec_command(
            f"rm /mnt/encfs/cdm_eventing/supply/{filename}"
        )
        if stderr.channel.recv_exit_status() != 0:
            raise RuntimeError(stderr.read().decode())