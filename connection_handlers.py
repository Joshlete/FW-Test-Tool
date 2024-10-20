import paramiko
from vncdotool import api
import logging
from typing import Callable, Optional, List
import socket
import time
import threading
import queue
from enum import Enum
import struct

class SSHHandler:
    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self, ip: str, username: str, password: str, timeout: int = 5) -> bool:
        """
        Establishes an SSH connection to the specified IP using username and password.

        :param ip: The IP address to connect to.
        :param username: The username for SSH authentication.
        :param password: The password for SSH authentication.
        :param timeout: The connection timeout in seconds.
        :return: True if connection is successful, False otherwise.
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Attempt connection with username and password, ignoring publickey authentication
            self.client.connect(ip, username=username, password=password, timeout=timeout, look_for_keys=False, allow_agent=False)
            
            return True
        except paramiko.AuthenticationException:
            logging.error("SSH authentication failed. Please check your username and password.")
            return False
        except Exception as e:
            logging.error(f"SSH connection failed: {e}")
            return False

    def execute_command(self, command: str) -> tuple:
        """
        Executes a command on the connected SSH client.

        :param command: The command to execute.
        :return: A tuple containing (stdin, stdout, stderr) of the executed command.
        """
        if not self.client:
            raise Exception("SSH client not connected")
        return self.client.exec_command(command)

    def disconnect(self):
        """
        Closes the SSH connection.
        """
        if self.client:
            self.client.close()
            self.client = None
            logging.info("Closed SSH connection")

    def is_connected(self) -> bool:
        """
        Checks if the SSH connection is active.

        :return: True if connected, False otherwise.
        """
        return self.client is not None and self.client.get_transport() and self.client.get_transport().is_active()

class VNCHandler:
    def __init__(self):
        self.client: Optional[api.VNCClient] = None

    def connect(self, ip: str, port: int = 5900) -> bool:
        """
        Establishes a VNC connection to the specified IP and port.

        :param ip: The IP address to connect to.
        :param port: The port number for VNC connection.
        :return: True if connection is successful, False otherwise.
        """
        try:
            self.client = api.connect(ip, port)
            return True
        except Exception as e:
            logging.error(f"VNC connection failed: {e}")
            return False

    def capture_screen(self, file_path: str):
        """
        Captures the screen and saves it to the specified file path.

        :param file_path: The path where the screenshot will be saved.
        """
        if not self.client:
            raise Exception("VNC client not connected")
        self.client.captureScreen(file_path)

    def disconnect(self):
        """
        Closes the VNC connection.
        """
        if self.client:
            self.client.disconnect()
            self.client = None

    def is_connected(self) -> bool:
        """
        Checks if the VNC connection is active.

        :return: True if connected, False otherwise.
        """
        if not self.client:
            return False
        try:
            self.client.refreshScreen()
            return True
        except Exception:
            return False

class SocketHandler:
    def __init__(self, on_disconnect: Optional[Callable] = None):
        self.sock: Optional[socket.socket] = None
        self.last_activity = 0
        self.heartbeat_interval = 5  # seconds
        self.watchdog_interval = 30  # seconds
        self.heartbeat_thread = None
        self.watchdog_thread = None
        self.on_disconnect = on_disconnect
        self.heartbeat_lock = threading.Lock()

    def connect(self, ip: str, port: int = 80, timeout: float = 2) -> bool:
        logging.info(f"Connecting socket to {ip}:{port}")
        try:
            self.sock = socket.create_connection((ip, port), timeout=timeout)
            self.last_activity = time.time()
            # self.start_heartbeat() # TODO: heartbeat is failing. Printer might be terminating the connection because of heartbeats. use ssh instead of socket?
            # self.start_watchdog()
            return True
        except Exception as e:
            logging.error(f"Socket connection failed: {e}")
            self.sock = None
            return False

    def start_heartbeat(self):
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def _heartbeat_loop(self):
        while self.is_connected():
            try:
                self.send_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception:
                logging.error("Heartbeat failed, connection might be lost")
                self._handle_disconnect()
                break

    def send_heartbeat(self):
        with self.heartbeat_lock:
            try:
                self.sock.settimeout(2)  # Set a short timeout for the heartbeat
                
                # Prepare the heartbeat message
                heartbeat_msg = b'\x00'
                
                # Log the attempt to send the heartbeat
                print(f"Attempting to send heartbeat: {heartbeat_msg!r}")
                
                # Send the heartbeat and get the number of bytes sent
                bytes_sent = self.sock.send(heartbeat_msg)
                
                # Log the result of the send operation
                if bytes_sent == len(heartbeat_msg):
                    print("Heartbeat sent successfully")
                else:
                    print(f"Partial heartbeat sent: {bytes_sent} out of {len(heartbeat_msg)} bytes")
                
                # Wait for a response
                response = self.sock.recv(1)
                
                # Log the response
                print(f"Received heartbeat response: {response!r}")
                
                # Any response is considered valid
                print("Valid heartbeat response received")
                
                self.last_activity = time.time()
            except socket.timeout:
                print("Heartbeat timed out, but connection might still be alive")
            except ConnectionResetError:
                print("Connection was forcibly closed by the remote host")
                raise
            except Exception as e:
                print(f"Failed to send heartbeat: {e}")
                raise
            finally:
                self.sock.settimeout(None)  # Reset the timeout to default

    def start_watchdog(self):
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop)
        self.watchdog_thread.daemon = True
        self.watchdog_thread.start()

    def _watchdog_loop(self):
        while self.is_connected():
            if time.time() - self.last_activity > self.watchdog_interval:
                logging.warning(f"No activity detected for {self.watchdog_interval} seconds, checking connection")
                if not self._check_connection():
                    logging.error("Connection lost")
                    self._handle_disconnect()
                    break
            time.sleep(self.watchdog_interval / 2)

    def _check_connection(self):
        try:
            with self.heartbeat_lock:
                self.sock.settimeout(5)  # Set a longer timeout for connection check
                # Try to send and receive a small amount of data
                self.sock.send(b'\x00')
                response = self.sock.recv(1)
                print(f"Connection check response: {response!r}")
                self.last_activity = time.time()
                return True  # Any response means the connection is alive
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False
        finally:
            self.sock.settimeout(None)  # Reset the timeout to default

    def is_connected(self) -> bool:
        return self.sock is not None and self.sock.fileno() != -1

    def send(self, data: bytes) -> int:
        if not self.is_connected():
            raise Exception("Socket is not connected")
        result = self.sock.send(data)
        self.last_activity = time.time()
        return result

    def recv(self, buffer_size: int = 1024) -> bytes:
        if not self.is_connected():
            raise Exception("Socket is not connected")
        result = self.sock.recv(buffer_size)
        self.last_activity = time.time()
        return result

    def disconnect(self):
        """
        Safely closes the socket connection, cleans up resources, and verifies disconnection.
        This method can be called multiple times without raising exceptions.
        """
        if self.sock:
            try:
                # Shutdown the socket first
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                # The socket might already be closed
                pass
            finally:
                # Close the socket
                self.sock.close()
                self.sock = None
        
        if self.on_disconnect:
            self.on_disconnect()

    def _handle_disconnect(self):
        self.disconnect()

    def settimeout(self, timeout: float):
        if self.sock:
            self.sock.settimeout(timeout)

    def verify_disconnection(self):
        """
        Verifies that the socket is truly disconnected.
        Returns True if disconnected, False otherwise.
        """
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                # Try to send data (0 bytes) to check if the connection is closed
                if self.sock:
                    self.sock.send(b'')
                # If send succeeds, the connection is still open
                logging.warning(f"Socket still connected (attempt {attempt + 1}/{max_attempts})")
                time.sleep(0.5)  # Wait before next attempt
            except (OSError, AttributeError):
                # OSError or AttributeError (if self.sock is None) indicates the socket is closed
                return True
        return False

class ConnectionEvent(Enum):
    SOCKET_CONNECTED = 1
    SOCKET_DISCONNECTED = 2
    SSH_CONNECTED = 3
    SSH_DISCONNECTED = 4
    VNC_CONNECTED = 5
    VNC_DISCONNECTED = 6
    CONNECTION_ERROR = 7

class ConnectionListener:
    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        pass

class ConnectionState:
    def __init__(self):
        self._lock = threading.Lock()
        self._socket_connected = False
        self._ssh_connected = False
        self._vnc_connected = False

    def set_socket_connected(self, value: bool):
        with self._lock:
            self._socket_connected = value

    def is_socket_connected(self) -> bool:
        with self._lock:
            return self._socket_connected

    def set_ssh_connected(self, value: bool):
        with self._lock:
            self._ssh_connected = value

    def is_ssh_connected(self) -> bool:
        with self._lock:
            return self._ssh_connected

    def set_vnc_connected(self, value: bool):
        with self._lock:
            self._vnc_connected = value

    def is_vnc_connected(self) -> bool:
        with self._lock:
            return self._vnc_connected

class PrinterConnectionManager:
    def __init__(self):
        # Configure logging
        self._configure_logging()
        
        self.socket_handler = SocketHandler(on_disconnect=self._on_socket_disconnect)
        self.ssh_handler = SSHHandler()
        self.vnc_handler = VNCHandler()
        self.connection_state = ConnectionState()
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.listeners: List[ConnectionListener] = []
        self.is_stopping = False
        self.is_user_disconnecting = False
        logging.info("PrinterConnectionManager initialized")

    def _configure_logging(self):
        """
        Configures logging to display messages in the console.
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def start_worker(self):
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logging.info("Worker thread started")

    def _worker_loop(self):
        logging.info("Worker loop started")
        while not self.is_stopping:
            try:
                task = self.task_queue.get(timeout=1)  # 1 second timeout
                logging.debug("Executing task from queue")
                self._execute_task(task)
            except queue.Empty:
                continue  # No task available, continue loop
        logging.info("Worker loop stopped")

    def _execute_task(self, task: Callable):
        try:
            task()
        except Exception as e:
            logging.error(f"Error executing task: {e}")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": str(e)})

    def queue_task(self, task: Callable):
        self.task_queue.put(task)
        logging.debug("Task added to queue")

    def add_listener(self, listener: ConnectionListener):
        self.listeners.append(listener)

    def remove_listener(self, listener: ConnectionListener):
        self.listeners.remove(listener)

    def notify_listeners(self, event: ConnectionEvent, data: dict = None):
        for listener in self.listeners:
            listener.on_connection_event(event, data)

    def connect_socket(self, ip: str, port: int = 80):
        self.queue_task(lambda: self._async_connect_socket(ip, port))

    def _async_connect_socket(self, ip: str, port: int):
        success = self.socket_handler.connect(ip, port)
        if success:
            self.connection_state.set_socket_connected(True)
            self.notify_listeners(ConnectionEvent.SOCKET_CONNECTED)
            logging.info("Socket connection successful")
        else:
            logging.error("Socket connection failed")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "Socket connection failed"})

    def disconnect_socket(self):
        self.queue_task(self._async_disconnect_socket)

    def _async_disconnect_socket(self):
        logging.info("Initiating user-requested socket disconnection")
        self.is_user_disconnecting = True
        try:
            print(">     [PrinterConnectionManager] Disconnecting socket")
            self._handle_socket_disconnection(user_initiated=True)
            self.socket_handler.disconnect()
        finally:
            self.is_user_disconnecting = False

    def _on_socket_disconnect(self):
        if not self.is_user_disconnecting:
            logging.info("Unexpected socket disconnection detected")
            self._handle_socket_disconnection(user_initiated=False)

    def _handle_socket_disconnection(self, user_initiated: bool):
        print(">     [PrinterConnectionManager] Handling socket disconnection")
        if not self.connection_state.is_socket_connected():
            return  # Socket already disconnected, no need to proceed

        self.connection_state.set_socket_connected(False)
        self.notify_listeners(ConnectionEvent.SOCKET_DISCONNECTED)
        
        print(">     [PrinterConnectionManager] Checking VNC and SSH connections")
        if not user_initiated:
            if self.connection_state.is_vnc_connected():
                logging.info("Disconnecting VNC due to unexpected socket disconnection")
                self.queue_task(self._async_disconnect_vnc)
            
            if self.connection_state.is_ssh_connected():
                logging.info("Disconnecting SSH due to unexpected socket disconnection")
                self.queue_task(self._async_disconnect_ssh)

        logging_message = "User initiated socket disconnection" if user_initiated else "Unexpected socket disconnection handled"
        logging.info(f"{logging_message}. VNC and SSH connections checked and disconnected if necessary.")

    def connect_ssh(self, ip: str, username: str, password: str):
        self.queue_task(lambda: self._async_connect_ssh(ip, username, password))

    def _async_connect_ssh(self, ip: str, username: str, password: str):
        logging.info(f"Attempting to connect SSH to {ip}")
        success = self.ssh_handler.connect(ip, username, password)
        if success:
            self.connection_state.set_ssh_connected(True)
            self.notify_listeners(ConnectionEvent.SSH_CONNECTED)
            logging.info("SSH connection successful")
        else:
            logging.error("SSH connection failed")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "SSH connection failed"})

    def disconnect_ssh(self):
        self.queue_task(self._async_disconnect_ssh)

    def _async_disconnect_ssh(self):
        logging.info("Disconnecting SSH")
        if self.connection_state.is_vnc_connected():
            logging.info("Disconnecting VNC before SSH")
            self._async_disconnect_vnc()
        
        self.ssh_handler.disconnect()
        self.connection_state.set_ssh_connected(False)
        self.notify_listeners(ConnectionEvent.SSH_DISCONNECTED)

    def connect_vnc(self, ip: str, port: int = 5900):
        self.queue_task(lambda: self._async_connect_vnc(ip, port))

    def _async_connect_vnc(self, ip: str, port: int):
        logging.info(f"Attempting to connect VNC to {ip}:{port}")
        if not self.connection_state.is_ssh_connected():
            logging.error("Cannot connect VNC: SSH connection not established")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "VNC connection failed: SSH not connected"})
            return

        success = self.vnc_handler.connect(ip, port)
        if success:
            self.connection_state.set_vnc_connected(True)
            self.notify_listeners(ConnectionEvent.VNC_CONNECTED)
            logging.info("VNC connection successful")
        else:
            logging.error("VNC connection failed")
            self.notify_listeners(ConnectionEvent.CONNECTION_ERROR, {"error": "VNC connection failed"})

    def disconnect_vnc(self):
        self.queue_task(self._async_disconnect_vnc)

    def _async_disconnect_vnc(self):
        logging.info("Disconnecting VNC")
        self.vnc_handler.disconnect()
        self.connection_state.set_vnc_connected(False)
        self.notify_listeners(ConnectionEvent.VNC_DISCONNECTED)

    def disconnect_all(self):
        self.queue_task(self._async_disconnect_all)

    def _async_disconnect_all(self):
        logging.info("Disconnecting all active connections")
        
        if self.connection_state.is_vnc_connected():
            self._async_disconnect_vnc()
            logging.info("VNC disconnected")
        
        if self.connection_state.is_ssh_connected():
            self._async_disconnect_ssh()
            logging.info("SSH disconnected")
        
        if self.connection_state.is_socket_connected():
            self._async_disconnect_socket()
            logging.info("Socket disconnected")
        logging.info("All active connections have been disconnected")

    def stop(self):
        logging.info("Stopping PrinterConnectionManager")
        self.is_stopping = True
        if self.worker_thread:
            self.worker_thread.join()
        logging.info("PrinterConnectionManager stopped")
