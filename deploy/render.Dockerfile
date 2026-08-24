FROM node:22-alpine AS web-build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST_DIR=/app/web APP_ENV=production ACCESS_MODE=public \
    DEPLOYMENT_MODE=render MAX_CONCURRENT_REQUESTS=2 APP_DB_POOL_SIZE=3 \
    AGENT_RESULT_SAMPLE_ROWS=0
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --upgrade pip && pip install .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=web-build /web/dist ./web
USER app
EXPOSE 10000
CMD ["python", "-m", "app.render_start"]
