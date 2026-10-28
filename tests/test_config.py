import pytest

from partner_catalog.config import Settings


@pytest.mark.parametrize("key", ["", "short", " " + "x" * 32, "x" * 257, "á" * 40, "x" * 32 + "\n"])
def test_invalid_key_is_rejected_without_disclosing_it(key):
    with pytest.raises(ValueError, match="PARTNER_API_KEY") as error:
        Settings(api_key=key)
    if len(key) > 10:
        assert key not in str(error.value)


def test_example_key_is_not_an_accepted_credential():
    with pytest.raises(ValueError, match="Replace the example"):
        Settings(api_key="replace-this-placeholder-with-a-random-local-key")


@pytest.mark.parametrize("url", ["postgresql://localhost/catalog", "sqlite:///:memory:"])
def test_unsupported_database_configuration_is_rejected(url):
    with pytest.raises(ValueError):
        Settings(api_key="x" * 40, database_url=url)


def test_factory_environment_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("PARTNER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="PARTNER_API_KEY"):
        Settings.from_environment()
    monkeypatch.setenv("PARTNER_API_KEY", "x" * 40)
    monkeypatch.setenv("PARTNER_DATABASE_URL", f"sqlite:///{tmp_path / 'environment.db'}")
    assert Settings.from_environment().database_url.endswith("environment.db")
