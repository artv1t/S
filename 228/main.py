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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "out"
LOGS_DIR = BASE_DIR / "logs"

KALSHI_API_KEY_ID = os.environ.get("KALSHI_API_KEY_ID", "177e5c48-edfa-4fa4-bfd2-43bee1ef886f")
KALSHI_PRIVATE_KEY_PEM = os.environ.get("KALSHI_PRIVATE_KEY_PEM", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-f1b0fc04db5a4beca73ed8b0803210cf")


class SystemOrchestrator:
    """Main orchestrator that runs all modules together."""
    
    def __init__(self, duration: Optional[int] = None):
        self.duration = duration
        self.running = False
        self.start_time: Optional[datetime] = None
        
        self.polymarket_listener = None
        self.kalshi_listener = None
        self.event_matcher = None
        
        self.stats = {
            "polymarket_events": 0,
            "kalshi_events": 0,
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
            if KALSHI_PRIVATE_KEY_PEM:
                return serialization.load_pem_private_key(
                    KALSHI_PRIVATE_KEY_PEM.encode(),
                    password=None,
                    backend=default_backend(),
                )
            return None
        
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
        if not private_key:
            logger.error("Kalshi private key not configured")
            return
        
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
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
            
            sport = None
            ticker_upper = ticker.upper()
            if "NBA" in ticker_upper or "NBAGAME" in ticker_upper:
                sport = "basketball"
            elif "NHL" in ticker_upper or "NHLGAME" in ticker_upper:
                sport = "hockey"
            elif "NFL" in ticker_upper or "NFLGAME" in ticker_upper:
                sport = "football"
            elif "MLB" in ticker_upper or "MLBGAME" in ticker_upper:
                sport = "baseball"
            elif "TENNIS" in ticker_upper or "ATP" in ticker_upper or "WTA" in ticker_upper or "TABLETENNIS" in ticker_upper:
                sport = "tennis"
            elif "SOCCER" in ticker_upper or "FOOTBALL" in ticker_upper:
                sport = "soccer"
            
            if not sport:
                return
            
            allowed_sports = {"basketball", "hockey", "tennis", "soccer", "esports", "football", "baseball"}
            if sport not in allowed_sports:
                return
            
            self.stats["kalshi_events"] += 1
            
            if self.stats["kalshi_events"] % 100 == 1:
                logger.info("KALSHI | %s | ticker=%s", sport.upper(), ticker[:50])
            
            if self.event_matcher:
                kalshi_data = {
                    "market_ticker": ticker,
                    "title": ticker,
                    "event_ticker": sport.upper(),
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
