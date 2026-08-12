# Project: AI-Powered Dynamic Dashboard Generator — Backend Foundation

I am building a portfolio project for an AI-powered dynamic dashboard system.

The final system will eventually allow a user to:

- create chat sessions;
- connect a PostgreSQL database to a session;
- let a LangGraph AI agent inspect the database schema;
- ask questions about business data in natural language;
- generate safe SQL queries;
- execute those queries;
- generate dashboard configurations;
- render dashboards dynamically in a React frontend;
- modify dashboards conversationally;
- support multiple LLM providers such as Groq, OpenAI, Gemini, and Ollama through an abstraction layer.

However, **do not implement the AI agent, LangGraph, LLM providers, dashboard generation logic, or React frontend yet.**

For this first phase, build only the backend foundation cleanly and professionally.

---

# 1. Technology stack

Use:

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- psycopg 3
- PostgreSQL
- Alembic
- pytest
- Docker
- Docker Compose

Use async APIs where appropriate.

Follow modern Python typing practices.

---

# 2. Architecture requirements

Use a modular architecture with clear separation of responsibilities.

Use a structure similar to:

```text
backend/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   ├── sessions.py
│   │   └── database_connections.py
│   │
│   ├── models/
│   │   ├── session.py
│   │   ├── message.py
│   │   ├── database_connection.py
│   │   └── dashboard.py
│   │
│   ├── schemas/
│   │   ├── session.py
│   │   ├── message.py
│   │   ├── database_connection.py
│   │   └── dashboard.py
│   │
│   ├── repositories/
│   │   ├── session_repository.py
│   │   ├── message_repository.py
│   │   └── database_connection_repository.py
│   │
│   ├── services/
│   │   ├── session_service.py
│   │   ├── database_connection_service.py
│   │   └── schema_inspection_service.py
│   │
│   ├── database/
│   │   ├── app_database.py
│   │   ├── connection_manager.py
│   │   ├── external_database.py
│   │   └── schema_inspector.py
│   │
│   └── core/
│       ├── exceptions.py
│       └── security.py
│
├── tests/
│
├── alembic/
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
└── .env.example
```

You may improve the structure if there is a strong architectural reason, but keep the responsibilities separated.

Avoid unnecessary abstractions.

---

# 3. Important distinction: two database concepts

The application has TWO different database concepts.

## A. Application database

This is PostgreSQL controlled by our application.

It stores:

- sessions;
- chat messages;
- database connection metadata;
- dashboards;
- dashboard configuration;
- timestamps and application state.

Call this the:

```text
App Database
```

## B. External/user database

This is the PostgreSQL database that the user wants the future AI agent to analyze.

Example:

```text
ecommerce database

customers
orders
products
order_items
payments
```

The application must connect to it dynamically using credentials supplied by the user.

Do NOT mix the App Database with external databases.

---

# 4. Application database entities

Implement SQLAlchemy models.

Use UUID primary keys.

Use timezone-aware timestamps.

## User

Do not build authentication yet.

For now, create a minimal User entity only if it makes the relationships cleaner.

Suggested fields:

```text
id
email
created_at
updated_at
```

Authentication will be implemented later.

---

## Session

A session represents one AI/dashboard conversation.

Fields:

```text
id: UUID

user_id: UUID | nullable for now

title: string

database_connection_id: UUID | nullable

ai_provider: string | nullable

ai_model: string | nullable

created_at

updated_at
```

A session should have:

```text
many messages
zero or one active database connection
zero or one current dashboard
```

The AI provider/model fields are placeholders for future development.

Do not integrate any AI SDK.

---

## Message

Fields:

```text
id: UUID

session_id: UUID

role:
    user
    assistant
    system

content: text

created_at
```

Create an enum for the message role.

---

## DatabaseConnection

This represents metadata necessary to connect to an external PostgreSQL database.

Fields:

```text
id: UUID

user_id: UUID | nullable

name: string

database_type: "postgresql"

host: string

port: integer

database_name: string

username: string

encrypted_password: text

ssl_mode: string

created_at

updated_at
```

Important:

Do NOT store plaintext database passwords.

Create a dedicated security service responsible for encryption and decryption.

For this portfolio project, use a proper symmetric encryption approach using a secret key loaded from environment variables.

The encryption API should look conceptually like:

```python
encrypt_secret(value: str) -> str

decrypt_secret(value: str) -> str
```

