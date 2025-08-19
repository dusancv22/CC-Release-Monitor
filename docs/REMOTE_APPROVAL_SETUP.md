# Remote Approval System Setup Guide

## Overview

The Remote Approval System allows you to control Claude Code sessions remotely through Telegram. When Claude Code attempts to use certain tools (like running bash commands or editing files), you'll receive a notification on Telegram and can approve or deny the action from your phone or any device with Telegram.

## Features

- 🔐 **Remote Control**: Approve/deny Claude Code actions from anywhere
- 📱 **Mobile Friendly**: Works perfectly on phone via Telegram
- 🎯 **Selective Filtering**: Auto-approve safe operations, require approval for sensitive ones
- 📊 **Statistics**: Track all approval requests and decisions
- ⏱️ **Timeout Handling**: Automatic fallback to local approval after timeout
- 🔍 **Detailed Information**: View full command/file details before approving

## Prerequisites

1. Python 3.9 or higher
2. Telegram Bot Token (from @BotFather)
3. Your Telegram User ID

## Installation

### Step 1: Install Dependencies

```bash
pip install -r CC-Release-Monitor/requirements.txt
```

### Step 2: Configure Environment

1. Copy `.env.example` to `.env`:
```bash
cp CC-Release-Monitor/.env.example .env
```

2. Edit `.env` and add:
```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Get your user ID by starting the bot and sending /start
AUTHORIZED_USERS=your_telegram_user_id_here

# Optional
APPROVAL_IPC_PORT=8765
APPROVAL_TIMEOUT_SECONDS=55
```

### Step 3: Configure Claude Code Hook

The hook is already configured in `.claude/settings.json`. This file tells Claude Code to use our approval system for all tool uses.

To enable the hook in Claude Code:
1. Ensure this repository is your current project in Claude Code
2. The hook will automatically activate for this project

To disable temporarily:
- Rename `.claude/settings.json` to `.claude/settings.json.disabled`

## Usage

### Starting the System

#### Windows:
```batch
start_remote_bot.bat
```

#### Linux/Mac:
```bash
python remote_bot.py
```

This starts:
1. The Telegram bot
2. The IPC server (port 8765)
3. Approval monitoring system

### Telegram Commands

Once the bot is running, send these commands in Telegram:

- `/start` - Initialize bot and get your User ID
- `/start_approval` - Enable approval monitoring
- `/approval_status` - Check system statistics
- `/stop_approval` - Disable approval monitoring

### Approval Workflow

1. **Claude Code attempts an action** (e.g., running a bash command)

2. **You receive a Telegram notification** with:
   - Tool name and description
   - Command or file details
   - Session information
   - Approval buttons

3. **You choose an action**:
   - ✅ **Approve** - Allow the action
   - ❌ **Deny** - Block the action
   - 📝 **Deny with Reason** - Provide feedback to Claude
   - ℹ️ **Details** - View more information

4. **Claude Code receives your decision** and proceeds accordingly

### Example Notification

```
🔐 Claude Code Approval Request

Tool: Bash Command
Description: Install Python packages
Command:
```bash
pip install fastapi uvicorn
```

Session: abc123...
Time: 14:32:15
Request ID: def456...

[✅ Approve] [❌ Deny]
[📝 Deny with Reason] [ℹ️ Details]
```

## Auto-Approval Rules

The system automatically approves certain safe operations:

### Safe Tools (Auto-Approved):
- `Read` - Reading files
- `Glob` - File pattern matching
- `Grep` - Searching files
- `LS` - Listing directories
- `TodoWrite` - Managing todos

### Safe Bash Commands (Auto-Approved):
- `ls`, `pwd`, `echo`, `date`, `which`, `where`

### Always Require Approval:
- Commands containing: `rm`, `del`, `format`, `kill`, `sudo`
- File writes to system directories
- Web access and API calls

## Security Considerations

1. **User Authorization**: Only Telegram users listed in `AUTHORIZED_USERS` can approve/deny
2. **Timeout Protection**: Requests timeout after 55 seconds, falling back to local approval
3. **Session Isolation**: Each request is tied to a specific Claude Code session
4. **Audit Trail**: All decisions are logged with timestamps and user IDs

## Troubleshooting

### Bot doesn't receive notifications

1. Check IPC server is running:
```bash
curl http://localhost:8765/
```

2. Verify hook is active:
```bash
# Check if hook file exists and is executable
ls -la .claude/hooks/remote_approval.py
```

3. Check logs:
```bash
# Hook logs
cat ~/.claude/hooks/remote_approval.log

# Bot logs
cat ./logs/bot.log
```

### "Not authorized" error

1. Get your User ID: Send `/start` to the bot
2. Add it to `.env`: `AUTHORIZED_USERS=123456789`
3. Restart the bot

### Requests timing out

- Ensure you have Telegram notifications enabled
- Check network connectivity
- Reduce `APPROVAL_TIMEOUT_SECONDS` if needed

## Advanced Configuration

### Custom Approval Rules

Edit `.claude/hooks/remote_approval.py` to customize:

```python
# Add tools that need approval
SENSITIVE_TOOLS = [
    "Bash",
    "Write",
    "YourCustomTool",
]

# Add safe commands
safe_commands = ["ls", "pwd", "your_safe_command"]
```

### Multiple Users

Add multiple user IDs separated by commas:
```env
AUTHORIZED_USERS=123456789,987654321,555555555
```

### Change IPC Port

If port 8765 is in use:
```env
APPROVAL_IPC_PORT=9876
```

Also update in `.claude/hooks/remote_approval.py`:
```python
IPC_SERVER = "http://localhost:9876"
```

## Testing

### Test the Hook Manually

```bash
# Create test input
echo '{"session_id":"test","tool_name":"Bash","tool_input":{"command":"echo test"}}' | python .claude/hooks/remote_approval.py
```

### Test IPC Server

```bash
# Check health
curl http://localhost:8765/

# Get statistics
curl http://localhost:8765/approval/stats
```

### Test End-to-End

1. Start the bot: `python remote_bot.py`
2. In Telegram: `/start_approval`
3. In Claude Code: Try to run a bash command
4. Approve/deny in Telegram
5. Verify Claude Code receives decision

## Architecture

```
Claude Code Session
        ↓
PreToolUse Hook (.claude/hooks/remote_approval.py)
        ↓
IPC Server (localhost:8765)
        ↓
Approval Queue (SQLite)
        ↓
Telegram Bot
        ↓
Your Phone/Device
        ↓
Approval Decision
        ↓
Claude Code Continues/Stops
```

## Uninstalling

To remove the remote approval system:

1. Stop the bot (Ctrl+C)
2. Remove or rename `.claude/settings.json`
3. Delete approval database: `rm ./data/approvals.db`
4. Remove hooks: `rm -rf .claude/hooks/`

## Support

For issues or questions:
1. Check the logs in `./logs/` and `~/.claude/hooks/`
2. Verify all services are running with `/status` command
3. Ensure your Telegram User ID is authorized

## Future Enhancements

Planned features:
- 🎯 Pattern-based auto-approval rules
- 📊 Detailed analytics dashboard
- 🔔 Notification grouping for batch approvals
- 🎤 Voice command support
- 📱 Mobile app for faster approvals
- 🔄 Session management (pause/resume Claude Code)
- 📺 Real-time streaming of Claude's output