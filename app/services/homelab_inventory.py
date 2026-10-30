"""Seed helpers for known homelab hardware/assets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ElectronicAsset


KNOWN_HOMELAB_ASSETS = [
    {
        "name": "host",
        "category": "Homelab Host",
        "location": "Homelab",
        "usage_status": "critical",
        "homelab_role": "primary_orchestration",
        "host_name": "host",
        "service_refs": ["lager", "life-ops-api", "homeassistant"],
        "sell_decision": "behalten",
        "sell_reason": "Kritischer Homelab-Host",
    },
    {
        "name": "node1",
        "category": "Homelab Host",
        "location": "Homelab",
        "usage_status": "critical",
        "homelab_role": "public_ingress_and_heavy_services",
        "host_name": "node1",
        "service_refs": ["marktwatch", "paperless", "ai-llm"],
        "sell_decision": "behalten",
        "sell_reason": "Kritischer Homelab-Host",
    },
]


def seed_known_homelab_assets(db: Session) -> list[ElectronicAsset]:
    assets = []
    for data in KNOWN_HOMELAB_ASSETS:
        existing = db.execute(
            select(ElectronicAsset).where(ElectronicAsset.host_name == data["host_name"])
        ).scalar_one_or_none()
        asset = existing or ElectronicAsset(name=data["name"])
        for key, value in data.items():
            if key == "service_refs":
                asset.service_refs = value
            else:
                setattr(asset, key, value)
        asset.manual_pin = 1
        if existing is None:
            db.add(asset)
        assets.append(asset)
    db.flush()
    return assets
