#!/bin/bash
# Nova Agent - Quick Setup Script
# This script helps you set up Nova Agent for local development and Northflank deployment

set -e

echo "🚀 Nova Agent - Quick Setup Script"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the Nova Agent project directory."
    exit 1
fi

# Step 1: Environment Setup
echo "📋 Step 1: Setting up environment..."
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "✅ Created .env file from template"
        echo "⚠️  Please edit .env file and add your Groq API key"
    else
        echo "❌ .env.template not found"
        exit 1
    fi
else
    echo "✅ .env file already exists"
fi

# Step 2: Install Python dependencies
echo ""
echo "📦 Step 2: Installing Python dependencies..."
if command -v python3 &> /dev/null; then
    python3 -m pip install -r requirements.txt
    echo "✅ Python dependencies installed"
else
    echo "❌ Python3 not found. Please install Python 3.11 or later."
    exit 1
fi

# Step 3: Install Playwright browsers
echo ""
echo "🎭 Step 3: Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium
echo "✅ Playwright browsers installed"

# Step 4: Create necessary directories
echo ""
echo "📁 Step 4: Creating directories..."
mkdir -p screenshots data logs
echo "✅ Directories created"

# Step 5: Test local run
echo ""
echo "🧪 Step 5: Testing local setup..."
echo "Starting Nova Agent locally for 10 seconds..."

# Start Nova Agent in background, then stop it after testing
timeout 10s python main.py 2>/dev/null &
PID=$!

# Wait a bit for startup
sleep 3

# Check if it's running
if ps -p $PID > /dev/null; then
    echo "✅ Nova Agent started successfully!"
    kill $PID 2>/dev/null || true
    wait $PID 2>/dev/null || true
else
    echo "⚠️  Nova Agent may not have started properly. Check the logs above."
fi

# Step 6: Git setup (if not already a git repo)
echo ""
echo "📋 Step 6: Git repository setup..."
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
    git add .
    git commit -m "Initial commit: Nova Agent application"
    echo "✅ Git repository initialized and committed"
else
    echo "✅ Git repository already exists"
fi

# Step 7: Docker setup check
echo ""
echo "🐳 Step 7: Docker setup check..."
if command -v docker &> /dev/null; then
    echo "✅ Docker found"
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        echo "✅ Docker Compose found"
        echo "💡 Use 'docker-compose up' to run with Docker"
    else
        echo "⚠️  Docker Compose not found"
    fi
else
    echo "⚠️  Docker not found (optional for local development)"
fi

# Step 8: Final instructions
echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "📋 Next Steps:"
echo "1. Edit .env file and add your Groq API key"
echo "2. Test locally: python main.py"
echo "3. Or use Docker: docker-compose up"
echo "4. Deploy to Northflank using the deployment guide"
echo ""
echo "🔑 Groq API Key:"
echo "- Get free key from: https://console.groq.com"
echo "- No credit card required"
echo "- 14,400 free requests per day"
echo ""
echo "🚀 Northflank Deployment:"
echo "- See: docs/northflank-deployment-guide.md"
echo "- Always-on, completely free"
echo "- 2 services, no credit card charges"
echo ""
echo "📚 Documentation:"
echo "- main.py: Main application file"
echo "- requirements.txt: Python dependencies"
echo "- Dockerfile: Container configuration"
echo "- northflank.yaml: Northflank deployment config"
echo "- .env.template: Configuration template"
echo ""
echo "Happy automating! 🎯"
