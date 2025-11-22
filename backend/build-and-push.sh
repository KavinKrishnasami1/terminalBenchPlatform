#!/bin/bash

# Build and push Docker image for Railway deployment
# Usage: ./build-and-push.sh [docker-hub|github]

set -e  # Exit on error

# Configuration
REGISTRY=${1:-"docker-hub"}  # Default to docker-hub
IMAGE_NAME="tbench-backend"
VERSION=${2:-"latest"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building Docker image for Railway deployment${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
  exit 1
fi

# Get username based on registry
if [ "$REGISTRY" = "github" ]; then
  read -p "Enter your GitHub username: " USERNAME
  IMAGE_TAG="ghcr.io/${USERNAME}/${IMAGE_NAME}:${VERSION}"
  REGISTRY_NAME="GitHub Container Registry"
else
  read -p "Enter your Docker Hub username: " USERNAME
  IMAGE_TAG="${USERNAME}/${IMAGE_NAME}:${VERSION}"
  REGISTRY_NAME="Docker Hub"
fi

echo ""
echo -e "${YELLOW}Registry: ${REGISTRY_NAME}${NC}"
echo -e "${YELLOW}Image: ${IMAGE_TAG}${NC}"
echo ""

# Build the image
echo -e "${GREEN}📦 Building Docker image...${NC}"
docker build -t ${IMAGE_TAG} .

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✅ Build successful!${NC}"
else
  echo -e "${RED}❌ Build failed${NC}"
  exit 1
fi

# Test the image locally
echo ""
echo -e "${GREEN}🧪 Testing image locally...${NC}"
echo "Starting container on port 8001..."

# Kill any existing container on port 8001
docker stop tbench-test 2>/dev/null || true
docker rm tbench-test 2>/dev/null || true

# Start test container
docker run -d \
  --name tbench-test \
  -p 8001:8001 \
  -e OPENROUTER_API_KEY=test-key \
  ${IMAGE_TAG}

# Wait for startup
echo "Waiting for startup..."
sleep 5

# Test health endpoint
if curl -f http://localhost:8001/ > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Container is healthy!${NC}"
  docker stop tbench-test
  docker rm tbench-test
else
  echo -e "${RED}❌ Container health check failed${NC}"
  echo "Logs:"
  docker logs tbench-test
  docker stop tbench-test
  docker rm tbench-test
  exit 1
fi

# Ask to push
echo ""
read -p "Push to ${REGISTRY_NAME}? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${GREEN}🚀 Pushing to ${REGISTRY_NAME}...${NC}"

  # Login if needed
  if [ "$REGISTRY" = "github" ]; then
    echo "Login to GitHub Container Registry (you'll need a Personal Access Token)"
    docker login ghcr.io -u ${USERNAME}
  else
    echo "Login to Docker Hub"
    docker login
  fi

  # Push
  docker push ${IMAGE_TAG}

  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Successfully pushed!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next steps:${NC}"
    echo "1. Go to Railway dashboard"
    echo "2. Select your backend service"
    echo "3. Settings → Source → Docker Image"
    echo "4. Enter: ${IMAGE_TAG}"
    echo "5. Click Deploy"
    echo ""
    echo -e "${GREEN}Image: ${IMAGE_TAG}${NC}"
  else
    echo -e "${RED}❌ Push failed${NC}"
    exit 1
  fi
else
  echo "Skipping push"
fi
