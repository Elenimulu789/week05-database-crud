# QA checklist and evidence

## Executed locally

| Check | Evidence |
| --- | --- |
| SQL parent and child create/read | API test and direct SQL walkthrough |
| SQL project and task update | API test confirms returned and subsequent state |
| SQL parent deletion cascades | Direct query confirms zero remaining child rows |
| Orphan insert rejected | Actual SQLite IntegrityError from an invalid parent UUID |
| SQL failed child insert rolls back parent timestamp | Transaction rollback regression |
| Redis document create/read/update/delete | fakeredis test of the production RedisStore |
| Concurrent task additions preserve both items | Two-writer test through WATCH/MULTI/EXEC against fakeredis |
| 200, 201, 204, 400, 404, 409 and 503 responses | API regression tests |
| Long, empty and whitespace-only names rejected | Parameterized validation tests |

See [test-results.txt](test-results.txt) and
[sql-demo-results.txt](sql-demo-results.txt).

## Remaining live checks on your laptop

- [ ] Start Docker Redis and run the suite with REDIS_URL set. Record the result.
- [ ] Run the Redis walkthrough and show the actual document in redis-cli.
- [ ] Open /docs and execute SQL and Redis requests. In DevTools Network, verify
      response codes and inspect terminal output.
- [ ] Record the direct SQL orphan rejection and parent cascade result.
- [ ] Keep webcam visible and record a final video between five and seven minutes.

The project uses the interactive API documentation and terminal walkthroughs.
A separate custom frontend was not built, so custom page mobile-layout testing
does not apply. The Redis simulator tests do not establish live Redis, Docker,
browser, or persistence behavior.
