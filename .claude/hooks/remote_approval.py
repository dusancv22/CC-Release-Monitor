#!/usr/bin/env python3
"""
Claude Code Remote Approval Hook

This hook intercepts tool use requests from Claude Code and sends them
to the Telegram bot for remote approval.
"""

import json
import sys
import time
import requests
from typing import Dict, Any, Optional
import logging
from pathlib import Path

# Configure logging
log_file = Path(__file__).parent / "remote_approval.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
IPC_SERVER = "http://localhost:8765"
TIMEOUT = 55  # seconds (hook timeout is 60s)
POLL_INTERVAL = 1  # seconds

# Tools that require approval
SENSITIVE_TOOLS = [
    "Bash",           # Shell commands
    "Write",          # File creation
    "Edit",           # File editing
    "MultiEdit",      # Multiple file edits
    "Task",           # Subagent tasks
    "WebFetch",       # Web access
    "WebSearch",      # Web searches
]

# Tools that should be auto-approved (safe operations)
SAFE_TOOLS = [
    "Read",           # Reading files
    "Glob",           # File pattern matching
    "Grep",           # Searching
    "LS",             # Listing directories
    "TodoWrite",      # Todo management
]


def should_require_approval(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Determine if a tool use should require approval."""
    
    # Always approve safe tools
    if tool_name in SAFE_TOOLS:
        return False
    
    # Check if tool is in sensitive list
    if tool_name not in SENSITIVE_TOOLS:
        return False
    
    # Additional filtering based on tool input
    if tool_name == "Bash":
        command = tool_input.get("command", "").lower()
        # Auto-approve certain safe commands
        safe_commands = ["ls", "pwd", "echo", "date", "which", "where"]
        if any(command.startswith(cmd) for cmd in safe_commands):
            return False
        # Always require approval for dangerous commands
        dangerous_commands = ["rm", "del", "format", "kill", "sudo"]
        if any(cmd in command for cmd in dangerous_commands):
            return True
    
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        # Auto-approve writing to certain safe locations
        if "/tmp/" in file_path or "\\temp\\" in file_path.lower():
            return False
    
    return True


def request_approval(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Request approval from remote Telegram bot."""
    
    # Extract relevant data
    session_id = input_data.get("session_id", "unknown")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    
    logger.info(f"Processing {tool_name} request for session {session_id[:8]}...")
    
    # Check if approval is needed
    if not should_require_approval(tool_name, tool_input):
        logger.info(f"Auto-approving {tool_name} (safe operation)")
        return {"continue": True}
    
    try:
        # Submit approval request to IPC server
        logger.info(f"Requesting approval for {tool_name}")
        response = requests.post(
            f"{IPC_SERVER}/approval/request",
            json={
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to create approval request: {response.text}")
            # Fall back to local approval
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "Remote approval server unavailable"
                }
            }
        
        request_id = response.json()["request_id"]
        logger.info(f"Created approval request {request_id[:8]}...")
        
        # Poll for approval with timeout
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < TIMEOUT:
            try:
                status_response = requests.get(
                    f"{IPC_SERVER}/approval/status/{request_id}",
                    timeout=5
                )
                
                if status_response.status_code != 200:
                    logger.error(f"Failed to get status: {status_response.text}")
                    time.sleep(POLL_INTERVAL)
                    continue
                
                status_data = status_response.json()
                current_status = status_data.get("status", "pending")
                
                if current_status != last_status:
                    logger.info(f"Request {request_id[:8]} status: {current_status}")
                    last_status = current_status
                
                if current_status == "approved":
                    logger.info(f"Request approved via Telegram")
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "allow",
                            "permissionDecisionReason": "Approved remotely via Telegram"
                        }
                    }
                    
                elif current_status == "denied":
                    reason = status_data.get("reason", "Denied via Telegram")
                    logger.info(f"Request denied: {reason}")
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason
                        }
                    }
                
                time.sleep(POLL_INTERVAL)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error polling for status: {e}")
                time.sleep(POLL_INTERVAL)
        
        # Timeout - ask user locally
        logger.warning(f"Request {request_id[:8]} timed out after {TIMEOUT}s")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"Remote approval timed out after {TIMEOUT}s"
            }
        }
        
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to IPC server - is it running?")
        # Server not available, fall back to normal flow
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Remote approval server not running"
            }
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in approval hook: {e}", exc_info=True)
        # On unexpected error, fall back to normal flow
        return {"continue": True}


def main():
    """Main entry point for the hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)
        
        # Only process PreToolUse events
        hook_event = input_data.get("hook_event_name", "")
        if hook_event != "PreToolUse":
            # Not our event, continue normally
            sys.exit(0)
        
        # Process approval request
        output = request_approval(input_data)
        
        # Return response to Claude Code
        print(json.dumps(output))
        sys.exit(0)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        print(json.dumps({
            "continue": True,
            "suppressOutput": True
        }))
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Hook failed: {e}", exc_info=True)
        # On any error, don't block Claude
        print(json.dumps({
            "continue": True,
            "suppressOutput": True
        }))
        sys.exit(0)


if __name__ == "__main__":
    main()