# InsightForge

InsightForge is the backend foundation for a provider-agnostic AI dashboard agent. The finished product will connect to a customer's PostgreSQL database, understand its schema, answer business questions, and build editable dashboards from natural-language requests.

This repository currently contains **Phase 1 and Phase 2**. There is intentionally no LLM, agent, generated SQL, or frontend yet.

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

## Run With Docker

Requirements: Docker Engine with Docker Compose v2.

```bash
docker compose up --build
```

This starts:

| Service | Purpose | Host port |
|---|---|---:|
| `api` | FastAPI and automatic Alembic migration | `8000` |
| `app-db` | InsightForge application PostgreSQL | `5433` |
| `demo-db` | External ecommerce PostgreSQL | `5434` |

Check the service:

```bash
curl http://localhost:8000/health
```

Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

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
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"Sales Analysis"}'
```

Test the demo connection:

```bash
curl -X POST http://localhost:8000/api/database-connections/test \
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

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/sessions` | Create a session |
| `GET` | `/api/sessions` | List by latest activity |
| `GET` | `/api/sessions/{id}` | Session, messages, safe connection metadata, and dashboard |
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

The integration suite also executes SELECT, aggregate, GROUP BY, JOIN, CTE, ORDER BY, limit, timeout, type-serialization, and payload-limit scenarios. It verifies that `dashboard_reader` cannot INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.

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

Metadata inspection remains separate from analytical query execution and uses PostgreSQL catalogs without reading customer table rows.

## Known Limitations

- Static column validation is intentionally conservative. Qualified columns are checked only when their physical table binding is unambiguous; PostgreSQL reports complex scope errors at execution time.
- SQL functions can have installation-specific side effects that an AST cannot infer. The denied-function list, read-only transaction, and restricted database role must remain layered together.
- Result byte limiting is a practical serialized-response approximation. A bounded cursor batch may briefly hold more data than the final response limit.
- Query parameters are supported by the private executor boundary but are not exposed through the Phase 2 API.
- Query history is session-scoped in the public API; direct connection executions are persisted with a null session for future audit tooling.

## Deferred To Phase 3

LangGraph state and nodes, LLM provider adapters, natural-language-to-SQL, dashboard planning/building, conversational editing, React rendering, authentication, RAG, embeddings, and multi-agent infrastructure are intentionally deferred.

The current services expose the boundaries Phase 3 needs: sessions are addressable by ID, schemas are cached by connection ID, SQL validation and execution share one service, dashboard query definitions contain stable IDs/names/SQL, and database credentials remain behind the external connection manager.
