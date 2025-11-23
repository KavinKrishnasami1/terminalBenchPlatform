FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (git for Harbor, docker for containers)
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Docker Compose plugin manually
RUN mkdir -p /usr/local/lib/docker/cli-plugins && \
    curl -SL https://github.com/docker/compose/releases/download/v2.31.0/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

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

# Copy and make startup scripts executable
COPY start.sh /app/start.sh
COPY start-worker.sh /app/start-worker.sh
RUN chmod +x /app/start.sh /app/start-worker.sh

# Expose port (Railway/Fly.io will use $PORT env var)
EXPOSE 8001

# Default command: start Docker daemon and FastAPI server
# For worker: override with start-worker.sh
CMD ["/app/start.sh"]
