# Docker Deployment

This directory contains Docker configuration files for Executive Assistant.

## Quick Start

### Build and Push Docker Image

```bash
# From the docker/ directory OR project root
cd docker/
bash build.sh
```

The `build.sh` script automatically switches to the project root before building.

### Deploy with Docker Compose

```bash
# From the docker/ directory OR project root
cd docker/
bash deploy.sh
```

The `deploy.sh` script automatically:
1. Pulls latest code from git
2. Pulls updated Docker images
3. Restarts containers
4. Streams logs

## Manual Docker Commands

### Build Image

```bash
# From project root
docker build --platform linux/amd64 -f docker/Dockerfile -t executive_assistant:latest .
```

### Start Services

```bash
# From project root
docker compose -f docker/docker-compose.yml up -d
```

### Stop Services

```bash
# From project root
docker compose -f docker/docker-compose.yml down
```

### View Logs

```bash
# All services
docker compose -f docker/docker-compose.yml logs -f

# Specific service
docker compose -f docker/docker-compose.yml logs -f executive_assistant
docker compose -f docker/docker-compose.yml logs -f postgres
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key variables:
- `ANTHROPIC_API_KEY` - Anthropic API key
- `OPENAI_API_KEY` - OpenAI API key
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` - Database config
- `EXECUTIVE_ASSISTANT_CHANNELS` - Channels to enable (telegram,http)

### First-Time Setup

Fix permissions for admin files:

```bash
sudo chown -R 1000:1000 ./data/admins
chmod -R u+rwX ./data/admins
```

## Files

- `Dockerfile` - Container image definition
- `docker-compose.yml` - Multi-container orchestration
- `build.sh` - Build and push image
- `deploy.sh` - Deploy and restart services
- `.env` - Environment configuration (not in git)
- `config.yaml` - Application configuration
- `migrations/` - Database migrations

## Troubleshooting

### Build fails with "no such file or directory"

Make sure you're running the scripts from the correct directory. The scripts automatically switch to the project root, so they work from anywhere:

```bash
# Both of these work now:
cd docker/ && bash build.sh
bash docker/build.sh
```

### Container won't start

Check logs:
```bash
docker compose -f docker/docker-compose.yml logs executive_assistant
```

### Database connection errors

Ensure postgres is running:
```bash
docker compose -f docker/docker-compose.yml ps postgres
```

### Permission errors on admin files

```bash
sudo chown -R 1000:1000 ./data/admins
chmod -R u+rwX ./data/admins
```
