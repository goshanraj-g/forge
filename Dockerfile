FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
