# Nova Agent - Docker Container Configuration
# Optimized for Northflank deployment and always-on free tier

# Use Python 3.11 slim image for better performance
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    libglib2.0-0 \
    libnss3-dev \
    libxss-dev \
    libappindicator3-1 \
    libsecret-1-0 \
    libnotify4 \
    gconf-service \
    libasound2-plugins \
    libatk-adaptor \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .

# Create necessary directories
RUN mkdir -p /tmp/screenshots /tmp/data /tmp/logs

# Set proper permissions
RUN chmod +x main.py

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Set user for security
RUN useradd -m -u 1000 nova && chown -R nova:nova /app
USER nova

# Start the application
CMD ["python", "main.py"]
