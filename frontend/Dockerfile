FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Accept build arg for API URL
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build Next.js app (NEXT_PUBLIC_API_URL will be baked into build)
RUN npm run build

# Expose port
EXPOSE 3000

# Start Next.js (Next.js automatically reads PORT env var)
CMD ["npm", "start"]
