#!/usr/bin/env python3
"""
Polymarket Sports Live Listener - Module 1A

A minimal, focused LIVE-data listener for Polymarket Sports WebSocket.
Filters events by: Soccer, Basketball, Hockey, Esports, Tennis (ATP/WTA) only.

NO trading, NO odds, NO orderbooks - just LIVE event data.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Set
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException


WS_ENDPOINT = "wss://sports-api.polymarket.com/ws"

ALLOWED_SPORT_TYPES: Set[str] = {
    "soccer", "football",
    "basketball",
    "hockey", "ice_hockey",
    "esports", "esport",
    "tennis",
}

EXCLUDED_LEAGUES: Set[str] = {
    "nfl", "cfb", "ncaaf",
    "golf", "pga",
    "cricket", "ipl",
    "ufc", "mma",
    "f1", "formula1", "formula_1",
    "chess",
    "boxing",
    "mlb", "baseball",
}

BASKETBALL_LEAGUES: Set[str] = {"nba", "euroleague", "ncaab", "fiba", "wnba", "acb"}
HOCKEY_LEAGUES: Set[str] = {"nhl", "khl", "iihf", "shl"}
ESPORTS_LEAGUES: Set[str] = {"cs2", "csgo", "dota2", "dota", "lol", "valorant", "rl"}
TENNIS_LEAGUES: Set[str] = {"atp", "wta"}

HEARTBEAT_INTERVAL = 20


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("polymarket_listener")

raw_logger = logging.getLogger("polymarket_raw")
raw_handler = logging.FileHandler("logs/raw_messages.log")
raw_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
raw_logger.addHandler(raw_handler)
raw_logger.setLevel(logging.DEBUG)

filtered_logger = logging.getLogger("polymarket_filtered")
filtered_handler = logging.FileHandler("logs/filtered_live.log")
filtered_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
filtered_logger.addHandler(filtered_handler)
filtered_logger.setLevel(logging.INFO)


@dataclass
class NormalizedEvent:
    """Normalized LIVE event from Polymarket."""
    source: str = "polymarket"
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


def classify_sport(data: dict) -> Optional[str]:
    """Classify event into allowed sport category using eventState.type or league abbreviation."""
    league_abbr = data.get("leagueAbbreviation", "").lower()
    
    if league_abbr in EXCLUDED_LEAGUES:
        return None
    
    event_state = data.get("eventState", {})
    sport_type = event_state.get("type", "").lower() if isinstance(event_state, dict) else ""
    
    if sport_type in ("soccer", "football"):
        return "soccer"
    if sport_type == "basketball":
        return "basketball"
    if sport_type in ("hockey", "ice_hockey"):
        return "hockey"
    if sport_type in ("esports", "esport"):
        return "esports"
    if sport_type == "tennis":
        return "tennis"
    
    if league_abbr in BASKETBALL_LEAGUES:
        return "basketball"
    if league_abbr in HOCKEY_LEAGUES:
        return "hockey"
    if league_abbr in ESPORTS_LEAGUES:
        return "esports"
    if league_abbr in TENNIS_LEAGUES:
        return "tennis"
    
    return None


def is_live_event(data: dict) -> bool:
    """Check if event is LIVE based on multiple criteria."""
    if data.get("live") is True:
        return True
    if data.get("status", "").lower() == "inprogress":
        return True
    if data.get("state", "").lower() == "in_progress":
        return True
    return False


def normalize_event(data: dict) -> Optional[NormalizedEvent]:
    """Convert raw Polymarket message to normalized event format."""
    if not is_live_event(data):
        return None
    
    sport = classify_sport(data)
    if sport is None:
        return None
    
    league_abbr = data.get("leagueAbbreviation", "")
    
    game_id = str(data.get("gameId", ""))
    home_team = data.get("homeTeam", "")
    away_team = data.get("awayTeam", "")
    
    event_url = None
    slug = data.get("slug")
    if slug:
        event_url = f"https://polymarket.com/event/{slug}"
    
    return NormalizedEvent(
        platform_event_id=game_id,
        sport=sport,
        league=league_abbr,
        home_team=home_team,
        away_team=away_team,
        status="LIVE",
        game_time=data.get("elapsed"),
        period=data.get("period"),
        score=data.get("score"),
        event_url=event_url,
    )


class PolymarketListener:
    """Polymarket Sports WebSocket Listener with auto-reconnect."""
    
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.live_events: dict[str, NormalizedEvent] = {}
        self.last_heartbeat = datetime.now(timezone.utc)
        self.message_count = 0
        self.filtered_count = 0
    
    def reset_reconnect_delay(self):
        """Reset reconnect delay after successful connection."""
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
        """Send heartbeat message every HEARTBEAT_INTERVAL seconds."""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            logger.info("polymarket_listener_alive | messages=%d | filtered=%d | live_events=%d",
                       self.message_count, self.filtered_count, len(self.live_events))
            self.last_heartbeat = datetime.now(timezone.utc)
    
    async def handle_message(self, message: str):
        """Process incoming WebSocket message."""
        self.message_count += 1
        
        raw_logger.debug(message)
        
        if message == "ping":
            if self.ws:
                await self.ws.send("pong")
                logger.debug("Responded to ping with pong")
            return
        
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Failed to parse message: %s", message[:100])
            return
        
        normalized = normalize_event(data)
        if normalized:
            self.filtered_count += 1
            self.live_events[normalized.platform_event_id] = normalized
            
            event_dict = normalized.to_dict()
            filtered_logger.info(json.dumps(event_dict))
            
            logger.info("LIVE | %s | %s | %s vs %s | %s | %s",
                       normalized.sport.upper(),
                       normalized.league,
                       normalized.home_team,
                       normalized.away_team,
                       normalized.score or "N/A",
                       normalized.period or "N/A")
    
    async def connect(self):
        """Connect to Polymarket WebSocket."""
        logger.info("Connecting to %s", WS_ENDPOINT)
        
        try:
            self.ws = await websockets.connect(
                WS_ENDPOINT,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=10,
            )
            logger.info("Connected to Polymarket Sports WebSocket")
            self.reset_reconnect_delay()
            return True
        except Exception as e:
            logger.error("Connection failed: %s", e)
            return False
    
    async def listen(self):
        """Main listening loop with auto-reconnect."""
        self.running = True
        
        heartbeat = asyncio.create_task(self.heartbeat_task())
        
        try:
            while self.running:
                if not await self.connect():
                    logger.info("Reconnecting in %d seconds...", self.reconnect_delay)
                    await asyncio.sleep(self.reconnect_delay)
                    self.increase_reconnect_delay()
                    continue
                
                try:
                    async for message in self.ws:
                        await self.handle_message(message)
                except ConnectionClosed as e:
                    logger.warning("Connection closed: code=%s reason=%s", e.code, e.reason)
                except WebSocketException as e:
                    logger.error("WebSocket error: %s", e)
                except Exception as e:
                    logger.error("Unexpected error: %s", e)
                
                if self.running:
                    logger.info("Reconnecting in %d seconds...", self.reconnect_delay)
                    await asyncio.sleep(self.reconnect_delay)
                    self.increase_reconnect_delay()
        
        finally:
            heartbeat.cancel()
            if self.ws:
                await self.ws.close()
            logger.info("Listener stopped")
    
    def stop(self):
        """Stop the listener."""
        self.running = False
        logger.info("Stop signal received")


async def main():
    """Main entry point."""
    import os
    os.makedirs("logs", exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("Polymarket Sports Live Listener - Module 1A")
    logger.info("Filtering: Soccer, Basketball, Hockey, Esports, Tennis (ATP/WTA)")
    logger.info("Endpoint: %s", WS_ENDPOINT)
    logger.info("=" * 60)
    
    listener = PolymarketListener()
    
    try:
        await listener.listen()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
