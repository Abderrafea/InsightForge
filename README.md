# InsightForge

InsightForge is a provider-agnostic AI dashboard application. It connects to a customer's PostgreSQL database, understands its schema, and builds or edits dashboards from natural-language requests.

This repository currently contains **Phase 1 through Phase 4**. It includes a provider-agnostic
LangGraph agent, a safe read-only query engine, immutable dashboard versions, and a responsive
React session/chat interface.

## Current Capabilities

Phase 1 provides the database and session foundation:

- Persistent dashboard/chat sessions and chronological messages
- Encrypted external PostgreSQL credentials
- Connection validation with sanitized failures and timeouts
- PostgreSQL schema discovery for tables, columns, primary keys, and foreign keys
- Cached schema metadata with force refresh support
- Dashboard persistence and typed future dashboard configuration models
- Async FastAPI, SQLAlchemy 2, psycopg 3, Alembic, and PostgreSQL
- A Dockerized ecommerce database with a dedicated read-only user
- Unit/API tests plus real PostgreSQL integration tests

Phase 2 adds the deterministic safe analytical query engine:

- PostgreSQL AST parsing with SQLGlot
- One-statement, `SELECT`-only enforcement with CTE support
- Schema-aware table validation and conservative qualified-column validation
- System-schema, dangerous-function, SQL-length, and join-count policies
- Read-only PostgreSQL transactions and database-side statement timeouts
- Server-side cursor streaming with row and serialized-payload limits
- JSON-safe conversion for timestamps, dates, decimals, UUIDs, binary data, and arrays
- Sanitized typed query errors and metadata-only query history
- Direct connection and session-context query endpoints

Phase 3 adds the AI orchestration layer:

- One typed LangGraph workflow for intent, schema inspection, planning, SQL, execution, and build
- Provider-neutral `LLMProvider` strategy with a factory-selected Groq adapter
- Pydantic structured outputs for intent, dashboard plans, generated SQL, and dashboard config
- Visible conditional SQL repair edges with a bounded retry budget
- Deterministic reuse of `SchemaInspectionService` and `SafeQueryService`
- Dashboard referential/field validation before one-per-session persistence
- Durable user/assistant messages and metadata-only `AgentRun` audit records
- Offline mocked-provider tests; real Groq access is optional

Phase 4 adds conversational editing and the product UI:

- Small typed dashboard patches instead of full regeneration for every edit
- `UI_ONLY`, `DATA_QUERY_REQUIRED`, and `MIXED` change classification
- Partial SQL generation, validation, and execution for affected queries only
- Clarification responses that perform no SQL and no dashboard mutation
- Immutable `DashboardVersion` snapshots linked to the assistant message that created them
- Session create/select/rename/delete, safe database connection workflow, and provider display
- Responsive chat, high-level agent progress, and context-aware Open Dashboard actions
- KPI, chart, and table rendering from `DashboardConfig` plus safely refreshed query data

## Architecture

InsightForge keeps two database responsibilities separate:

```text
Client
  |
  v
FastAPI -> Service -> Repository -> App PostgreSQL
                    sessions, messages, encrypted connection metadata,
                    schema cache, and dashboard configuration
  |
  v
ExternalDatabaseConnectionManager -> External PostgreSQL
                                     metadata inspection only in Phase 1
```

The **App Database** belongs to InsightForge. An **External Database** belongs to the user and is reached dynamically using a saved `connection_id`. Credentials are decrypted only inside the backend connection layer; future agent components will never receive raw host credentials.

The Phase 1 request flow follows:

```text
API router -> application service -> repository / database infrastructure
```

The external connection manager creates short-lived connections, applies a timeout, supports PostgreSQL SSL modes, sanitizes driver errors, and closes every connection in a `finally` block.

Phase 2 treats every submitted query, including future AI-generated SQL, as untrusted:

```text
Client / future LangGraph tool
             |
             v
       SafeQueryService
             |
             +--> SQLGlot AST validator
             +--> QueryPolicy and schema checks
             +--> query history metadata
             |
             v
       SafeQueryExecutor
             |
             +--> READ ONLY transaction
             +--> PostgreSQL statement_timeout
             +--> server-side cursor and result limits
             |
             v
ExternalDatabaseConnectionManager
             |
             v
Restricted external PostgreSQL user
```

The API and future agent will call the same `SafeQueryService`; there is no public generic `execute_any_sql` path.

