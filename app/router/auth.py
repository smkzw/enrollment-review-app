"""Local lightweight authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.authz import (
    ADMIN_USERNAME,
    create_user,
    current_user,
    load_normalized_users,
    login_user as auth_login_user,
    mark_help_seen,
    users_path,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthPayload(BaseModel):
    username: str
    password: str = ""


class HelpSeenPayload(BaseModel):
    username: str = ""


def _users_path():
    """Compatibility helper used by tests."""
    return users_path()


@router.get("/status")
async def auth_status():
    users = load_normalized_users(persist=True)
    return {
        "registered_users": len(users),
        "has_users": bool(users),
        "admin_available": True,
        "admin_username": ADMIN_USERNAME,
    }


@router.post("/register", status_code=201)
async def register_user(body: AuthPayload):
    user = create_user(body.username, body.password)
    return {
        "status": "registered",
        "username": user["username"],
        "first_user": user["first_user"],
        "help_seen": user["help_seen"],
    }


@router.post("/login")
async def login_user(body: AuthPayload):
    user = auth_login_user(body.username, body.password)
    return {
        "status": "logged_in",
        "username": user["username"],
        "role": user["role"],
        "token": user["token"],
        "help_seen": user["help_seen"],
        "requires_help": user["requires_help"],
    }


@router.post("/help-seen")
async def set_help_seen(body: HelpSeenPayload, request: Request):
    user = current_user(request, required=False)
    username = user["username"] if user else body.username.strip()
    changed = mark_help_seen(username)
    return {"status": "updated", "username": username, "changed": changed}
