# Recording guide

No API key is needed. Start Docker Redis and the API using the README commands.
Have /docs, README.md, ai_prompt_log.md and a second terminal ready. Keep your
webcam visible throughout. Rehearse to about 6:30.

| Time | Action and explanation |
| --- | --- |
| 0:00–1:30 | Show the README ER diagram and sample JSON side by side. Explain that SQLite separates project and task facts with a foreign key. Redis embeds tasks for a one-key lookup. Open the audit log and explain the missing SQLite exception handlers and the controlled HTTP responses added during the AI-assisted review. |
| 1:30–3:30 | Run `uv run python -m src.demo sql --pause`. Advance through create/read/update, the direct table inspection, the rejected orphan insert, task deletion and parent cascade. Explain why the foreign key is enforced inside SQLite. |
| 3:30–5:15 | Run `uv run python -m src.demo redis --pause`. Show embedded tasks and the raw GET output. While paused, optionally inspect the key with redis-cli. Explain the WATCH/MULTI/EXEC update and why concurrent changes trigger a retry. Finish with document deletion and verify the missing key. |
| 5:15–6:30 | Run tests with REDIS_URL pointing to Docker Redis. Show docs/QA.md and the actual results. In /docs, demonstrate a 201, a 200, an invalid 400 and a missing 404. Conclude that SQL fits cross-project queries and enforced relations, while the embedded Redis aggregate fits fetching and replacing a small complete project. |

## Submission copy

### Week 05 Hands-On Assignment Submission

- **Live demo URL** — N/A — Local Polyglot Backend
- **GitHub repository** — [Add your published week05-database-crud URL]
- **Video demonstration** — [Add your verified Unlisted/Public YouTube URL]

#### Video timestamps

- 0:00 — Schema Architecture and AI Audit
- 1:30 — Relational CRUD and Foreign Key Constraint Demo
- 3:30 — NoSQL CRUD and Document Structure Demo
- 5:15 — QA Checklist and Architectural Heuristics
