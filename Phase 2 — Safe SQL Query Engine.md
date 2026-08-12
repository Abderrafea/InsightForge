# Phase 2 — Safe SQL Query Engine

Continue the existing **AI-Powered Dynamic Dashboard Generator** project from Phase 1.

Phase 1 already contains:

- FastAPI backend;
- App PostgreSQL database;
- external PostgreSQL connection management;
- sessions;
- messages;
- database connection metadata;
- encrypted external database passwords;
- schema inspection;
- schema caching;
- dashboard domain models;
- Docker Compose;
- tests.

Do NOT rebuild or replace working Phase 1 functionality.

Before modifying anything:

1. inspect the existing repository;
2. understand the current architecture;
3. reuse existing services, repositories, models, configuration, and dependency injection;
4. preserve backwards compatibility with existing endpoints and tests.

---

# Phase 2 Goal

Build a secure **read-only SQL query execution layer** that will later be exposed to the LangGraph AI agent as a controlled tool.

The desired future flow will be:

```text
AI Agent
   ↓
generated SQL
   ↓
SafeQueryService
   ↓
SQLGlot parser
   ↓
QueryPolicy
   ↓
ExternalDatabaseConnectionManager
   ↓
User PostgreSQL
   ↓
controlled result
```

However:

**Do NOT implement LangGraph or any LLM yet.**

Phase 2 should contain only deterministic backend functionality.

---

# 1. Add SQLGlot

Install and configure:

```text
sqlglot
```

Use PostgreSQL as the SQL dialect.

Do NOT validate SQL using simple string checks such as:

```python
query.startswith("SELECT")
```

The validator must parse the SQL into an AST using SQLGlot.

Conceptually:

```python
expression = sqlglot.parse_one(
    sql,
    read="postgres"
)
```

Then inspect the parsed syntax tree.

---

# 2. Architecture

Extend the existing project with something similar to:

```text
backend/app/
│
├── query/
│   ├── models.py
│   ├── service.py
│   ├── validator.py
│   ├── policy.py
│   ├── executor.py
│   └── exceptions.py
│
├── security/
│   ├── sql_validator.py
│   └── query_policy.py
│
└── api/
    └── queries.py
```

You may adapt this to the existing architecture.

Responsibilities should remain separated:

```text
API Router
    ↓
Query Service
    ↓
SQL Validator
    ↓
Query Policy
    ↓
Query Executor
    ↓
External Database
```

Do not put SQL validation directly inside FastAPI routes.

---

# 3. Core query models

Create appropriate Pydantic/domain models.

At minimum define something conceptually similar to:

```python
class QueryRequest(BaseModel):
    sql: str
```

```python
class QueryValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    referenced_tables: list[str]
    statement_type: str | None
```

```python
class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    execution_time_ms: float
```

Do not expose driver-specific objects through the API.

Return JSON-safe values.

Handle PostgreSQL types such as:

```text
datetime
date
Decimal
UUID
```

correctly.

---

# 4. SQL Validator

Implement a dedicated SQL validator using SQLGlot.

Suggested abstraction:

```python
class SQLValidator:

    def validate(
        self,
        sql: str,
        allowed_schema: dict | None = None,
    ) -> QueryValidationResult:
        ...
```

The validator must:

1. parse SQL;
2. reject invalid syntax;
3. reject multiple SQL statements;
4. determine statement type;
5. inspect referenced tables;
6. inspect disallowed operations;
7. return structured validation errors.

---

# 5. SELECT-only policy

The first version of the project should allow only read queries.

Allowed root operations:

```text
SELECT
WITH ... SELECT
```

