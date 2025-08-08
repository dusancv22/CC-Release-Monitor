"""
Telegram bot implementation for CC Release Monitor.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, Bot, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError, NetworkError, TimedOut

from .config import Config
from .utils import get_utc_now, format_datetime


logger = logging.getLogger(__name__)


class CCReleaseMonitorBot:
    """CC Release Monitor Telegram Bot."""
    
    def __init__(self, config: Config):
        """
        Initialize the bot.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.application: Optional[Application] = None
        self.is_running = False
        self.start_time = get_utc_now()
        
        # Bot statistics
        self.stats = {
            "commands_processed": 0,
            "errors_handled": 0,
            "uptime_start": self.start_time,
        }
    
    async def initialize(self) -> None:
        """Initialize the bot application."""
        try:
            # Create application
            self.application = (
                Application.builder()
                .token(self.config.telegram_bot_token)
                .build()
            )
            
            # Add command handlers
            await self._setup_handlers()
            
            # Set bot commands
            await self._setup_bot_commands()
            
            logger.info("Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def _setup_handlers(self) -> None:
        """Set up command and message handlers."""
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
        
        # Unknown command handler (should be last)
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self.unknown_command)
        )
        
        logger.info("Bot handlers set up successfully")
    
    async def _setup_bot_commands(self) -> None:
        """Set up bot commands menu."""
        commands = [
            BotCommand("start", "Start the bot and get welcome message"),
            BotCommand("help", "Show help information"),
            BotCommand("status", "Show bot status and statistics"),
        ]
        
        try:
            if self.application and self.application.bot:
                await self.application.bot.set_my_commands(commands)
                logger.info("Bot commands menu set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up bot commands: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        try:
            self.stats["commands_processed"] += 1
            
            welcome_message = (
                "🤖 *CC Release Monitor Bot*\n\n"
                "Welcome! I'm your Claude Code Release Monitor bot.\n\n"
                "🔍 I can help you monitor Claude Code releases and keep you updated "
                "with the latest changes and announcements.\n\n"
                "*Available Commands:*\n"
                "• /help - Show detailed help information\n"
                "• /status - Show bot status and statistics\n\n"
                "📝 *Getting Started:*\n"
                "Use /help to learn more about my features and capabilities.\n\n"
                "💡 *Tip:* I'll automatically notify you about new releases when they're available!"
            )
            
            await update.message.reply_text(
                welcome_message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Start command handled for user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await self._send_error_message(update, "Failed to process start command")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        try:
            self.stats["commands_processed"] += 1
            
            help_message = (
                "📚 *CC Release Monitor Bot Help*\n\n"
                "*Commands:*\n"
                "• `/start` - Start the bot and see welcome message\n"
                "• `/help` - Show this help information\n"
                "• `/status` - Show bot status and statistics\n\n"
                "*Features:*\n"
                "🔔 Automatic release notifications\n"
                "⏰ Configurable check intervals\n"
                "🔇 Quiet hours support\n"
                "📊 Release tracking and statistics\n\n"
                "*About:*\n"
                "This bot monitors Claude Code releases and provides timely notifications "
                "about new versions, updates, and important announcements.\n\n"
                "🛠️ *Status:* Currently in active development\n"
                "📅 *Version:* 1.0.0\n\n"
                "If you encounter any issues or have suggestions, please let us know!"
            )
            
            await update.message.reply_text(
                help_message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Help command handled for user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await self._send_error_message(update, "Failed to process help command")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        try:
            self.stats["commands_processed"] += 1
            
            uptime = get_utc_now() - self.stats["uptime_start"]
            uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
            
            status_message = (
                "📊 *Bot Status*\n\n"
                f"🟢 *Status:* {'Running' if self.is_running else 'Stopped'}\n"
                f"⏱️ *Uptime:* {uptime_str}\n"
                f"🕐 *Started:* {format_datetime(self.stats['uptime_start'])}\n"
                f"📈 *Commands Processed:* {self.stats['commands_processed']}\n"
                f"❌ *Errors Handled:* {self.stats['errors_handled']}\n\n"
                "*Configuration:*\n"
                f"⏲️ Check Interval: {self.config.check_interval_minutes} minutes\n"
                f"🔄 Max Retries: {self.config.max_retries}\n"
                f"🔔 Notifications: {'Enabled' if self.config.enable_notifications else 'Disabled'}\n"
                f"🌙 Quiet Hours: {self.config.quiet_hours_start}:00 - {self.config.quiet_hours_end}:00\n\n"
                "✅ All systems operational"
            )
            
            await update.message.reply_text(
                status_message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Status command handled for user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await self._send_error_message(update, "Failed to process status command")
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown commands."""
        try:
            unknown_message = (
                "❓ *Unknown Command*\n\n"
                "I don't recognize that command. Here are the available commands:\n\n"
                "• /start - Start the bot\n"
                "• /help - Show help information\n"
                "• /status - Show bot status\n\n"
                "Use /help for more detailed information."
            )
            
            await update.message.reply_text(
                unknown_message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Unknown command handled for user {update.effective_user.id}: {update.message.text}")
            
        except Exception as e:
            logger.error(f"Error in unknown command handler: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation."""
        self.stats["errors_handled"] += 1
        
        error = context.error
        logger.error(f"Bot error occurred: {error}")
        
        # Handle specific error types
        if isinstance(error, NetworkError):
            logger.warning("Network error occurred, bot will retry automatically")
        elif isinstance(error, TimedOut):
            logger.warning("Request timed out, bot will retry automatically")
        elif isinstance(error, TelegramError):
            logger.error(f"Telegram API error: {error}")
        else:
            logger.error(f"Unexpected error: {error}")
        
        # Try to notify user if update is available
        if update and update.effective_message:
            try:
                await self._send_error_message(
                    update,
                    "An error occurred while processing your request. Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")
    
    async def _send_error_message(self, update: Update, message: str) -> None:
        """Send error message to user."""
        try:
            error_message = f"⚠️ *Error*\n\n{message}"
            await update.message.reply_text(
                error_message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def start(self) -> None:
        """Start the bot."""
        if not self.application:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        try:
            logger.info("Starting CC Release Monitor Bot...")
            self.is_running = True
            
            # Initialize the application
            await self.application.initialize()
            
            logger.info("Bot started successfully and ready to poll for updates")
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if not self.application:
            return
        
        try:
            logger.info("Stopping CC Release Monitor Bot...")
            self.is_running = False
            
            # Stop and shutdown application
            await self.application.stop()
            await self.application.shutdown()
            
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error while stopping bot: {e}")
    
    async def run_forever(self) -> None:
        """Run the bot until interrupted."""
        try:
            await self.start()
            
            # Start polling - this will run indefinitely until stopped
            await self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping bot...")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
        finally:
            await self.stop()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        return {
            **self.stats,
            "is_running": self.is_running,
            "uptime_seconds": (get_utc_now() - self.stats["uptime_start"]).total_seconds(),
        }