Phase 3 adds orchestration without weakening that boundary:

```text
User -> FastAPI -> AgentService -> LangGraph
                                  |
                 +----------------+----------------+
                 |                |                |
                 v                v                v
            LLMProvider     Schema Service   SafeQueryService
                 |                                 |
                 v                                 v
          GroqProvider adapter              External PostgreSQL
```

The graph topology is:

```text
START -> understand_request -> inspect_schema -> plan_dashboard -> generate_sql
                                                                  |
                                                                  v
                                                             validate_sql
                                                               /      \
                                           invalid + retries /        \ valid
                                                           v            v
                                                     generate_sql  execute_queries
                                                                       |
                                                repairable error -------+
                                                                       v
                                                                build_dashboard
                                                                       |
                                                                      END
```

AI nodes are `understand_request`, `plan_dashboard`, `generate_sql`, and `build_dashboard`.
Schema lookup, validation, execution, retry routing, and persistence are deterministic.

The provider design applies four explicit patterns:

- **Strategy:** `LLMProvider` defines interchangeable model behavior.
- **Factory:** `LLMFactory` selects the configured provider.
- **Adapter:** `GroqProvider` normalizes `ChatGroq` behind the internal protocol.
- **Dependency inversion:** graph nodes depend only on `LLMProvider`, never on `ChatGroq`.

Each graph invocation sets `thread_id = session_id`. The App Database remains the durable product
source of truth for messages and dashboards; Phase 3 does not duplicate chat history in a separate
checkpoint database.

Phase 4 connects the complete stack as follows:

```text
                  React
                    |
              Session Chat UI
                    |
                    v
                 FastAPI
                    |
                    v
                 LangGraph
                    |
       +------------+------------+
       |                         |
       v                         v
   LLMProvider             SafeQueryService
       |                         |
       v                         v
      Groq                  PostgreSQL
```

The modification path preserves unrelated dashboard state:

```text
User request -> Intent classifier -> Load current dashboard -> Modification planner
    -> UI-only? -> Apply deterministic patch
    -> Data change? -> Generate affected SQL only -> Validate -> Execute
    -> Apply patch -> Validate DashboardConfig -> Persist dashboard version
```

## Run With Docker

Requirements: Docker Engine with Docker Compose v2.

```bash
docker compose up --build
```

This starts:

| Service | Purpose | Host port |
|---|---|---:|
| `web` | React application and API reverse proxy | `5173` |
| `api` | FastAPI and automatic Alembic migration | `8001` |
| `app-db` | InsightForge application PostgreSQL | `5435` |
| `demo-db` | External ecommerce PostgreSQL | `5434` |

Check the service:

```bash
curl http://localhost:8001/health
```

