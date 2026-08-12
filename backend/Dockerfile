FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --upgrade pip && pip install .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

USER app

FROM base AS test
USER root
RUN pip install "setuptools>=75" wheel \
    && pip install --no-build-isolation ".[dev]"
COPY backend/tests ./tests
USER app
CMD ["pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
