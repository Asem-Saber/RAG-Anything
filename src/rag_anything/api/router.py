from fastapi import APIRouter

from rag_anything.api.routes import health, auth

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)