"""
routers/auth.py — Recruiter authentication (signup, signin, signout, me).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

from config import settings
from models.schemas import AuthResponse, RecruiterPublic, RecruiterSigninRequest, RecruiterSignupRequest
from services.session_store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Recruiter Auth"])


def get_current_recruiter(authorization: Optional[str] = Header(None)) -> RecruiterPublic:
    """Dependency — extract recruiter from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.split(" ", 1)[1]
    try:
        recruiter = store.get_recruiter_by_token(token)
    except Exception as exc:
        logger.error("Token lookup failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication check failed.")
    if not recruiter:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please sign in again.")
    return recruiter


@router.post("/signup", response_model=AuthResponse)
async def signup(body: RecruiterSignupRequest):
    """Create a new recruiter account."""
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=422, detail="Invalid email address.")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters.")
    if not body.full_name.strip():
        raise HTTPException(status_code=422, detail="Full name is required.")

    try:
        recruiter = store.create_recruiter(
            email=body.email,
            password=body.password,
            full_name=body.full_name.strip(),
            company_name=body.company_name,
        )
    except Exception as exc:
        logger.error("Signup failed for %s: %s", body.email, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Account creation failed.")

    if not recruiter:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    try:
        token = store.create_recruiter_session(recruiter.id, settings.session_expire_hours)
    except Exception as exc:
        logger.error("Session creation failed for recruiter %s: %s", recruiter.id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Session creation failed.")

    public = RecruiterPublic(
        id=recruiter.id, email=recruiter.email,
        full_name=recruiter.full_name, company_name=recruiter.company_name,
    )
    logger.info("Recruiter signed up: %s (%s)", recruiter.email, recruiter.id)
    return AuthResponse(token=token, recruiter=public)


@router.post("/signin", response_model=AuthResponse)
async def signin(body: RecruiterSigninRequest):
    """Sign in and receive a session token."""
    try:
        recruiter = store.authenticate_recruiter(body.email, body.password)
    except Exception as exc:
        logger.error("Signin error for %s: %s", body.email, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Sign-in failed.")

    if not recruiter:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    try:
        token = store.create_recruiter_session(recruiter.id, settings.session_expire_hours)
    except Exception as exc:
        logger.error("Session creation failed for %s: %s", recruiter.id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Session creation failed.")

    logger.info("Recruiter signed in: %s", body.email)
    return AuthResponse(token=token, recruiter=recruiter)


@router.get("/me", response_model=RecruiterPublic)
async def me(recruiter: RecruiterPublic = Depends(get_current_recruiter)):
    """Return the currently authenticated recruiter."""
    return recruiter


@router.post("/signout")
async def signout(authorization: Optional[str] = Header(None)):
    """Invalidate the current session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            store.delete_recruiter_session(token)
            logger.info("Recruiter signed out (token revoked)")
        except Exception as exc:
            logger.warning("Signout token deletion failed: %s", exc)
    return {"detail": "Signed out successfully."}
