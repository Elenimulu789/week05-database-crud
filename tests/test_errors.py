import sqlite3
from uuid import uuid4

from redis.exceptions import ConnectionError


def test_sql_constraint_errors_are_http_responses(client, sql, monkeypatch):
    def reject(*_args):
        raise sqlite3.IntegrityError("internal diagnostic")
    monkeypatch.setattr(sql, "create", reject)
    response = client.post("/sql/projects", json={"name": "Sample"})
    assert response.status_code == 409
    assert "internal diagnostic" not in response.text


def test_redis_unavailable_returns_503(client, documents, monkeypatch):
    def reject(*_args):
        raise ConnectionError("private endpoint details")
    monkeypatch.setattr(documents, "get", reject)
    response = client.get(f"/redis/projects/{uuid4()}")
    assert response.status_code == 503
    assert "private" not in response.text
