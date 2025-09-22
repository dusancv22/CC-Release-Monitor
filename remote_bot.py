#!/usr/bin/env python3
"""
CC Release Monitor with Remote Approval System

Enhanced version of the bot that includes remote approval capabilities
for Claude Code sessions.
"""

import logging
import os
import asyncio
import threading
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Load environment variables
load_dotenv()

# Import our modules
from src.config import Config
from src.github_client import GitHubClient  
from src.version_manager import VersionManager
from src.release_parser import ReleaseParser
from src.utils import setup_logging, format_datetime
from src.bot_approval import register_approval_handlers
from src.ipc_server import run_server

# Configure logging
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
    exit(1)

# Global variables
config = Config()
github_client = GitHubClient(config)
version_manager = VersionManager(config)
release_parser = ReleaseParser()
scheduler = AsyncIOScheduler()
monitoring_active = False
approval_handler = None
ipc_server_thread = None

# Store authorized chat IDs
authorized_chats = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    authorized_chats.add(chat_id)
    
    welcome_message = (
        "🚀 **CC Release Monitor Bot with Remote Approval**\n\n"
        "I monitor the Claude Code repository for updates and provide remote approval for Claude Code sessions.\n\n"
        
        "**📦 Release Monitoring:**\n"
        "• `/check` - Check for new releases\n"
        "• `/latest` - Show latest release info\n"
        "• `/commits` - Show recent commits\n"
        "• `/changelog` - Show changelog updates\n"
        "• `/start_monitoring` - Start automatic monitoring\n"
        "• `/stop_monitoring` - Stop automatic monitoring\n\n"
        
        "**🔐 Remote Approval System:**\n"
        "• `/start_approval` - Start approval monitoring\n"
        "• `/stop_approval` - Stop approval monitoring\n"
        "• `/approval_status` - Show approval statistics\n\n"
        
        "**ℹ️ Other Commands:**\n"
        "• `/help` - Show this help message\n"
        "• `/status` - Show bot status\n"
        "• `/version` - Show version info\n\n"
        
        f"Your Chat ID: `{chat_id}` - add this to AUTHORIZED_USERS in .env"
    )
    
    await update.message.reply_text(welcome_message)
    logger.info(f"Bot started for chat {chat_id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "📚 **Available Commands**\n\n"
        
        "**Basic:**\n"
        "• `/start` - Initialize the bot\n"
        "• `/help` - Show this help message\n"
        "• `/status` - Show bot and monitoring status\n\n"
        
        "**Monitoring:**\n"
        "• `/check` - Manually check for updates\n"
        "• `/latest` - Show latest release details\n"
        "• `/commits [count]` - Show recent commits (default: 5)\n"
        "• `/commit <sha>` - Show specific commit details\n"
        "• `/changelog` - Show recent changelog\n"
        "• `/changelog_latest` - Show latest changelog entry\n"
        "• `/version` - Show version tracking info\n\n"
        
        "**Automatic Monitoring:**\n"
        "• `/start_monitoring` - Enable automatic checks\n"
        "• `/stop_monitoring` - Disable automatic checks\n\n"
        
        "**Remote Approval:**\n"
        "• `/start_approval` - Enable Claude Code approval system\n"
        "• `/stop_approval` - Disable approval system\n"
        "• `/approval_status` - Show approval statistics\n\n"
        
        "When approval is enabled, you'll receive notifications for Claude Code tool use "
        "requests and can approve/deny them remotely."
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send bot status information."""
    chat_id = update.effective_chat.id
    
    # Check IPC server status
    ipc_status = "❌ Offline"
    try:
        import requests
        response = requests.get("http://localhost:8765/", timeout=2)
        if response.status_code == 200:
            ipc_status = "✅ Online"
    except:
        pass
    
    # Get approval monitoring status
    approval_status = "❌ Inactive"
    if approval_handler and approval_handler.is_monitoring:
        approval_status = "✅ Active"
    
    status_message = (
        "📊 **Bot Status**\n\n"
        f"**Release Monitoring:** {'✅ Active' if monitoring_active else '❌ Inactive'}\n"
        f"**Approval Monitoring:** {approval_status}\n"
        f"**IPC Server:** {ipc_status}\n"
        f"**Your Chat ID:** `{chat_id}`\n"
        f"**Authorized:** {'✅ Yes' if chat_id in authorized_chats else '❌ No'}\n\n"
    )
    
    # Add version info
    last_version = version_manager.get_last_known_version()
    if last_version:
        status_message += f"**Latest Version:** {last_version}\n"
    
    # Add statistics
    stats = version_manager.get_statistics()
    status_message += f"**Total Checks:** {stats.get('total_checks', 0)}\n"
    status_message += f"**New Releases Found:** {stats.get('new_releases_found', 0)}\n"
    
    # Add approval statistics if available
    if approval_handler:
        try:
            import requests
            response = requests.get("http://localhost:8765/approval/stats", timeout=2)
            if response.status_code == 200:
                approval_stats = response.json()
                status_message += f"\n**Approval Requests:**\n"
                by_status = approval_stats.get("by_status", {})
                status_message += f"• Total: {approval_stats.get('total', 0)}\n"
                status_message += f"• Pending: {by_status.get('pending', 0)}\n"
                status_message += f"• Approved: {by_status.get('approved', 0)}\n"
                status_message += f"• Denied: {by_status.get('denied', 0)}\n"
        except:
            pass
    
    await update.message.reply_text(status_message, parse_mode='Markdown')


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually check for new releases."""
    await update.message.reply_text("🔍 Checking for new releases...")
    
    try:
        # Check for new releases
        release = await github_client.get_latest_release_async()
        
        if release:
            parsed = release_parser.parse_release(release)
            current_version = parsed.get("version", "Unknown")
            
            # Check if it's new
            is_new = version_manager.update_version(release)
            
            if is_new:
                # Format and send notification
                message = release_parser.format_release_for_notification(parsed, include_body=True)
                await update.message.reply_text(
                    f"🎉 **New Release Found!**\n\n{message}",
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                version_manager.mark_notification_sent(current_version)
            else:
                await update.message.reply_text(
                    f"✅ No new releases. Latest version is still {current_version}",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("❌ Could not fetch release information")
            
    except Exception as e:
        logger.error(f"Error checking releases: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show information about the latest release."""
    try:
        release = await github_client.get_latest_release_async()
        
        if release:
            parsed = release_parser.parse_release(release)
            message = release_parser.format_release_for_notification(parsed, include_body=True)
            
            await update.message.reply_text(
                f"📦 **Latest Release**\n\n{message}",
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text("❌ Could not fetch latest release")
            
    except Exception as e:
        logger.error(f"Error fetching latest release: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def periodic_monitoring() -> None:
    """Periodic monitoring function that runs in background."""
    if not monitoring_active:
        return
    
    logger.info("Running periodic monitoring check...")
    
    try:
        # Check for new releases
        release = await github_client.get_latest_release_async()
        
        if release:
            is_new = version_manager.update_version(release)
            
            if is_new:
                parsed = release_parser.parse_release(release)
                current_version = parsed.get("version", "Unknown")
                
                # Send notification to all authorized chats
                message = release_parser.format_release_for_notification(parsed, include_body=True)
                
                for chat_id in authorized_chats:
                    try:
                        await Application.get_instance().bot.send_message(
                            chat_id=chat_id,
                            text=f"🎉 **New Release Found!**\n\n{message}",
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification to {chat_id}: {e}")
                
                version_manager.mark_notification_sent(current_version)
                
    except Exception as e:
        logger.error(f"Error in periodic monitoring: {e}")


async def start_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start automatic monitoring."""
    global monitoring_active
    
    if monitoring_active:
        await update.message.reply_text("📡 Monitoring is already active")
        return
    
    monitoring_active = True
    authorized_chats.add(update.effective_chat.id)
    
    # Schedule periodic checks
    scheduler.add_job(
        periodic_monitoring,
        trigger=IntervalTrigger(minutes=config.check_interval_minutes),
        id='release_monitor',
        replace_existing=True
    )
    
    if not scheduler.running:
        scheduler.start()
    
    await update.message.reply_text(
        f"✅ **Monitoring Started**\n\n"
        f"I will check for new releases every {config.check_interval_minutes} minutes.\n"
        f"You'll receive notifications when new releases are found.",
        parse_mode='Markdown'
    )
    
    logger.info(f"Started monitoring for chat {update.effective_chat.id}")


async def stop_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop automatic monitoring."""
    global monitoring_active
    
    if not monitoring_active:
        await update.message.reply_text("📡 Monitoring is not active")
        return
    
    monitoring_active = False
    
    # Remove scheduled job
    try:
        scheduler.remove_job('release_monitor')
    except:
        pass
    
    await update.message.reply_text(
        "⏹️ **Monitoring Stopped**\n\n"
        "Automatic checking has been disabled.\n"
        "Use `/start_monitoring` to resume.",
        parse_mode='Markdown'
    )
    
    logger.info(f"Stopped monitoring for chat {update.effective_chat.id}")


def start_ipc_server():
    """Start the IPC server in a separate thread."""
    logger.info("Starting IPC server thread...")
    run_server(host="127.0.0.1", port=8765)


async def post_init(application: Application) -> None:
    """Initialize the bot after startup."""
    global approval_handler, ipc_server_thread
    
    # Start IPC server in background thread
    ipc_server_thread = threading.Thread(target=start_ipc_server, daemon=True)
    ipc_server_thread.start()
    logger.info("IPC server thread started")
    
    # Wait a moment for server to start
    await asyncio.sleep(2)
    
    # Register approval handlers
    approval_handler = register_approval_handlers(application, config)
    
    # Set bot commands
    await application.bot.set_my_commands([
        BotCommand("start", "Initialize the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("status", "Show bot status"),
        BotCommand("check", "Check for new releases"),
        BotCommand("latest", "Show latest release"),
        BotCommand("start_monitoring", "Start automatic monitoring"),
        BotCommand("stop_monitoring", "Stop automatic monitoring"),
        BotCommand("start_approval", "Start approval monitoring"),
        BotCommand("stop_approval", "Stop approval monitoring"),
        BotCommand("approval_status", "Show approval statistics"),
    ])
    
    logger.info("Bot initialization complete")


def main() -> None:
    """Start the bot."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("latest", latest_command))
    application.add_handler(CommandHandler("start_monitoring", start_monitoring_command))
    application.add_handler(CommandHandler("stop_monitoring", stop_monitoring_command))
    
    # Run the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()