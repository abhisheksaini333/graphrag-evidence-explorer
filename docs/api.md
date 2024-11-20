# Local HTTP API

Requests use JSON, a single bounded Content-Length and the workspace origin. Errors contain an `error` code and, where useful, a message. The API is for a trusted local operator and does not authenticate users.

| Method and path | Operation |
| --- | --- |
| GET `/api/health` | Ready state, current corpus generation and profile |
| GET `/api/documents` | Active document summaries |
| GET `/api/documents/{id}` | Current source revision |
| POST `/api/documents` | Create/update `id`, `title`, `text`, with `expected_revision` for updates |
| POST `/api/documents/{id}/delete` | Tombstone with `expected_revision` |
| POST `/api/demo` | Idempotently add and queue the owned sample collection |
| POST `/api/index` | Queue `document_id`; optional `max_calls` and `max_tokens` |
| GET `/api/jobs` | Job states, attempts and reserved usage |
| POST `/api/jobs/{id}/cancel` | Cancel publication authority |
| POST `/api/jobs/{id}/retry` | Retry within the existing budget/attempt limits |
| GET `/api/extractions/{job_id}` | Current source extraction diagnostics |
| GET `/api/graph` | Current entities, relationships, communities and evidence |
| GET `/api/entities/{id}` | Two-hop source-linked neighborhood |
| GET `/api/passages/{id}` | Current original passage |
| GET `/api/corrections` | Recent correction history |
| POST `/api/corrections` | Set `claim_id`, `status` accepted/rejected, `reason`, `expected_generation` |
| POST `/api/query` | Run `question` in `mode` vector/local/global |
| POST `/api/community-report` | Draft `community_id` with `expected_generation` |
| GET `/api/queries` | Recent query/report records |
| GET `/api/queries/{id}` | Run and model-call diagnostics, with stale-content redaction |

Mutations return409 when the supplied source revision or generation is stale. Reload before deciding again. Query admission returns429 when another query/report is running. A200 query response can contain `status: failed`: the HTTP request completed, but the model output did not satisfy the answer contract. Inspect the run's status and error, not HTTP status alone.
