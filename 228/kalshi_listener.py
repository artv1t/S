#!/usr/bin/env python3
"""
Kalshi Sports Live Listener - Module 1B

A minimal, focused LIVE-data listener for Kalshi WebSocket API.
Receives REAL-TIME updates (ticker, orderbook, trades) for sports markets.
Filters by: Basketball (NBA), Hockey (NHL), Soccer, Football (NFL), Baseball (MLB), Tennis (ATP/WTA).

This is TRUE live streaming, not REST polling.
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
from typing import Optional, Set, List, Dict
import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


API_BASE_URL = "https://api.elections.kalshi.com"
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"

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
    "KXNFL",
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
WS_PING_INTERVAL = 30


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("kalshi_listener")

raw_logger = logging.getLogger("kalshi_raw")
raw_handler = logging.FileHandler("out/raw_kalshi.jsonl")
raw_handler.setFormatter(logging.Formatter("%(message)s"))
raw_logger.addHandler(raw_handler)
raw_logger.setLevel(logging.DEBUG)
raw_logger.propagate = False

filtered_logger = logging.getLogger("kalshi_filtered")
filtered_handler = logging.FileHandler("logs/kalshi_filtered.log")
filtered_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
filtered_logger.addHandler(filtered_handler)
filtered_logger.setLevel(logging.INFO)
filtered_logger.propagate = False


@dataclass
class LiveUpdate:
    """A real-time update from Kalshi WebSocket."""
    update_type: str
    market_ticker: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "source": "kalshi",
            "update_type": self.update_type,
            "market_ticker": self.market_ticker,
            "timestamp": self.timestamp,
            "data": self.data,
        }


def load_private_key():
    """Load the RSA private key from file or environment variable."""
    pem_data = None
    
    if PRIVATE_KEY_PATH and os.path.exists(PRIVATE_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "r") as f:
            pem_data = f.read()
    elif PRIVATE_KEY_PEM:
        pem_data = PRIVATE_KEY_PEM
    
    if not pem_data:
        raise ValueError(
            "Kalshi private key not found. Set KALSHI_PRIVATE_KEY_PATH or KALSHI_PRIVATE_KEY_PEM environment variable."
        )
    
    return serialization.load_pem_private_key(
        pem_data.encode("utf-8"),
        password=None,
        backend=default_backend()
    )


def create_signature(private_key, timestamp: str, method: str, path: str) -> str:
    """Create RSA-PSS signature for Kalshi API authentication."""
    message = f"{timestamp}{method}{path}".encode("utf-8")
    
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return base64.b64encode(signature).decode("utf-8")


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


def classify_sport_from_ticker(ticker: str, title: str = "") -> Optional[str]:
    """Classify market into sport category based on ticker and title."""
    ticker_upper = ticker.upper()
    title_lower = title.lower() if title else ""
    
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


def is_sports_market(ticker: str, title: str = "") -> bool:
    """Check if market is a sports market based on ticker prefix."""
    ticker_upper = ticker.upper()
    title_lower = title.lower() if title else ""
    
    for prefix in SPORTS_MARKET_PREFIXES:
        if ticker_upper.startswith(prefix):
            return True
    
    for keyword in SPORTS_KEYWORDS:
        if keyword in ticker_upper.lower() or keyword in title_lower:
            return True
    
    return False


def is_active_market(market: dict) -> bool:
    """Check if market is currently active/open."""
    status = market.get("status", "").lower()
    return status in ("open", "active", "trading")


class KalshiWebSocketListener:
    """Kalshi Sports WebSocket Listener - TRUE live streaming."""
    
    def __init__(self):
        self.private_key = load_private_key()
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.sports_tickers: Set[str] = set()
        self.ticker_info: Dict[str, dict] = {}
        self.update_count = 0
        self.update_counts_by_ticker: Dict[str, int] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.message_id = 1
    
    def reset_reconnect_delay(self):
        self.reconnect_delay = 1
    
    def increase_reconnect_delay(self):
        delays = [1, 2, 5, 10, 30]
        current_idx = delays.index(self.reconnect_delay) if self.reconnect_delay in delays else -1
        if current_idx < len(delays) - 1:
            self.reconnect_delay = delays[current_idx + 1]
        else:
            self.reconnect_delay = self.max_reconnect_delay
    
    async def discover_sports_markets(self) -> List[str]:
        """Discover active sports markets via REST API."""
        path = "/trade-api/v2/markets"
        url = f"{API_BASE_URL}{path}?limit=500&status=open"
        headers = get_auth_headers(self.private_key, "GET", path)
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = data.get("markets", [])
                    
                    sports_tickers = []
                    for market in markets:
                        ticker = market.get("ticker", "")
                        title = market.get("title", "")
                        
                        if is_sports_market(ticker, title) and is_active_market(market):
                            sports_tickers.append(ticker)
                            self.ticker_info[ticker] = {
                                "title": title,
                                "sport": classify_sport_from_ticker(ticker, title),
                                "event_ticker": market.get("event_ticker", ""),
                            }
                    
                    logger.info("Discovered %d active sports markets", len(sports_tickers))
                    return sports_tickers
                else:
                    error_text = await response.text()
                    logger.error("Discovery API error %d: %s", response.status, error_text[:200])
                    return []
        except Exception as e:
            logger.error("Discovery request failed: %s", e)
            return []
    
    async def connect_websocket(self) -> bool:
        """Connect to Kalshi WebSocket with authentication."""
        ws_path = "/trade-api/ws/v2"
        timestamp = str(int(time.time() * 1000))
        signature = create_signature(self.private_key, timestamp, "GET", ws_path)
        
        headers = {
            "KALSHI-ACCESS-KEY": API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }
        
        try:
            self.ws = await self.session.ws_connect(
                WS_URL,
                headers=headers,
                heartbeat=WS_PING_INTERVAL,
            )
            logger.info("WebSocket connected to %s", WS_URL)
            self.reset_reconnect_delay()
            return True
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            self.increase_reconnect_delay()
            return False
    
    async def subscribe_to_channels(self, tickers: List[str]):
        """Subscribe to ticker and orderbook channels for sports markets."""
        if not self.ws or self.ws.closed:
            return
        
        subscription = {
            "id": self.message_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"],
            }
        }
        self.message_id += 1
        
        await self.ws.send_json(subscription)
        logger.info("Subscribed to ticker channel (all markets)")
        
        if tickers:
            batch_size = 50
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i+batch_size]
                
                orderbook_sub = {
                    "id": self.message_id,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["orderbook_delta"],
                        "market_tickers": batch,
                    }
                }
                self.message_id += 1
                await self.ws.send_json(orderbook_sub)
                logger.info("Subscribed to orderbook_delta for %d markets (batch %d)", 
                           len(batch), i // batch_size + 1)
                
                trades_sub = {
                    "id": self.message_id,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["trade"],
                        "market_tickers": batch,
                    }
                }
                self.message_id += 1
                await self.ws.send_json(trades_sub)
    
    def process_message(self, msg_data: dict):
        """Process incoming WebSocket message."""
        msg_type = msg_data.get("type", "")
        
        raw_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw": msg_data,
        }
        raw_logger.info(json.dumps(raw_entry))
        
        if msg_type == "ticker":
            self.handle_ticker_update(msg_data)
        elif msg_type == "orderbook_snapshot":
            self.handle_orderbook_snapshot(msg_data)
        elif msg_type == "orderbook_delta":
            self.handle_orderbook_delta(msg_data)
        elif msg_type == "trade":
            self.handle_trade(msg_data)
        elif msg_type == "subscribed":
            logger.debug("Subscription confirmed: %s", msg_data)
        elif msg_type == "error":
            logger.error("WebSocket error: %s", msg_data)
    
    def handle_ticker_update(self, msg_data: dict):
        """Handle ticker update message."""
        msg = msg_data.get("msg", {})
        ticker = msg.get("market_ticker", "")
        
        if not is_sports_market(ticker):
            return
        
        self.update_count += 1
        self.update_counts_by_ticker[ticker] = self.update_counts_by_ticker.get(ticker, 0) + 1
        
        info = self.ticker_info.get(ticker, {})
        sport = info.get("sport") or classify_sport_from_ticker(ticker)
        
        update = LiveUpdate(
            update_type="ticker",
            market_ticker=ticker,
            data={
                "yes_bid": msg.get("yes_bid"),
                "yes_ask": msg.get("yes_ask"),
                "no_bid": msg.get("no_bid"),
                "no_ask": msg.get("no_ask"),
                "last_price": msg.get("last_price"),
                "volume": msg.get("volume"),
            }
        )
        
        filtered_logger.info(json.dumps(update.to_dict()))
        
        yes_bid = msg.get("yes_bid", 0)
        yes_ask = msg.get("yes_ask", 0)
        logger.info("TICKER | %s | %s | bid=%s ask=%s | updates=%d",
                   sport.upper() if sport else "SPORT",
                   ticker,
                   yes_bid, yes_ask,
                   self.update_counts_by_ticker[ticker])
    
    def handle_orderbook_snapshot(self, msg_data: dict):
        """Handle orderbook snapshot message."""
        msg = msg_data.get("msg", {})
        ticker = msg.get("market_ticker", "")
        
        if not is_sports_market(ticker):
            return
        
        self.update_count += 1
        self.update_counts_by_ticker[ticker] = self.update_counts_by_ticker.get(ticker, 0) + 1
        
        info = self.ticker_info.get(ticker, {})
        sport = info.get("sport") or classify_sport_from_ticker(ticker)
        
        yes_levels = msg.get("yes", [])
        no_levels = msg.get("no", [])
        
        update = LiveUpdate(
            update_type="orderbook_snapshot",
            market_ticker=ticker,
            data={
                "yes_levels": len(yes_levels),
                "no_levels": len(no_levels),
                "best_yes_bid": yes_levels[0] if yes_levels else None,
                "best_no_bid": no_levels[0] if no_levels else None,
            }
        )
        
        filtered_logger.info(json.dumps(update.to_dict()))
        
        logger.info("ORDERBOOK_SNAPSHOT | %s | %s | yes_levels=%d no_levels=%d | updates=%d",
                   sport.upper() if sport else "SPORT",
                   ticker,
                   len(yes_levels), len(no_levels),
                   self.update_counts_by_ticker[ticker])
    
    def handle_orderbook_delta(self, msg_data: dict):
        """Handle orderbook delta (incremental update) message."""
        msg = msg_data.get("msg", {})
        ticker = msg.get("market_ticker", "")
        
        if not is_sports_market(ticker):
            return
        
        self.update_count += 1
        self.update_counts_by_ticker[ticker] = self.update_counts_by_ticker.get(ticker, 0) + 1
        
        info = self.ticker_info.get(ticker, {})
        sport = info.get("sport") or classify_sport_from_ticker(ticker)
        
        update = LiveUpdate(
            update_type="orderbook_delta",
            market_ticker=ticker,
            data={
                "price": msg.get("price"),
                "delta": msg.get("delta"),
                "side": msg.get("side"),
            }
        )
        
        filtered_logger.info(json.dumps(update.to_dict()))
        
        logger.info("ORDERBOOK_DELTA | %s | %s | price=%s delta=%s side=%s | updates=%d",
                   sport.upper() if sport else "SPORT",
                   ticker,
                   msg.get("price"), msg.get("delta"), msg.get("side"),
                   self.update_counts_by_ticker[ticker])
    
    def handle_trade(self, msg_data: dict):
        """Handle trade message."""
        msg = msg_data.get("msg", {})
        ticker = msg.get("market_ticker", "")
        
        if not is_sports_market(ticker):
            return
        
        self.update_count += 1
        self.update_counts_by_ticker[ticker] = self.update_counts_by_ticker.get(ticker, 0) + 1
        
        info = self.ticker_info.get(ticker, {})
        sport = info.get("sport") or classify_sport_from_ticker(ticker)
        
        update = LiveUpdate(
            update_type="trade",
            market_ticker=ticker,
            data={
                "count": msg.get("count"),
                "yes_price": msg.get("yes_price"),
                "no_price": msg.get("no_price"),
            }
        )
        
        filtered_logger.info(json.dumps(update.to_dict()))
        
        logger.info("TRADE | %s | %s | yes_price=%s count=%s | updates=%d",
                   sport.upper() if sport else "SPORT",
                   ticker,
                   msg.get("yes_price"), msg.get("count"),
                   self.update_counts_by_ticker[ticker])
    
    async def heartbeat_task(self):
        """Log heartbeat message every HEARTBEAT_INTERVAL seconds."""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            top_tickers = sorted(
                self.update_counts_by_ticker.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            logger.info("kalshi_listener_alive | total_updates=%d | tracked_tickers=%d | top: %s",
                       self.update_count,
                       len(self.update_counts_by_ticker),
                       ", ".join(f"{t}:{c}" for t, c in top_tickers))
    
    async def listen_websocket(self):
        """Listen for WebSocket messages."""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        self.process_message(data)
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON: %s", msg.data[:100])
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket error: %s", self.ws.exception())
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket closed")
                    break
        except Exception as e:
            logger.error("WebSocket listen error: %s", e)
    
    async def run(self):
        """Main run loop with reconnection logic."""
        self.running = True
        self.session = aiohttp.ClientSession()
        
        heartbeat_task = asyncio.create_task(self.heartbeat_task())
        
        try:
            while self.running:
                tickers = await self.discover_sports_markets()
                self.sports_tickers = set(tickers)
                
                if not tickers:
                    logger.warning("No sports markets found, retrying in %ds", self.reconnect_delay)
                    await asyncio.sleep(self.reconnect_delay)
                    self.increase_reconnect_delay()
                    continue
                
                if await self.connect_websocket():
                    await self.subscribe_to_channels(tickers)
                    await self.listen_websocket()
                
                if self.running:
                    logger.info("Reconnecting in %ds...", self.reconnect_delay)
                    await asyncio.sleep(self.reconnect_delay)
                    self.increase_reconnect_delay()
        finally:
            heartbeat_task.cancel()
            if self.ws and not self.ws.closed:
                await self.ws.close()
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
    os.makedirs("out", exist_ok=True)
    
    if not API_KEY_ID:
        logger.error("KALSHI_API_KEY_ID environment variable not set")
        logger.error("Set: export KALSHI_API_KEY_ID=your-api-key-id")
        sys.exit(1)
    
    if not PRIVATE_KEY_PATH and not PRIVATE_KEY_PEM:
        logger.error("Kalshi private key not configured")
        logger.error("Set: export KALSHI_PRIVATE_KEY_PATH=/path/to/private_key.pem")
        logger.error("Or:  export KALSHI_PRIVATE_KEY_PEM=-----BEGIN RSA PRIVATE KEY-----...")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Kalshi Sports Live Listener - Module 1B (WebSocket)")
    logger.info("TRUE LIVE STREAMING - not REST polling!")
    logger.info("Filtering: Basketball (NBA), Hockey (NHL), Football (NFL),")
    logger.info("           Baseball (MLB), Tennis (ATP/WTA), Soccer")
    logger.info("WebSocket: %s", WS_URL)
    logger.info("Raw log: out/raw_kalshi.jsonl")
    logger.info("=" * 60)
    
    listener = KalshiWebSocketListener()
    
    try:
        await listener.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
