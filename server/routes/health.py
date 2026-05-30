from fastapi import APIRouter
from server.core.config import get_settings
from server.health import run_all_checks

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, object]:
    return await run_all_checks()


@router.get("/api/config")
async def client_config() -> dict[str, str]:
    cfg = get_settings()
    return {
        "vapiPublicKey": cfg.vapi_public_key,
        "vapiAssistantId": cfg.vapi_assistant_id,
    }
