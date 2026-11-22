from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from uuid import uuid4

import pytest

from src.stores import Conflict, Missing


@pytest.mark.parametrize("engine", ["sql", "redis"])
def test_full_crud_and_http_statuses(client, engine):
    path = f"/{engine}/projects"
    response = client.post(path, json={"name": "Weekend build"})
    assert response.status_code == 201
    project = response.json()
    endpoint = f"{path}/{project['id']}"
    response = client.post(endpoint + "/tasks", json={"title": "Design data model"})
    assert response.status_code == 201
    item = response.json()
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.json()["tasks"][0]["id"] == item["id"]
    response = client.put(endpoint, json={"name": "Review build"})
    assert response.status_code == 200
    assert response.json()["name"] == "Review build"
    response = client.put(endpoint + "/tasks/" + item["id"], json={"title": "Review model", "status": "done"})
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert client.get(path).json()[0]["id"] == project["id"]
    assert client.delete(endpoint + "/tasks/" + item["id"]).status_code == 204
    assert client.get(endpoint).json()["tasks"] == []
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).status_code == 404
    assert client.delete(endpoint).status_code == 404


def test_sql_cascade_and_orphan_rejection(sql):
    project = sql.create("Integrity")
    sql.add_task(project["id"], "Child")
    sql.delete(project["id"])
    with sql.connection() as db:
        assert db.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                       (str(uuid4()), str(uuid4()), "Orphan", "todo", "now", "now"))


def test_sql_transaction_rolls_back(sql):
    project = sql.create("Rollback")
    before = sql.get(project["id"])
    with pytest.raises(sqlite3.IntegrityError):
        sql.add_task(project["id"], "")
    assert sql.get(project["id"]) == before


def test_parameterized_text_is_data(sql):
    name = "O'Brien; project notes"
    assert sql.get(sql.create(name)["id"])["name"] == name
    assert len(sql.list()) == 1


def test_document_is_one_embedded_value(documents):
    project = documents.create("Embedded")
    documents.add_task(project["id"], "Read in one GET")
    raw = documents.client.get(documents.prefix + project["id"])
    value = json.loads(raw)
    assert value["tasks"][0]["title"] == "Read in one GET"
    documents.delete(project["id"])
    assert documents.client.get(documents.prefix + project["id"]) is None


def test_concurrent_document_adds_preserve_both_tasks(documents):
    project = documents.create("Concurrent")
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda n: documents.add_task(project["id"], f"Task {n}"), range(2)))
    assert sorted(task["title"] for task in documents.get(project["id"])["tasks"]) == ["Task 0", "Task 1"]


@pytest.mark.parametrize("engine", ["sql", "redis"])
@pytest.mark.parametrize("payload", [{"name": ""}, {"name": " "}, {"name": "x" * 101}, {"name": "Valid", "extra": 1}])
def test_invalid_input_returns_400(client, engine, payload):
    assert client.post(f"/{engine}/projects", json=payload).status_code == 400


@pytest.mark.parametrize("engine", ["sql", "redis"])
def test_child_cannot_be_updated_through_other_parent(client, engine):
    path = f"/{engine}/projects"
    first = client.post(path, json={"name": "First"}).json()["id"]
    second = client.post(path, json={"name": "Second"}).json()["id"]
    item = client.post(f"{path}/{first}/tasks", json={"title": "Private to first"}).json()["id"]
    assert client.put(f"{path}/{second}/tasks/{item}", json={"title": "Changed", "status": "done"}).status_code == 404
    assert client.get(f"{path}/{first}").json()["tasks"][0]["status"] == "todo"
