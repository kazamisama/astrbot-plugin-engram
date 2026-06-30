"""Persona management handler for the page API (v1.65).

Endpoints:
  list_personas()                   -> all personas (newest first)
  get_persona_detail(actor_id)      -> single persona full record
  build_persona(actor_id)           -> trigger LLM rebuild for one actor
  update_persona(actor_id, summary, tags) -> edit summary / tags in-place
  delete_persona(actor_id)          -> hard delete one persona
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .utils import PageApiUtils


class PersonaHandler:
    def __init__(self, utils: "PageApiUtils") -> None:
        self.utils = utils

    def list_personas(self, service) -> dict[str, Any]:
        if service is None:
            return self.utils.error("Memory service not initialized.")
        store = getattr(service, "persona_store", None)
        if store is None:
            return self.utils.ok({"items": [], "count": 0})
        try:
            items = store.all(limit=500)
        except Exception as e:
            return self.utils.error(f"Failed to list personas: {e}")
        result = []
        for p in items:
            result.append({
                "actor_id": p.actor_id,
                "summary": p.summary or "",
                "tags": p.tags or [],
                "platform": p.platform or "",
                "source_count": p.source_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            })
        return self.utils.ok({"items": result, "count": len(result)})

    def get_persona_detail(self, service, actor_id: str) -> dict[str, Any]:
        if service is None:
            return self.utils.error("Memory service not initialized.")
        actor_id = (actor_id or "").strip()
        if not actor_id:
            return self.utils.error("Missing actor_id.")
        store = getattr(service, "persona_store", None)
        if store is None:
            return self.utils.error("Persona store not available.")
        p = store.get(actor_id)
        if p is None:
            return self.utils.error(f"Persona not found: {actor_id}")
        return self.utils.ok({
            "actor_id": p.actor_id,
            "summary": p.summary or "",
            "tags": p.tags or [],
            "platform": p.platform or "",
            "source_count": p.source_count,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    def build_persona(self, service, actor_id: str) -> dict[str, Any]:
        if service is None:
            return self.utils.error("Memory service not initialized.")
        actor_id = (actor_id or "").strip()
        if not actor_id:
            return self.utils.error("Missing actor_id.")
        try:
            persona = service.build_persona(actor_id)
        except Exception as e:
            return self.utils.error(f"Build persona failed: {e}")
        if persona is None:
            return self.utils.error("Persona build returned None (no engrams for this actor?).")
        return self.utils.ok({
            "actor_id": persona.actor_id,
            "summary": persona.summary or "",
            "tags": persona.tags or [],
            "platform": persona.platform or "",
            "source_count": persona.source_count,
            "updated_at": persona.updated_at,
        })

    def update_persona(self, service, actor_id: str,
                       summary: str = "", tags: Any = None) -> dict[str, Any]:
        if service is None:
            return self.utils.error("Memory service not initialized.")
        actor_id = (actor_id or "").strip()
        if not actor_id:
            return self.utils.error("Missing actor_id.")
        store = getattr(service, "persona_store", None)
        if store is None:
            return self.utils.error("Persona store not available (persona feature disabled?).")
        existing = store.get(actor_id)
        if existing is None:
            return self.utils.error(f"Persona not found: {actor_id}")
        from hippocampus.persona import Persona
        p = Persona(
            actor_id=actor_id,
            summary=summary if summary is not None else existing.summary,
            tags=list(tags) if tags is not None else list(existing.tags),
            platform=existing.platform,
            source_count=existing.source_count,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        try:
            store.upsert(p)
        except Exception as e:
            return self.utils.error(f"Update persona failed: {e}")
        return self.utils.ok({
            "actor_id": p.actor_id,
            "summary": p.summary,
            "tags": p.tags,
            "updated_at": p.updated_at,
        })

    def delete_persona(self, service, actor_id: str) -> dict[str, Any]:
        if service is None:
            return self.utils.error("Memory service not initialized.")
        actor_id = (actor_id or "").strip()
        if not actor_id:
            return self.utils.error("Missing actor_id.")
        store = getattr(service, "persona_store", None)
        if store is None:
            return self.utils.error("Persona store not available.")
        ok = store.delete(actor_id)
        if not ok:
            return self.utils.error(f"Persona not found or already deleted: {actor_id}")
        return self.utils.ok({"deleted": actor_id})
