from urllib.parse import unquote, urlsplit

import psycopg
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from scripts import check_database
from scripts.configure_database import connection_url, save_url


def test_password_encoding_and_existing_environment_preserved(tmp_path):
    password = "a@b:/#?$'\""
    url = connection_url("example.com", "postgres.project", password)
    assert unquote(urlsplit(url).password) == password
    environment = tmp_path / ".env"
    environment.write_text("AEROROUTE_MAPBOX_TOKEN=keep-me\nAEROROUTE_DATABASE_URL=old\n")
    save_url(environment, url)
    assert "AEROROUTE_MAPBOX_TOKEN=keep-me" in environment.read_text()
    assert environment.read_text().count("AEROROUTE_DATABASE_URL=") == 1
    assert environment.stat().st_mode & 0o777 == 0o600


def test_database_error_does_not_expose_connection_credentials(monkeypatch, capsys):
    monkeypatch.setattr(
        check_database, "get_settings", lambda: Settings(database_url=SecretStr("private-url"))
    )

    def fail(*args, **kwargs):
        assert kwargs["sslmode"] == "verify-full"
        raise psycopg.OperationalError("private-url")

    monkeypatch.setattr(check_database.psycopg, "connect", fail)
    assert check_database.main() == 1
    assert "private-url" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "result,expected", [(None, 1), (("3.3.7", "public"), 1), (("3.3.7", "gis"), 0)]
)
def test_database_check_requires_postgis_in_dedicated_schema(monkeypatch, result, expected):
    class Connection:
        read_only = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            assert self.read_only
            return self

        def fetchone(self):
            return result

    monkeypatch.setattr(
        check_database, "get_settings", lambda: Settings(database_url=SecretStr("private-url"))
    )
    monkeypatch.setattr(check_database.psycopg, "connect", lambda *args, **kwargs: Connection())
    assert check_database.main() == expected
