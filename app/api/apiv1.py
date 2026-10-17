from fastapi import APIRouter

from app.api.endpoints import auth, login, user, webhook, message, \
    media, tmdb, history, system, dashboard, \
    transfer, mediaserver, storage, mfa

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(login.router, prefix="/login", tags=["login"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(mfa.router, prefix="/mfa", tags=["mfa"])
api_router.include_router(message.router, prefix="/message", tags=["message"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(tmdb.router, prefix="/tmdb", tags=["tmdb"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(transfer.router, prefix="/transfer", tags=["transfer"])
api_router.include_router(mediaserver.router, prefix="/mediaserver", tags=["mediaserver"])
