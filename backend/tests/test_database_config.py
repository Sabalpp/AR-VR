import pytest

from app.config import Settings


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_tiger_url_uses_installed_driver_and_preserves_tls(scheme):
    settings = Settings(
        _env_file=None, database_url=f"{scheme}://user:p%40ss@db.example:1234/tsdb?sslmode=require"
    )
    assert (
        settings.database_url
        == "postgresql+psycopg://user:p%40ss@db.example:1234/tsdb?sslmode=require"
    )


def test_explicit_driver_url_is_unchanged():
    url = "postgresql+psycopg://user:password@db.example/tsdb?sslmode=verify-full"
    assert Settings(_env_file=None, database_url=url).database_url == url
