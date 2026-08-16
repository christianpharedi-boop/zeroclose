from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..agent import TreasuryAgent
from ..audit.api import audit_snapshot, audit_stream
from ..audit.auth import AuditorTokenAuth
from ..audit.verifier import verify_chain
from ..connectors.stripe_mapper import map_event, verify_signature


def create_app(agent: TreasuryAgent | None = None, *, auditor_auth: AuditorTokenAuth | None = None, stripe_webhook_secret: str | None = None) -> FastAPI:
    treasury = agent or TreasuryAgent("default")
    auth = auditor_auth or AuditorTokenAuth()
    processed_webhooks: set[str] = set()
    app = FastAPI(title="ZeroClose Treasury API", version="0.1.0")

    def require_auditor(token: str | None) -> None:
        if auth.tokens and not token or (auth.tokens and not auth.verify(token or "")):
            raise HTTPException(status_code=401, detail="valid auditor token required")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, **treasury.status()}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return treasury.status()

    @app.post("/policy/evaluate")
    async def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        return treasury.authorize(payload).model_dump()

    @app.post("/webhooks/{provider}")
    async def webhook(provider: str, request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")) -> dict[str, Any]:
        raw = await request.body()
        if provider.lower() == "stripe" and stripe_webhook_secret:
            if not stripe_signature or not verify_signature(raw, stripe_signature, stripe_webhook_secret):
                raise HTTPException(status_code=400, detail="invalid Stripe signature")
        payload: Any = await request.json()
        event = map_event(raw) if provider.lower() == "stripe" else payload
        event_id = event.get("event_id") or event.get("id") if isinstance(event, dict) else None
        if event_id and event_id in processed_webhooks:
            return {"accepted": True, "provider": provider, "event_id": event_id, "duplicate": True}
        if event_id:
            processed_webhooks.add(event_id)
        treasury.ledger.append(f"{provider}_webhook", event)
        return {"accepted": True, "provider": provider, "event_id": event_id, "duplicate": False}

    @app.get("/audit/verify")
    def audit_verify(x_auditor_token: str | None = Header(default=None)) -> dict[str, Any]:
        require_auditor(x_auditor_token)
        events = treasury.ledger.snapshot()
        return {"valid": verify_chain(events), "event_count": len(events)}

    @app.get("/audit/snapshot")
    def audit_point_in_time(sequence: int | None = None, x_auditor_token: str | None = Header(default=None)) -> dict[str, Any]:
        require_auditor(x_auditor_token)
        return audit_snapshot(treasury.ledger, sequence)

    @app.get("/audit/stream")
    async def audit_sse(after_sequence: int = 0, x_auditor_token: str | None = Header(default=None)) -> StreamingResponse:
        require_auditor(x_auditor_token)
        return StreamingResponse(audit_stream(treasury.ledger, after_sequence=after_sequence), media_type="text/event-stream")

    return app


app = create_app()
