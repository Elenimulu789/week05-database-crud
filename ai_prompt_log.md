# AI prompt and audit log

## Initial drafting prompt

> Build a local project-and-task CRUD demo with SQLite and Redis, with commands
> that can be run during a class recording and an audit log explaining the
> modeling decisions. Use normalized SQL parent and child tables, actual foreign
> keys and cascade deletion. Use one embedded JSON project value in Redis, with
> optimistic concurrency to avoid lost task updates. Provide a unified API,
> terminal walkthrough, tests, setup instructions and a recording guide.

ChatGPT generated the schema, CRUD code, HTTP API, test suite, and documentation.
ChatGPT reviewed and corrected the draft and executed the local checks. The
student still needs to run the real Redis walkthrough and record the demo.

## Finding · Unhandled database exceptions in the initial HTTP layer

The first generated API mapped missing records and Redis failures, but omitted
SQLite constraint and lock errors. An integrity violation escaping that layer
would produce an unhelpful server error rather than a controlled response.

The final API registers handlers for SQLite integrity and operational errors.
A focused regression test forces a constraint error and verifies a 409 response
without the internal diagnostic text. A second test verifies that an unavailable
Redis endpoint produces a 503 without exposing connection details.

Before:

```python
@app.exception_handler(Missing)
async def missing(_request, error):
    return JSONResponse({"detail": str(error)}, status_code=404)
# No SQLite exception handler in this draft.
```

After:

```python
@app.exception_handler(sqlite3.IntegrityError)
async def integrity(_request, _error):
    return JSONResponse(
        {"detail": "The database rejected a constraint violation."},
        status_code=409,
    )
```

## Schema audit results

- SQLite has real REFERENCES and ON DELETE CASCADE, and enables foreign keys
  on every opened connection. A negative test executes an orphan INSERT in
  SQLite and verifies an IntegrityError.
- Projects and tasks have separate independent facts. No project names are
  copied into task rows, and the child foreign key has an index.
- Every variable SQL value uses a bound parameter. SQL identifiers are fixed.
- Redis embeds tasks in their parent project's value. The project detail path
  uses one GET, without a second task collection or manual round trips.
- Redis uses WATCH before reading and MULTI/EXEC when replacing the value.
  Conflicts retry from a fresh read, preserving concurrent task additions.
- UUIDs are generated server side. Redis creates keys with NX. SQLite enforces
  primary key uniqueness.
- Redis embeds up to 100 tasks per project to keep aggregate writes bounded.
  A larger, cross-project reporting workload would need a different model.

## Additional verification decisions

The environment blocked an actual Redis server from opening its socket.
The tests therefore use fakeredis by default. Setting REDIS_URL makes the same
suite use a real server. That distinction appears in the README and QA checklist.
The delivered app always uses real Redis for its Redis endpoints.

The test dependencies are cross-platform. The final project does not require
redislite, a Linux-only package explored during local verification.
