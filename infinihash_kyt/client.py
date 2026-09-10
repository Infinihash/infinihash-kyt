"""Infinihash KYT Python SDK — v0.2.1

Thin requests wrapper around the Infinihash KYT API (https://kyt.infinihash.com).
Covers the full public surface: screening, cases, SAR workflow, webhooks, API key
management, wallet risk, bulk screening, travel-rule checks, and intelligence lookup.

Quick start
-----------
    from infinihash_kyt import KYT

    client = KYT(api_key="ih_kyt_...")          # or set INFINIHASH_KYT_KEY env var

    # Screen a wallet
    result = client.screen.address(
        "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
        chain="ethereum",
    )
    print(result["risk_score"], result["risk_level"])

    # Open a compliance case and add a note
    case = client.cases.create(address="0x722122dF12D4e14e13Ac3b6895a86e84145b6967")
    client.cases.add_note(case["id"], "Reviewed — escalating to SAR workflow.")

    # Register a webhook for high-risk alerts
    client.webhooks.create(
        url="https://your-server.example.com/hooks/kyt",
        events=["high_risk_screening"],
    )

Auth
----
Issue API keys at https://kyt.infinihash.com/kyt/admin (X-API-Key header).
Pass api_key= to the constructor or export INFINIHASH_KYT_KEY in the environment.

Errors
------
All non-2xx responses raise KYTError(status, message, body).
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

import requests

DEFAULT_BASE_URL = "https://kyt.infinihash.com"
DEFAULT_TIMEOUT = 30

# Supported chains — informational only, server validates the canonical list.
CHAINS = ["ethereum", "bitcoin", "tron", "solana", "polygon", "bnb", "arbitrum", "avalanche"]

# Webhook event types
WEBHOOK_EVENTS = [
    "high_risk_screening",
    "case_escalated",
    "sar_deadline_approaching",
    "sar_filed",
    "bulk_complete",
]


class KYTError(Exception):
    """Raised on any non-2xx response from the KYT API.

    Attributes:
        status  HTTP status code (int)
        body    Parsed response body (dict | str | None)
    """

    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.body = body


class _Resource:
    def __init__(self, client: "KYT"):
        self._c = client


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class Screen(_Resource):
    """Wallet and transaction screening.

    All screenings are asynchronous: the initial POST returns immediately with
    status="pending". Poll screen.get(id) until status="complete" (typically
    under 2 seconds for cached addresses).
    """

    def address(self, address: str, chain: str = "ethereum") -> dict:
        """Screen a wallet address for sanctions, mixer exposure, and risk signals.

        Args:
            address: On-chain address (checksummed ETH or native format for other chains).
            chain:   Blockchain identifier. Defaults to "ethereum".

        Returns:
            Screening dict with id, status, risk_score (0-100), risk_level, flags, narrative.
        """
        return self._c._request(
            "POST",
            "/api/v1/screen",
            json={"type": "wallet", "value": address, "chain": chain},
        )

    def get(self, screening_id: str) -> dict:
        """Fetch a screening by ID. Poll until status == 'complete'."""
        return self._c._request("GET", f"/api/v1/screen/{screening_id}")

    def address_frequency(self, address: str, chain: str = "ethereum") -> dict:
        """Return historical screening frequency for an address.

        Useful for detecting addresses that have been queried many times by
        multiple tenants — a signal of known bad actors.
        """
        return self._c._request(
            "GET",
            f"/api/v1/screen/address/{address}/frequency",
            params={"chain": chain},
        )

    def regenerate_narrative(self, screening_id: str) -> dict:
        """Re-generate the AI compliance narrative for an existing screening.

        Use when the narrative needs refreshing after new intelligence is ingested.
        Returns the updated screening object.
        """
        return self._c._request(
            "POST", f"/api/v1/screen/{screening_id}/narrative"
        )


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

class Cases(_Resource):
    """Compliance case management and SAR workflow.

    Cases track high-risk addresses through your internal review process and
    generate FinCEN-ready SAR drafts automatically.
    """

    def create(self, address: str, chain: str = "ethereum", notes: str = "") -> dict:
        """Open a new compliance case for an address.

        Args:
            address: Wallet address to investigate.
            chain:   Chain the address belongs to.
            notes:   Initial notes (optional, can be added later).

        Returns:
            Case dict with id, status, sar_stage, created_at.
        """
        return self._c._request(
            "POST",
            "/api/v1/cases",
            json={"address": address, "chain": chain, "notes": notes},
        )

    def list(self) -> list:
        """List all cases for your organisation (newest first)."""
        return self._c._request("GET", "/api/v1/cases")

    def get(self, case_id: str) -> dict:
        """Fetch a case with full note history and SAR stage."""
        return self._c._request("GET", f"/api/v1/cases/{case_id}")

    def add_note(self, case_id: str, note: str, author: str = "sdk") -> dict:
        """Append an investigator note to a case.

        Args:
            case_id: UUID of the case.
            note:    Free-text note body.
            author:  Display name of the analyst (default "sdk").
        """
        return self._c._request(
            "POST",
            f"/api/v1/cases/{case_id}/notes",
            json={"author": author, "note": note},
        )

    def escalate_sar(self, case_id: str, deadline_days: int = 30) -> dict:
        """Escalate a case into the SAR filing workflow.

        Sets sar_stage to "in_progress" and records the filing deadline.
        The system will generate a draft SAR PDF automatically.

        Args:
            case_id:       UUID of the case.
            deadline_days: Days until SAR must be filed (default 30, per FinCEN rules).
        """
        return self._c._request(
            "PATCH",
            f"/api/v1/cases/{case_id}/escalate-sar",
            json={"deadline_days": deadline_days},
        )

    def mark_sar_filed(self, case_id: str, bsa_id: str = "") -> dict:
        """Mark a SAR as filed with FinCEN. Closes the SAR workflow for this case.

        Args:
            case_id: UUID of the case.
            bsa_id:  BSA ID assigned by FinCEN after filing (optional but recommended).
        """
        return self._c._request(
            "PATCH",
            f"/api/v1/cases/{case_id}/mark-sar-filed",
            json={"bsa_id": bsa_id},
        )

    def sar_pdf(self, case_id: str) -> bytes:
        """Download the SAR draft as a PDF. Returns raw bytes.

        Save to disk:
            with open("sar_draft.pdf", "wb") as f:
                f.write(client.cases.sar_pdf(case_id))
        """
        return self._c._request("GET", f"/api/v1/cases/{case_id}/sar", raw=True)

    def sar_export_fincen(self, case_id: str) -> dict:
        """Export a read-only FinCEN-structured JSON draft.

        The returned object maps to FinCEN SAR form fields. Your compliance
        team must add subject personal information before filing — the API
        never stores PII.
        """
        return self._c._request("GET", f"/api/v1/cases/{case_id}/sar/export")

    def export_fincen(self, case_id: str) -> dict:
        """Alias for sar_export_fincen — alternate route on the server."""
        return self._c._request("GET", f"/api/v1/cases/{case_id}/export/fincen")


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

class Webhooks(_Resource):
    """Webhook endpoint management.

    Webhooks deliver real-time push notifications to your server when
    screening events occur. Payloads are signed with HMAC-SHA256 using
    your webhook secret — verify the X-KYT-Signature header on receipt.
    """

    def list_events(self) -> list:
        """Return the list of supported event types you can subscribe to."""
        return self._c._request("GET", "/api/v1/webhooks/events")

    def list(self) -> list:
        """List all webhook endpoints registered for your organisation."""
        return self._c._request("GET", "/api/v1/webhooks")

    def create(
        self,
        url: str,
        events: Optional[List[str]] = None,
        description: str = "",
    ) -> dict:
        """Register a new webhook endpoint.

        Args:
            url:         HTTPS URL that will receive POST payloads.
            events:      List of event types to subscribe to.
                         Defaults to ["high_risk_screening"].
            description: Human label for the webhook (optional).

        Returns:
            Webhook dict with id, secret (shown once — store it securely).
        """
        return self._c._request(
            "POST",
            "/api/v1/webhooks",
            json={
                "url": url,
                "events": events or ["high_risk_screening"],
                "description": description,
            },
        )

    def update(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[str]] = None,
        active: Optional[bool] = None,
    ) -> dict:
        """Update an existing webhook (partial update — only send fields to change)."""
        payload: dict = {}
        if url is not None:
            payload["url"] = url
        if events is not None:
            payload["events"] = events
        if active is not None:
            payload["active"] = active
        return self._c._request("PATCH", f"/api/v1/webhooks/{webhook_id}", json=payload)

    def delete(self, webhook_id: str) -> None:
        """Delete a webhook endpoint. Returns None on success (HTTP 204)."""
        self._c._request("DELETE", f"/api/v1/webhooks/{webhook_id}")

    def test(self, webhook_id: str) -> None:
        """Send a test payload to a webhook. Returns None on success (HTTP 202)."""
        self._c._request("POST", f"/api/v1/webhooks/{webhook_id}/test")


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class Keys(_Resource):
    """API key management for your organisation.

    Use these endpoints to issue, list, and revoke programmatic API keys.
    Only your first key (issued via the dashboard) can manage other keys.
    """

    def list(self) -> list:
        """List all active API keys for your organisation (secrets are redacted)."""
        return self._c._request("GET", "/api/v1/keys")

    def create(self, name: str) -> dict:
        """Issue a new API key.

        Args:
            name: Human label for this key (e.g. "production-server", "ci-pipeline").

        Returns:
            Dict with id, name, key (full value — shown once, store securely), created_at.
        """
        return self._c._request("POST", "/api/v1/keys", json={"name": name})

    def revoke(self, key_id: str) -> None:
        """Permanently revoke an API key by ID. Returns None on success (HTTP 204)."""
        self._c._request("DELETE", f"/api/v1/keys/{key_id}")

    def usage(self) -> dict:
        """Return screening usage and quota for the current billing period."""
        return self._c._request("GET", "/api/v1/keys/usage")


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

class Wallet(_Resource):
    """Detailed wallet intelligence beyond a point-in-time screening."""

    def risk(self, address: str, chain: str = "ethereum") -> dict:
        """Return the current risk profile for a wallet address.

        Aggregates all historical screenings, entity labels, and cluster
        data for the address into a single risk summary.

        Args:
            address: On-chain wallet address.
            chain:   Blockchain identifier.

        Returns:
            Dict with risk_score, risk_level, entity_name, cluster_size,
            exposure breakdown by category (sanctions, mixer, exchange, etc.).
        """
        return self._c._request(
            "GET",
            f"/api/v1/wallet/{address}/risk",
            params={"chain": chain},
        )

    def report(self, address: str, chain: str = "ethereum") -> dict:
        """Return a detailed transaction-flow report for a wallet.

        Includes inbound/outbound volume, counterparty categories, and
        a list of flagged transactions.

        Args:
            address: On-chain wallet address.
            chain:   Blockchain identifier.
        """
        return self._c._request(
            "GET",
            f"/api/v1/wallet/{address}/report",
            params={"chain": chain},
        )


# ---------------------------------------------------------------------------
# Bulk
# ---------------------------------------------------------------------------

class Bulk(_Resource):
    """Batch-screen multiple addresses in a single API call.

    Ideal for onboarding sweeps or periodic portfolio re-screening.
    Results are processed asynchronously — poll bulk.status() until complete,
    then fetch results with bulk.export(job_id).
    """

    def screen(self, addresses: List[dict]) -> dict:
        """Submit a batch screening job (JSON body).

        Args:
            addresses: List of dicts, each with "address" and "chain" keys.
                       Example: [{"address": "0xABC...", "chain": "ethereum"}]

        Returns:
            Dict with job_id and poll_url.
        """
        return self._c._request("POST", "/api/v1/bulk", json={"addresses": addresses})

    def status(self) -> dict:
        """Return the status of the most recent bulk job for your organisation."""
        return self._c._request("GET", "/api/v1/bulk/status")

    def export(self, job_id: str) -> dict:
        """Download the results of a completed bulk job.

        Args:
            job_id: UUID returned by bulk.screen().

        Returns:
            Dict with results list and summary statistics.
        """
        return self._c._request("GET", f"/api/v1/bulk/export/{job_id}")


# ---------------------------------------------------------------------------
# Travel Rule
# ---------------------------------------------------------------------------

class TravelRule(_Resource):
    """FATF Travel Rule compliance checks.

    Determine whether a counterparty address belongs to a regulated VASP
    and whether travel rule information must be shared.
    """

    def check(self, originator: str, beneficiary: str, amount_usd: float, chain: str = "ethereum") -> dict:
        """Perform a Travel Rule compliance check for a proposed transfer.

        Args:
            originator:  Sending wallet address.
            beneficiary: Receiving wallet address.
            amount_usd:  Transfer value in USD equivalent.
            chain:       Blockchain identifier.

        Returns:
            Dict with travel_rule_required (bool), originator_vasp, beneficiary_vasp,
            threshold_usd, and recommended_action.
        """
        return self._c._request(
            "POST",
            "/api/v1/travel-rule/check",
            json={
                "originator": originator,
                "beneficiary": beneficiary,
                "amount_usd": amount_usd,
                "chain": chain,
            },
        )

    def identify_vasp(self, address: str, chain: str = "ethereum") -> dict:
        """Identify whether an address belongs to a known VASP.

        Args:
            address: On-chain address to look up.
            chain:   Blockchain identifier.

        Returns:
            Dict with vasp_name, vasp_type, jurisdiction, regulated (bool).
        """
        return self._c._request(
            "GET",
            f"/api/v1/travel-rule/vasp/{address}",
            params={"chain": chain},
        )


# ---------------------------------------------------------------------------
# Intelligence
# ---------------------------------------------------------------------------

class Intel(_Resource):
    """Intelligence database lookups.

    Query the Infinihash label graph directly — useful for building internal
    dashboards or enriching your own risk models.
    """

    def stats(self) -> dict:
        """Return aggregate statistics on the intelligence database.

        Includes total label count, chain breakdown, and data freshness.
        """
        return self._c._request("GET", "/api/v1/stats")

    def lookup(self, address: str) -> dict:
        """Cross-chain address lookup across the full intelligence graph.

        Returns all labels, entity associations, and risk signals found
        for the address across every chain in the database.

        Args:
            address: Address to look up (chain prefix optional, e.g. "eth:0xABC...").
        """
        return self._c._request("GET", f"/api/v1/intel/lookup/{address}")

    def recent_screenings(self) -> list:
        """Return recent screening activity for your organisation (last 50)."""
        return self._c._request("GET", "/api/v1/intel/recent-screenings")


# ---------------------------------------------------------------------------
# Monitor (legacy alias — prefer Webhooks)
# ---------------------------------------------------------------------------

class Monitor(_Resource):
    """Simple monitoring subscriptions.

    Prefer the Webhooks resource for new integrations — it supports full
    CRUD, HMAC signing, and event filtering.
    """

    def register(self, webhook_url: str, events: Optional[List[str]] = None) -> dict:
        """Register a monitoring subscription (legacy endpoint)."""
        return self._c._request(
            "POST",
            "/api/v1/monitor",
            json={
                "webhook_url": webhook_url,
                "events": events or ["high_risk_screening"],
            },
        )

    def delete(self, monitor_id: str) -> None:
        """Delete a monitoring subscription."""
        self._c._request("DELETE", f"/api/v1/monitor/{monitor_id}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class KYT:
    """Infinihash KYT API client.

    Args:
        api_key:  Your KYT API key (ih_kyt_...).
                  Falls back to INFINIHASH_KYT_KEY environment variable.
        base_url: Override the API base URL (useful for sandbox/staging).
        timeout:  Request timeout in seconds (default 30).
        session:  Bring your own requests.Session (for connection pooling,
                  custom adapters, or test mocking).

    Namespaces
    ----------
    client.screen       — Wallet & address screening
    client.cases        — Compliance case management + SAR workflow
    client.webhooks     — Webhook endpoint CRUD
    client.keys         — API key management
    client.wallet       — Wallet risk profiles and transaction reports
    client.bulk         — Batch screening jobs
    client.travel_rule  — FATF Travel Rule checks
    client.intel        — Intelligence database lookups
    client.monitor      — Legacy monitoring subscriptions

    Example
    -------
        from infinihash_kyt import KYT

        client = KYT(api_key="ih_kyt_...")
        result = client.screen.address("0x722122dF12D4e14e13Ac3b6895a86e84145b6967")
        if result["risk_level"] in ("high", "critical"):
            case = client.cases.create(address=result["value"])
            client.cases.escalate_sar(case["id"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = api_key or os.environ.get("INFINIHASH_KYT_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing API key. Pass api_key= or set INFINIHASH_KYT_KEY."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

        # Resource namespaces
        self.screen = Screen(self)
        self.cases = Cases(self)
        self.webhooks = Webhooks(self)
        self.keys = Keys(self)
        self.wallet = Wallet(self)
        self.bulk = Bulk(self)
        self.travel_rule = TravelRule(self)
        self.intel = Intel(self)
        self.monitor = Monitor(self)  # legacy alias

    def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: Any = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "infinihash-kyt-python/0.2.0",
        }
        resp = self._session.request(
            method, url, json=json, params=params, headers=headers, timeout=self.timeout
        )
        if resp.status_code >= 400:
            body: Any
            try:
                body = resp.json()
                msg = (
                    body.get("detail", resp.reason)
                    if isinstance(body, dict)
                    else resp.reason
                )
            except ValueError:
                body = resp.text
                msg = resp.reason
            raise KYTError(resp.status_code, msg, body)
        if raw:
            return resp.content
        if not resp.content:
            return None
        return resp.json()

    def health(self) -> dict:
        """Check API liveness. Returns {"status": "ok"} when the service is healthy."""
        return self._request("GET", "/api/v1/health")