Open the application at [http://localhost:5173](http://localhost:5173). Interactive API
documentation is available at [http://localhost:8001/docs](http://localhost:8001/docs).

To enable the AI endpoint, configure a Groq model and API key before starting the API:

```bash
AI_PROVIDER=groq
AI_MODEL=<a Groq model that supports structured output>
GROQ_API_KEY=<secret>
AI_TEMPERATURE=0
AGENT_MAX_SQL_RETRIES=3
AGENT_MAX_CONTEXT_MESSAGES=20
AGENT_MIN_WIDGETS=2
AGENT_MAX_WIDGETS=8
AGENT_RESULT_SAMPLE_ROWS=5
```

No model name is hardcoded. The API can boot without AI credentials so Phase 1/2 routes remain
usable, but the agent endpoint returns a clear configuration error until `AI_MODEL` and
`GROQ_API_KEY` are set.

Inside the Docker network, use these demo external-database values:

```text
host: demo-db
port: 5432
database: demo_ecommerce
username: dashboard_reader
password: dashboard_reader_dev
ssl_mode: disable
```

From a backend running directly on the host, use `localhost` and port `5434` instead.

## Example API Flow

Create a session:

```bash
curl -X POST http://localhost:8001/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"Sales Analysis"}'
```

Test the demo connection:

```bash
curl -X POST http://localhost:8001/api/database-connections/test \
  -H "Content-Type: application/json" \
  -d '{
    "host":"demo-db",
    "port":5432,
    "database_name":"demo_ecommerce",
    "username":"dashboard_reader",
    "password":"dashboard_reader_dev",
    "ssl_mode":"disable"
  }'
```

Save it by sending the same body to `POST /api/database-connections` with `"name":"Ecommerce DB"`. Then attach it and inspect the schema:

```text
PUT /api/sessions/{session_id}/database-connection/{connection_id}
GET /api/database-connections/{connection_id}/schema
GET /api/database-connections/{connection_id}/schema?refresh=true
```

Store and retrieve messages:

```text
POST /api/sessions/{session_id}/messages
GET  /api/sessions/{session_id}/messages
```

Validate and execute analytical SQL:

```text
POST /api/database-connections/{connection_id}/queries/validate
POST /api/database-connections/{connection_id}/queries/execute
POST /api/sessions/{session_id}/queries/execute
GET  /api/sessions/{session_id}/queries
```

Request body:

```json
{
  "sql": "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
}
```

After attaching a database, invoke the dashboard agent:

```bash
curl -X POST http://localhost:8001/api/sessions/{session_id}/agent/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"Build me a sales performance dashboard"}'
```

The response contains the persisted assistant message and the validated `DashboardConfig`. It does
not include prompts, credentials, chain-of-thought, or database result datasets.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/sessions` | Create a session |
| `GET` | `/api/sessions` | List by latest activity |
| `GET` | `/api/sessions/{id}` | Session, messages, safe connection metadata, and dashboard |
| `PATCH` | `/api/sessions/{id}` | Rename a session |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `POST` | `/api/sessions/{id}/messages` | Store a message without calling AI |
| `GET` | `/api/sessions/{id}/messages` | List messages chronologically |
| `POST` | `/api/database-connections/test` | Validate external PostgreSQL access |
| `POST` | `/api/database-connections` | Validate, encrypt, and save a connection |
| `PUT` | `/api/sessions/{id}/database-connection/{connection_id}` | Select a session's active connection |
| `GET` | `/api/database-connections/{id}/schema` | Inspect or retrieve cached metadata |
| `POST` | `/api/database-connections/{id}/queries/validate` | Validate SQL without executing it |
| `POST` | `/api/database-connections/{id}/queries/execute` | Execute a controlled read query |
| `POST` | `/api/sessions/{id}/queries/execute` | Execute through a session's connection |
| `GET` | `/api/sessions/{id}/queries` | List query history newest first |
| `POST` | `/api/sessions/{id}/agent/messages` | Run the LangGraph dashboard workflow |
| `GET` | `/api/sessions/{id}/dashboard` | Get dashboard config and safely refreshed query data |

## Example Queries

Revenue:

```sql
SELECT SUM(total_amount) AS total_revenue
FROM orders;
```

Monthly revenue:

```sql
SELECT
    DATE_TRUNC('month', created_at) AS month,
    SUM(total_amount) AS revenue
FROM orders
GROUP BY 1
ORDER BY 1;
```

Top products:

```sql
SELECT
    p.name,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 10;
```

New customers by month:

```sql
SELECT
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) AS new_customers
FROM customers
GROUP BY 1
ORDER BY 1;
```

## Local Development

Create an environment and install the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Copy `backend/.env.example` to `backend/.env` and adjust the database URL. Generate a new Fernet key instead of using the development example:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Apply migrations and run the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Create new migrations with:

```bash
alembic revision --autogenerate -m "describe the change"
```

Run the frontend locally against an API on port `8000`:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server is available at `http://localhost:5173`. Production Docker uses nginx
to serve the built assets and proxy `/api` directly to the internal API service.

## Phase 4 UI Reference

The session layout follows the supplied [`design.png`](design.png) reference: a 284px desktop
sidebar, chat-focused main area, right-aligned user messages, assistant dashboard actions, and a
bottom composer. The sketch was translated into a responsive operational interface rather than
copied literally. Mobile uses an accessible sidebar drawer and a single-column dashboard.

The palette is implemented as Tailwind design tokens:

```text
#2F4157  primary text and commands
#567C8E  secondary actions and icons
#A2C1D1  borders and selection accents
#C7D9E5  secondary surfaces
#E3ECF2  selected and light surfaces
#F3F6F9  application canvas
```

## Tests

Fast unit and API tests use an isolated SQLite App Database and mock only the external PostgreSQL boundary:

```bash
cd backend
pytest -q
ruff check .
```

Run the complete suite, including schema discovery against the Dockerized PostgreSQL demo database:

```bash
docker compose --profile test run --rm tests
```

Run the frontend tests and production type/build check:

```bash
cd frontend
npm test
npm run build
```

The backend suite also tests provider selection, graph flow, SQL repair, retry exhaustion,
line-to-bar edits without SQL, partial monthly-to-weekly query updates, KPI addition, widget
removal, top-five limits, clarification, version creation, session isolation, provider failure
sanitization, and credential isolation. PostgreSQL integration tests execute SELECT, aggregate,
GROUP BY, JOIN, CTE, ORDER BY, limit, timeout, type-serialization, and payload-limit scenarios.
They verify that `dashboard_reader` cannot INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.

The frontend suite covers session rendering and creation, selection, dashboard actions, composer
keyboard behavior, loading progress, empty state, and disconnected database state.

A real Groq structured-output smoke test exists but is disabled by default. Run it only with valid
AI configuration:

```bash
RUN_GROQ_INTEGRATION_TESTS=1 pytest -q tests/integration/test_groq_provider.py
```

## Security Expectations

- Create a dedicated read-only PostgreSQL user for every external database. Never use `postgres`, a superuser, or the database owner.
- Generate a unique `SECRET_ENCRYPTION_KEY` for each environment and keep it in a secret manager.
- Passwords and encrypted password values are excluded from every response schema.
- Validation responses omit rejected input values because those inputs may contain credentials.
- External errors are mapped to safe messages; raw driver exceptions are never returned.
- SSL modes are supported. Production deployments should normally use `verify-full` with trusted certificates.
- The demo credentials are local-development values and must not be reused elsewhere.
- SQLGlot parses the complete PostgreSQL statement; validation does not use prefix checks.
- Only one root read query is accepted, while mutation nodes inside CTEs are also rejected.
- System schemas and a configurable defense-in-depth list of dangerous functions are blocked.
- Every analytical query runs in a database-enforced read-only transaction.
- PostgreSQL enforces the statement timeout; Python also provides a secondary deadline.
- Named server-side cursors stream bounded batches. The executor fetches one extra row to report truncation and never rewrites aggregate or CTE semantics.
- Query history stores SQL and sanitized metadata, never result datasets or credentials.
- Agent state contains IDs, schema metadata, plans, SQL, bounded result samples, and dashboard
  configuration, but never database passwords, encrypted passwords, or secret-bearing URLs.
- Provider keys stay inside application configuration and the Groq adapter.
- Every AI-generated query is revalidated and executed by Phase 2's `SafeQueryService`.
- Generated dashboards must pass Pydantic structure, reference, and result-field validation before
  storage.
- UI-only modifications never call SQL generation or `SafeQueryService.execute`.
- Session responses expose a connection summary but do not expose host, username, password, or a
  connection string. Connection form credentials live only for the lifetime of the open dialog.
- Standard logs contain provider/model/run metadata, never prompt internals or query results.

Metadata inspection remains separate from analytical query execution and uses PostgreSQL catalogs without reading customer table rows.

## Known Limitations

- Static column validation is intentionally conservative. Qualified columns are checked only when their physical table binding is unambiguous; PostgreSQL reports complex scope errors at execution time.
- SQL functions can have installation-specific side effects that an AST cannot infer. The denied-function list, read-only transaction, and restricted database role must remain layered together.
- Result byte limiting is a practical serialized-response approximation. A bounded cursor batch may briefly hold more data than the final response limit.
- Query parameters are supported by the private executor boundary but are not exposed through the Phase 2 API.
- Query history is session-scoped in the public API; direct connection executions are persisted with a null session for future audit tooling.
- Groq is the only implemented provider adapter; other factory values fail explicitly.
- Provider calls are request/response based; streaming, cancellation, background runs, and durable
  LangGraph checkpoints are not included.
- The dashboard builder sees column metadata and a configurable small sample of already bounded
  query results so it can bind chart fields correctly.
- Version snapshots are persisted, but version browsing and rollback controls are not exposed in
  the Phase 4 UI.
- Contextual reference resolution depends on the configured model's structured output; ambiguous
  matches are deliberately returned as clarification questions.

## Deferred To Phase 5

Potential Phase 5 work includes response streaming, cancellation, version history/rollback UI,
additional provider adapters, richer dashboard interaction, and production authentication. RAG,
embeddings, multi-agent orchestration, billing, scheduling, and unrelated enterprise infrastructure
remain intentionally out of scope unless a future phase explicitly calls for them.
