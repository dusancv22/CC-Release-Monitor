#!/usr/bin/env python3
"""
CC Release Monitor - Main entry point.

This script starts the CC Release Monitor Telegram bot.
"""

import asyncio
import signal
import sys
import logging
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config, ConfigError
from src.bot import CCReleaseMonitorBot
from src.utils import setup_logging


logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handle graceful shutdown of the application."""
    
    def __init__(self):
        self.shutdown_requested = False
        self.bot: CCReleaseMonitorBot = None
    
    def signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_names = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}
        signal_name = signal_names.get(signum, f"Signal {signum}")
        
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown_requested = True
        
        if self.bot:
            # Create a new event loop task for shutdown
            asyncio.create_task(self.bot.stop())
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        if sys.platform != 'win32':
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        else:
            # Windows doesn't support SIGTERM, only SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self.signal_handler)


async def main() -> int:
    """Main application entry point."""
    shutdown_handler = GracefulShutdown()
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = Config()
        logger.info(f"Configuration loaded: {config}")
        
        # Setup logging with config
        setup_logging(config.log_level, config.log_directory)
        logger.info("Logging configured successfully")
        
        # Initialize bot
        logger.info("Initializing CC Release Monitor Bot...")
        bot = CCReleaseMonitorBot(config)
        shutdown_handler.bot = bot
        
        await bot.initialize()
        logger.info("Bot initialized successfully")
        
        # Setup signal handlers for graceful shutdown
        shutdown_handler.setup_signal_handlers()
        
        # Start bot
        logger.info("Starting bot...")
        await bot.run_forever()
        
        logger.info("Bot stopped gracefully")
        return 0
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Please check your .env file and ensure all required variables are set.", file=sys.stderr)
        return 1
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    
    finally:
        # Ensure bot is stopped
        if shutdown_handler.bot:
            try:
                await shutdown_handler.bot.stop()
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}")


def run_bot() -> None:
    """Synchronous wrapper for running the bot."""
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            print("ERROR: Python 3.8 or higher is required", file=sys.stderr)
            sys.exit(1)
        
        # Set up initial logging (will be reconfigured later with proper settings)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        logger.info("Starting CC Release Monitor...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {Path.cwd()}")
        
        # Run the main async function
        if sys.platform == 'win32':
            # Windows-specific event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_bot()