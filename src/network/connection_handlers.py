import asyncio
import asyncssh
from typing import Optional, List
from enum import Enum
import logging

# Define connection events
class ConnectionEvent(Enum):
    SSH_CONNECTED = 3
    SSH_DISCONNECTED = 4
    VNC_CONNECTED = 5
    VNC_DISCONNECTED = 6
    CONNECTION_ERROR = 7
    SSH_CONNECTION_LOST = 9

# Listener interface
class ConnectionListener:
    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        pass

class ConnectionState(Enum):
    DISCONNECTED = 'disconnected'
    SSH_CONNECTED = 'ssh_connected'
    VNC_CONNECTED = 'vnc_connected'

class PrinterConnectionManager:
    """
    Manages SSH and VNC connections to a printer and notifies listeners of connection events.
    """
    def __init__(self, on_state_change=None):
        self.on_state_change = on_state_change
        self.ssh_client = None
        self.vnc_client = None
        self.ssh_monitor_task = None
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
    def _notify_state_change(self, state, error=None):
        """Simple callback instead of listener pattern"""
        if self.on_state_change:
            self.on_state_change(state, error)

    async def connect_ssh(self, ip: str, username: str, password: str, port: int = 22):
        try:
            print(f"Connecting to SSH at {ip}:{port} using username: {username}")
            self.ssh_client = await asyncssh.connect(
                ip, username=username, 
                password=password, 
                port=port,
                known_hosts=None
            )
            self._notify_state_change('connected')
            return True
        except Exception as e:
            self._notify_state_change('error', str(e))
            return False

    async def disconnect_ssh(self):
        if self.ssh_client:
            self.logger.debug("Closing SSH client")
            self.ssh_client.close()
            self.logger.debug("Awaiting SSH client to close")
            try:
                await asyncio.wait_for(self.ssh_client.wait_closed(), timeout=3)
            except asyncio.TimeoutError:
                self.logger.error("Timeout waiting for SSH client to close")
            self.logger.debug("SSH client closed")
            self.ssh_client = None
            self._notify_state_change('disconnected')
        else:
            self.logger.debug("No SSH client to disconnect")

    async def connect_vnc(self, ip: str, port: int = 5900):
        """
        Public method to establish VNC connection.
        """
        await self._connect_vnc(ip, port)

    async def disconnect_vnc(self):
        """
        Public method to disconnect VNC.
        """
        await self._disconnect_vnc()

    async def _connect_vnc(self, ip: str, port: int = 5900):
        """
        Establishes a VNC connection to the printer.
        """
        try:
            print(f"Connecting to VNC at {ip}:{port}")
            self.vnc_client = await self.loop.run_in_executor(None, self.sync_connect_vnc, ip, port)
            self._notify_state_change('vnc_connected')
        except Exception as e:
            print(f"VNC connection failed: {e}")
            self._notify_state_change('error', "VNC connection failed")
            self._notify_state_change('ssh_connected')

    def sync_connect_vnc(self, ip: str, port: int):
        from vncdotool import api
        return api.connect(ip, port)

    async def _disconnect_vnc(self):
        """
        Disconnects the VNC connection.
        """
        print("Disconnecting VNC")
        if self.vnc_client:
            await self.loop.run_in_executor(None, self.vnc_client.disconnect)
            self.vnc_client = None
        self._notify_state_change('vnc_disconnected')

    async def disconnect_all(self) -> None:
        self.logger.debug("Starting disconnect_all")
        try:
            # Cancel monitor task if it exists and is still running
            if self.ssh_monitor_task:
                if not self.ssh_monitor_task.done():
                    self.logger.debug("Cancelling SSH monitor task")
                    self.ssh_monitor_task.cancel()
                    try:
                        await self.ssh_monitor_task
                        self.logger.debug("SSH monitor task cancelled")
                    except asyncio.CancelledError:
                        self.logger.debug("SSH monitor task cancelled successfully")
                    except Exception as e:
                        self.logger.error(f"Error cancelling SSH monitor task: {e}")
                else:
                    self.logger.debug("SSH monitor task already done")
                self.ssh_monitor_task = None
            else:
                self.logger.debug("No SSH monitor task to cancel")

            # Then disconnect VNC if connected
            if self.vnc_client:
                self.logger.debug("Disconnecting VNC")
                await self._disconnect_vnc()
                self.vnc_client = None
                self.logger.debug("VNC disconnected")
            else:
                self.logger.debug("No VNC client to disconnect")

            # Finally disconnect SSH if connected
            if self.ssh_client:
                self.logger.debug("Disconnecting SSH")
                await self.disconnect_ssh()
                self.logger.debug("SSH disconnected")
            else:
                self.logger.debug("No SSH client to disconnect")

            self._notify_state_change('disconnected')
            self.logger.debug("disconnect_all completed successfully")

        except Exception as e:
            self.logger.error(f"Error during disconnect_all: {e}")
            self._notify_state_change('error', str(e))
        
        self.logger.debug("disconnect_all completed")


