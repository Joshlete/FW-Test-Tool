import asyncio
import asyncssh
import logging
from transitions.extensions.asyncio import AsyncMachine
from typing import Optional, List
from enum import Enum

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

class PrinterConnectionManager:
    """
    Manages SSH and VNC connections to a printer and notifies listeners of connection events.
    """
    def __init__(self, loop):
        self.loop = loop
        self.listeners: List[ConnectionListener] = []
        self.ssh_client: Optional[asyncssh.SSHClientConnection] = None
        self.vnc_client: Optional[object] = None  # Replace 'object' with actual VNC client type if available

        # Define states and transitions
        states = ['disconnected', 'ssh_connected', 'vnc_connected']
        transitions = [
            {'trigger': 'connect_ssh', 'source': 'disconnected', 'dest': 'ssh_connected', 'before': 'do_connect_ssh'},
            {'trigger': 'disconnect_ssh', 'source': '*', 'dest': 'disconnected', 'before': 'do_disconnect_ssh'},
            {'trigger': 'connect_vnc', 'source': 'ssh_connected', 'dest': 'vnc_connected', 'before': 'do_connect_vnc'},
            {'trigger': 'disconnect_vnc', 'source': '*', 'dest': 'ssh_connected', 'before': 'do_disconnect_vnc'},
            {'trigger': 'disconnect_all', 'source': '*', 'dest': 'disconnected', 'before': 'do_disconnect_all'},
        ]

        self.machine = AsyncMachine(model=self, states=states, transitions=transitions, initial='disconnected')

    # Connection methods
    async def do_connect_ssh(self, ip: str, username: str, password: str, port: int = 22):
        """
        Establishes an SSH connection to the printer.
        """
        try:
            print(f"Connecting to SSH at {ip}:{port} using username: {username}")
            self.ssh_client = await asyncssh.connect(
                ip, username=username, 
                password=password, 
                port=port,
                known_hosts=None
            )
            self.notify_listeners(ConnectionEvent.SSH_CONNECTED)
            self.ssh_monitor_task = self.loop.create_task(self.monitor_ssh_connection())
            print("SSH monitor task started")
            return True
        except Exception as e:
            print(f"SSH connection failed: {e}")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "SSH connection failed"})
            await self.machine.set_state('disconnected')

    async def do_disconnect_ssh(self):
        """
        Disconnects the SSH connection.
        """
        print("Disconnecting SSH")        
        if self.ssh_client:
            try:
                self.ssh_client.close()
                await self.ssh_client.wait_closed()
                self.ssh_client = None
            except Exception as e:
                print(f"Error during SSH disconnection: {e}")
        else:
            print("SSH client is already None, skipping disconnection.")
        if hasattr(self, 'ssh_monitor_task'):
            self.ssh_monitor_task.cancel()
            try:
                await self.ssh_monitor_task
            except asyncio.CancelledError:
                pass
        self.notify_listeners(ConnectionEvent.SSH_DISCONNECTED)

    async def monitor_ssh_connection(self):
        """
        Periodically checks if the SSH connection is still alive.
        """
        try:
            while self.ssh_client and not self.ssh_client._transport.is_closing():
                await asyncio.sleep(5)
                try:
                    await self.ssh_client.run('echo "ping"', check=True)
                except (asyncssh.DisconnectError, asyncssh.ConnectionLost):
                    print("SSH connection lost during health check")
                    self.notify_listeners(ConnectionEvent.SSH_CONNECTION_LOST)
                    await self.disconnect_ssh()
                    break
                except Exception as e:
                    print(f"Error during SSH health check: {e}")
        except asyncio.CancelledError:
            print("SSH monitor task cancelled")
        except Exception as e:
            print(f"Exception in monitor_ssh_connection: {e}")

    async def do_connect_vnc(self, ip: str, port: int = 5900):
        """
        Establishes a VNC connection to the printer.
        """
        try:
            print(f"Connecting to VNC at {ip}:{port}")
            self.vnc_client = await self.loop.run_in_executor(None, self.sync_connect_vnc, ip, port)
            self.notify_listeners(ConnectionEvent.VNC_CONNECTED)
        except Exception as e:
            print(f"VNC connection failed: {e}")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "VNC connection failed"})
            await self.machine.set_state('ssh_connected')

    def sync_connect_vnc(self, ip: str, port: int):
        from vncdotool import api
        return api.connect(ip, port)

    async def do_disconnect_vnc(self):
        """
        Disconnects the VNC connection.
        """
        print("Disconnecting VNC")
        if self.vnc_client:
            await self.loop.run_in_executor(None, self.vnc_client.disconnect)
            self.vnc_client = None
        self.notify_listeners(ConnectionEvent.VNC_DISCONNECTED)

    async def do_disconnect_all(self):
        """
        Disconnects all active connections.
        """
        print("Disconnecting all connections")
        if self.state == 'vnc_connected':
            await self.do_disconnect_vnc()
        if self.state in ['ssh_connected', 'vnc_connected']:
            await self.do_disconnect_ssh()

    # Listener methods
    def notify_listeners(self, event: ConnectionEvent, data: dict = None):
        """
        Notifies all registered listeners of a connection event.
        """
        for listener in self.listeners:
            listener.on_connection_event(event, data)

    def add_listener(self, listener: ConnectionListener):
        """
        Adds a listener to receive connection events.
        """
        self.listeners.append(listener)

    def remove_listener(self, listener: ConnectionListener):
        """
        Removes a listener.
        """
        self.listeners.remove(listener)
    
    async def stop_connections(self):
        """
        Stops all ongoing connections without shutting down the asyncio event loop.
        """
        print("Stopping PrinterConnectionManager")
        if hasattr(self, 'ssh_monitor_task'):
            self.ssh_monitor_task.cancel()
            try:
                await self.ssh_monitor_task
            except asyncio.CancelledError:
                pass
        await self.do_disconnect_all()
        print("PrinterConnectionManager stopped")
