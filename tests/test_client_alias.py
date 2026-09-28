"""`Client` (used in the docs quickstarts) must be the same class as `KYT`."""
import infinihash_kyt
from infinihash_kyt import Client, KYT


def test_client_is_kyt_alias():
    assert Client is KYT
    assert "Client" in infinihash_kyt.__all__


def test_client_constructs():
    c = Client(api_key="ih_kyt_test")
    assert c.base_url == "https://kyt.infinihash.com"
    assert hasattr(c.screen, "address")


def test_version():
    assert infinihash_kyt.__version__ == "0.2.2"
