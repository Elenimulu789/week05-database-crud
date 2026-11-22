"""Identical CRUD behavior over normalized rows and embedded JSON documents."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from redis import Redis, WatchError


class Missing(ValueError):
    pass


class Conflict(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def project(name):
    now = timestamp()
    return {"id": str(uuid4()), "name": name, "created_at": now, "updated_at": now, "tasks": []}


def task(title):
    now = timestamp()
    return {"id": str(uuid4()), "title": title, "status": "todo", "created_at": now, "updated_at": now}


class SQLStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=3)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _get(db, id_):
        rows = db.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   t.id task_id, t.title, t.status, t.created_at task_created, t.updated_at task_updated
            FROM projects p LEFT JOIN tasks t ON p.id = t.project_id
            WHERE p.id = ? ORDER BY t.created_at, t.id
        """, (id_,)).fetchall()
        if not rows:
            raise Missing("Project not found.")
        first = rows[0]
        result = {key: first[key] for key in ("id", "name", "created_at", "updated_at")}
        result["tasks"] = [
            {"id": row["task_id"], "title": row["title"], "status": row["status"],
             "created_at": row["task_created"], "updated_at": row["task_updated"]}
            for row in rows if row["task_id"] is not None
        ]
        return result

    def get(self, id_):
        with self.connection() as db:
            return self._get(db, id_)

    def list(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY created_at, id")]

    def create(self, name):
        value = project(name)
        with self.connection() as db:
            db.execute("INSERT INTO projects VALUES (?, ?, ?, ?)",
                       tuple(value[key] for key in ("id", "name", "created_at", "updated_at")))
        return value

    def rename(self, id_, name):
        with self.connection() as db:
            cursor = db.execute("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?", (name, timestamp(), id_))
            if not cursor.rowcount:
                raise Missing("Project not found.")
            return self._get(db, id_)

    def delete(self, id_):
        with self.connection() as db:
            if not db.execute("DELETE FROM projects WHERE id = ?", (id_,)).rowcount:
                raise Missing("Project not found.")

    def add_task(self, id_, title):
        value = task(title)
        with self.connection() as db:
            if not db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp(), id_)).rowcount:
                raise Missing("Project not found.")
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                       (value["id"], id_, value["title"], value["status"], value["created_at"], value["updated_at"]))
        return value

    def update_task(self, id_, task_id, title, status):
        with self.connection() as db:
            now = timestamp()
            cursor = db.execute("UPDATE tasks SET title = ?, status = ?, updated_at = ? WHERE id = ? AND project_id = ?",
                                (title, status, now, task_id, id_))
            if not cursor.rowcount:
                raise Missing("Task not found.")
            db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, id_))
            return next(t for t in self._get(db, id_)["tasks"] if t["id"] == task_id)

    def delete_task(self, id_, task_id):
        with self.connection() as db:
            if not db.execute("DELETE FROM tasks WHERE id = ? AND project_id = ?", (task_id, id_)).rowcount:
                raise Missing("Task not found.")
            db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp(), id_))


class RedisStore:
    """One project aggregate per key, updated with optimistic concurrency."""
    def __init__(self, client: Redis, prefix="week05:project:"):
        self.client = client
        self.prefix = prefix

    def get(self, id_):
        raw = self.client.get(self.prefix + id_)
        if raw is None:
            raise Missing("Project not found.")
        return json.loads(raw)

    def list(self):
        # SCAN suits this classroom data volume; global listing needs an index at scale.
        keys = sorted(self.client.scan_iter(match=self.prefix + "*", count=100))
        result = []
        for key in keys:
            raw = self.client.get(key)
            if raw is not None:
                value = json.loads(raw)
                result.append({k: value[k] for k in ("id", "name", "created_at", "updated_at")})
        return sorted(result, key=lambda value: (value["created_at"], value["id"]))

    def create(self, name):
        value = project(name)
        if not self.client.set(self.prefix + value["id"], json.dumps(value), nx=True):
            raise Conflict("Generated identifier collided. Retry.")
        return value

    def _edit(self, id_, change):
        key = self.prefix + id_
        for _attempt in range(8):
            with self.client.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    if raw is None:
                        raise Missing("Project not found.")
                    value = json.loads(raw)
                    result = change(value)
                    value["updated_at"] = timestamp()
                    pipe.multi()
                    pipe.set(key, json.dumps(value))
                    pipe.execute()
                    return result
                except WatchError:
                    continue
        raise Conflict("Concurrent edit detected. Retry your request.")

    def rename(self, id_, name):
        def change(value):
            value["name"] = name
            return value
        return self._edit(id_, change)

    def delete(self, id_):
        if not self.client.delete(self.prefix + id_):
            raise Missing("Project not found.")

    def add_task(self, id_, title):
        value = task(title)
        def change(document):
            if len(document["tasks"]) >= 100:
                raise Conflict("The embedded task limit is 100.")
            document["tasks"].append(value)
            return value
        return self._edit(id_, change)

    def update_task(self, id_, task_id, title, status):
        def change(document):
            item = next((item for item in document["tasks"] if item["id"] == task_id), None)
            if item is None:
                raise Missing("Task not found.")
            item.update(title=title, status=status, updated_at=timestamp())
            return item
        return self._edit(id_, change)

    def delete_task(self, id_, task_id):
        def change(document):
            found = next((item for item in document["tasks"] if item["id"] == task_id), None)
            if found is None:
                raise Missing("Task not found.")
            document["tasks"].remove(found)
        self._edit(id_, change)
