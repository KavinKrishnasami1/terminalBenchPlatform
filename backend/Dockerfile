FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (git for Harbor, docker for containers)
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Create both virtual environments
RUN python -m venv /app/venv
RUN python -m venv /app/harbor-venv

# Install FastAPI backend dependencies
COPY requirements.txt .
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Install Harbor in separate venv to avoid dependency conflicts
RUN /app/harbor-venv/bin/pip install --no-cache-dir \
    git+https://github.com/laude-institute/harbor.git

# Copy backend code
COPY . .

# Set PATH to use main venv by default
ENV PATH="/app/venv/bin:$PATH"
# Set Harbor binary path for subprocess calls
ENV HARBOR_BIN="/app/harbor-venv/bin/harbor"

# Expose port (Railway will use $PORT env var)
EXPOSE 8001

# Start FastAPI server using main venv
# Use $PORT from Railway, fallback to 8001 for local development
CMD ["/bin/bash", "-c", "/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}"]
