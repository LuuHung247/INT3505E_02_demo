# Stage 1: Build dependencies
FROM python:3.10-slim AS builder

WORKDIR /app

# Install dependencies vào virtual environment
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

WORKDIR /app

# Copy virtual environment từ builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy source code
COPY . .

# Set PATH để dùng venv
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 5003

CMD ["python", "book.py"]