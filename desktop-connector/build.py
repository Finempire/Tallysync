#!/usr/bin/env python3
"""Build script for creating Windows executable"""
import PyInstaller.__main__
import os

# Change to the script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

PyInstaller.__main__.run([
    'connector.py',
    '--onefile',
    '--name=TallySyncConnector',
    '--add-data=connector_config.example.json;.',
    '--hidden-import=requests',
    '--hidden-import=tkinter',
    '--windowed',  # GUI mode, no console window
    '--clean',
])

print("\n" + "="*50)
print("Build complete!")
print("Executable: dist/TallySyncConnector.exe")
print("="*50)
