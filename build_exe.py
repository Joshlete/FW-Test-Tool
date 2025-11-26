import subprocess
import os
import sys
import shutil
import glob
from src.version import VERSION

def build():
    print(f"Building FW Test Tool v{VERSION}...")

    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')

    # Find chromium path
    local_app_data = os.environ.get('LOCALAPPDATA')
    playwright_path = os.path.join(local_app_data, 'ms-playwright')
    
    try:
        chromium_paths = glob.glob(os.path.join(playwright_path, 'chromium-*'))
        if not chromium_paths:
            print("Warning: No Chromium found in ms-playwright. EWS Capture might fail.")
            chromium_arg = []
        else:
            chromium_path = chromium_paths[-1] # Get latest
            chromium_name = os.path.basename(chromium_path)
            print(f"Bundling Chromium from: {chromium_path}")
            chromium_arg = ['--add-data', f"{chromium_path}{os.pathsep}browsers/{chromium_name}"]
    except Exception as e:
        print(f"Warning: Failed to locate Chromium: {e}")
        chromium_arg = []

    # Define PyInstaller arguments
    # Use sys.executable to ensure we use the same python environment
    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',
        '--onefile',
        '--console',  # Show console window
        '--name', f"FW Test Tool v{VERSION}",
        '--clean',
        
        # Collect Playwright dependencies
        '--collect-all', 'playwright',
        
        # Explicitly collect PySide6 and its dependencies
        # Using hidden imports often works better than collect-all if the package is not detected correctly
        '--hidden-import', 'PySide6',
        '--hidden-import', 'PySide6.QtCore',
        '--hidden-import', 'PySide6.QtGui',
        '--hidden-import', 'PySide6.QtWidgets',
        '--collect-all', 'PySide6', 
        '--collect-all', 'shiboken6',

        # Include QSS styles
        # format is "source;dest" for Windows
        '--add-data', f"src/ui_qt/styles.qss{os.pathsep}src/ui_qt",
        
    ] + chromium_arg + [
        
        # Add any other assets here if needed
        # '--add-data', f"src/ui_qt/assets{os.pathsep}src/ui_qt/assets",

        # Main entry point
        'main_qt.py'
    ]

    print(f"Running command: {' '.join(args)}")
    
    try:
        subprocess.check_call(args)
        print(f"\nBuild complete! Executable is in dist/FW Test Tool v{VERSION}.exe")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()

