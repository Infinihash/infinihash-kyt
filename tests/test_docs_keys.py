"""Audit 2026-11 C-2 / C-3: key docs must point self-serve users at a page
they can open, and show the key format the engine actually mints.

- /kyt/admin/api-keys renders "Admin role required." for non-admins, and
  signup always creates role="user". The self-serve page is
  /kyt/settings/api-keys.
- The engine mints ``kyt_...`` keys (clearauthority-kyt
  app/auth/api_keys.py); ``ih_kyt_...`` does not exist.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = [ROOT / "README.md", ROOT / "infinihash_kyt" / "client.py", ROOT / "infinihash_kyt" / "__init__.py"]


def test_key_docs_point_at_settings_not_admin():
    for f in FILES:
        assert "/kyt/admin" not in f.read_text(), f"{f.name} still links /kyt/admin"
    assert any("https://kyt.infinihash.com/kyt/settings/api-keys" in f.read_text() for f in FILES)


def test_key_format_examples_use_kyt_prefix():
    for f in FILES:
        assert "ih_kyt_" not in f.read_text(), f"{f.name} still shows ih_kyt_ keys"
