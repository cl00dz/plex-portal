# Dockerfile for Plex Portal Application
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    DEBUG=False

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Expose port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
