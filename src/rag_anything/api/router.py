"""Aggregates the route modules. Mounted at /api by the app factory."""

from fastapi import APIRouter

from rag_anything.api.routes import auth, health, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)