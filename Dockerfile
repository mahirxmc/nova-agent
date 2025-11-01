# Nova Agent Dockerfile - Optimized for Northflank
FROM python:3.11-slim
# Set environment variables for optimized performance
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
# Install system dependencies for Playwright and browser automation
RUN apt-get update && apt-get install -y \
# Essential packages
ca-certificates \
fonts-liberation \
libasound2 \
libatk-bridge2.0-0 \
libdrm2 \
libgtk-3-0 \
libnspr4 \
libnss3 \
libxcomposite1 \
libxdamage1 \
libxrandr2 \
libxss1 \
libxtst6 \
xdg-utils \
libu2f-udev \
libvulkan1 \
# Additional dependencies for better compatibility
wget \
gnupg \
unzip \
curl \
git \
# Memory optimization
&& apt-get install -y --no-install-recommends \
&& rm -rf /var/lib/apt/lists/*
# Set working directory
WORKDIR /app
# Copy requirements first for better caching
COPY requirements.txt .
# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
pip install --no-cache-dir -r requirements.txt
# Install Playwright browsers
RUN playwright install chromium && \
playwright install-deps chromium
# Copy application code
COPY . .
# Create directories for screenshots and temporary files
RUN mkdir -p /tmp/screenshots /tmp/data && \
chmod 755 /tmp/screenshots /tmp/data
# Set environment variables for the application
ENV PORT=7860
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONPATH=/app
# Expose the port
EXPOSE 7860
# Health check to ensure the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
CMD curl -f http://localhost:7860/health || exit 1
# Start the application
CMD ["python", "main.py"]
