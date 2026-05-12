# infinihash-kyt

Official Python SDK for the [Infinihash KYT API](https://kyt.infinihash.com/docs).

> **Status: Alpha** — API is stable; SDK wrapper is actively being built. Full docs coming soon.

## Installation

```bash
pip install infinihash-kyt
```

## Quick Start

```python
from infinihash_kyt import InfinihashKYT

kyt = InfinihashKYT(api_key="your-key-here")

result = kyt.screen(
    type="wallet",
    value="0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
    chain="ethereum",
)

print(result.risk_level)   # critical
print(result.action)       # block
print(result.narrative)
```

## Features

- Wallet and transaction screening
- SAR narrative generation
- Case management
- Webhook subscription helpers
- Async support via `asyncio`

## Documentation

Full API reference at [kyt.infinihash.com/docs](https://kyt.infinihash.com/docs).

## Support

Questions? [support@infinihash.com](mailto:support@infinihash.com)

## License

MIT © Infinihash LLC
