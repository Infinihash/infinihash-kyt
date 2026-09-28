"""Infinihash KYT Python SDK (alpha).

Thin requests wrapper around https://kyt.infinihash.com/api/v1. Designed to be
boring on purpose: every call returns the raw JSON the server sent back, and
errors surface as exceptions you can catch.

Quick start:

    from infinihash_kyt import Client  # alias of KYT
    client = Client(api_key="ih_kyt_...")
    result = client.screen.address(
        "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
        chain="ethereum",
    )
    print(result["risk_score"], result["risk_level"])

Set the env var INFINIHASH_KYT_KEY if you prefer not to pass api_key explicitly.
"""

from .client import Client, KYT, KYTError

__all__ = ["Client", "KYT", "KYTError"]
__version__ = "0.2.2"
