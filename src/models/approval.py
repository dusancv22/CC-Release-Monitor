"""Approval request models and queue management for remote Claude Code control."""

import sqlite3
import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    """Represents an approval request from Claude Code."""
    
    request_id: str
    session_id: str
    timestamp: datetime
    tool_name: str
    tool_input: Dict[str, Any]
    status: str = "pending"  # pending, approved, denied, timeout
    response_time: Optional[datetime] = None
    user_id: Optional[int] = None
    decision_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['response_time'] = self.response_time.isoformat() if self.response_time else None
        data['tool_input'] = json.dumps(self.tool_input)
        return data
    
    @classmethod
    def from_row(cls, row: tuple) -> 'ApprovalRequest':
        """Create from database row."""
        return cls(
            request_id=row[0],
            session_id=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            tool_name=row[3],
            tool_input=json.loads(row[4]),
            status=row[5],
            response_time=datetime.fromisoformat(row[6]) if row[6] else None,
            user_id=row[7],
            decision_reason=row[8]
        )
    
    def format_for_telegram(self) -> str:
        """Format request for Telegram notification."""
        if self.tool_name == "Bash":
            command = self.tool_input.get("command", "")
            description = self.tool_input.get("description", "")
            message = f"🔐 **Claude Code Approval Request**\n\n"
            message += f"**Tool:** Bash Command\n"
            if description:
                message += f"**Description:** {description}\n"
            message += f"**Command:**\n```bash\n{command}\n```\n"
        elif self.tool_name in ["Write", "Edit", "MultiEdit"]:
            file_path = self.tool_input.get("file_path", "Unknown")
            message = f"🔐 **Claude Code Approval Request**\n\n"
            message += f"**Tool:** {self.tool_name}\n"
            message += f"**File:** `{file_path}`\n"
            if self.tool_name == "Write":
                content_preview = self.tool_input.get("content", "")[:200]
                if content_preview:
                    message += f"**Preview:**\n```\n{content_preview}...\n```\n"
        else:
            message = f"🔐 **Claude Code Approval Request**\n\n"
            message += f"**Tool:** {self.tool_name}\n"
            message += f"**Details:** `{str(self.tool_input)[:100]}...`\n"
        
        message += f"\n**Session:** `{self.session_id[:8]}...`\n"
        message += f"**Time:** {self.timestamp.strftime('%H:%M:%S')}\n"
        message += f"**Request ID:** `{self.request_id[:8]}...`"
        
        return message


class ApprovalQueue:
    """Manages approval requests in SQLite database."""
    
    def __init__(self, db_path: str = "./data/approvals.db"):
        """Initialize the approval queue with database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_input TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    response_time TEXT,
                    user_id INTEGER,
                    decision_reason TEXT,
                    CHECK (status IN ('pending', 'approved', 'denied', 'timeout'))
                )
            """)
            
            # Create indices for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON approval_requests(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON approval_requests(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON approval_requests(session_id)
            """)
            
            conn.commit()
            logger.info(f"Initialized approval database at {self.db_path}")
    
    def add_request(self, session_id: str, tool_name: str, 
                   tool_input: Dict[str, Any]) -> str:
        """Add a new approval request and return its ID."""
        request_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        request = ApprovalRequest(
            request_id=request_id,
            session_id=session_id,
            timestamp=timestamp,
            tool_name=tool_name,
            tool_input=tool_input
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO approval_requests 
                (request_id, session_id, timestamp, tool_name, tool_input, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request.request_id,
                request.session_id,
                request.timestamp.isoformat(),
                request.tool_name,
                json.dumps(request.tool_input),
                request.status
            ))
            conn.commit()
        
        logger.info(f"Added approval request {request_id} for {tool_name}")
        return request_id
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a specific approval request by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM approval_requests 
                WHERE request_id = ?
            """, (request_id,))
            row = cursor.fetchone()
            
            if row:
                return ApprovalRequest.from_row(row)
            return None
    
    def get_pending(self, limit: int = 10) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM approval_requests 
                WHERE status = 'pending'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            return [ApprovalRequest.from_row(row) for row in cursor.fetchall()]
    
    def update_status(self, request_id: str, status: str, 
                     user_id: Optional[int] = None, 
                     reason: Optional[str] = None) -> bool:
        """Update the status of an approval request."""
        response_time = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE approval_requests 
                SET status = ?, response_time = ?, user_id = ?, decision_reason = ?
                WHERE request_id = ? AND status = 'pending'
            """, (status, response_time.isoformat(), user_id, reason, request_id))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Updated request {request_id} to {status}")
                return True
            else:
                logger.warning(f"Failed to update request {request_id} - may already be processed")
                return False
    
    def cleanup_old_requests(self, hours: int = 24):
        """Clean up old requests older than specified hours."""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM approval_requests 
                WHERE datetime(timestamp) < datetime('now', '-' || ? || ' hours')
            """, (hours,))
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old approval requests")
            return deleted
    
    def timeout_pending_requests(self, seconds: int = 60):
        """Mark old pending requests as timeout."""
        cutoff_time = datetime.now().timestamp() - seconds
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE approval_requests 
                SET status = 'timeout', response_time = ?
                WHERE status = 'pending' 
                AND datetime(timestamp) < datetime('now', '-' || ? || ' seconds')
            """, (datetime.now().isoformat(), seconds))
            conn.commit()
            
            timed_out = cursor.rowcount
            if timed_out > 0:
                logger.info(f"Timed out {timed_out} pending requests")
            return timed_out
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about approval requests."""
        with sqlite3.connect(self.db_path) as conn:
            # Count by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) FROM approval_requests 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Count by tool
            cursor = conn.execute("""
                SELECT tool_name, COUNT(*) FROM approval_requests 
                GROUP BY tool_name
            """)
            tool_counts = dict(cursor.fetchall())
            
            # Recent activity
            cursor = conn.execute("""
                SELECT COUNT(*) FROM approval_requests 
                WHERE datetime(timestamp) > datetime('now', '-1 hour')
            """)
            recent_count = cursor.fetchone()[0]
            
            return {
                "by_status": status_counts,
                "by_tool": tool_counts,
                "recent_hour": recent_count,
                "total": sum(status_counts.values())
            }