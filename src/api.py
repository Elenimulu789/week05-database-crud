"""Unified HTTP CRUD surface. Interactive Swagger UI is at /docs."""
from contextlib import asynccontextmanager
import os
import sqlite3
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis import Redis, RedisError

from src.stores import Conflict, Missing, RedisStore, SQLStore


class Name(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a nonempty project name.")
        return value


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a nonempty task title.")
        return value


class TaskUpdate(TaskInput):
    status: Literal["todo", "done"]


def create_app(sql=None, documents=None):
    @asynccontextmanager
    async def lifespan(app):
        yield
        if owned:
            client.close()

    owned = documents is None
    client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                            socket_connect_timeout=2, socket_timeout=2)
    stores = {
        "sql": sql or SQLStore(Path(os.getenv("SQLITE_PATH", "data/projects.db"))),
        "redis": documents or RedisStore(client),
    }
    app = FastAPI(title="Project CRUD · SQLite and Redis", lifespan=lifespan)

    @app.exception_handler(Missing)
    async def missing(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity(_request, _error):
        return JSONResponse({"detail": "The database rejected a constraint violation."}, status_code=409)

    @app.exception_handler(sqlite3.OperationalError)
    async def sql_unavailable(_request, _error):
        return JSONResponse({"detail": "The SQL database is busy or unavailable."}, status_code=503)

    @app.exception_handler(RedisError)
    async def unavailable(_request, _error):
        return JSONResponse({"detail": "Redis is unavailable. Start the Redis service."}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request, _error):
        return JSONResponse({"detail": "Check the engine, identifiers, required fields, and field lengths."}, status_code=400)

    def store(engine):
        return stores[engine]

    @app.get("/")
    def home():
        return {"application": "Project CRUD", "interactive_api": "/docs", "engines": list(stores)}

    @app.get("/{engine}/projects")
    def list_projects(engine: Literal["sql", "redis"]):
        return store(engine).list()

    @app.post("/{engine}/projects", status_code=201)
    def create_project(engine: Literal["sql", "redis"], body: Name):
        return store(engine).create(body.name)

    @app.get("/{engine}/projects/{id_}")
    def get_project(engine: Literal["sql", "redis"], id_: UUID):
        return store(engine).get(str(id_))

    @app.put("/{engine}/projects/{id_}")
    def rename_project(engine: Literal["sql", "redis"], id_: UUID, body: Name):
        return store(engine).rename(str(id_), body.name)

    @app.delete("/{engine}/projects/{id_}", status_code=204)
    def delete_project(engine: Literal["sql", "redis"], id_: UUID):
        store(engine).delete(str(id_))
        return Response(status_code=204)

    @app.post("/{engine}/projects/{id_}/tasks", status_code=201)
    def add_task(engine: Literal["sql", "redis"], id_: UUID, body: TaskInput):
        return store(engine).add_task(str(id_), body.title)

    @app.put("/{engine}/projects/{id_}/tasks/{task_id}")
    def update_task(engine: Literal["sql", "redis"], id_: UUID, task_id: UUID, body: TaskUpdate):
        return store(engine).update_task(str(id_), str(task_id), body.title, body.status)

    @app.delete("/{engine}/projects/{id_}/tasks/{task_id}", status_code=204)
    def delete_task(engine: Literal["sql", "redis"], id_: UUID, task_id: UUID):
        store(engine).delete_task(str(id_), str(task_id))
        return Response(status_code=204)

    return app
