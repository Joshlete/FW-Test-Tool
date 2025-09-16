from time import sleep
from sys import path
path.append("G:\\sfte\\env\\non_sirius\\dunetuf")

from LIB_Print import PRINT
from LIB_UDW import UDW_DUNE

# Global configuration
PRINT_JOB_WAIT_TIME = 6  # seconds to wait for print job completion
PRINT_REPORTS_WAIT_TIME = 25  # seconds to wait for print reports to complete

# Print times for pages:
# 100% soaker pages: 6 to 8 seconds
# reports: 20-25 seconds

# Color mapping for print jobs
COLOR_MAP = {
    "CYAN": "C",
    "MAGENTA": "M", 
    "YELLOW": "Y",
    "BLACK": "K"
}

# Color emojis for display
COLOR_EMOJIS = {
    "CYAN": "🔵",
    "MAGENTA": "🔴",
    "YELLOW": "🟡", 
    "BLACK": "⚫"
}

def clean_udw_result(string):
    return int(string.replace(";", " "))

class Soaker:
    def __init__(self):
        self.ip = "15.8.177.144"
        self.print = PRINT(self.ip)
        self.UDW = UDW_DUNE(self.ip, True, False)

    def start(self):
        color = "CYAN"  # Can be CYAN, MAGENTA, YELLOW, or BLACK
        self.print_until_percentage_IIC(color, -1, print_reports=True)

    def printPSR(self):
        """Print Printer Status Report"""
        print(f"\n📋 Printing Printer Status Report (PSR)...")
        self.print.print_psr()
        print(f"✅ PSR print job sent")

    def print10Tap(self):
        """Print 10-Tap diagnostic report"""
        print(f"\n🔧 Printing 10-Tap diagnostic report...")
        self.print.print_10tap()
        print(f"✅ 10-Tap print job sent")

    def print_until_percentage_IIC(self, color, percent, print_reports=False):
        print(f"\n{'='*50}")
        print(f"🖨️  STARTING INK SOAKING FOR {color}")
        print(f"📊 Target: {percent}%")
        print(f"{'='*50}")
        
        while True:
            # Get current ink level for the specific color
            result = self.UDW.udw(cmd=f"constat.get_raw_percent_remaining {color}")
            current_ink_lvl = int(result.split(",")[2].replace(";", " "))
            
            print(f"\n📈 {color} Ink Level: {current_ink_lvl}%, Target: {percent}%")
            
            if current_ink_lvl > percent:
                color_code = COLOR_MAP[color]
                color_emoji = COLOR_EMOJIS[color]
                
                print(f"   {color_emoji} Printing {color} job: {color_code}_out_6x6_pn.pcl")
                self.print.printPCL(f'G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\AmpereXL\\{color_code}_out_6x6_pn.pcl')
                
                print(f"   ⏳ Waiting {PRINT_JOB_WAIT_TIME} seconds for print job completion...")
                sleep(PRINT_JOB_WAIT_TIME)
                print(f"   ✅ Print job completed")
            else:
                print(f"\n🎯 TARGET REACHED!")
                print(f"🛑 {color} ink level ({current_ink_lvl}%) is at or below target ({percent}%)")
                print(f"{'='*50}")
                
                # Print diagnostic reports
                if print_reports:
                    sleep(PRINT_REPORTS_WAIT_TIME/2)
                    self.print10Tap()
                    sleep(PRINT_REPORTS_WAIT_TIME)
                    self.printPSR()
                
                print(f"✅ SOAKING COMPLETE FOR {color}")
                print(f"{'='*50}\n")
                return

    def print_until_percentage_IPH(self, pen, percent):
        print(f"printing to {percent}%.")
        prev_ink_level = 999
        while True:
            result = self.UDW.udw(cmd=f"constat.get_gas_gauge {pen}")
            current_ink_lvl = int(result.split(",")[4].replace(";", " "))
            print("...waiting for ink level change.", end="")
            while current_ink_lvl >= prev_ink_level:
                print(".", end="")
                sleep(3)
            print()
            prev_ink_level = current_ink_lvl
            print(f'pen at: {current_ink_lvl}%')
            if current_ink_lvl > percent:
                if pen == "CMY":
                    print('...printing job 25%_CMY.pcl...')
                    self.print.printPCL('G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid\\25%_CMY.pcl')
                elif pen == "K":
                    print('...printing job ISO_K.pcl...')
                    self.print.printPCL('G:\\iws_tests\\Print\\external\\Ink_Triggers\\PythonScripts\\drivenFiles\\pcl3\\ISO_K.pcl')
            else:
                print(f'...stopping')
                return


    def print_to_t4(self, pen):
        while True:
            print("----------------------------------------")
            if pen == "K":
                if self.did_pass_t4_trigger("K"):
                    print("K Passed T4 trigger. Stopping.")
                    return
                else:
                    self.print.printPCL('C:\\temp\\25%_Black.pcl')
                    sleep(45)
            elif pen == "CMY":
                if self.did_pass_t4_trigger("C") or self.did_pass_t4_trigger("M") or self.did_pass_t4_trigger("Y"):
                    print("CMY Passed T4 trigger. Stopping.")
                    return
                else:
                    self.print.printPCL('C:\\temp\\25%_CMY.pcl')
                    sleep(45)


    def did_pass_t4_trigger(self, color):
        if color == "K":
            dot_cnt = clean_udw_result(self.UDW.udw(cmd=f"ds2.get_by_name DSID_PEN_HISTORY_DS_K_0_MOD_DOT_COUNT_K"))
        else:
            dot_cnt = clean_udw_result(self.UDW.udw(cmd=f"ds2.get_by_name DSID_PEN_HISTORY_DS_CMY_0_MOD_DOT_COUNT_{color}"))
        print(f'checking {color} for passing t4 trigger... dot count: {dot_cnt} | t4 trigger: {self.get_t4_trigger(color)}')
        # now check if t4 was passed and return if did
        return dot_cnt > self.get_t4_trigger(color)


    def get_t4_trigger(self, color):
        if color == "K":
            return clean_udw_result(self.UDW.udw(cmd="pen.get_trigger_for_chamber 1 0 4 0"))
        elif color == "C":
            return clean_udw_result(self.UDW.udw(cmd="pen.get_trigger_for_chamber 0 0 4 0"))
        elif color == "M":
            return clean_udw_result(self.UDW.udw(cmd="pen.get_trigger_for_chamber 0 1 4 0"))
        elif color == "Y":
            return clean_udw_result(self.UDW.udw(cmd="pen.get_trigger_for_chamber 0 2 4 0"))


Soaker().start()