from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request):
    catalogue = await request.app.state.deps.engines.catalogue()
    return {
        "status": "ok",
        "engines": [
            {"provider": e["provider"], "label": e["label"], "available": e["available"]}
            for e in catalogue
        ],
    }


@router.get("/models")
async def models(request: Request):
    """Feeds the model pickers: one entry per engine, models included."""
    return await request.app.state.deps.engines.catalogue()
