# Claude Code Remote Approval System Design

## Overview
Transform the CC Release Monitor bot into a remote controller for Claude Code sessions, enabling approval/denial of commands through Telegram.

## Architecture Components

### 1. Approval Queue System (`src/approval_queue.py`)
- **SQLite Database** for persistent storage of pending approvals
- **Approval Request Schema:**
  ```python
  {
      "request_id": "uuid",
      "session_id": "claude_session_id",
      "timestamp": "datetime",
      "tool_name": "Bash",
      "command": "rm -rf ./test",
      "tool_input": {...},
      "status": "pending|approved|denied|timeout",
      "response_time": "datetime|null",
      "user_id": "telegram_user_id|null"
  }
  ```

### 2. IPC Communication Layer (`src/ipc_server.py`)
- **HTTP Server** (FastAPI/Flask) running on localhost:8765
- Endpoints:
  - `POST /approval/request` - Hook submits approval request
  - `GET /approval/status/{request_id}` - Hook polls for decision
  - `POST /approval/respond` - Bot sends user decision

### 3. Claude Code Hook (`hooks/remote_approval.py`)
- Intercepts PreToolUse events
- Sends request to IPC server
- Polls for response (with timeout)
- Returns appropriate JSON to Claude Code

### 4. Telegram Bot Enhancement (`src/bot_approval.py`)
- Monitor approval queue
- Send notifications with inline keyboards
- Handle callback queries for approve/deny
- Update queue with decisions

## Implementation Details

### Phase 1: Core Infrastructure

#### 1.1 Approval Queue Database
```python
# src/models/approval.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import sqlite3
import json
import uuid

@dataclass
class ApprovalRequest:
    request_id: str
    session_id: str
    timestamp: datetime
    tool_name: str
    tool_input: Dict[str, Any]
    status: str = "pending"
    response_time: Optional[datetime] = None
    user_id: Optional[int] = None
    decision_reason: Optional[str] = None
    
class ApprovalQueue:
    def __init__(self, db_path: str = "./data/approvals.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        # Create tables if not exists
        pass
    
    def add_request(self, session_id: str, tool_name: str, 
                   tool_input: Dict) -> str:
        # Add new approval request
        pass
    
    def get_pending(self) -> List[ApprovalRequest]:
        # Get all pending approvals
        pass
    
    def update_status(self, request_id: str, status: str, 
                     user_id: int = None, reason: str = None):
        # Update approval status
        pass
```

#### 1.2 IPC Server
```python
# src/ipc_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from typing import Dict, Any

app = FastAPI()

class ApprovalRequestModel(BaseModel):
    session_id: str
    tool_name: str
    tool_input: Dict[str, Any]

class ApprovalResponseModel(BaseModel):
    request_id: str
    decision: str  # "approve", "deny", "ask"
    reason: Optional[str] = None

@app.post("/approval/request")
async def create_approval_request(request: ApprovalRequestModel):
    # Create request in queue
    # Return request_id
    pass

@app.get("/approval/status/{request_id}")
async def get_approval_status(request_id: str):
    # Check status in queue
    # Return decision if available
    pass

@app.post("/approval/respond")
async def submit_approval_response(response: ApprovalResponseModel):
    # Update queue with decision
    pass
```

### Phase 2: Hook Implementation

#### 2.1 PreToolUse Hook
```python
#!/usr/bin/env python3
# hooks/remote_approval.py
import json
import sys
import time
import requests
from typing import Dict, Any

IPC_SERVER = "http://localhost:8765"
TIMEOUT = 55  # seconds (hook timeout is 60s)

def request_approval(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Request approval from remote Telegram bot"""
    
    # Extract relevant data
    session_id = input_data.get("session_id")
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})
    
    # Skip non-sensitive tools
    if tool_name not in ["Bash", "Write", "Edit", "MultiEdit"]:
        return {"continue": True}
    
    try:
        # Submit approval request
        response = requests.post(
            f"{IPC_SERVER}/approval/request",
            json={
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input
            }
        )
        request_id = response.json()["request_id"]
        
        # Poll for approval
        start_time = time.time()
        while time.time() - start_time < TIMEOUT:
            status_response = requests.get(
                f"{IPC_SERVER}/approval/status/{request_id}"
            )
            status_data = status_response.json()
            
            if status_data["status"] != "pending":
                if status_data["status"] == "approved":
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "allow",
                            "permissionDecisionReason": f"Approved via Telegram by user"
                        }
                    }
                elif status_data["status"] == "denied":
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": status_data.get("reason", "Denied via Telegram")
                        }
                    }
            
            time.sleep(1)
        
        # Timeout - ask user locally
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Remote approval timed out"
            }
        }
        
    except Exception as e:
        # On error, fall back to normal flow
        return {"continue": True}

if __name__ == "__main__":
    input_data = json.load(sys.stdin)
    output = request_approval(input_data)
    print(json.dumps(output))
    sys.exit(0)
```

