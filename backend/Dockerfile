FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app /app/app

# Copy ML runtime (ml/src + artifacts). Build context must be the repo root:
#   docker build -f backend/Dockerfile <repo-root>
COPY ml /app/ml

# Make both app/ and ml/ importable (predict.py imports from ml.src)
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
