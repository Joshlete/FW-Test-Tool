import asyncio
import asyncssh
import logging
from transitions.extensions.asyncio import AsyncMachine
from typing import Callable, Optional, List
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

# PrinterConnectionManager class
class PrinterConnectionManager:
    def __init__(self, loop):
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

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
        try:
            logging.info(f"Connecting to SSH at {ip}:{port} using username: {username} and password: {password}")
            self.ssh_client = await asyncssh.connect(
                ip, username=username, 
                password=password, 
                port=port,
                known_hosts=None
            )
            self.notify_listeners(ConnectionEvent.SSH_CONNECTED)
            # Start SSH connection monitoring
            self.ssh_monitor_task = self.loop.create_task(self.monitor_ssh_connection())
            logging.info("SSH monitor task started")
        except Exception as e:
            logging.error(f"SSH connection failed: {e}")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "SSH connection failed"})
            self.machine.set_state('disconnected')  # Remove 'await' if 'set_state' is not async


    async def do_disconnect_ssh(self):
        logging.info("Disconnecting SSH")        
        if self.ssh_client:
            try:
                self.ssh_client.close()
                await self.ssh_client.wait_closed()
                self.ssh_client = None
            except Exception as e:
                logging.error(f"Error during SSH disconnection: {e}")
        else:
            logging.warning("SSH client is already None, skipping disconnection.")
        # Cancel SSH monitor task
        if hasattr(self, 'ssh_monitor_task'):
            self.ssh_monitor_task.cancel()
            try:
                await self.ssh_monitor_task
            except asyncio.CancelledError:
                pass
        self.notify_listeners(ConnectionEvent.SSH_DISCONNECTED)

    async def monitor_ssh_connection(self):
        """
        Periodically check if the SSH connection is still alive.
        """
        try:
            while True:
                logging.info("Sleeping for 5 seconds before checking SSH connection")
                await asyncio.sleep(5)  # Check every 5 seconds
                logging.info("Woke up from sleep, checking SSH connection")
                
                if not self.ssh_client or self.ssh_client._transport is None:
                    logging.warning("SSH connection lost")
                    self.notify_listeners(ConnectionEvent.SSH_DISCONNECTED)
                    await self.disconnect_ssh()
                    break
                else:
                    # Perform a harmless command to check connection
                    logging.info("SSH connection is still active, performing health check")
                    try:
                        await self.ssh_client.run('echo "ping"', check=True)
                    except (asyncssh.DisconnectError, asyncssh.ConnectionLost):
                        logging.warning("SSH connection lost during health check")
                        self.notify_listeners(ConnectionEvent.SSH_DISCONNECTED)
                        await self.disconnect_ssh()
                        break
                    except Exception as e:
                        logging.error(f"Error during SSH health check: {e}")
        except asyncio.CancelledError:
            logging.info("SSH monitor task cancelled")
        except Exception as e:
            logging.error(f"Exception in monitor_ssh_connection: {e}")

    async def do_connect_vnc(self, ip: str, port: int = 5900):
        try:
            logging.info(f"Connecting to VNC at {ip}:{port}")
            # Assuming vncdotool or similar library is used synchronously
            loop = asyncio.get_event_loop()
            self.vnc_client = await loop.run_in_executor(None, self.sync_connect_vnc, ip, port)
            self.notify_listeners(ConnectionEvent.VNC_CONNECTED)
        except Exception as e:
            logging.error(f"VNC connection failed: {e}")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "VNC connection failed"})
            self.machine.set_state('ssh_connected')

    def sync_connect_vnc(self, ip: str, port: int):
        from vncdotool import api
        return api.connect(ip, port)

    async def do_disconnect_vnc(self):
        logging.info("Disconnecting VNC")
        if self.vnc_client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.vnc_client.disconnect)
            self.vnc_client = None
        self.notify_listeners(ConnectionEvent.VNC_DISCONNECTED)

    async def do_disconnect_all(self):
        logging.info("Disconnecting all connections")
        if self.state == 'vnc_connected':
            await self.do_disconnect_vnc()
        if self.state in ['ssh_connected', 'vnc_connected']:
            await self.do_disconnect_ssh()

    # Listener methods
    def notify_listeners(self, event: ConnectionEvent, data: dict = None):
        for listener in self.listeners:
            listener.on_connection_event(event, data)

    def add_listener(self, listener: ConnectionListener):
        self.listeners.append(listener)

    def remove_listener(self, listener: ConnectionListener):
        self.listeners.remove(listener)



## EXAMPLE ##
# async def main():
#     manager = PrinterConnectionManager()
#     listener = MyConnectionListener()
#     manager.add_listener(listener)

#     # Connect via SSH
#     await manager.connect_ssh('192.168.1.100', 'username', 'password')

#     # Wait for some time to observe the connection monitoring
#     await asyncio.sleep(30)  # Wait for 30 seconds

#     # Disconnect all connections
#     await manager.disconnect_all()

# asyncio.run(main())


class MyConnectionListener(ConnectionListener):
    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        if event == ConnectionEvent.SSH_CONNECTED:
            print("SSH connection established.")
        elif event == ConnectionEvent.SSH_DISCONNECTED:
            print("SSH connection disconnected.")
        elif event == ConnectionEvent.SSH_CONNECTION_LOST:
            print("SSH connection lost unexpectedly.")
        # Handle other events as needed
