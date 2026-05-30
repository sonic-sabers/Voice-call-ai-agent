from fastapi import APIRouter
from server.health import run_all_checks

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, object]:
    return await run_all_checks()
