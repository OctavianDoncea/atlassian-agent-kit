FROM python:3.11-slim
WORDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY evals/ evals/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD alembic upgrade head && uvicorn agentkit.api.main:app --host 0.0.0.0 --port 8000