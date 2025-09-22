#!/usr/bin/env python3
"""
System tray application for CC Release Monitor Bot
Runs the bot in the background with a system tray icon
"""

import sys
import os
import subprocess
import threading
import logging
from pathlib import Path
from datetime import datetime

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
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for the tray application"""
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"tray_bot_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("Tray bot application started")
        
    def _candidate_python_paths(self):
        """Yield possible Python executables to run the bot"""
        script_dir = Path(__file__).parent
        candidates = []

        current_exec = Path(sys.executable) if sys.executable else None
        if current_exec:
            candidates.append(current_exec)
            if current_exec.name.lower() == "pythonw.exe":
                candidates.append(current_exec.with_name("python.exe"))

        candidates.extend([
            script_dir / "venv" / "Scripts" / "pythonw.exe",
            script_dir / "venv" / "Scripts" / "python.exe"
        ])

        venv_env = os.environ.get("VIRTUAL_ENV")
        if venv_env:
            venv_dir = Path(venv_env)
            candidates.extend([
                venv_dir / "Scripts" / "pythonw.exe",
                venv_dir / "Scripts" / "python.exe"
            ])

        seen = set()
        for candidate in candidates:
            if not candidate:
                continue
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate

    def resolve_python_executable(self):
        """Determine which Python executable should launch the bot"""
        for candidate in self._candidate_python_paths():
            if candidate.exists():
                return str(candidate)
        return "python"

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
        try:
            if self.bot_process and self.bot_process.poll() is None:
                self.logger.info("Bot is already running")
                return
                
            # Start the bot in a subprocess
            bot_path = Path(__file__).parent / "simple_bot.py"
            python_exe = self.resolve_python_executable()

            if not bot_path.exists():
                self.logger.error(f"Bot script not found at {bot_path}")
                return

            if python_exe != "python" and not Path(python_exe).exists():
                self.logger.error(f"Python executable not found at {python_exe}")
                return

            if python_exe == "python":
                self.logger.warning("Falling back to 'python' from PATH; activate your virtual environment if available.")

            self.logger.info(f"Starting bot: {python_exe} {bot_path}")
            
            # Use CREATE_NO_WINDOW flag to hide console on Windows
            if sys.platform == 'win32':
                CREATE_NO_WINDOW = 0x08000000
                self.bot_process = subprocess.Popen(
                    [python_exe, str(bot_path)],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(Path(__file__).parent)
                )
            else:
                self.bot_process = subprocess.Popen(
                    [python_exe, str(bot_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(Path(__file__).parent)
                )
            
            self.logger.info(f"Bot started in background with PID: {self.bot_process.pid}")
            
            # Start a thread to monitor the process
            threading.Thread(target=self._monitor_bot_process, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            print(f"Failed to start bot: {e}")
    
    def _monitor_bot_process(self):
        """Monitor the bot process and log output"""
        if not self.bot_process:
            return
            
        try:
            # Read stderr in a separate thread to capture startup errors
            while self.bot_process.poll() is None:
                if self.bot_process.stderr:
                    error_line = self.bot_process.stderr.readline()
                    if error_line:
                        error_msg = error_line.decode('utf-8', errors='ignore').strip()
                        if error_msg:
                            self.logger.error(f"Bot stderr: {error_msg}")
                
                # Check if process is still alive
                threading.Event().wait(5)
            
            # Process has ended, log the exit code
            exit_code = self.bot_process.returncode
            if exit_code != 0:
                self.logger.error(f"Bot process ended with exit code: {exit_code}")
                # Try to read any remaining error output
                if self.bot_process.stderr:
                    remaining_errors = self.bot_process.stderr.read().decode('utf-8', errors='ignore')
                    if remaining_errors.strip():
                        self.logger.error(f"Bot final errors: {remaining_errors.strip()}")
            else:
                self.logger.info("Bot process ended normally")
                
        except Exception as e:
            self.logger.error(f"Error monitoring bot process: {e}")
    
    def stop_bot(self, icon=None, item=None):
        """Stop the bot process"""
        try:
            if self.bot_process and self.bot_process.poll() is None:
                self.logger.info("Stopping bot process...")
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
                self.logger.info("Bot stopped")
            else:
                self.logger.info("Bot is not running")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
            if self.bot_process:
                try:
                    self.bot_process.kill()
                    self.logger.info("Bot process killed forcefully")
                except:
                    pass
    
    def restart_bot(self, icon=None, item=None):
        """Restart the bot process"""
        self.logger.info("Restarting bot...")
        self.stop_bot()
        threading.Event().wait(2)  # Wait a bit before restarting
        self.start_bot()
        self.logger.info("Bot restart completed")
    
    def quit_app(self, icon=None, item=None):
        """Quit the application"""
        self.logger.info("Shutting down tray application...")
        self.stop_bot()
        if self.icon:
            self.icon.stop()
        self.logger.info("Tray application shut down")
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
        self.logger.info("Starting system tray with automatic bot launch...")
        self.start_bot()
        
        # Run the icon (this blocks until exit)
        try:
            self.icon.run()
        except Exception as e:
            self.logger.error(f"Error running system tray: {e}")
            self.stop_bot()
            raise
    
    def run_hidden(self):
        """Run the bot in hidden mode without tray icon"""
        self.logger.info("Running in hidden mode without system tray...")
        self.start_bot()
        self.logger.info("Bot is running in the background (hidden mode)")
        try:
            # Keep the script running
            while True:
                if self.bot_process and self.bot_process.poll() is not None:
                    self.logger.error("Bot process ended unexpectedly")
                    break
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received, stopping bot...")
            self.stop_bot()

def main():
    try:
        app = BotTrayApp()
        
        if TRAY_AVAILABLE and sys.platform == 'win32':
            app.logger.info("Starting CC Release Monitor Bot with system tray icon...")
            app.run_with_tray()
        else:
            app.logger.info("pystray not available or not on Windows, starting in hidden mode...")
            app.run_hidden()
    except Exception as e:
        print(f"Fatal error in main: {e}")
        logging.error(f"Fatal error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()