"""Route regression tests for the Infinihash KYT Python SDK.

Why this file exists
--------------------
Two intelligence methods shipped pointing at routes that do not exist:

    intel.lookup()             GET /api/v1/lookup/{address}        -> 404
    intel.recent_screenings()  GET /api/v1/recent-screenings       -> 404

The correct routes are namespaced under /api/v1/intel/. A 404 on an
intelligence lookup is the worst possible failure mode for a compliance tool:
to the caller it is indistinguishable from "this address is clean". These tests
make that class of bug impossible to reintroduce silently.

Layers:
  1. Exact-literal assertions for the two routes that were broken (offline,
     always run).
  2. A full sweep of every /api/v1/... literal in client.py against the live
     OpenAPI document (network; skipped if the spec is unreachable so a flaky
     network never turns into a red build, but a *mismatch* always fails).
"""

from __future__ import annotations

import inspect
import re
import urllib.request

import pytest

from infinihash_kyt import client as client_mod

SPEC_URL = "https://kyt.infinihash.com/api/v1/openapi.json"

SOURCE = inspect.getsource(client_mod)

# Every "/api/v1/..." string literal in the client, f-string or not.
ROUTE_LITERAL_RE = re.compile(r'["\'](/api/v1/[^"\']*)["\']')

# Path params: f"{screening_id}" here, "{screening_id}" in the spec. Collapse
# both to a single placeholder so the comparison is about the route shape.
PARAM_RE = re.compile(r"\{[^{}]*\}")


def normalise(path: str) -> str:
    return PARAM_RE.sub("{}", path).rstrip("/")


def sdk_routes() -> set[str]:
    return {normalise(m) for m in ROUTE_LITERAL_RE.findall(SOURCE)}


# --------------------------------------------------------------------------
# 1. The two routes that were broken. Exact strings, no network needed.
# --------------------------------------------------------------------------

def test_intel_lookup_route_is_namespaced_under_intel():
    src = inspect.getsource(client_mod.Intel.lookup)
    assert 'f"/api/v1/intel/lookup/{address}"' in src
    assert "/api/v1/lookup/" not in src, (
        "intel.lookup() must call /api/v1/intel/lookup/{address}. "
        "The un-namespaced /api/v1/lookup/{address} returns 404, which a "
        "caller reads as 'address is clean'."
    )


def test_intel_recent_screenings_route_is_namespaced_under_intel():
    src = inspect.getsource(client_mod.Intel.recent_screenings)
    assert '"/api/v1/intel/recent-screenings"' in src
    assert '"/api/v1/recent-screenings"' not in src, (
        "intel.recent_screenings() must call /api/v1/intel/recent-screenings; "
        "the un-namespaced route returns 404."
    )


def test_no_unnamespaced_intel_routes_anywhere_in_the_client():
    """Belt and braces: these two literals must not reappear in any method."""
    for dead in ("/api/v1/lookup/", "/api/v1/recent-screenings"):
        assert dead not in SOURCE, f"dead route {dead} is back in client.py"


def test_route_literals_are_well_formed():
    routes = sdk_routes()
    assert routes, "no /api/v1 routes found in client.py — regex broke?"
    for r in routes:
        assert r.startswith("/api/v1/"), r
        assert " " not in r, r


# --------------------------------------------------------------------------
# 2. Every route in the SDK must exist in the live OpenAPI document.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def spec_paths() -> set[str]:
    import json

    # The edge blocks the default python-urllib User-Agent, so send a real one.
    req = urllib.request.Request(
        SPEC_URL,
        headers={"User-Agent": "infinihash-kyt-sdk-tests/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            spec = json.load(resp)
    except Exception as exc:  # noqa: BLE001 - network flake must not fail CI
        pytest.skip(f"live OpenAPI spec unreachable ({exc}); skipping sweep")
    paths = spec.get("paths") or {}
    assert paths, "OpenAPI document has no paths"
    return {normalise(p) for p in paths}


def test_every_sdk_route_exists_in_the_live_spec(spec_paths):
    missing = sorted(r for r in sdk_routes() if r not in spec_paths)
    assert not missing, (
        "SDK calls routes the API does not serve: "
        + ", ".join(missing)
        + f"\nLive spec: {SPEC_URL}"
    )