No password should ever appear in application logs.

Never return the encrypted password or plaintext password through API responses.

---

# 5. Dashboard domain model

Do not implement dashboard generation yet.

Create the persistence/domain models necessary for future use.

A Dashboard belongs to a Session.

Suggested fields:

```text
id
session_id
title
config_json
created_at
updated_at
```

Use PostgreSQL JSONB for the dashboard configuration if appropriate.

Also define Pydantic schemas representing the future DashboardConfig.

The initial supported widget types will eventually be:

```text
kpi
line_chart
bar_chart
pie_chart
area_chart
table
```

Create models such as:

```python
WidgetConfig
DashboardConfig
LayoutConfig
QueryDefinition
```

Keep these models clean but do not create the rendering logic.

A conceptual dashboard structure should support:

```json
{
  "title": "Sales Dashboard",

  "queries": [],

  "widgets": [],

  "layout": []
}
```

Keep query definitions, widgets, and layout separate.

---

# 6. Session API

Implement REST endpoints.

## Create session

```http
POST /api/sessions
```

Request example:

```json
{
  "title": "Sales Analysis"
}
```

Response:

```json
{
  "id": "...",
  "title": "Sales Analysis",
  "created_at": "...",
  "updated_at": "..."
}
```

---

## List sessions

```http
GET /api/sessions
```

Return sessions ordered by most recently updated.

---

## Get session

```http
GET /api/sessions/{session_id}
```

Return:

- session metadata;
- messages;
- linked database connection metadata;
- current dashboard if available.

Never return database passwords.

---

## Delete session

```http
DELETE /api/sessions/{session_id}
```

---

# 7. Message API

Implement:

```http
POST /api/sessions/{session_id}/messages
```

Request:

```json
{
  "role": "user",
  "content": "Build me a sales dashboard"
}
```

For now, this only stores messages.

Do NOT call any AI model.

Also implement:

```http
GET /api/sessions/{session_id}/messages
```

Messages should be ordered chronologically.

---

# 8. External PostgreSQL connection API

Create:

```http
POST /api/database-connections/test
```

Request:

```json
{
  "host": "localhost",
  "port": 5432,
  "database_name": "ecommerce",
  "username": "dashboard_reader",
  "password": "secret",
  "ssl_mode": "prefer"
}
```

The backend should:

1. validate the input;
2. attempt to connect;
3. run a lightweight safe query such as:

```sql
SELECT 1;
```

4. close the connection correctly;
5. return success or a safe user-friendly failure message.

Example:

```json
{
  "success": true
}
```

Do not expose raw driver exceptions containing credentials or sensitive connection details.

---

# 9. Save external database connection

Create:

```http
POST /api/database-connections
```

Input:

```json
{
  "name": "Ecommerce DB",
  "host": "localhost",
  "port": 5432,
  "database_name": "ecommerce",
  "username": "dashboard_reader",
  "password": "secret",
  "ssl_mode": "prefer"
}
```

Before saving:

1. test the connection;
2. reject invalid credentials;
3. encrypt the password;
4. persist only the encrypted password.

Return:

```json
{
  "id": "...",
  "name": "Ecommerce DB",
  "host": "localhost",
  "port": 5432,
  "database_name": "ecommerce",
  "username": "dashboard_reader",
  "ssl_mode": "prefer"
}
```

Never return:

```text
password
encrypted_password
```

---

# 10. Attach database connection to session

Create:

```http
PUT /api/sessions/{session_id}/database-connection/{connection_id}
```

This associates the connection with the session.

A session should be able to change its connected database.

---

# 11. External database connection manager

Implement a dedicated abstraction.

Something conceptually similar to:

```python
class ExternalDatabaseConnectionManager:

    async def test_connection(...):
        ...

    async def create_connection(...):
        ...

    async def close_connection(...):
        ...
```

Do not expose database credentials outside this layer unnecessarily.

Future AI components should reference:

```text
connection_id
```

instead of receiving raw database credentials.

Design the code so a future tool can do:

```python
execute_query(
    connection_id=session.database_connection_id,
    sql=query
)
```

without the AI knowing the host, username, or password.

---

# 12. PostgreSQL schema inspection

Implement:

```http
GET /api/database-connections/{connection_id}/schema
```

The backend should connect to the external PostgreSQL database and return structured schema metadata.