Reject:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
MERGE
COPY
GRANT
REVOKE
VACUUM
ANALYZE
COMMENT
SET
RESET
CALL
DO
```

Also reject transaction-control statements such as:

```text
BEGIN
COMMIT
ROLLBACK
SAVEPOINT
```

The policy should be explicit and easy to extend.

---

# 6. CTE support

Valid analytical SQL frequently uses Common Table Expressions.

Allow:

```sql
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', created_at) AS month,
        SUM(total_amount) AS revenue
    FROM orders
    GROUP BY 1
)
SELECT *
FROM monthly_sales
ORDER BY month;
```

Do not incorrectly reject a query merely because it starts with:

```text
WITH
```

The validator should determine the actual operation represented by the AST.

---

# 7. One statement only

Reject input like:

```sql
SELECT * FROM orders;
DROP TABLE orders;
```

Even if the first statement is valid.

Only a single statement may be submitted.

---

# 8. Schema-aware validation

Phase 1 already contains database schema inspection.

Reuse that functionality.

When validating a query for a particular:

```text
connection_id
```

retrieve the known schema.

Validate referenced tables when reasonably possible.

Example:

```sql
SELECT *
FROM orders;
```

If:

```text
orders
```

exists:

```text
✅ valid table
```

If:

```text
orderzz
```

does not exist:

```text
❌ reject
```

Return an error such as:

```text
Unknown table: orderzz
```

Do the same for explicitly referenced columns where SQLGlot provides enough reliable information.

Be careful with:

```text
aliases
CTEs
derived tables
aggregates
```

Do not create overly naive column validation that rejects valid SQL.

If column validation cannot be safely determined for a complex expression, prefer PostgreSQL execution errors rather than incorrect static rejection.

---

# 9. Schema restrictions

Queries should be limited to approved/user schemas.

By default, allow:

```text
public
```

and other user schemas discovered during schema inspection.

Reject access to system schemas such as:

```text
pg_catalog
information_schema
pg_toast
```

unless the specific schema-inspection infrastructure requires them internally.

User-submitted analytical queries must not access internal PostgreSQL catalogs.

---

# 10. Dangerous function policy

Read-only queries can still call undesirable functions.

Create a configurable denied-function list.

Initially reject dangerous or irrelevant functions such as functions capable of:

- accessing server files;
- executing server-side programs;
- modifying configuration;
- terminating database processes;
- reading environment/server internals.

Do not rely solely on this list for security.

The database connection should still use a restricted read-only database account.

Design this as defense in depth.

---

# 11. Query limits

Create a central:

```python
QueryPolicy
```

with configurable limits.

Suggested defaults:

```text
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 10
MAX_SQL_LENGTH = 20_000
MAX_JOINS = 8
```

Keep values configurable through application settings.

---

# 12. Automatic row limiting

Raw analytical queries should not accidentally return hundreds of thousands of rows.

Implement a result limit.

Preferred behavior:

If the query has no appropriate limit, safely enforce a server-side limit.

Conceptually:

```text
requested query
    ↓
safe wrapper / limit enforcement
    ↓
max 1000 rows
```

Do not modify aggregate queries in a way that changes their meaning.

For example:

```sql
SELECT SUM(total_amount)
FROM orders;
```

does not require a meaningful row limit.

But:

```sql
SELECT *
FROM orders;
```

should return at most the configured number of rows.

An acceptable alternative is to enforce limits during result fetching rather than rewriting SQL.

Choose the safest implementation and document the reasoning.

Return:

```json
{
  "truncated": true
}
```

when additional rows existed but were intentionally not returned.

---

# 13. Database statement timeout

Do not rely only on Python-side timeout handling.

Where possible, configure PostgreSQL statement timeout for the connection/transaction.

Conceptually:

```sql
SET LOCAL statement_timeout = '10s';
```

or use an equivalent safe driver configuration.

The timeout must apply to user analytical queries.

Do not leave a slow query running indefinitely after the HTTP request terminates.

---

# 14. Read-only transaction

When executing user queries, use a PostgreSQL read-only transaction where possible.

Conceptually:

```text
BEGIN READ ONLY
```

or equivalent driver configuration.

This gives another security layer in addition to:

```text
SQLGlot validation
+
read-only PostgreSQL user
```

Your security model should therefore look like:

```text
Generated/User SQL
       ↓
SQLGlot validation
       ↓
Query policy
       ↓
Read-only transaction
       ↓
Read-only PostgreSQL account
       ↓
PostgreSQL
```

---

# 15. Query Executor

Implement something conceptually like:

```python
class SafeQueryExecutor:

    async def execute(
        self,
        connection_id: UUID,
        sql: str,
    ) -> QueryResult:
        ...
```

Responsibilities:

- obtain external DB credentials through the existing secure connection service;
- decrypt internally;
- establish connection;
- execute within a read-only context;
- enforce timeout;
- enforce row/result limits;
- convert rows into JSON-safe dictionaries;
- close connections reliably;
- return controlled metadata.

The AI layer added later should only need:

```python
execute_query(
    connection_id,
    sql,
)
```

It must never need the actual database password.

---

# 16. Safe Query Service

Create a higher-level service:

```python
class SafeQueryService:

    async def validate(...):
        ...

    async def execute(...):
        ...
