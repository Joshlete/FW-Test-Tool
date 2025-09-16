import pygame
import paramiko
from vncdotool import api
import logging
import threading
import time

logging.basicConfig(level=logging.INFO)

class LiveStream:
    def __init__(self, ip, port=5900, window_size=(800, 600)):
        self.ip = ip
        self.port = port
        self.window_size = window_size
        self.vnc_client = None
        self.ssh_client = None
        self.screen = None
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()

    def connect(self):
        try:
            logging.info(f"Connecting to IP: {self.ip}")

            # Establish SSH connection
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.ip, username="root", password="myroot", timeout=5)
            logging.info("SSH connection successful!")

            # Terminate any existing remoteControlPanel processes
            self.ssh_client.exec_command("pkill remoteControlPanel")
            logging.info("Terminated existing remoteControlPanel processes")

            # Start a new VNC server
            command = "cd /core/bin && ./remoteControlPanel -t /dev/input/event0 &"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8').strip()
                raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")
            logging.info("Started VNC server")

            # Establish VNC connection
            self.vnc_client = api.connect(f"{self.ip}::{self.port}", password=None)
            logging.info("VNC connection successful!")

            print(f">     [Dune] Connected successfully")
            return True
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            return False

    def start(self):
        if not self.connect():
            print("Failed to connect. Exiting.")
            return

        pygame.init()
        self.screen = pygame.display.set_mode(self.window_size)
        pygame.display.set_caption("Dune FPUI Live View")

        self.running = True
        
        # Start VNC update thread
        vnc_thread = threading.Thread(target=self._vnc_update_loop)
        vnc_thread.start()

        self._main_loop()

    def _vnc_update_loop(self):
        while self.running:
            try:
                with self.frame_lock:
                    self.current_frame = self.vnc_client.captureScreen()
            except Exception as e:
                logging.error(f"Error updating VNC frame: {e}")
            time.sleep(0.03)  # Adjust this value to control update frequency

    def _main_loop(self):
        clock = pygame.time.Clock()
        while self.running:
            self._handle_events()
            self._update_display()
            clock.tick(30)  # Limit to 30 FPS

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.stop()

    def _update_display(self):
        with self.frame_lock:
            if self.current_frame:
                pygame_surface = pygame.image.fromstring(self.current_frame, (480, 272), 'RGB')
                self.screen.blit(pygame.transform.scale(pygame_surface, self.window_size), (0, 0))
                pygame.display.flip()

    def stop(self):
        self.running = False
        if self.vnc_client:
            self.vnc_client.disconnect()
        if self.ssh_client:
            try:
                self.ssh_client.exec_command("pkill remoteControlPanel")
                logging.info("Terminated remoteControlPanel processes")
            except Exception as e:
                logging.error(f"Error terminating remoteControlPanel processes: {e}")
            self.ssh_client.close()
        pygame.quit()

if __name__ == "__main__":
    # Example usage
    ip_address = "15.8.177.182"
    live_stream = LiveStream(ip_address)
    live_stream.start()