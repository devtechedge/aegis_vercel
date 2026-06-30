from fastapi import APIRouter

router = APIRouter(prefix="/fleet", tags=["fleet"])

@router.get("/")
async def list_fleet():
    return {"bots": ["bot-alpha", "bot-beta", "bot-gamma"]}

@router.get("/{bot_id}")
async def get_bot(bot_id: str):
    return {"bot_id": bot_id, "status": "active"}
