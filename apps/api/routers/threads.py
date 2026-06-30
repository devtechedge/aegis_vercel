from fastapi import APIRouter

router = APIRouter(prefix="/threads", tags=["threads"])

@router.get("/")
async def list_threads():
    return {"threads": []}

@router.post("/")
async def create_thread():
    return {"id": "thread_123", "status": "created"}
