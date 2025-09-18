#!/bin/bash

# Solana Sniper Bot Setup Script
# This script sets up the development environment

set -e

echo "🔧 Setting up Solana Sniper Bot development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check Node.js version
print_status "Checking Node.js version..."
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    print_error "Node.js version 18+ is required. Current version: $(node -v)"
    exit 1
fi

print_success "Node.js version: $(node -v)"

# Check npm
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed. Please install npm first."
    exit 1
fi

print_success "npm version: $(npm -v)"

# Install dependencies
print_status "Installing dependencies..."
npm install

# Create required directories
print_status "Creating required directories..."
mkdir -p data logs wallets
chmod 700 wallets
chmod 755 data logs

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env file from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your configuration."
fi

# Build the project
print_status "Building the project..."
npm run build

# Run tests
print_status "Running tests..."
npm test

print_success "🎉 Setup completed successfully!"
print_warning "📋 Next steps:"
print_warning "   1. Edit .env file with your RPC endpoints and configuration"
print_warning "   2. Add your wallet JSON files to ./wallets/ directory"
print_warning "   3. Start with paper mode: npm run start:paper"
print_warning "   4. Test thoroughly before enabling live trading"

echo ""
echo "🚀 Available commands:"
echo "  Development (paper):  npm run dev:paper"
echo "  Development (live):   npm run dev:live"
echo "  Production (paper):   npm run start:paper"
echo "  Production (live):    npm run start:live"
echo "  Build:                npm run build"
echo "  Test:                 npm test"
echo "  Lint:                 npm run lint"