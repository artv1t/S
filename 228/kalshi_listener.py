#!/usr/bin/env python3
"""
Kalshi Sports Live Listener - Module 1B

A minimal, focused LIVE-data listener for Kalshi API.
Filters active markets by: Basketball (NBA), Hockey (NHL), Soccer, Esports, Tennis (ATP/WTA).

NO trading, NO odds, NO orderbooks - just LIVE event data.
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Set, List
import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


API_BASE_URL = "https://api.elections.kalshi.com"

API_KEY_ID = os.environ.get("KALSHI_API_KEY_ID", "")
PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
PRIVATE_KEY_PEM = os.environ.get("KALSHI_PRIVATE_KEY_PEM", "")

SPORTS_MARKET_PREFIXES: Set[str] = {
    "KXMVENBASINGLEGAME",
    "KXMVENFLSINGLEGAME",
    "KXMVNHLSINGLEGAME",
    "KXMVEMLBSINGLEGAME",
    "KXMVETENNISSINGLEGAME",
    "KXMVESOCCERSINGLEGAME",
    "KXNBA",
    "KXNHL",
    "KXMLB",
    "KXTENNIS",
    "KXSOCCER",
}

SPORTS_KEYWORDS: Set[str] = {
    "nba", "nfl", "nhl", "mlb",
    "basketball", "hockey", "football", "baseball",
    "tennis", "atp", "wta",
    "soccer",
}

HEARTBEAT_INTERVAL = 20
POLL_INTERVAL = 15


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("kalshi_listener")

raw_logger = logging.getLogger("kalshi_raw")
raw_handler = logging.FileHandler("logs/kalshi_raw.log")
raw_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
raw_logger.addHandler(raw_handler)
raw_logger.setLevel(logging.DEBUG)

filtered_logger = logging.getLogger("kalshi_filtered")
filtered_handler = logging.FileHandler("logs/kalshi_filtered.log")
filtered_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
filtered_logger.addHandler(filtered_handler)
filtered_logger.setLevel(logging.INFO)


@dataclass
class NormalizedEvent:
    """Normalized LIVE event from Kalshi."""
    source: str = "kalshi"
    platform_event_id: str = ""
    sport: str = ""
    league: str = ""
    home_team: str = ""
    away_team: str = ""
    status: str = "LIVE"
    game_time: Optional[str] = None
    period: Optional[str] = None
    score: Optional[str] = None
    timestamp_received: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "platform_event_id": self.platform_event_id,
            "sport": self.sport,
            "league": self.league,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "status": self.status,
            "game_time": self.game_time,
            "period": self.period,
            "score": self.score,
            "timestamp_received": self.timestamp_received,
            "event_url": self.event_url,
        }


def load_private_key():
    """Load the RSA private key from file or environment variable."""
    pem_data = None
    
    if PRIVATE_KEY_PATH and os.path.exists(PRIVATE_KEY_PATH):
        with open(PRIVATE_KEY_PATH, 'r') as f:
            pem_data = f.read()
    elif PRIVATE_KEY_PEM:
        pem_data = PRIVATE_KEY_PEM
    
    if not pem_data:
        raise ValueError(
            "Kalshi private key not found. Set KALSHI_PRIVATE_KEY_PATH or KALSHI_PRIVATE_KEY_PEM environment variable."
        )
    
    return serialization.load_pem_private_key(
        pem_data.encode('utf-8'),
        password=None,
        backend=default_backend()
    )


def create_signature(private_key, timestamp: str, method: str, path: str) -> str:
    """Create RSA-PSS signature for Kalshi API authentication."""
    path_without_query = path.split('?')[0]
    message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
    
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return base64.b64encode(signature).decode('utf-8')


def get_auth_headers(private_key, method: str, path: str) -> dict:
    """Generate authentication headers for Kalshi API request."""
    timestamp = str(int(time.time() * 1000))
    signature = create_signature(private_key, timestamp, method, path)
    
    return {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
    }


def classify_sport_from_ticker(ticker: str, title: str) -> Optional[str]:
    """Classify market into sport category based on ticker and title."""
    ticker_upper = ticker.upper()
    title_lower = title.lower()
    
    if "NBA" in ticker_upper or "basketball" in title_lower:
        return "basketball"
    if "NHL" in ticker_upper or "hockey" in title_lower:
        return "hockey"
    if "NFL" in ticker_upper:
        return "football"
    if "MLB" in ticker_upper or "baseball" in title_lower:
        return "baseball"
    if "TENNIS" in ticker_upper or "atp" in title_lower or "wta" in title_lower:
        return "tennis"
    if "SOCCER" in ticker_upper or "soccer" in title_lower:
        return "soccer"
    
    return None


def is_sports_market(market: dict) -> bool:
    """Check if market is a sports market based on ticker prefix."""
    ticker = market.get("ticker", "").upper()
    title = market.get("title", "").lower()
    event_ticker = market.get("event_ticker", "").upper()
    
    for prefix in SPORTS_MARKET_PREFIXES:
        if ticker.startswith(prefix) or event_ticker.startswith(prefix):
            return True
    
    for keyword in SPORTS_KEYWORDS:
        if keyword in ticker.lower() or keyword in title:
            return True
    
    return False


def is_active_market(market: dict) -> bool:
    """Check if market is currently active/open."""
    status = market.get("status", "").lower()
    return status in ("open", "active", "trading")


def normalize_market(market: dict) -> Optional[NormalizedEvent]:
    """Convert Kalshi market to normalized event format."""
    if not is_active_market(market):
        return None
    
    if not is_sports_market(market):
        return None
    
    ticker = market.get("ticker", "")
    title = market.get("title", "")
    event_ticker = market.get("event_ticker", "")
    
    sport = classify_sport_from_ticker(ticker, title)
    if sport is None:
        return None
    
    league = sport.upper()
    if "NBA" in ticker.upper():
        league = "NBA"
    elif "NFL" in ticker.upper():
        league = "NFL"
    elif "NHL" in ticker.upper():
        league = "NHL"
    elif "MLB" in ticker.upper():
        league = "MLB"
    elif "ATP" in title.upper():
        league = "ATP"
    elif "WTA" in title.upper():
        league = "WTA"
    
    event_url = f"https://kalshi.com/markets/{ticker}" if ticker else None
    
    return NormalizedEvent(
        platform_event_id=event_ticker or ticker,
        sport=sport,
        league=league,
        home_team=title[:50] if len(title) > 50 else title,
        away_team="",
        status="LIVE",
        event_url=event_url,
    )


class KalshiListener:
    """Kalshi Sports API Listener with polling."""
    
    def __init__(self):
        self.private_key = load_private_key()
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.live_events: dict[str, NormalizedEvent] = {}
        self.last_heartbeat = datetime.now(timezone.utc)
        self.request_count = 0
        self.filtered_count = 0
        self.session: Optional[aiohttp.ClientSession] = None
    
    def reset_reconnect_delay(self):
        """Reset reconnect delay after successful request."""
        self.reconnect_delay = 1
    
    def increase_reconnect_delay(self):
        """Increase reconnect delay with exponential backoff."""
        delays = [1, 2, 5, 10, 30]
        current_idx = delays.index(self.reconnect_delay) if self.reconnect_delay in delays else -1
        if current_idx < len(delays) - 1:
            self.reconnect_delay = delays[current_idx + 1]
        else:
            self.reconnect_delay = self.max_reconnect_delay
    
    async def heartbeat_task(self):
        """Log heartbeat message every HEARTBEAT_INTERVAL seconds."""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            logger.info("kalshi_listener_alive | requests=%d | filtered=%d | live_events=%d",
                       self.request_count, self.filtered_count, len(self.live_events))
            self.last_heartbeat = datetime.now(timezone.utc)
    
    async def fetch_active_markets(self) -> List[dict]:
        """Fetch active markets from Kalshi API."""
        path = "/trade-api/v2/markets?limit=500"
        url = f"{API_BASE_URL}{path}"
        headers = get_auth_headers(self.private_key, "GET", path)
        
        try:
            async with self.session.get(url, headers=headers) as response:
                self.request_count += 1
                
                if response.status == 200:
                    data = await response.json()
                    raw_logger.debug(json.dumps(data))
                    self.reset_reconnect_delay()
                    return data.get("markets", [])
                else:
                    error_text = await response.text()
                    logger.error("API error %d: %s", response.status, error_text[:200])
                    self.increase_reconnect_delay()
                    return []
        except Exception as e:
            logger.error("Request failed: %s", e)
            self.increase_reconnect_delay()
            return []
    
    async def process_markets(self, markets: List[dict]):
        """Process and filter markets for LIVE sports."""
        new_events = 0
        
        for market in markets:
            normalized = normalize_market(market)
            if normalized:
                event_key = normalized.platform_event_id
                
                if event_key not in self.live_events:
                    self.filtered_count += 1
                    new_events += 1
                    self.live_events[event_key] = normalized
                    
                    event_dict = normalized.to_dict()
                    filtered_logger.info(json.dumps(event_dict))
                    
                    logger.info("LIVE | %s | %s | %s | %s",
                               normalized.sport.upper(),
                               normalized.league,
                               normalized.home_team,
                               normalized.event_url or "N/A")
        
        if new_events > 0:
            logger.info("Found %d new sports events this poll", new_events)
    
    async def poll_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                markets = await self.fetch_active_markets()
                await self.process_markets(markets)
            except Exception as e:
                logger.error("Poll error: %s", e)
            
            await asyncio.sleep(POLL_INTERVAL)
    
    async def listen(self):
        """Main listening loop."""
        self.running = True
        
        self.session = aiohttp.ClientSession()
        heartbeat = asyncio.create_task(self.heartbeat_task())
        
        try:
            logger.info("Starting Kalshi listener with %ds poll interval", POLL_INTERVAL)
            await self.poll_loop()
        finally:
            heartbeat.cancel()
            if self.session:
                await self.session.close()
            logger.info("Listener stopped")
    
    def stop(self):
        """Stop the listener."""
        self.running = False
        logger.info("Stop signal received")


async def main():
    """Main entry point."""
    os.makedirs("logs", exist_ok=True)
    
    if not API_KEY_ID:
        logger.error("KALSHI_API_KEY_ID environment variable not set")
        logger.error("Set: export KALSHI_API_KEY_ID='your-api-key-id'")
        sys.exit(1)
    
    if not PRIVATE_KEY_PATH and not PRIVATE_KEY_PEM:
        logger.error("Kalshi private key not configured")
        logger.error("Set: export KALSHI_PRIVATE_KEY_PATH='/path/to/private_key.pem'")
        logger.error("Or:  export KALSHI_PRIVATE_KEY_PEM='-----BEGIN RSA PRIVATE KEY-----...'")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Kalshi Sports Live Listener - Module 1B")
    logger.info("Filtering: Basketball (NBA), Hockey (NHL), Football (NFL),")
    logger.info("           Baseball (MLB), Tennis (ATP/WTA), Soccer")
    logger.info("API: %s", API_BASE_URL)
    logger.info("=" * 60)
    
    listener = KalshiListener()
    
    try:
        await listener.listen()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
