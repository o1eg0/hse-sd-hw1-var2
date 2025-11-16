from fastapi import APIRouter

from .public import router as public_router

router = APIRouter(prefix="/v1")
router.include_router(public_router)
