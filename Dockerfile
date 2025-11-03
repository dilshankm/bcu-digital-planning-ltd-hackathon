# =============================
# 1. Builder stage
# =============================
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Configure pip and trusted hosts
RUN pip config set global.trusted-host "pypi.org pypi.python.org files.pythonhosted.org"

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================
# 2. Runtime stage
# =============================
FROM python:3.10-slim

# Minimal runtime setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app directory and user WITH home directory
WORKDIR /app
RUN groupadd -r appuser && \
    useradd -r -g appuser -m -d /home/appuser appuser

# Copy your app code
COPY . .

# Create DSPy cache directory and fix all permissions
RUN mkdir -p /home/appuser/.dspy_cache && \
    chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 8080

# Start your FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