```

Execution flow:

```text
1. load connection
2. load cached schema
3. validate SQL
4. apply query policy
5. execute query
6. sanitize result
7. return QueryResult
```

Never bypass validation through the public service.

If internal raw execution functionality exists, make it private or clearly isolated.

---

# 17. Query API

Implement:

```http
POST /api/database-connections/{connection_id}/queries/validate
```

Request:

```json
{
  "sql": "SELECT COUNT(*) AS total_orders FROM orders"
}
```

Response:

```json
{
  "valid": true,
  "errors": [],
  "referenced_tables": [
    "orders"
  ],
  "statement_type": "SELECT"
}
```

Invalid example:

```json
{
  "valid": false,
  "errors": [
    "DELETE statements are not allowed"
  ],
  "referenced_tables": [
    "orders"
  ],
  "statement_type": "DELETE"
}
```

---

# 18. Execute query API

Implement:

```http
POST /api/database-connections/{connection_id}/queries/execute
```

Request:

```json
{
  "sql": "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
}
```

Example response:

```json
{
  "columns": [
    "status",
    "count"
  ],

  "rows": [
    {
      "status": "paid",
      "count": 420
    },
    {
      "status": "pending",
      "count": 31
    }
  ],

  "row_count": 2,

  "truncated": false,

  "execution_time_ms": 14.7
}
```

Never return:

- credentials;
- connection strings;
- raw stack traces;
- raw psycopg exceptions.

---

# 19. Session-based query endpoint

Also add an endpoint that uses the database connected to a session.

For example:

```http
POST /api/sessions/{session_id}/queries/execute
```

Request:

```json
{
  "sql": "SELECT COUNT(*) AS customers FROM customers"
}
```

The backend should:

```text
session_id
    ↓
Session
    ↓
database_connection_id
    ↓
SafeQueryService
```

If the session has no database attached:

```text
400 Bad Request
```

with a clean message.

This endpoint is important because the future LangGraph agent will operate primarily in the context of a session.

---

# 20. Query persistence

Create an application DB entity for executed analytical queries.

Suggested:

```text
QueryExecution
--------------------------------
id
session_id nullable
database_connection_id
sql
status
row_count
truncated
execution_time_ms
error_message nullable
created_at
```

Do NOT store full query result datasets in the App Database.

Persist metadata only.

This table will later help with:

```text
query history
agent debugging
dashboard reconstruction
auditability
```

Do not store database credentials in query logs.

---

# 21. Query status

Use a clear enum such as:

```text
SUCCESS
VALIDATION_FAILED
EXECUTION_FAILED
TIMEOUT
```

Store sanitized error information.

Do not persist raw database stack traces.

---

# 22. Query history API

Implement:

```http
GET /api/sessions/{session_id}/queries
```

Return historical queries ordered newest first.

Example:

```json
[
  {
    "id": "...",
    "sql": "SELECT COUNT(*) AS total_orders FROM orders",
    "status": "SUCCESS",
    "row_count": 1,
    "execution_time_ms": 8.2,
    "created_at": "..."
  }
]
```

This will be useful later when the agent modifies an existing dashboard.

---

# 23. Dashboard query definitions

Phase 1 already introduced:

```text
DashboardConfig
queries
widgets
layout
```

Now improve `QueryDefinition`.

Suggested structure:

```python
class QueryDefinition(BaseModel):
    id: str
    name: str
    sql: str
```

Example:

```json
{
  "id": "monthly_revenue",
  "name": "Monthly Revenue",
  "sql": "SELECT ..."
}
```

Do NOT execute DashboardConfig queries automatically yet unless explicitly requested.

The goal is only to make dashboard query definitions compatible with the safe query engine.

---

# 24. Future AI tool API

Design the service layer so Phase 3 can expose tools approximately like:

```python
get_database_schema(connection_id)

validate_sql(connection_id, sql)

execute_sql(connection_id, sql)
```

Later, the LangGraph agent should be able to call:

```text
execute_sql
```

without knowing:

```text
host
port
username
password
```

Keep that boundary strict.

---

# 25. Query error feedback

The future AI agent needs useful error feedback to repair SQL.

Therefore execution errors should be sanitized but still informative.

For example:

Bad:

```text
psycopg.errors.UndefinedColumn:
column orders.pricee does not exist...
internal connection details...
```

Better:

```json
{
  "code": "QUERY_EXECUTION_FAILED",
  "message": "Column 'pricee' does not exist in table 'orders'."
}
```

Possible sanitized categories:

```text
UNKNOWN_TABLE
UNKNOWN_COLUMN
SYNTAX_ERROR
QUERY_TIMEOUT
PERMISSION_DENIED
QUERY_VALIDATION_FAILED
DATABASE_CONNECTION_FAILED
QUERY_EXECUTION_FAILED
```

Create typed domain exceptions where appropriate.

---

# 26. Query result size protection

In addition to row limits, introduce a maximum serialized payload size or equivalent protection.

For example:

```text
MAX_RESULT_BYTES
```

or a practical approximation.

A query could return only 1000 rows but each row might contain very large text fields.

If the maximum response size is exceeded:

- truncate safely;
- report that truncation occurred;
- do not crash the backend.

---

# 27. SQL comments

Support harmless SQL comments where possible:

```sql
-- monthly revenue

