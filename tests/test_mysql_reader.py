from types import SimpleNamespace

import pytest
from sqlalchemy import URL

from ingestion import mysql_reader


def _settings(**overrides):
    values = {
        "mysql_url": None,
        "db_host": "db.internal",
        "db_port": 3306,
        "db_name": "learning",
        "db_username": "chatbot",
        "db_password": "p@ss:/word",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_mysql_connection_url_prefers_explicit_mysql_url(monkeypatch):
    explicit_url = "mysql+pymysql://user:password@example.com/database"
    monkeypatch.setattr(
        mysql_reader,
        "get_settings",
        lambda: _settings(mysql_url=explicit_url),
    )

    assert mysql_reader.build_mysql_connection_url() == explicit_url


def test_build_mysql_connection_url_uses_db_settings_safely(monkeypatch):
    monkeypatch.setattr(mysql_reader, "get_settings", lambda: _settings())

    url = mysql_reader.build_mysql_connection_url()

    assert isinstance(url, URL)
    assert url.drivername == "mysql+pymysql"
    assert url.username == "chatbot"
    assert url.password == "p@ss:/word"
    assert url.host == "db.internal"
    assert url.port == 3306
    assert url.database == "learning"


def test_build_mysql_connection_url_rejects_incomplete_db_settings(monkeypatch):
    monkeypatch.setattr(
        mysql_reader,
        "get_settings",
        lambda: _settings(db_password=""),
    )

    with pytest.raises(RuntimeError, match="MYSQL_URL or complete DB_\\* settings"):
        mysql_reader.build_mysql_connection_url()