Inspect:

- schemas;
- tables;
- columns;
- PostgreSQL data types;
- nullable status;
- primary keys;
- foreign keys;
- referenced tables;
- referenced columns.

Ignore PostgreSQL internal/system schemas.

Focus primarily on user schemas such as:

```text
public
```

but make the solution reasonably reusable.

Example response:

```json
{
  "database": "ecommerce",

  "tables": [
    {
      "schema": "public",

      "name": "orders",

      "columns": [
        {
          "name": "id",
          "type": "integer",
          "nullable": false,
          "primary_key": true
        },
        {
          "name": "customer_id",
          "type": "integer",
          "nullable": false,
          "primary_key": false
        },
        {
          "name": "total_amount",
          "type": "numeric",
          "nullable": false,
          "primary_key": false
        }
      ],

      "foreign_keys": [
        {
          "column": "customer_id",
          "references_table": "customers",
          "references_column": "id"
        }
      ]
    }
  ]
}
```

Use PostgreSQL metadata/catalog queries or SQLAlchemy inspection where appropriate.

Do not retrieve all rows from the user's tables.

Schema inspection should inspect metadata only.

---

# 13. Schema cache

Create a simple schema cache table in the App Database.

Suggested entity:

```text
DatabaseSchemaCache

id
database_connection_id
schema_json
created_at
updated_at
```

When:

```http
GET /api/database-connections/{connection_id}/schema
```

is called:

- support retrieving a cached schema;
- provide an option to force refresh.

For example:

```http
GET /api/database-connections/{connection_id}/schema?refresh=true
```

The cache will later prevent the AI agent from repeatedly inspecting the database.

---

# 14. Database security requirements

Even though AI is not implemented yet, design this layer securely.

The external DB connection should ideally use a dedicated read-only PostgreSQL user.

Document this expectation in the README.

Never require:

```text
root
postgres superuser
database owner
```

Later, AI-generated SQL will be restricted separately.

For now:

- credentials stay backend-only;
- credentials are encrypted at rest;
- database passwords are never logged;
- external PostgreSQL connections support SSL;
- database exceptions are sanitized;
- connection timeouts must exist;
- connections must always be properly closed.

---

# 15. Configuration

Use Pydantic Settings or an equivalent modern approach.

Environment variables should include something like:

```env
APP_DATABASE_URL=postgresql+psycopg://...

SECRET_ENCRYPTION_KEY=...

APP_ENV=development
```

Create:

```text
.env.example
```

Do not commit real credentials.

---

# 16. Alembic

Set up Alembic migrations.

Create the initial migration for:

```text
users if implemented
sessions
messages
database_connections
dashboards
database_schema_cache
```

Do not rely on:

```python
Base.metadata.create_all()
```

as the primary production migration mechanism.

---

# 17. FastAPI conventions

Use:

```text
/api
```

as the base API prefix.

Add:

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

Use dependency injection for:

- DB sessions;
- services where appropriate.

Implement global exception handling.

Use appropriate HTTP response codes:

```text
200
201
204
400
404
409
422
500
```

Avoid leaking internal stack traces through APIs.

---

# 18. Testing

Write meaningful tests.

At minimum test:

## Sessions

- create session;
- retrieve session;
- list sessions;
- delete session.

## Messages

- create message;
- retrieve messages;
- invalid session.

## Credential security

Verify API responses never expose:

```text
password
encrypted_password
```

## Connection validation

Mock external database connections where appropriate.

Test:

- successful connection;
- incorrect password;
- unreachable host;
- invalid port.

## Schema inspection

Use a test PostgreSQL database with tables such as:

```text
customers
products
orders
order_items
```

Verify that:

- tables are discovered;
- columns are discovered;
- primary keys are detected;
- foreign keys are detected.

---

# 19. Demo database

Add a second PostgreSQL database through Docker Compose representing the external business database.

Call it something like:

```text
demo_ecommerce
```

Create tables:

```text
customers

id
name
email
country
created_at
```

```text
products

id
name
category
price
created_at
```

```text
orders

id
customer_id
total_amount
status
created_at
```

```text
order_items

id
order_id
product_id
quantity
unit_price
```

Add appropriate:

- primary keys;
- foreign keys;
- indexes.

Insert enough synthetic sample records for testing.

The system should therefore run locally with:

```text
App PostgreSQL
+
Demo Ecommerce PostgreSQL
+
FastAPI
```

through Docker Compose.

---

# 20. Docker Compose

Create services conceptually similar to:

```text
api
app-db
demo-db
```

The FastAPI backend should connect to:

```text
app-db
```

for its own persistence.

The user can connect through the API to:

```text
demo-db
```

as if it were an external customer database.

Make sure networking works correctly between containers.

---

# 21. README

Write a professional README explaining:

## Project goal

This project will eventually become a provider-agnostic AI dashboard agent.

## Current phase

Phase 1 implements:

- persistent chat sessions;
- database connection management;
- encrypted database credentials;
- PostgreSQL schema discovery;
- schema caching;
- dashboard domain models;
- clean backend architecture.

## Architecture

Explain clearly:

```text
App PostgreSQL
```

versus:

```text
External PostgreSQL
```

Also document how to run:

```bash
docker compose up --build
```

and migrations.

Document example API usage.

---

# 22. Engineering requirements

Please follow these rules carefully.

### Code quality

- use descriptive names;
- type all public functions;
- keep functions small;
- avoid giant service classes;
- avoid circular dependencies;
- use dependency injection where useful;
- use async correctly;
- follow SOLID principles without overengineering.

### Separation of concerns

API controllers should not contain database logic.

Desired direction:

```text
Router
  ↓
Service
  ↓
Repository / DB infrastructure
```

External database connections should go through:

```text
ExternalDatabaseConnectionManager
```

Schema extraction should go through:

```text
SchemaInspectionService
```

### Security

Never log:

```text
password
connection string containing passwords
API secrets
```

Never expose passwords in API responses.

---

# 23. Do NOT implement yet

Explicitly do NOT implement:

```text
LangGraph
LangChain agents
Groq
OpenAI
Gemini
Ollama
LLM prompts
natural language to SQL
SQLGlot validation
AI-generated SQL
AI dashboard planner
AI dashboard builder
React frontend
authentication
OAuth
RAG
vector database
embeddings
MCP
multi-agent architecture
Kafka
Redis
Kubernetes
```

Those belong to later phases.

Do leave the architecture ready for them.

---

# 24. Future architecture awareness

The next phase will introduce:

```text
LangGraph
     ↓
AgentState
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
```

Therefore design the current services so future LangGraph nodes can easily call functions such as:

```python
get_schema(connection_id)

get_session(session_id)

get_messages(session_id)

get_current_dashboard(session_id)

execute_readonly_query(connection_id, query)
```

Do NOT implement the last AI query execution capability yet unless required for basic database testing.

---

# 25. Implementation process

Do not generate the entire project blindly in one huge step.

Work incrementally.

First:

1. inspect the repository;
2. create or confirm the project structure;
3. configure dependencies;
4. configure App PostgreSQL;
5. create SQLAlchemy models;
6. set up Alembic;
7. implement session/message persistence;
8. implement external database connection handling;
9. implement credential encryption;
10. implement schema inspection;
11. implement schema caching;
12. add the demo ecommerce database;
13. add tests;
14. update README.

After each major section:

- run tests;
- run static/type checks if configured;
- fix failures before continuing.

Do not leave placeholder implementations if the functionality can reasonably be completed.

---

# 26. Definition of Done

Phase 1 is complete when I can:

### Start everything

```bash
docker compose up --build
```

### Create a session

```text
POST /api/sessions
```

### Save messages

```text
POST /api/sessions/{id}/messages
```

### Test an external PostgreSQL connection

```text
POST /api/database-connections/test
```

### Save the connection securely

```text
POST /api/database-connections
```

### Attach it to the session

```text
PUT /api/sessions/{session_id}/database-connection/{connection_id}
```

### Inspect its schema

```text
GET /api/database-connections/{connection_id}/schema
```

and receive tables, columns, PKs, and FKs.

### Reopen a session

and retrieve:

```text
session
messages
database connection metadata
dashboard if one exists
```

without exposing database passwords.

### Run tests successfully

All tests should pass.

---

Build this as production-style portfolio code rather than a quick prototype.

Prefer clarity and maintainability over unnecessary complexity.

At the end, provide a concise summary of:

- files created;
- architecture decisions;
- endpoints implemented;
- tests implemented;
- commands required to run the project;
- anything intentionally deferred to Phase 2.