# infinihash-kyt (Python)

Thin Python wrapper for the Infinihash KYT REST API. Screen wallets, manage
cases, pull SAR drafts.

## Install

```bash
pip install infinihash-kyt
```

## Use

```python
from infinihash_kyt import Client  # `KYT` is an identical alias

client = Client(api_key="ih_kyt_...")  # or set INFINIHASH_KYT_KEY in your env

# Screen a wallet
r = client.screen.address("0x722122dF12D4e14e13Ac3b6895a86e84145b6967", chain="ethereum")
print(r["risk_score"], r["risk_level"])

# Open a case
case = client.cases.create(
    address="0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
    chain="ethereum",
    notes="High-risk exposure detected from automated screen.",
)

# FinCEN-shaped JSON template (read-only - you still file with FinCEN yourself)
export = client.cases.sar_export_fincen(case["id"])
```

## Errors

All non-2xx responses raise `KYTError(status, message, body)`. The body field
preserves the parsed JSON the server sent back, when available.

## Status

Alpha. The surface area mirrors what is documented at
https://kyt.infinihash.com/docs. If you need an endpoint that is not in the
client, file an issue.
