FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy pyproject.toml
COPY pyproject.toml .

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Default command
CMD ["uv", "run", "ea", "cli"]
