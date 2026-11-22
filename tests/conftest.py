from uuid import uuid4
import os
import pytest
from redis import Redis
from fastapi.testclient import TestClient

from src.api import create_app
from src.stores import RedisStore, SQLStore


@pytest.fixture(scope="session")
def redis_server():
    url = os.getenv("REDIS_URL")
    if url:
        server = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    else:
        from fakeredis import FakeRedis
        server = FakeRedis()
    server.ping()
    yield server
    server.close()


@pytest.fixture
def sql(tmp_path):
    return SQLStore(tmp_path / "test.db")


@pytest.fixture
def documents(redis_server):
    store = RedisStore(redis_server, prefix=f"test:{uuid4()}:")
    yield store
    keys = list(redis_server.scan_iter(match=store.prefix + "*"))
    if keys:
        redis_server.delete(*keys)


@pytest.fixture
def client(sql, documents):
    with TestClient(create_app(sql, documents)) as api:
        yield api
