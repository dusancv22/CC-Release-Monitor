#!/usr/bin/env python3
"""
System tray application for CC Release Monitor Bot
Runs the bot in the background with a system tray icon
"""

import sys
import os
import subprocess
import threading
from pathlib import Path

# Try to import pystray, if not available, fall back to simple hidden mode
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("pystray not installed. Install with: pip install pystray pillow")
    print("Running in simple hidden mode instead...")

class BotTrayApp:
    def __init__(self):
        self.bot_process = None
        self.icon = None
        
    def create_icon_image(self):
        """Create a simple icon for the system tray"""
        # Create a simple blue circle icon
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        # Draw a blue circle
        draw.ellipse([8, 8, width-8, height-8], fill='#0088ff', outline='#004488')
        # Add "CC" text
        try:
            draw.text((20, 20), "CC", fill='white')
        except:
            pass  # Font might not be available
        return image
    
    def start_bot(self, icon=None, item=None):
        """Start the bot process"""
        if self.bot_process and self.bot_process.poll() is None:
            print("Bot is already running")
            return
            
        # Start the bot in a subprocess
        bot_path = Path(__file__).parent / "simple_bot.py"
        python_exe = r"C:\Users\Dusan\miniconda3\python.exe"
        
        # Use CREATE_NO_WINDOW flag to hide console on Windows
        if sys.platform == 'win32':
            CREATE_NO_WINDOW = 0x08000000
            self.bot_process = subprocess.Popen(
                [python_exe, str(bot_path)],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            self.bot_process = subprocess.Popen(
                [python_exe, str(bot_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        print("Bot started in background")
    
    def stop_bot(self, icon=None, item=None):
        """Stop the bot process"""
        if self.bot_process and self.bot_process.poll() is None:
            self.bot_process.terminate()
            self.bot_process.wait(timeout=5)
            print("Bot stopped")
        else:
            print("Bot is not running")
    
    def restart_bot(self, icon=None, item=None):
        """Restart the bot process"""
        self.stop_bot()
        self.start_bot()
        print("Bot restarted")
    
    def quit_app(self, icon=None, item=None):
        """Quit the application"""
        self.stop_bot()
        if self.icon:
            self.icon.stop()
        sys.exit(0)
    
    def run_with_tray(self):
        """Run the application with system tray icon"""
        # Create the icon
        image = self.create_icon_image()
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Start Bot", self.start_bot, default=True),
            pystray.MenuItem("Stop Bot", self.stop_bot),
            pystray.MenuItem("Restart Bot", self.restart_bot),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app)
        )
        
        # Create the system tray icon
        self.icon = pystray.Icon(
            "CC Release Monitor",
            image,
            "CC Release Monitor Bot",
            menu
        )
        
        # Start the bot automatically
        self.start_bot()
        
        # Run the icon (this blocks until exit)
        self.icon.run()
    
    def run_hidden(self):
        """Run the bot in hidden mode without tray icon"""
        self.start_bot()
        print("Bot is running in the background (hidden mode)")
        print("Press Ctrl+C to stop...")
        try:
            # Keep the script running
            while True:
                if self.bot_process and self.bot_process.poll() is not None:
                    print("Bot process ended unexpectedly")
                    break
                threading.Event().wait(1)
        except KeyboardInterrupt:
            print("\nStopping bot...")
            self.stop_bot()

def main():
    app = BotTrayApp()
    
    if TRAY_AVAILABLE and sys.platform == 'win32':
        print("Starting CC Release Monitor Bot with system tray icon...")
        app.run_with_tray()
    else:
        print("Starting CC Release Monitor Bot in hidden mode...")
        app.run_hidden()

if __name__ == "__main__":
    main()