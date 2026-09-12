FROM python:3.12-slim

WORKDIR /app

# Python runtime performance and hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root application user
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# Copy application code and ML runtime (build context: repo root)
COPY --chown=appuser:appuser backend/app /app/app
COPY --chown=appuser:appuser ml /app/ml

USER appuser

EXPOSE 8000

# Docker healthcheck querying the backend health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').getcode() == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
