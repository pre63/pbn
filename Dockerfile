# Base image with dependencies
FROM python:3.13-alpine AS base

# Install system dependencies for LaTeX and psutil
RUN apk add --no-cache \
    py3-pip \
    && rm -rf /var/cache/apk/*

# App image
FROM base

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py /app/
COPY src/ /app/src/
COPY static/ /app/static/
COPY templates/ /app/templates/
COPY content/ /app/content/

# Run as non-root user
USER nobody

# Expose port 8080
EXPOSE 8080

# Command to run the application
CMD ["python3", "-m", "src.app"]