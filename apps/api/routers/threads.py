from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/threads", tags=["threads"])

@router.get("/")
async def list_threads():
    return {"threads": []}

@router.post("/")
async def create_thread():
    return {"id": "thread_123", "status": "created"}

class ResumeRequest(BaseModel):
    approved: bool = True
    comment: str | None = None
    payload: Any | None = None

@router.post("/{thread_id}/resume")
async def resume_thread(thread_id: str, req: ResumeRequest):
    """Resume an interrupted graph (HITL)"""
    try:
        import sys, os
        ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if ROOT not in sys.path: sys.path.insert(0, ROOT)
        from packages.aegis_graph.supervisor import graph
        from langgraph.types import Command
        config = {"configurable": {"thread_id": thread_id}}
        result = await graph.ainvoke(Command(resume={"approved": req.approved, "comment": req.comment}), config=config)
        return {"thread_id": thread_id, "resumed": True, "confidence": result.get("confidence", 0), "needs_approval": result.get("needs_human_approval", False)}
    except Exception as e:
        return {"thread_id": thread_id, "resumed": False, "error": str(e), "mock": True, "approved": req.approved}
