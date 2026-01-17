#!/usr/bin/env python3
"""
Main Entry Point - Sports Arbitrage Bot

Runs the complete system:
- Module 1A: Polymarket Live Listener
- Module 1B: Kalshi Live Listener  
- Module 2: Event Matcher (Kalshi <-> Polymarket)
- Module 3: (placeholder for future)

Usage:
    python main.py [--duration SECONDS] [--module1-only] [--module2-only]
"""

import os
import sys
import json
import signal
import asyncio
import logging
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "out"
LOGS_DIR = BASE_DIR / "logs"

# HARDCODED API KEYS (user requested - read-only accounts, no money)
KALSHI_API_KEY_ID = "177e5c48-edfa-4fa4-bfd2-43bee1ef886f"
KALSHI_PRIVATE_KEY_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA50JaZjtsJHnf6APoKQ3lXO8FVtNb7az7wCpw345zrDe8nPmm
TPA1hzt1jFpwOEGwFZ6yHJFGfj/WitxSx1RGzthCmJQsWktAmDo9IieyvKNPJ6Cg
Y/ci4tr352jYrTEY9b3ork4UQcqTyabxZh870qiNiG0DSNic7ovAHW0GB8uQ0ceg
+D2i+Yl0LUCKcSTEKrCYjOryDohjPs8SLhVij/RavrJSPr9asNPJvqArgk7fqJJB
8pQGKCIh54wvGasAfNIbHeV4TUvyRaSYaGFuE6rYHG6x72B+wh71d15cSm3gJghI
gXFOmbdzawTQZfrWh+wNP0b7mnlEw6OFosahaQIDAQABAoIBAAyJsEc/5D9vhJxK
fu8f394rnstb6u1ePilnW6aBLYQKIw2TKukbslk+N+OnwRMJu6tWZuNt3GeqnB37
7zh7mRmsh6LIUMXF8+705FzaUGJSC8/zEVMOImvwcXWQPYQZR/hFxyxREx/UhPHv
PUH7QkXr6b16ZI3R4aM8vCoUP7oTHMixp3VPuT+N+VpiofuDgOdMBh/parfVWOVk
dXFcG5I5JPN9UqD4Ob46zsLi+rEUJXluHC1JRVvxsFAoHqpg3rVbqW26Ho44tqcr
VOlwctuKYx6N86HTKgr6ldi7DDk2rz1lwSyjZqIfMhvUMNDXTL6Y/Ua8BRJhEQ64
2II9BZECgYEA9hhan8GebyKSTpNbAvc+TsMq+A54T0P3ptofbgxW+n4xrMik4wM4
uj7pwrxUUgld6133OnS7MmyP/9ZwMFZGhuWKgrygpSDiskvTX5r7W9HrpedHdGHu
hmqR12W+vWTNd1asvqOtkcGTQW+y/IEY8jFUJv0d+nqYoh/mPiL82fkCgYEA8JEi
/8r56IBNGWq9y2h3HxhBSOw2OzPTGo/66t7HhEejRYHROpRYmVVVf51K/P9eqddN
fNAxq91uN0vlulWormwxzoPUva2hTePKEK2ryym6Uj8puw92t4OuYXmkqt2HFmOE
rGmf8hZJhKW/o2uv7brlZcKvB6uWyhVy9j1UXvECgYAGZB+GYprgu/8ct0r3yr/9
f6gQBSAuvs8hsCx8ySlBHCHiINvXYXAJtjSP8CAoeUHNKQWQqRNrfdJHjKQhPTxb
qH5uYsOxRiddBgcZRoccnVkHV/hNF3YAW6gp9eR8Oq/zV3bpBIsva92NJ394e0nQ
kGNlF9G9fY2VOErcdkAm0QKBgQCi+rEreug0jDevsJFE7VFGz7frH5zeHw42QLVN
ygCBrcb/oCOP/FDKEPYLrxTOsnP/vM3ScXo1ZZ7194V75+yPvt0/fDD1EFzn2Btd
kUuCKJMChahQAvn6+kt53l+hItQSZvnLlQO3j0HfjCt5G8vk02n2tx69o5JU9pMc
IBC5AQKBgQDR5Rkp+a7ZfIL6LhPH4tljbYr8Oqnpbyj1ekxPF1LkYWZzvfPXpf+L
fZd1sRSqZsE6MMMgUPUQ8+ZDmymRG80JnnwpgHdk4rt2KfSLAal2FB852rX0lR/Y
VpA+eCkRB2RAUsq3pbc7Bdt+qaV5sWwkoT+ks4t2q94gKia1ThpB8Q==
-----END RSA PRIVATE KEY-----"""
DEEPSEEK_API_KEY = "sk-f1b0fc04db5a4beca73ed8b0803210cf"


def parse_teams_from_title(title: str) -> tuple:
    """Extract team names from Kalshi market title like 'Washington St. at San Francisco Winner?'."""
    patterns = [
        r"^(.+?)\s+vs\.?\s+(.+?)(?:\s+Winner\??|\s*\?|\s*$)",
        r"^(.+?)\s+v\s+(.+?)(?:\s+Winner\??|\s*\?|\s*$)",
        r"^(.+?)\s+at\s+(.+?)(?:\s+Winner\??|\s*\?|\s*$)",
        r"^(.+?)\s+-\s+(.+?)(?:\s+Winner\??|\s*\?|\s*$)",
        r"^(.+?)\s+@\s+(.+?)(?:\s+Winner\??|\s*\?|\s*$)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            team_a = match.group(1).strip()
            team_b = match.group(2).strip()
            for suffix in [" Winner", " to Win", " Win", "?"]:
                team_a = team_a.replace(suffix, "").strip()
                team_b = team_b.replace(suffix, "").strip()
            return team_a, team_b
    
    return "", ""


def classify_kalshi_sport(category: str, sub_title: str, title: str) -> Optional[str]:
    """Classify sport from Kalshi event metadata."""
    combined = f"{category} {sub_title} {title}".lower()
    
    if "basketball" in combined or "nba" in combined or "ncaa" in combined or "cbb" in combined:
        return "basketball"
    if "hockey" in combined or "nhl" in combined:
        return "hockey"
    if "soccer" in combined:
        return "soccer"
    if "tennis" in combined or "atp" in combined or "wta" in combined:
        return "tennis"
    if "esports" in combined or "valorant" in combined or "counter" in combined or "cs2" in combined:
        return "esports"
    
    return None


class SystemOrchestrator:
    """Main orchestrator that runs all modules together."""
    
    def __init__(self, duration: Optional[int] = None):
        self.duration = duration
        self.running = False
        self.start_time: Optional[datetime] = None
        
        self.polymarket_listener = None
        self.kalshi_listener = None
        self.event_matcher = None
        
        # Kalshi market metadata cache: ticker -> {sport, team_a, team_b, title, event_ticker}
        self.kalshi_market_cache: Dict[str, Dict[str, Any]] = {}
        
        self.stats = {
            "polymarket_events": 0,
            "kalshi_events": 0,
            "kalshi_markets_discovered": 0,
            "matches_found": 0,
            "errors": 0,
        }
    
    async def setup(self):
        """Initialize all modules."""
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        from event_matcher import EventMatcher
        self.event_matcher = EventMatcher(deepseek_api_key=DEEPSEEK_API_KEY)
        
        logger.info("System initialized")
        logger.info("  Kalshi API Key: %s...", KALSHI_API_KEY_ID[:8] if KALSHI_API_KEY_ID else "NOT SET")
        logger.info("  DeepSeek API Key: %s...", DEEPSEEK_API_KEY[:8] if DEEPSEEK_API_KEY else "NOT SET")
        logger.info("  Output directory: %s", OUT_DIR)
    
    async def run_polymarket_listener(self):
        """Run Polymarket listener and feed events to matcher."""
        import websockets
        
        WS_URL = "wss://sports-api.polymarket.com/ws"
        
        while self.running:
            try:
                logger.info("Connecting to Polymarket WebSocket...")
                async with websockets.connect(WS_URL, ping_interval=30) as ws:
                    logger.info("Polymarket WebSocket connected")
                    
                    while self.running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                            data = json.loads(msg)
                            
                            if isinstance(data, list):
                                for event in data:
                                    await self._process_polymarket_event(event)
                            elif isinstance(data, dict):
                                await self._process_polymarket_event(data)
                                
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error("Polymarket message error: %s", e)
                            self.stats["errors"] += 1
                            
            except Exception as e:
                logger.error("Polymarket connection error: %s", e)
                self.stats["errors"] += 1
                if self.running:
                    await asyncio.sleep(5)
    
    async def _process_polymarket_event(self, event: dict):
        """Process a Polymarket event."""
        try:
            event_state = event.get("eventState", {})
            sport_type = event_state.get("type", "").lower()
            league_abbr = event.get("leagueAbbreviation", "").lower()
            is_live = event.get("live", False) or event.get("status", "").lower() == "inprogress"
            
            sport = None
            if sport_type in ("soccer", "football"):
                sport = "soccer"
            elif sport_type in ("basketball", "college-basketball"):
                sport = "basketball"
            elif sport_type in ("hockey", "ice_hockey", "ice-hockey"):
                sport = "hockey"
            elif sport_type in ("esports", "esport"):
                sport = "esports"
            elif sport_type == "tennis":
                sport = "tennis"
            elif league_abbr in ("nba", "ncaab", "euroleague", "fiba", "wnba"):
                sport = "basketball"
            elif league_abbr in ("nhl", "khl"):
                sport = "hockey"
            elif league_abbr in ("atp", "wta"):
                sport = "tennis"
            elif league_abbr in ("cs2", "csgo", "dota2", "lol", "valorant"):
                sport = "esports"
            
            if not sport:
                return
            
            if not is_live:
                return
            
            self.stats["polymarket_events"] += 1
            
            home_team = event.get("homeTeam", {})
            away_team = event.get("awayTeam", {})
            team_a = home_team.get("name", "") if isinstance(home_team, dict) else str(home_team)
            team_b = away_team.get("name", "") if isinstance(away_team, dict) else str(away_team)
            
            logger.info(
                "POLYMARKET | %s | %s vs %s | LIVE",
                sport.upper(),
                team_a,
                team_b,
            )
            
            if self.event_matcher:
                result = await self.event_matcher.process_polymarket_event(event)
                if result:
                    self.stats["matches_found"] += 1
                    logger.info(
                        "MATCH FOUND | %s | %s vs %s | confidence=%.2f",
                        result.sport,
                        result.canonical_team1,
                        result.canonical_team2,
                        result.confidence,
                    )
                    
        except Exception as e:
            logger.error("Error processing Polymarket event: %s", e)
            self.stats["errors"] += 1
    
    async def discover_kalshi_markets(self, session, private_key, create_signature):
        """Discover all sports markets from Kalshi REST API and cache metadata."""
        import time
        
        API_BASE = "https://api.elections.kalshi.com"
        markets_path = "/trade-api/v2/markets"
        
        # Sports series to query - these contain game winner markets
        sports_series = [
            ("KXNCAAMBGAME", "basketball"),   # Men's College Basketball Game
            ("KXNCAAWBGAME", "basketball"),   # Women's College Basketball Game
            ("KXNBAGAME", "basketball"),      # NBA Game
            ("KXNHLGAME", "hockey"),          # NHL Game
            ("KXATPGAME", "tennis"),          # ATP Tennis
            ("KXWTAGAME", "tennis"),          # WTA Tennis
            ("KXSOCCERGAME", "soccer"),       # Soccer Game (if exists)
            ("KXMLSGAME", "soccer"),          # MLS Game
            ("KXUEFAGAME", "soccer"),         # UEFA Game
            ("KXVALORANTGAME", "esports"),    # Valorant Game
        ]
        
        try:
            for series_ticker, sport in sports_series:
                timestamp = str(int(time.time() * 1000))
                signature = create_signature(private_key, timestamp, "GET", markets_path)
                
                headers = {
                    "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
                    "KALSHI-ACCESS-SIGNATURE": signature,
                    "KALSHI-ACCESS-TIMESTAMP": timestamp,
                }
                
                params = {"limit": 200, "status": "open", "series_ticker": series_ticker}
                async with session.get(f"{API_BASE}{markets_path}", headers=headers, params=params) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    markets = data.get("markets", [])
                    
                    if not markets:
                        continue
                    
                    logger.info("Found %d markets in series %s", len(markets), series_ticker)
                    
                    for market in markets:
                        ticker = market.get("ticker", "")
                        title = market.get("title", "")
                        event_ticker = market.get("event_ticker", "")
                        
                        # Parse team names from title like "Washington St. at San Francisco Winner?"
                        team_a, team_b = parse_teams_from_title(title)
                        
                        self.kalshi_market_cache[ticker] = {
                            "sport": sport,
                            "team_a": team_a,
                            "team_b": team_b,
                            "title": title,
                            "event_ticker": event_ticker,
                            "series_ticker": series_ticker,
                        }
                        self.stats["kalshi_markets_discovered"] += 1
            
            logger.info("Cached %d sports markets from Kalshi", self.stats["kalshi_markets_discovered"])
            
            # Log some examples with team names
            examples = [(t, i) for t, i in self.kalshi_market_cache.items() if i["team_a"] and i["team_b"]][:5]
            for ticker, info in examples:
                logger.info("  Example: %s | %s vs %s", 
                           info["sport"].upper(), info["team_a"], info["team_b"])
                
        except Exception as e:
            logger.error("Error discovering Kalshi markets: %s", e)
    
    async def run_kalshi_listener(self):
        """Run Kalshi listener and feed events to matcher."""
        import aiohttp
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64
        import time
        
        API_BASE = "https://api.elections.kalshi.com"
        WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
        
        def load_private_key():
            return serialization.load_pem_private_key(
                KALSHI_PRIVATE_KEY_PEM.encode(),
                password=None,
                backend=default_backend(),
            )
        
        def create_signature(private_key, timestamp: str, method: str, path: str) -> str:
            message = f"{timestamp}{method}{path}".encode()
            signature = private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return base64.b64encode(signature).decode()
        
        private_key = load_private_key()
        
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    # First, discover all sports markets and cache metadata
                    if not self.kalshi_market_cache:
                        logger.info("Discovering Kalshi sports markets via REST API...")
                        await self.discover_kalshi_markets(session, private_key, create_signature)
                    
                    # Connect to WebSocket
                    ws_path = "/trade-api/ws/v2"
                    timestamp = str(int(time.time() * 1000))
                    signature = create_signature(private_key, timestamp, "GET", ws_path)
                    
                    headers = {
                        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
                        "KALSHI-ACCESS-SIGNATURE": signature,
                        "KALSHI-ACCESS-TIMESTAMP": timestamp,
                    }
                    
                    logger.info("Connecting to Kalshi WebSocket...")
                    async with session.ws_connect(WS_URL, headers=headers, heartbeat=30) as ws:
                        logger.info("Kalshi WebSocket connected")
                        
                        subscribe_msg = {
                            "id": 1,
                            "cmd": "subscribe",
                            "params": {"channels": ["ticker"]},
                        }
                        await ws.send_json(subscribe_msg)
                        
                        async for msg in ws:
                            if not self.running:
                                break
                            
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                    await self._process_kalshi_message(data)
                                except Exception as e:
                                    logger.error("Kalshi message error: %s", e)
                                    self.stats["errors"] += 1
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error("Kalshi WebSocket error")
                                break
                                
            except Exception as e:
                logger.error("Kalshi connection error: %s", e)
                self.stats["errors"] += 1
                if self.running:
                    await asyncio.sleep(5)
    
    async def _process_kalshi_message(self, data: dict):
        """Process a Kalshi WebSocket message."""
        try:
            msg_type = data.get("type", "")
            
            if msg_type != "ticker":
                return
            
            msg = data.get("msg", {})
            ticker = msg.get("market_ticker", "")
            
            # Look up market metadata from cache (populated by REST discovery)
            market_info = self.kalshi_market_cache.get(ticker)
            
            if market_info:
                # Use cached metadata with team names
                sport = market_info.get("sport")
                team_a = market_info.get("team_a", "")
                team_b = market_info.get("team_b", "")
                title = market_info.get("title", "")
            else:
                # Fallback: try to classify from ticker prefix
                ticker_upper = ticker.upper()
                sport = None
                if "NBA" in ticker_upper or "CBB" in ticker_upper or "NCAA" in ticker_upper:
                    sport = "basketball"
                elif "NHL" in ticker_upper:
                    sport = "hockey"
                elif "SOCCER" in ticker_upper:
                    sport = "soccer"
                elif "TENNIS" in ticker_upper or "ATP" in ticker_upper or "WTA" in ticker_upper:
                    sport = "tennis"
                
                if not sport:
                    return
                
                team_a = ""
                team_b = ""
                title = ticker
            
            if not sport:
                return
            
            allowed_sports = {"basketball", "hockey", "tennis", "soccer", "esports"}
            if sport not in allowed_sports:
                return
            
            self.stats["kalshi_events"] += 1
            
            # Log events with team names more frequently
            if team_a and team_b:
                logger.info("KALSHI | %s | %s vs %s | LIVE", sport.upper(), team_a, team_b)
            elif self.stats["kalshi_events"] % 50 == 1:
                logger.info("KALSHI | %s | ticker=%s", sport.upper(), ticker[:40])
            
            if self.event_matcher:
                # Build enriched kalshi_data with team names from cache
                kalshi_data = {
                    "market_ticker": ticker,
                    "title": title,
                    "event_ticker": market_info.get("event_ticker", "") if market_info else "",
                    "sport": sport,
                    "team_a": team_a,
                    "team_b": team_b,
                    **msg,
                }
                result = await self.event_matcher.process_kalshi_event(kalshi_data)
                if result:
                    self.stats["matches_found"] += 1
                    logger.info(
                        "MATCH FOUND | %s | %s vs %s | confidence=%.2f",
                        result.sport,
                        result.canonical_team1,
                        result.canonical_team2,
                        result.confidence,
                    )
                    
        except Exception as e:
            logger.error("Error processing Kalshi message: %s", e)
            self.stats["errors"] += 1
    
    async def run_duration_timer(self):
        """Stop the system after duration seconds."""
        if self.duration:
            await asyncio.sleep(self.duration)
            logger.info("Duration reached (%d seconds), stopping...", self.duration)
            self.running = False
    
    async def run_stats_logger(self):
        """Log stats periodically."""
        while self.running:
            await asyncio.sleep(30)
            if self.running:
                logger.info(
                    "STATS | Polymarket: %d | Kalshi: %d | Matches: %d | Errors: %d",
                    self.stats["polymarket_events"],
                    self.stats["kalshi_events"],
                    self.stats["matches_found"],
                    self.stats["errors"],
                )
    
    async def run(self):
        """Run the complete system."""
        self.running = True
        self.start_time = datetime.now(timezone.utc)
        
        await self.setup()
        
        logger.info("=" * 60)
        logger.info("SPORTS ARBITRAGE BOT STARTING")
        logger.info("=" * 60)
        if self.duration:
            logger.info("Will run for %d seconds", self.duration)
        
        tasks = [
            asyncio.create_task(self.run_polymarket_listener()),
            asyncio.create_task(self.run_kalshi_listener()),
            asyncio.create_task(self.run_stats_logger()),
        ]
        
        if self.duration:
            tasks.append(asyncio.create_task(self.run_duration_timer()))
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        finally:
            self.running = False
            if self.event_matcher:
                await self.event_matcher.close()
        
        self.print_stats()
    
    def print_stats(self):
        """Print final statistics."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        
        logger.info("=" * 60)
        logger.info("FINAL STATISTICS")
        logger.info("=" * 60)
        logger.info("Runtime: %.1f seconds", elapsed)
        logger.info("Polymarket events: %d", self.stats["polymarket_events"])
        logger.info("Kalshi events: %d", self.stats["kalshi_events"])
        logger.info("Matches found: %d", self.stats["matches_found"])
        logger.info("Errors: %d", self.stats["errors"])
        
        if self.event_matcher:
            self.event_matcher.print_stats()
    
    def stop(self):
        """Stop the system gracefully."""
        logger.info("Stopping system...")
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Sports Arbitrage Bot")
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=None,
        help="Run for specified duration in seconds (default: run forever)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode with sample data",
    )
    
    args = parser.parse_args()
    
    orchestrator = SystemOrchestrator(duration=args.duration)
    
    def signal_handler(sig, frame):
        logger.info("Received signal %s", sig)
        orchestrator.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    logger.info("System shutdown complete")


if __name__ == "__main__":
    main()
