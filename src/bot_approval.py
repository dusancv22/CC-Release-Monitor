"""Telegram bot approval handler for Claude Code remote control."""

import asyncio
import logging
import requests
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, 
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Application
)

from src.models.approval import ApprovalQueue, ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalHandler:
    """Handles approval requests from Claude Code via Telegram."""
    
    def __init__(self, config: Any, application: Application):
        """Initialize the approval handler."""
        self.config = config
        self.application = application
        self.queue = ApprovalQueue()
        self.ipc_server_url = "http://localhost:8765"
        
        # Track pending notifications to avoid duplicates
        self.pending_notifications: Set[str] = set()
        
        # Track users waiting for denial reasons
        self.awaiting_denial_reason: Dict[int, str] = {}
        
        # Authorized users (from config or environment)
        self.authorized_users = self._get_authorized_users()
        
        # Start background task for checking pending approvals
        self.monitoring_task = None
        self.is_monitoring = False
        
        logger.info(f"Initialized ApprovalHandler with {len(self.authorized_users)} authorized users")
    
    def _get_authorized_users(self) -> Set[int]:
        """Get list of authorized Telegram user IDs from config."""
        users = set()
        
        # Try to get from environment/config
        user_list = self.config.get("AUTHORIZED_USERS", "")
        if user_list:
            for user_id in user_list.split(","):
                try:
                    users.add(int(user_id.strip()))
                except ValueError:
                    logger.warning(f"Invalid user ID in AUTHORIZED_USERS: {user_id}")
        
        # If no users configured, log warning
        if not users:
            logger.warning("No authorized users configured for remote approval")
        
        return users
    
    async def start_monitoring(self):
        """Start monitoring for new approval requests."""
        if self.is_monitoring:
            logger.info("Approval monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitor_approvals())
        logger.info("Started approval monitoring")
    
    async def stop_monitoring(self):
        """Stop monitoring for approval requests."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped approval monitoring")
    
    async def _monitor_approvals(self):
        """Background task to check for new approval requests."""
        logger.info("Approval monitor task started")
        
        while self.is_monitoring:
            try:
                # Check for pending approvals via IPC server
                response = requests.get(
                    f"{self.ipc_server_url}/approval/pending",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    requests_list = data.get("requests", [])
                    
                    for req_data in requests_list:
                        request_id = req_data["request_id"]
                        
                        # Skip if already notified
                        if request_id in self.pending_notifications:
                            continue
                        
                        # Create ApprovalRequest object
                        request = ApprovalRequest(
                            request_id=request_id,
                            session_id=req_data["session_id"],
                            timestamp=datetime.fromisoformat(req_data["timestamp"]),
                            tool_name=req_data["tool_name"],
                            tool_input=req_data["tool_input"],
                            project_dir=req_data.get("project_dir")
                        )
                        
                        # Send notification
                        await self._send_approval_notification(request)
                        self.pending_notifications.add(request_id)
                
                # Also timeout old requests
                requests.post(
                    f"{self.ipc_server_url}/approval/timeout",
                    json={"seconds": 60},
                    timeout=5
                )
                
            except Exception as e:
                logger.error(f"Error in approval monitor: {e}")
            
            # Wait before next check
            await asyncio.sleep(2)
        
        logger.info("Approval monitor task stopped")
    
    async def _send_approval_notification(self, request: ApprovalRequest):
        """Send approval request notification to authorized users."""
        # Format message
        message = request.format_for_telegram()
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", 
                    callback_data=f"approve:{request.request_id}"
                ),
                InlineKeyboardButton(
                    "❌ Deny", 
                    callback_data=f"deny:{request.request_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📝 Deny with Reason", 
                    callback_data=f"deny_reason:{request.request_id}"
                ),
                InlineKeyboardButton(
                    "ℹ️ Details", 
                    callback_data=f"details:{request.request_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to all authorized users
        for user_id in self.authorized_users:
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info(f"Sent approval request {request.request_id[:8]} to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send approval to user {user_id}: {e}")
    
    async def handle_approval_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle approval/denial button callbacks."""
        query = update.callback_query
        user_id = query.from_user.id
        
        # Check authorization
        if user_id not in self.authorized_users:
            await query.answer("⚠️ You are not authorized to approve/deny requests", show_alert=True)
            return
        
        await query.answer()
        
        # Parse callback data
        data_parts = query.data.split(":", 1)
        if len(data_parts) != 2:
            await query.answer("Invalid callback data", show_alert=True)
            return
        
        action = data_parts[0]
        request_id = data_parts[1]
        
        # Handle different actions
        if action == "approve":
            await self._handle_approve(query, request_id, user_id)
        
        elif action == "deny":
            await self._handle_deny(query, request_id, user_id, reason="Denied by user")
        
        elif action == "deny_reason":
            await self._handle_deny_with_reason(query, request_id, user_id, context)
        
        elif action == "details":
            await self._handle_show_details(query, request_id)
    
    async def _handle_approve(self, query, request_id: str, user_id: int):
        """Handle approval of a request."""
        try:
            # Send approval to IPC server
            response = requests.post(
                f"{self.ipc_server_url}/approval/respond",
                json={
                    "request_id": request_id,
                    "decision": "approve",
                    "user_id": user_id
                },
                timeout=5
            )
            
            if response.status_code == 200:
                await query.edit_message_text(
                    f"✅ **Request Approved**\n\n"
                    f"Request ID: `{request_id[:8]}...`\n"
                    f"Approved by: {query.from_user.first_name}\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}"
                )
                logger.info(f"User {user_id} approved request {request_id[:8]}")
            else:
                await query.edit_message_text(
                    f"⚠️ Failed to approve request: {response.json().get('detail', 'Unknown error')}"
                )
        
        except Exception as e:
            logger.error(f"Error approving request: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def _handle_deny(self, query, request_id: str, user_id: int, reason: str):
        """Handle denial of a request."""
        try:
            # Send denial to IPC server
            response = requests.post(
                f"{self.ipc_server_url}/approval/respond",
                json={
                    "request_id": request_id,
                    "decision": "deny",
                    "reason": reason,
                    "user_id": user_id
                },
                timeout=5
            )
            
            if response.status_code == 200:
                await query.edit_message_text(
                    f"❌ **Request Denied**\n\n"
                    f"Request ID: `{request_id[:8]}...`\n"
                    f"Denied by: {query.from_user.first_name}\n"
                    f"Reason: {reason}\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}"
                )
                logger.info(f"User {user_id} denied request {request_id[:8]}")
            else:
                await query.edit_message_text(
                    f"⚠️ Failed to deny request: {response.json().get('detail', 'Unknown error')}"
                )
        
        except Exception as e:
            logger.error(f"Error denying request: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def _handle_deny_with_reason(self, query, request_id: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle denial with custom reason."""
        # Store the request ID for this user
        self.awaiting_denial_reason[user_id] = request_id
        
        await query.edit_message_text(
            f"📝 **Provide Denial Reason**\n\n"
            f"Please type the reason for denying this request.\n"
            f"Request ID: `{request_id[:8]}...`\n\n"
            f"_Send your reason as a regular message_"
        )
    
    async def _handle_show_details(self, query, request_id: str):
        """Show detailed information about a request."""
        try:
            # Get request details from queue
            request = self.queue.get_request(request_id)
            
            if request:
                details = f"📋 **Request Details**\n\n"
                details += f"**Request ID:** `{request.request_id}`\n"
                details += f"**Session ID:** `{request.session_id}`\n"
                details += f"**Tool:** {request.tool_name}\n"
                details += f"**Timestamp:** {request.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                details += f"**Status:** {request.status}\n\n"
                details += f"**Tool Input:**\n```json\n{json.dumps(request.tool_input, indent=2)[:500]}\n```"
                
                # Add back button
                keyboard = [[
                    InlineKeyboardButton("🔙 Back", callback_data=f"back:{request_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    details,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.answer("Request not found", show_alert=True)
        
        except Exception as e:
            logger.error(f"Error showing details: {e}")
            await query.answer(f"Error: {str(e)}", show_alert=True)
    
    async def handle_denial_reason_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages that might be denial reasons."""
        user_id = update.effective_user.id
        
        # Check if this user is waiting to provide a denial reason
        if user_id not in self.awaiting_denial_reason:
            return
        
        request_id = self.awaiting_denial_reason.pop(user_id)
        reason = update.message.text
        
        try:
            # Send denial with reason to IPC server
            response = requests.post(
                f"{self.ipc_server_url}/approval/respond",
                json={
                    "request_id": request_id,
                    "decision": "deny",
                    "reason": reason,
                    "user_id": user_id
                },
                timeout=5
            )
            
            if response.status_code == 200:
                await update.message.reply_text(
                    f"❌ **Request Denied with Reason**\n\n"
                    f"Request ID: `{request_id[:8]}...`\n"
                    f"Reason: {reason}\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Failed to deny request: {response.json().get('detail', 'Unknown error')}"
                )
        
        except Exception as e:
            logger.error(f"Error processing denial reason: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def approval_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /approval_status command to show statistics."""
        user_id = update.effective_user.id
        
        if user_id not in self.authorized_users:
            await update.message.reply_text("⚠️ You are not authorized to view approval status")
            return
        
        try:
            # Get statistics from IPC server
            response = requests.get(f"{self.ipc_server_url}/approval/stats", timeout=5)
            
            if response.status_code == 200:
                stats = response.json()
                
                message = "📊 **Approval System Status**\n\n"
                message += f"**Monitoring:** {'✅ Active' if self.is_monitoring else '❌ Inactive'}\n"
                message += f"**IPC Server:** ✅ Connected\n\n"
                
                message += "**Statistics:**\n"
                by_status = stats.get("by_status", {})
                message += f"• Pending: {by_status.get('pending', 0)}\n"
                message += f"• Approved: {by_status.get('approved', 0)}\n"
                message += f"• Denied: {by_status.get('denied', 0)}\n"
                message += f"• Timeout: {by_status.get('timeout', 0)}\n"
                message += f"• Total: {stats.get('total', 0)}\n\n"
                
                message += "**By Tool:**\n"
                by_tool = stats.get("by_tool", {})
                for tool, count in by_tool.items():
                    message += f"• {tool}: {count}\n"
                
                message += f"\n**Recent (1h):** {stats.get('recent_hour', 0)} requests"
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("⚠️ Failed to get statistics from IPC server")
        
        except requests.exceptions.ConnectionError:
            await update.message.reply_text(
                "❌ **IPC Server Offline**\n\n"
                "The approval server is not running.\n"
                "Start it with: `python src/ipc_server.py`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def start_approval_monitoring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_approval command."""
        user_id = update.effective_user.id
        
        if user_id not in self.authorized_users:
            await update.message.reply_text("⚠️ You are not authorized to control approval monitoring")
            return
        
        await self.start_monitoring()
        await update.message.reply_text(
            "✅ **Approval Monitoring Started**\n\n"
            "I will now notify you of any Claude Code requests that need approval.",
            parse_mode='Markdown'
        )
    
    async def stop_approval_monitoring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop_approval command."""
        user_id = update.effective_user.id
        
        if user_id not in self.authorized_users:
            await update.message.reply_text("⚠️ You are not authorized to control approval monitoring")
            return
        
        await self.stop_monitoring()
        await update.message.reply_text(
            "⏹️ **Approval Monitoring Stopped**\n\n"
            "I will no longer notify you of Claude Code requests.",
            parse_mode='Markdown'
        )


def register_approval_handlers(application: Application, config: Any) -> ApprovalHandler:
    """Register approval handlers with the Telegram bot application."""
    
    # Create approval handler
    handler = ApprovalHandler(config, application)
    
    # Register command handlers
    application.add_handler(
        CommandHandler("approval_status", handler.approval_status_command)
    )
    application.add_handler(
        CommandHandler("start_approval", handler.start_approval_monitoring_command)
    )
    application.add_handler(
        CommandHandler("stop_approval", handler.stop_approval_monitoring_command)
    )
    
    # Register callback query handler
    application.add_handler(
        CallbackQueryHandler(handler.handle_approval_callback)
    )
    
    # Register text message handler for denial reasons
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handler.handle_denial_reason_message
        )
    )
    
    logger.info("Registered approval handlers")
    return handler