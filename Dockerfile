# Stage 1: Build Nuxt frontend
FROM node:22-slim AS build

RUN corepack enable && corepack prepare pnpm@10.18.2 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN pnpm build


# Stage 2: Production
FROM python:3.13-slim

# Install Node.js 22 (needed for Nuxt SSR runtime) and ffmpeg (needed for yt-dlp postprocessing)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates ffmpeg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy Nuxt build output
COPY --from=build /app/.output ./.output

# Copy backend source
COPY backend/ ./backend/

# Copy start script
COPY start.sh ./start.sh
RUN chmod +x start.sh

# Create directories for runtime data
RUN mkdir -p downloads /app/nltk_data

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NLTK_DATA=/app/nltk_data

EXPOSE 3000

CMD ["./start.sh"]
