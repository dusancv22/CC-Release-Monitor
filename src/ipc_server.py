"""IPC server for communication between Claude Code hooks and Telegram bot."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.approval import ApprovalQueue, ApprovalRequest

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Claude Code Approval Server", version="1.0.0")

# Add CORS middleware for local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize approval queue
approval_queue = ApprovalQueue()

# Store for notification callbacks
notification_callbacks = []


class ApprovalRequestModel(BaseModel):
    """Model for incoming approval requests."""
    session_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    project_dir: Optional[str] = None


class ApprovalResponseModel(BaseModel):
    """Model for approval responses."""
    request_id: str
    decision: str  # "approve", "deny"
    reason: Optional[str] = None
    user_id: Optional[int] = None


class ApprovalStatusResponse(BaseModel):
    """Model for approval status responses."""
    request_id: str
    status: str
    decision: Optional[str] = None
    reason: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "Claude Code Approval Server",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/approval/request")
async def create_approval_request(
    request: ApprovalRequestModel,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Create a new approval request.
    Called by the Claude Code hook when a tool needs approval.
    """
    try:
        # Add request to queue
        request_id = approval_queue.add_request(
            session_id=request.session_id,
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            project_dir=request.project_dir
        )
        
        # Trigger notification callbacks in background
        background_tasks.add_task(notify_new_request, request_id)
        
        logger.info(f"Created approval request {request_id} for {request.tool_name}")
        
        return {
            "request_id": request_id,
            "status": "pending"
        }
    except Exception as e:
        logger.error(f"Error creating approval request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/approval/status/{request_id}")
async def get_approval_status(request_id: str) -> ApprovalStatusResponse:
    """
    Get the status of an approval request.
    Called by the Claude Code hook to poll for a decision.
    """
    try:
        request = approval_queue.get_request(request_id)
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        response = ApprovalStatusResponse(
            request_id=request_id,
            status=request.status
        )
        
        if request.status in ["approved", "denied"]:
            response.decision = request.status
            response.reason = request.decision_reason
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting approval status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approval/respond")
async def submit_approval_response(response: ApprovalResponseModel) -> Dict[str, str]:
    """
    Submit a decision for an approval request.
    Called by the Telegram bot when user makes a decision.
    """
    try:
        # Map decision to status
        status = "approved" if response.decision == "approve" else "denied"
        
        # Update request status
        success = approval_queue.update_status(
            request_id=response.request_id,
            status=status,
            user_id=response.user_id,
            reason=response.reason
        )
        
        if not success:
            raise HTTPException(
                status_code=409, 
                detail="Request already processed or not found"
            )
        
        logger.info(f"Updated request {response.request_id} to {status}")
        
        return {
            "request_id": response.request_id,
            "status": status,
            "message": f"Request {status}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting approval response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/approval/pending")
async def get_pending_approvals(limit: int = 10) -> Dict[str, Any]:
    """
    Get all pending approval requests.
    Used by the Telegram bot to check for new requests.
    """
    try:
        pending = approval_queue.get_pending(limit=limit)
        
        return {
            "count": len(pending),
            "requests": [
                {
                    "request_id": req.request_id,
                    "session_id": req.session_id,
                    "tool_name": req.tool_name,
                    "tool_input": req.tool_input,
                    "timestamp": req.timestamp.isoformat(),
                    "project_dir": req.project_dir
                }
                for req in pending
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approval/timeout")
async def timeout_old_requests(seconds: int = 60) -> Dict[str, int]:
    """
    Mark old pending requests as timed out.
    Called periodically to clean up stale requests.
    """
    try:
        count = approval_queue.timeout_pending_requests(seconds=seconds)
        
        return {
            "timed_out": count,
            "message": f"Timed out {count} requests older than {seconds} seconds"
        }
        
    except Exception as e:
        logger.error(f"Error timing out requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/approval/stats")
async def get_approval_statistics() -> Dict[str, Any]:
    """Get statistics about approval requests."""
    try:
        stats = approval_queue.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approval/cleanup")
async def cleanup_old_requests(hours: int = 24) -> Dict[str, int]:
    """
    Clean up old approval requests from database.
    """
    try:
        count = approval_queue.cleanup_old_requests(hours=hours)
        
        return {
            "deleted": count,
            "message": f"Deleted {count} requests older than {hours} hours"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket support for real-time notifications (optional enhancement)
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass  # Connection might be closed

manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def notify_new_request(request_id: str):
    """Notify connected clients about new approval request."""
    request = approval_queue.get_request(request_id)
    if request:
        await manager.broadcast({
            "type": "new_request",
            "request_id": request_id,
            "tool_name": request.tool_name,
            "timestamp": request.timestamp.isoformat()
        })
    
    # Also trigger any registered callbacks
    for callback in notification_callbacks:
        try:
            await callback(request_id)
        except Exception as e:
            logger.error(f"Error in notification callback: {e}")


def register_notification_callback(callback):
    """Register a callback for new approval requests."""
    notification_callbacks.append(callback)


def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Run the IPC server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(f"Starting IPC server on {host}:{port}")
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    run_server()