"""A terminal walkthrough with database inspection after each CRUD operation."""
import argparse
import json
import os
from uuid import uuid4
import sqlite3

from redis import Redis

from src.stores import RedisStore, SQLStore


def show(label, value):
    print("\n" + label)
    print(json.dumps(value, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", choices=["sql", "redis"])
    parser.add_argument("--pause", action="store_true", help="Pause between steps for recording")
    args = parser.parse_args()

    client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_timeout=2)
    store = SQLStore("data/projects.db") if args.engine == "sql" else RedisStore(client)

    def step(label, value):
        show(label, value)
        if args.pause:
            input("Press Enter for the next step...")

    try:
        project = store.create("Classroom release")
        id_ = project["id"]
        step("CREATE project", project)
        item = store.add_task(id_, "Review the data model")
        step("CREATE task", item)
        step("READ complete project", store.get(id_))
        step("LIST projects", store.list())
        step("UPDATE project", store.rename(id_, "Classroom release reviewed"))
        step("UPDATE task", store.update_task(id_, item["id"], "Model reviewed", "done"))

        if args.engine == "sql":
            with store.connection() as db:
                step("Direct SQLite rows", {
                    "projects": [dict(row) for row in db.execute("SELECT * FROM projects WHERE id = ?", (id_,))],
                    "tasks": [dict(row) for row in db.execute("SELECT * FROM tasks WHERE project_id = ?", (id_,))],
                    "foreign_keys": db.execute("PRAGMA foreign_keys").fetchone()[0],
                })
            try:
                with store.connection() as db:
                    db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
                               (str(uuid4()), str(uuid4()), "Orphan", "todo", "now", "now"))
            except sqlite3.IntegrityError as error:
                step("REJECTED orphan insert", {"error": str(error)})
        else:
            raw = client.get(store.prefix + id_)
            step("Direct Redis GET of the embedded document", json.loads(raw))

        store.delete_task(id_, item["id"])
        step("DELETE task", store.get(id_))
        store.add_task(id_, "Child to check during parent deletion")
        store.delete(id_)
        if args.engine == "sql":
            with store.connection() as db:
                remaining = db.execute("SELECT count(*) FROM tasks WHERE project_id = ?", (id_,)).fetchone()[0]
                step("DELETE project and verify cascade", {"remaining_child_rows": remaining})
        else:
            step("DELETE project and embedded tasks", {"redis_key_exists": bool(client.exists(store.prefix + id_))})
    finally:
        client.close()


if __name__ == "__main__":
    main()
