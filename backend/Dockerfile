FROM python:3.12-slim

WORKDIR /app

# Copy project metadata for dependency install
COPY pyproject.toml ./
COPY backend/ ./backend/

# Install the project and all its dependencies
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "backend.app.workers.temporal_worker"]
