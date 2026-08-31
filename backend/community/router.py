"""Opt-in ranks over Tailscale/LAN. Off until the owner enables publish."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.community.network import device_urls, public_base_from_peer, tailscale_status
from backend.community.ranks import build_ranks, local_card
from backend.community.store import load_settings, save_settings
from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User

router = APIRouter(prefix="/api/community", tags=["community"])


class CommunitySettingsBody(BaseModel):
    publish_ranks: bool = False
    peers: list[str] = Field(default_factory=list)


def _device_urls(ts: dict) -> dict:
    return device_urls(ts)


@router.get("/network")
def community_network():
    ts = tailscale_status()
    settings = load_settings()
    return {
        "tailscale": ts,
        "urls": _device_urls(ts),
        "publish_ranks": bool(settings.get("publish_ranks")),
        "peers": settings.get("peers") or [],
    }


@router.put("/settings")
def put_community_settings(
    body: CommunitySettingsBody,
    user: User = Depends(get_current_user),
):
    del user
    cleaned_peers: list[str] = []
    for raw in body.peers:
        base = public_base_from_peer(raw)
        if base:
            cleaned_peers.append(base)
    saved = save_settings({"publish_ranks": body.publish_ranks, "peers": cleaned_peers})
    return saved


@router.get("/public-card")
def public_card(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Peer-fetchable summary. 404 unless this machine opted in."""
    if not load_settings().get("publish_ranks"):
        raise HTTPException(status_code=404, detail="Ranks not published on this machine")
    card = local_card(db, user)
    card.pop("you", None)
    return card


@router.get("/ranks")
def community_ranks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return build_ranks(db, user)
