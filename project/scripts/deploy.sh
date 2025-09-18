#!/bin/bash

# Solana Sniper Bot Deployment Script
# Usage: ./scripts/deploy.sh [environment]

set -e

ENVIRONMENT=${1:-production}
PROJECT_NAME="solana-sniper-bot"

echo "🚀 Deploying Solana Sniper Bot to $ENVIRONMENT..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warning "Please edit .env file with your configuration before running the bot."
    else
        print_error ".env.example file not found. Cannot create .env file."
        exit 1
    fi
fi

# Create required directories
print_status "Creating required directories..."
mkdir -p data logs wallets
chmod 700 wallets
chmod 755 data logs

# Build and deploy
print_status "Building Docker image..."
docker-compose build

print_status "Starting services..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check health
print_status "Checking service health..."
if curl -f http://localhost:3001/health > /dev/null 2>&1; then
    print_success "✅ Bot is healthy and running!"
    print_success "🌐 API available at: http://localhost:3001"
    print_success "📊 Health check: http://localhost:3001/health"
    print_success "📈 Metrics: http://localhost:3001/metrics"
else
    print_error "❌ Bot health check failed. Check logs with: docker-compose logs"
    exit 1
fi

# Show running containers
print_status "Running containers:"
docker-compose ps

print_success "🎉 Deployment completed successfully!"
print_warning "⚠️  Remember to:"
print_warning "   1. Configure your .env file properly"
print_warning "   2. Add your wallet files to ./wallets/ directory"
print_warning "   3. Start with PAPER_MODE=true for testing"
print_warning "   4. Monitor logs with: docker-compose logs -f"

echo ""
echo "📋 Useful commands:"
echo "  Start:    docker-compose up -d"
echo "  Stop:     docker-compose down"
echo "  Logs:     docker-compose logs -f"
echo "  Restart:  docker-compose restart"
echo "  Update:   ./scripts/deploy.sh"