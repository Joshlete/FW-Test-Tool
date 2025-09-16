import paramiko
import socket
from multiprocessing import Event

# Server
def start_ssh_server(stop_event):
    class SSHServer(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            print(f"Attempting login with username: {username} and password: {password}")
            if (username == "root" and password == "myroot"):
                print("Authentication successful")
                return paramiko.AUTH_SUCCESSFUL
            print("Authentication failed")
            return paramiko.AUTH_FAILED

    host_key = paramiko.RSAKey.generate(2048)  # Necessary for SSH protocol
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 2222))
    sock.listen(1)
    sock.settimeout(5)  # Set a timeout for the accept() call
    print("SSH server listening on 127.0.0.1:2222")
    print("Press Ctrl+C to stop the server")

    try:
        while not stop_event.is_set():
            try:
                client, addr = sock.accept()
                print(f"Connected by {addr}")
                try:
                    t = paramiko.Transport(client)
                    t.add_server_key(host_key)  # Required for secure connection
                    server = SSHServer()
                    t.start_server(server=server)
                    channel = t.accept(20)  # Wait for authentication
                    if channel is None:
                        print("Authentication failed.")
                    else:
                        print("Authenticated!")
                        # Keep the channel open for user interaction
                        try:
                            while True:
                                # Read data from the channel
                                data = channel.recv(1024)
                                if not data:
                                    break
                                # Echo the received data back to the client
                                channel.send(data)
                                # Check for a specific command to close the connection
                                if data.strip() == b'exit':
                                    print("User requested to close the connection.")
                                    break
                        except Exception as e:
                            print(f"Error during communication: {e}")
                        finally:
                            channel.close()
                except paramiko.SSHException as e:
                    print(f"SSH Exception: {e}")
                except Exception as e:
                    print(f"Error handling connection: {e}")
                finally:
                    client.close()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error accepting connection: {e}")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down server...")
    finally:
        sock.close()
        print("Server stopped")

if __name__ == "__main__":
    try:
        start_ssh_server(Event())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Exiting...")
    print("Program terminated.")

# Run the client in another terminal with:
# python sockserve.py client