SELECT ...
```

But comments must not bypass validation.

Validation must operate on the parsed SQL structure.

---

# 28. Parameterized SQL support

For this phase, the AI-generated queries will eventually be complete analytical SQL strings.

Do not unnecessarily build a complex parameter system yet.

However, design the executor so future parameterized queries could be supported.

Do NOT concatenate sensitive user values into database administrative queries.

---

# 29. Do not execute arbitrary user database commands

Any internal code used for:

```text
schema inspection
connection testing
```

should remain separate from:

```text
analytical user query execution
```

Do not expose a generic:

```python
execute_any_sql()
```

through the application service layer.

Prefer explicit methods:

```python
test_connection()

inspect_schema()

execute_readonly_query()
```

---

# 30. Logging

Add structured logging for query execution.

Useful metadata:

```text
query_execution_id
session_id
connection_id
status
execution_time_ms
row_count
truncated
```

Do NOT log:

```text
database password
encrypted password
complete connection URL with password
query result datasets
```

For SQL itself:

It is acceptable for this portfolio project to log executed SQL at DEBUG level if clearly documented, but avoid logging SQL in production mode by default because queries may contain sensitive literals.

Prefer query IDs and metadata in standard logs.

---

# 31. Tests — SQL validation

Write extensive tests for the validator.

Valid:

```sql
SELECT * FROM orders
```

```sql
SELECT COUNT(*) FROM orders
```

```sql
SELECT
    customer_id,
    SUM(total_amount)
FROM orders
GROUP BY customer_id
```

```sql
WITH revenue AS (
    SELECT SUM(total_amount) AS total
    FROM orders
)
SELECT *
FROM revenue
```

```sql
SELECT
    o.id,
    c.name
FROM orders o
JOIN customers c
    ON c.id = o.customer_id
```

Invalid:

```sql
DELETE FROM orders
```

```sql
UPDATE orders SET status = 'paid'
```

```sql
DROP TABLE customers
```

```sql
CREATE TABLE test(id int)
```

```sql
SELECT * FROM orders;
DROP TABLE orders;
```

```sql
SELECT * FROM pg_catalog.pg_user
```

Also test:

- malformed SQL;
- empty SQL;
- very long SQL;
- unknown table;
- CTE table aliases;
- joins;
- subqueries.

---

# 32. Tests — execution

Using the existing demo ecommerce database, verify:

```text
simple SELECT
aggregate
GROUP BY
JOIN
CTE
ORDER BY
LIMIT
```

Verify:

```text
row limits work
timeouts are handled
connections close correctly
result serialization works
```

---

# 33. Security integration test

Create a dedicated read-only PostgreSQL user for the demo database.

Example:

```text
dashboard_reader
```

It should be able to:

```text
SELECT ✅
```

and unable to:

```text
INSERT ❌
UPDATE ❌
DELETE ❌
DROP ❌
ALTER ❌
CREATE ❌
```

Add tests or setup validation demonstrating these restrictions.

This is important because SQL validation is not the only security boundary.

---

# 34. Demo database improvements

If needed, extend the Phase 1 demo ecommerce database with realistic data.

Tables should include:

```text
customers
products
orders
order_items
payments
```

Use enough records for meaningful analytical queries.

Optional:

Use a deterministic seed so tests remain reproducible.

---

# 35. Example analytical queries

Add sample queries to the README.

Examples:

## Revenue

```sql
SELECT
    SUM(total_amount) AS total_revenue
FROM orders;
```

## Monthly revenue

```sql
SELECT
    DATE_TRUNC('month', created_at) AS month,
    SUM(total_amount) AS revenue
FROM orders
GROUP BY 1
ORDER BY 1;
```

## Top products

```sql
SELECT
    p.name,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p
    ON p.id = oi.product_id
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 10;
```

## New customers by month

```sql
SELECT
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) AS new_customers
FROM customers
GROUP BY 1
ORDER BY 1;
```

All of these should run through the same safe query engine.

---

# 36. README architecture update

Update README with:

```text
Phase 1
Database/session infrastructure

Phase 2
Safe analytical query engine
```

Add architecture:

```text
Client
   ↓
FastAPI
   ↓
SafeQueryService
   ↓
