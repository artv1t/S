#!/bin/bash

# Health Check Script for Solana Sniper Bot
# Usage: ./scripts/health-check.sh

API_URL="http://localhost:3001"
TIMEOUT=10

echo "🔍 Performing health check for Solana Sniper Bot..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if bot is running
if ! curl -f -s --max-time $TIMEOUT "$API_URL/health" > /dev/null; then
    print_error "Bot is not responding at $API_URL"
    exit 1
fi

print_success "Bot is responding"

# Get detailed health info
HEALTH_RESPONSE=$(curl -s --max-time $TIMEOUT "$API_URL/health")
BOT_STATUS=$(echo "$HEALTH_RESPONSE" | grep -o '"running":[^,]*' | cut -d':' -f2)

if [ "$BOT_STATUS" = "true" ]; then
    print_success "Bot is running"
else
    print_warning "Bot is stopped"
fi

# Check metrics endpoint
if curl -f -s --max-time $TIMEOUT "$API_URL/metrics" > /dev/null; then
    print_success "Metrics endpoint is accessible"
else
    print_error "Metrics endpoint is not accessible"
fi

# Check positions endpoint
if curl -f -s --max-time $TIMEOUT "$API_URL/api/positions" > /dev/null; then
    print_success "Positions endpoint is accessible"
else
    print_error "Positions endpoint is not accessible"
fi

# Get system metrics
METRICS_RESPONSE=$(curl -s --max-time $TIMEOUT "$API_URL/api/metrics/system")
if [ $? -eq 0 ]; then
    MEMORY_MB=$(echo "$METRICS_RESPONSE" | grep -o '"heapUsed":[^,]*' | cut -d':' -f2)
    UPTIME=$(echo "$METRICS_RESPONSE" | grep -o '"uptime":[^,]*' | cut -d':' -f2)
    
    print_success "Memory usage: ${MEMORY_MB} MB"
    print_success "Uptime: ${UPTIME} seconds"
fi

echo ""
echo "🎉 Health check completed!"
echo "📊 Full status: $API_URL/health"
echo "📈 Metrics: $API_URL/metrics"
echo "🌐 Dashboard: http://localhost:3000 (if running)"