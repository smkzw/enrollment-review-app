"""Local authentication and project authorization helpers."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from app.config import PROJECTS_DIR
from app.models import ProjectConfig

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ENROLLMENT_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "20121116"
ADMIN_ROLE = "admin"
USER_ROLE = "user"
ADMIN_SESSION_TTL_HOURS = int(os.getenv("ENROLLMENT_SESSION_TTL_HOURS", "24"))
_ADMIN_SESSIONS: dict[str, datetime] = {}


def users_path() -> Path:
    path = PROJECTS_DIR / "_system"
    path.mkdir(parents=True, exist_ok=True)
    return path / "users.json"


def password_hash(password: str) -> str:
    if not password:
        return ""
    salt = secrets.token_hex(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return not password
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = stored_hash.split("$", 3)
            computed = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return secrets.compare_digest(computed, digest)
        except Exception:
            return False
    return secrets.compare_digest(stored_hash, hashlib.sha256(password.encode("utf-8")).hexdigest())


def admin_token() -> str:
    token = secrets.token_urlsafe(32)
    _ADMIN_SESSIONS[token] = datetime.now() + timedelta(hours=ADMIN_SESSION_TTL_HOURS)
    return token


def _validate_admin_session(token: str) -> bool:
    now = datetime.now()
    expired = [key for key, expires_at in _ADMIN_SESSIONS.items() if expires_at <= now]
    for key in expired:
        _ADMIN_SESSIONS.pop(key, None)
    return bool(token and _ADMIN_SESSIONS.get(token, now) > now)


def load_users() -> list[dict]:
    path = users_path()
    if not path.exists():
        return []
    try:
        users = json.loads(path.read_text(encoding="utf-8"))
        return users if isinstance(users, list) else []
    except Exception:
        return []


def save_users(users: list[dict]) -> None:
    users_path().write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_user(user: dict) -> dict:
    user = dict(user or {})
    user["username"] = str(user.get("username") or "").strip()
    user["password_hash"] = str(user.get("password_hash") or "")
    user["role"] = USER_ROLE
    user["help_seen"] = bool(user.get("help_seen"))
    user["created_at"] = str(user.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if not user.get("token"):
        user["token"] = secrets.token_urlsafe(32)
    return user


def load_normalized_users(persist: bool = False) -> list[dict]:
    users = [normalize_user(u) for u in load_users() if str(u.get("username") or "").strip() and u.get("username") != ADMIN_USERNAME]
    if persist:
        save_users(users)
    return users


def normal_user_count() -> int:
    return len(load_normalized_users())


def create_user(username: str, password: str = "") -> dict:
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="请输入用户名")
    if username == ADMIN_USERNAME:
        raise HTTPException(status_code=409, detail="admin 是系统内置超级管理员账号，请直接登录")

    users = load_normalized_users(persist=True)
    if any(u.get("username") == username for u in users):
        raise HTTPException(status_code=409, detail="该用户名已注册")

    first_user = len(users) == 0
    user = normalize_user({
        "username": username,
        "password_hash": password_hash(password),
        "role": USER_ROLE,
        "help_seen": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    users.append(user)
    save_users(users)
    return {**user, "first_user": first_user}


def login_user(username: str, password: str = "") -> dict:
    username = username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="请输入用户名")
    if username == ADMIN_USERNAME:
        if password != ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="密码不正确")
        return {
            "username": ADMIN_USERNAME,
            "role": ADMIN_ROLE,
            "token": admin_token(),
            "help_seen": True,
            "requires_help": False,
        }

    users = load_normalized_users(persist=True)
    for user in users:
        if user.get("username") != username:
            continue
        stored_hash = user.get("password_hash") or ""
        if not verify_password(password, stored_hash):
            raise HTTPException(status_code=401, detail="密码不正确")
        return {
            "username": username,
            "role": USER_ROLE,
            "token": user["token"],
            "help_seen": bool(user.get("help_seen")),
            "requires_help": not bool(user.get("help_seen")),
        }
    raise HTTPException(status_code=404, detail="用户不存在，请先注册")


def mark_help_seen(username: str) -> bool:
    username = (username or "").strip()
    if not username or username == ADMIN_USERNAME:
        return False
    users = load_normalized_users(persist=True)
    changed = False
    for user in users:
        if user.get("username") == username:
            if not user.get("help_seen"):
                user["help_seen"] = True
                changed = True
            break
    if changed:
        save_users(users)
    return changed


def validate_user_token(username: str, token: str) -> Optional[dict]:
    username = (username or "").strip()
    token = token or ""
    if not username or not token:
        return None
    if username == ADMIN_USERNAME and _validate_admin_session(token):
        return {"username": ADMIN_USERNAME, "role": ADMIN_ROLE, "token": token, "help_seen": True}
    for user in load_normalized_users(persist=True):
        if user.get("username") == username and user.get("token") == token:
            return {
                "username": username,
                "role": USER_ROLE,
                "token": token,
                "help_seen": bool(user.get("help_seen")),
            }
    return None


def current_user(request: Request, required: bool = True) -> Optional[dict]:
    username = request.headers.get("X-Enrollment-User") or request.query_params.get("user") or ""
    token = request.headers.get("X-Enrollment-Token") or request.query_params.get("token") or ""
    user = validate_user_token(username, token)
    if not user and required:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def is_admin(user: dict | None) -> bool:
    return bool(user and user.get("role") == ADMIN_ROLE and user.get("username") == ADMIN_USERNAME)


def legacy_owner_username() -> str:
    users = load_normalized_users()
    if len(users) == 1:
        return users[0].get("username", "")
    return ""


def can_access_project(user: dict | None, cfg: ProjectConfig) -> bool:
    return bool(user)


def require_project_access(user: dict | None, cfg: ProjectConfig) -> None:
    if not can_access_project(user, cfg):
        raise HTTPException(status_code=403, detail="无权访问该项目")


def can_modify_project(user: dict | None, cfg: ProjectConfig) -> bool:
    if is_admin(user):
        return True
    if not user:
        return False
    owner = getattr(cfg, "owner_username", "") or ""
    if owner:
        return owner == user.get("username")
    return user.get("username") == legacy_owner_username()


def require_project_modify(user: dict | None, cfg: ProjectConfig) -> None:
    if not can_modify_project(user, cfg):
        raise HTTPException(status_code=403, detail="无权修改该项目")


def can_modify_subject(user: dict | None, cfg: ProjectConfig, subject_info: object | dict | None) -> bool:
    if is_admin(user):
        return True
    if not user:
        return False
    if isinstance(subject_info, dict):
        owner = str(subject_info.get("owner_username") or "")
    else:
        owner = str(getattr(subject_info, "owner_username", "") or "")
    if owner:
        return owner == user.get("username")
    return can_modify_project(user, cfg)


def require_subject_modify(user: dict | None, cfg: ProjectConfig, subject_info: object | dict | None) -> None:
    if not can_modify_subject(user, cfg, subject_info):
        raise HTTPException(status_code=403, detail="无权修改该受试者资料")