┌─────────────────────┐
│ SQLGlot Validator   │
│ Query Policy        │
│ Timeout             │
│ Result Limits       │
└─────────┬───────────┘
          ↓
ExternalDatabaseConnectionManager
          ↓
Read-only PostgreSQL connection
          ↓
External PostgreSQL
```

Explain defense in depth:

```text
1. SQL AST validation
2. query allowlist/policy
3. read-only transaction
4. restricted DB user
5. timeout
6. row/result limits
```

---

# 37. Do NOT implement in Phase 2

Do not implement:

```text
LangGraph
LangChain agent
Groq
OpenAI
Gemini
Ollama
LLMProvider
LLMFactory
prompt engineering
natural language → SQL
AI dashboard planner
AI dashboard builder
React frontend
RAG
vector database
embeddings
multi-agent system
MCP
```

Those come in Phase 3+.

---

# 38. Important architectural principle

Phase 2 must make the following distinction clear:

```text
LLM/Agent — future
    ↓
UNTRUSTED SQL
    ↓
SafeQueryService
    ↓
TRUST BOUNDARY
    ↓
External PostgreSQL
```

The future AI model should be treated as an **untrusted generator**.

Never assume that SQL is safe merely because an LLM generated it.

The future agent must not have any way to bypass:

```text
SafeQueryService
```

---

# 39. Future LangGraph compatibility

Phase 3 will add approximately:

```text
START
  ↓
understand_request
  ↓
inspect_schema
  ↓
plan_dashboard
  ↓
generate_sql
  ↓
validate_sql
  ↓
execute_sql
  ↓
build_dashboard
  ↓
END
```

Therefore expose clean service functions that future LangGraph nodes can call without HTTP.

For example:

```python
schema = await schema_service.get_schema(
    connection_id
)
```

```python
validation = query_service.validate(
    connection_id,
    sql
)
```

```python
result = await query_service.execute(
    connection_id,
    sql
)
```

Do not make LangGraph depend on FastAPI routes.

The API and future agent should both call the same application services.

Desired structure:

```text
              FastAPI
                 │
                 ▼
         SafeQueryService
                 ▲
                 │
        LangGraph — future
```

This is important.

---

# 40. Implementation order

Work incrementally.

## Step 1

Inspect current Phase 1 implementation.

Run existing tests before changing anything.

## Step 2

Install SQLGlot.

## Step 3

Create:

```text
QueryRequest
QueryResult
QueryValidationResult
```

## Step 4

Implement SQL AST parsing.

## Step 5

Implement SELECT-only policy.

## Step 6

Add schema-aware table validation.

## Step 7

Implement restricted query executor.

## Step 8

Add timeout and result limits.

## Step 9

Implement query persistence.

## Step 10

Add API endpoints.

## Step 11

Add read-only demo DB user.

## Step 12

Add tests.

## Step 13

Update documentation.

Run tests after each important stage.

Fix failures before continuing.

---

# 41. Definition of Done

Phase 2 is complete when I can run:

```bash
docker compose up --build
```

and successfully:

### Validate safe SQL

```http
POST /api/database-connections/{id}/queries/validate
```

with:

```sql
SELECT COUNT(*) FROM orders;
```

and receive:

```text
valid = true
```

### Reject destructive SQL

```sql
DELETE FROM orders;
```

must return:

```text
valid = false
```

### Reject multiple statements

```sql
SELECT * FROM orders;
DROP TABLE orders;
```

must be blocked.

### Execute analytical SQL

```http
POST /api/database-connections/{id}/queries/execute
```

with:

```sql
SELECT
    status,
    COUNT(*)
FROM orders
GROUP BY status;
```

and receive structured JSON results.

### Execute through a session

```http
POST /api/sessions/{session_id}/queries/execute
```

using the database connection attached to that session.

### Enforce row limits

A large query must not return unlimited rows.

### Enforce timeout

A pathological/slow query must terminate safely.

### Protect the database

The demo analytical DB user must be read-only.

### Persist query metadata

Executed queries should appear through:

```http
GET /api/sessions/{session_id}/queries
```

### Run tests

All existing Phase 1 tests and new Phase 2 tests must pass.

---

# 42. Final output after implementation

When implementation is finished, give me a concise technical report containing:

1. files created;
2. files modified;
3. architecture decisions;
4. SQLGlot validation approach;
5. security rules implemented;
6. query execution flow;
7. new API endpoints;
8. migrations created;
9. tests added;
10. commands required to run;
11. known limitations;
12. what is intentionally deferred to Phase 3.

Do not start Phase 3 automatically.

Stop after Phase 2 is fully implemented and tested.