### Phase 3: Telegram Bot Integration

#### 3.1 Bot Approval Handler
```python
# src/bot_approval.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
import json
from typing import Dict, Any

class ApprovalHandler:
    def __init__(self, approval_queue: ApprovalQueue):
        self.queue = approval_queue
        self.pending_notifications = {}
    
    async def check_pending_approvals(self, context: ContextTypes.DEFAULT_TYPE):
        """Check for new approval requests"""
        pending = self.queue.get_pending()
        
        for request in pending:
            if request.request_id not in self.pending_notifications:
                await self.send_approval_request(context, request)
                self.pending_notifications[request.request_id] = True
    
    async def send_approval_request(self, context: ContextTypes.DEFAULT_TYPE, 
                                   request: ApprovalRequest):
        """Send approval request to user"""
        # Format message based on tool type
        if request.tool_name == "Bash":
            command = request.tool_input.get("command", "")
            message = f"🔐 *Claude Code Approval Request*\n\n"
            message += f"**Tool:** Bash Command\n"
            message += f"**Command:**\n```bash\n{command}\n```\n"
            message += f"**Session:** `{request.session_id[:8]}...`\n"
            message += f"**Time:** {request.timestamp.strftime('%H:%M:%S')}"
        else:
            message = f"🔐 *Claude Code Approval Request*\n\n"
            message += f"**Tool:** {request.tool_name}\n"
            message += f"**Details:** {json.dumps(request.tool_input, indent=2)}"
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", 
                    callback_data=f"approve:{request.request_id}"),
                InlineKeyboardButton("❌ Deny", 
                    callback_data=f"deny:{request.request_id}")
            ],
            [
                InlineKeyboardButton("📝 Deny with Reason", 
                    callback_data=f"deny_reason:{request.request_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to authorized users
        for user_id in self.authorized_users:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_approval_callback(self, update: Update, 
                                      context: ContextTypes.DEFAULT_TYPE):
        """Handle approval/denial callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.split(":")
        action = data[0]
        request_id = data[1]
        
        if action == "approve":
            self.queue.update_status(request_id, "approved", 
                                    user_id=query.from_user.id)
            await query.edit_message_text("✅ Command approved!")
            
        elif action == "deny":
            self.queue.update_status(request_id, "denied", 
                                    user_id=query.from_user.id,
                                    reason="Denied by user")
            await query.edit_message_text("❌ Command denied!")
            
        elif action == "deny_reason":
            # Store request_id for next message
            context.user_data['pending_deny'] = request_id
            await query.edit_message_text(
                "Please type the reason for denial:"
            )
```

### Phase 4: Configuration

#### 4.1 Claude Code Settings
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/remote_approval.py",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

#### 4.2 Bot Configuration
```python
# .env additions
ENABLE_REMOTE_APPROVAL=true
APPROVAL_IPC_PORT=8765
APPROVAL_TIMEOUT_SECONDS=55
AUTHORIZED_USERS=123456789,987654321  # Telegram user IDs
```

## Security Considerations

1. **Authentication**: Only authorized Telegram users can approve/deny
2. **Encryption**: Consider TLS for IPC server in production
3. **Timeout Handling**: Automatic timeout after 55 seconds
4. **Audit Logging**: Log all approval decisions with timestamps
5. **Session Isolation**: Ensure approvals are tied to specific sessions

## Benefits

1. **Remote Control**: Manage Claude Code from anywhere via Telegram
2. **Security**: Additional layer of approval for sensitive operations
3. **Audit Trail**: Complete log of all approved/denied actions
4. **Flexibility**: Customize which tools require approval
5. **Mobile Friendly**: Control from phone without access to terminal

## Potential Enhancements

1. **Context Preview**: Show file contents before edits
2. **Batch Approvals**: Approve multiple similar commands at once
3. **Trust Patterns**: Auto-approve certain safe patterns
4. **Session Management**: Start/stop Claude sessions remotely
5. **Real-time Monitoring**: Stream Claude's responses to Telegram
6. **Voice Commands**: Use Telegram voice messages for approval