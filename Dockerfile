# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY --chown=app:app api /app/api
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Development image: adds pytest and ruff.
FROM runtime AS dev
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
USER app
