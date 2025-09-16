import requests

class UDW:
    def __init__(self):
        self.commands_sent = []
    def send_udw_command_to_printer(self, ip, cmd):
        """
        Send a UDW command to the printer, represented by the cmd argument

        Args:
            ip: the ip of the printer
            cmd: the command to send to the printer

        Returns:
            nothing.

        Effects:
            Will print to the terminal the output.

        """
        cmd_to_send = cmd.strip().replace(" ", "+")
        response = requests.get(f'https://{ip}/UDW/Command?entry={cmd_to_send}%3B', verify=False).text
        print(f"> sent off command: https://{ip}/UDW/Command?entry={cmd_to_send}%3B")
        print(f"> [RESPONSE] \n {response} \n> [END RESPONSE]")