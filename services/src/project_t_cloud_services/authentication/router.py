"""Authentication and device-pairing API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ..config import CloudConfig
from ..storage import CloudDatabase
from .passwords import hash_password, verify_password
from .tokens import AuthenticatedPrincipal, decode_bearer_token, issue_sync_token, issue_user_token

_bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=5, max_length=254)
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=256)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class PairDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: str = Field(..., min_length=3, max_length=128)
    device_id: str | None = Field(default=None, min_length=3, max_length=128)
    device_label: str = Field(..., min_length=1, max_length=120)
    os_platform: str = Field(..., min_length=2, max_length=64)
    runtime_version: str = Field(default="0.5.0", min_length=1, max_length=32)
    sync_enabled: bool = True


def get_current_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedPrincipal:
    cfg: CloudConfig = request.app.state.cloud_config
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Missing bearer token."}},
        )
    principal = decode_bearer_token(cfg.jwt_secret, creds.credentials)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Invalid or expired token."}},
        )
    return principal


def create_auth_router(*, db: CloudDatabase, config: CloudConfig) -> APIRouter:
    router = APIRouter(prefix="/api/cloud/v1/auth", tags=["Authentication"])

    @router.post("/register", status_code=status.HTTP_201_CREATED)
    def register(body: RegisterRequest) -> dict[str, object]:
        if db.get_user_by_email(body.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "email_exists", "message": "Email already registered."}},
            )
        pw_hash = hash_password(body.password)
        user = db.create_user(
            email=body.email,
            display_name=body.display_name,
            password_hash=pw_hash,
        )
        token = issue_user_token(
            secret=config.jwt_secret,
            user_id=user["id"],
            email=user["email"],
            ttl_seconds=config.jwt_ttl_seconds,
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "display_name": user["display_name"],
            },
        }

    @router.post("/login")
    def login(body: LoginRequest) -> dict[str, object]:
        user = db.get_user_by_email(body.email)
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "invalid_credentials", "message": "Invalid email or password."}},
            )
        token = issue_user_token(
            secret=config.jwt_secret,
            user_id=user["id"],
            email=user["email"],
            ttl_seconds=config.jwt_ttl_seconds,
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "display_name": user["display_name"],
            },
        }

    @router.get("/me")
    def get_me(principal: AuthenticatedPrincipal = Depends(get_current_principal)) -> dict[str, object]:
        user = db.get_user_by_id(principal.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "unauthorized", "message": "User not found."}},
            )
        return {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "token_scope": principal.token_scope,
        }

    @router.post("/devices/pair")
    def pair_device(
        body: PairDeviceRequest,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        dev_id = body.device_id or f"dev_{uuid.uuid4().hex[:12]}"
        dev, inst = db.pair_device_and_installation(
            user_id=principal.user_id,
            device_id=dev_id,
            device_label=body.device_label,
            os_platform=body.os_platform,
            installation_id=body.installation_id,
            runtime_version=body.runtime_version,
            sync_enabled=body.sync_enabled,
        )
        sync_token = issue_sync_token(
            secret=config.jwt_secret,
            user_id=principal.user_id,
            email=principal.email,
            installation_id=inst["id"],
            device_id=dev["id"],
        )
        return {
            "device": {
                "id": dev["id"],
                "device_label": dev["device_label"],
                "os_platform": dev["os_platform"],
            },
            "installation": {
                "id": inst["id"],
                "runtime_version": inst["runtime_version"],
                "sync_enabled": bool(inst["sync_enabled"]),
            },
            "sync_token": sync_token,
        }

    @router.get("/devices")
    def list_devices(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        return {"devices": db.list_devices_for_user(principal.user_id)}

    return router
