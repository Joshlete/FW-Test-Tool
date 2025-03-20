from sys import path
path.append("G:\\sfte\\env\\non_sirius\\dunetuf")

from dunetuf.job.sendjob import DunePrintJob

# from dunetuf.udw import DuneUnderware

class Print:
    pcl_dict = [
        {
            "name": "100% Black",
            "path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid\\100%_Black.pcl"
        },
        {
            "name": "50% Black",
            "path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid\\50%_Black.pcl"
        },
        {
            "name": "25% CMY",
            "path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid\\25%_CMY.pcl"
        }
    ]

    def __init__(self, ip_address):
        self.ip = ip_address
        self.print = DunePrintJob(self.ip, 9100)

    def send_job(self, filepath):
        print(f"> [Print.send_job] Sending print job. File: {filepath}")
        self.print.send_job(filepath, noHeaders=True, verbose=True, asyncPrint=True)