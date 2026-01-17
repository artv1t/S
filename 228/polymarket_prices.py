"""
Polymarket CLOB Price Fetcher

Fetches real-time best ASK prices from Polymarket CLOB API.
Read-only, no API keys required.

API Endpoints:
- Gamma API: https://gamma-api.polymarket.com/events - Get events with clobTokenIds
- CLOB API: https://clob.polymarket.com/book?token_id=X - Get orderbook with asks
"""

import asyncio
import aiohttp
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# Sports series IDs from Polymarket
SPORTS_SERIES = {
    "nba": "10345",
    "nhl": "10346", 
    "ncaab": "39",
    "epl": "10188",
    "laliga": "10193",
}


@dataclass
class PolymarketMarket:
    """Represents a Polymarket market with pricing info."""
    event_id: str
    event_title: str
    market_id: str
    question: str
    outcomes: List[str]
    clob_token_ids: List[str]
    outcome_prices: List[float]
    best_asks: Dict[str, float]  # outcome -> best ask price
    timestamp: datetime


class PolymarketPriceFetcher:
    """
    Fetches real-time prices from Polymarket CLOB API.
    
    Usage:
        fetcher = PolymarketPriceFetcher()
        await fetcher.start()
        
        # Get best ask for a specific token
        best_ask = await fetcher.get_best_ask(token_id)
        
        # Get all sports markets with prices
        markets = await fetcher.get_sports_markets()
        
        await fetcher.close()
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.markets_cache: Dict[str, PolymarketMarket] = {}
        self.token_to_event: Dict[str, str] = {}  # token_id -> event_title
        self.stats = {
            "api_calls": 0,
            "cache_hits": 0,
            "errors": 0,
        }
    
    async def start(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_best_ask(self, token_id: str) -> Optional[float]:
        """
        Get the best (lowest) ask price for a token.
        
        Args:
            token_id: The CLOB token ID
            
        Returns:
            Best ask price as decimal (e.g., 0.65), or None if no asks
        """
        if not self.session:
            await self.start()
        
        try:
            url = f"{CLOB_API_BASE}/book?token_id={token_id}"
            self.stats["api_calls"] += 1
            
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("CLOB API error: %d for token %s", resp.status, token_id[:20])
                    self.stats["errors"] += 1
                    return None
                
                data = await resp.json()
                asks = data.get("asks", [])
                
                if not asks:
                    return None
                
                # Best ask is the lowest price in the asks array
                # asks are sorted by price ascending, so first is best
                best_ask = min(float(ask["price"]) for ask in asks)
                return best_ask
                
        except Exception as e:
            logger.error("Error fetching best ask for %s: %s", token_id[:20], e)
            self.stats["errors"] += 1
            return None
    
    async def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Get full orderbook for a token.
        
        Args:
            token_id: The CLOB token ID
            
        Returns:
            Dict with 'bids' and 'asks' arrays
        """
        if not self.session:
            await self.start()
        
        try:
            url = f"{CLOB_API_BASE}/book?token_id={token_id}"
            self.stats["api_calls"] += 1
            
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    self.stats["errors"] += 1
                    return None
                
                return await resp.json()
                
        except Exception as e:
            logger.error("Error fetching orderbook: %s", e)
            self.stats["errors"] += 1
            return None
    
    async def get_sports_events(self, series_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Get active sports events from Gamma API.
        
        Args:
            series_id: Optional series ID to filter by sport
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self.session:
            await self.start()
        
        try:
            params = {
                "active": "true",
                "closed": "false",
                "limit": str(limit),
            }
            if series_id:
                params["series_id"] = series_id
            
            url = f"{GAMMA_API_BASE}/events"
            self.stats["api_calls"] += 1
            
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    self.stats["errors"] += 1
                    return []
                
                return await resp.json()
                
        except Exception as e:
            logger.error("Error fetching sports events: %s", e)
            self.stats["errors"] += 1
            return []
    
    async def get_market_prices(self, event_title: str, outcomes: List[str], 
                                 clob_token_ids: List[str]) -> Dict[str, float]:
        """
        Get best ask prices for all outcomes of a market.
        
        Args:
            event_title: Event title for logging
            outcomes: List of outcome names (e.g., ["Yes", "No"] or ["Team A", "Team B"])
            clob_token_ids: List of CLOB token IDs corresponding to outcomes
            
        Returns:
            Dict mapping outcome name to best ask price
        """
        prices = {}
        
        for i, (outcome, token_id) in enumerate(zip(outcomes, clob_token_ids)):
            best_ask = await self.get_best_ask(token_id)
            if best_ask is not None:
                prices[outcome] = best_ask
                logger.debug("POLY_PRICE | %s | %s @ %.4f", event_title[:30], outcome, best_ask)
        
        return prices
    
    async def discover_sports_markets(self) -> Dict[str, PolymarketMarket]:
        """
        Discover all active sports markets and cache them.
        
        Returns:
            Dict mapping event_title to PolymarketMarket
        """
        markets = {}
        
        for sport, series_id in SPORTS_SERIES.items():
            events = await self.get_sports_events(series_id=series_id, limit=20)
            
            for event in events:
                event_title = event.get("title", "")
                event_id = event.get("id", "")
                
                for market in event.get("markets", []):
                    clob_ids_raw = market.get("clobTokenIds")
                    outcomes_str = market.get("outcomes", "[]")
                    prices_str = market.get("outcomePrices", "[]")
                    
                    if not clob_ids_raw:
                        continue
                    
                    try:
                        # Parse JSON strings - API returns these as strings, not lists
                        clob_ids = json.loads(clob_ids_raw) if isinstance(clob_ids_raw, str) else clob_ids_raw
                        outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        prices = [float(p) for p in prices]
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.debug("Parse error for %s: %s", event_title, e)
                        continue
                    
                    # Only include 2-outcome markets (binary)
                    if len(outcomes) != 2 or len(clob_ids) != 2:
                        continue
                    
                    # Skip prop bets (Yes/No, Over/Under) - only keep moneyline (Team vs Team)
                    outcomes_lower = [o.lower() for o in outcomes]
                    if "yes" in outcomes_lower or "no" in outcomes_lower:
                        continue
                    if "over" in outcomes_lower or "under" in outcomes_lower:
                        continue
                    
                    # Skip markets with 0 or 1 prices (already resolved)
                    if 0.0 in prices or 1.0 in prices:
                        continue
                    
                    pm = PolymarketMarket(
                        event_id=event_id,
                        event_title=event_title,
                        market_id=market.get("id", ""),
                        question=market.get("question", ""),
                        outcomes=outcomes,
                        clob_token_ids=clob_ids,
                        outcome_prices=prices,
                        best_asks={},
                        timestamp=datetime.now(timezone.utc),
                    )
                    
                    # Store mapping from token to event
                    for token_id in clob_ids:
                        self.token_to_event[token_id] = event_title
                    
                    markets[event_title] = pm
                    logger.info("POLY_MARKET | %s | %s | outcomes=%s", 
                               sport.upper(), event_title, outcomes)
        
        self.markets_cache = markets
        return markets
    
    async def refresh_prices(self, event_title: str) -> Optional[Dict[str, float]]:
        """
        Refresh best ask prices for a specific event.
        
        Args:
            event_title: The event title to refresh
            
        Returns:
            Dict mapping outcome to best ask price, or None if not found
        """
        market = self.markets_cache.get(event_title)
        if not market:
            return None
        
        prices = await self.get_market_prices(
            event_title,
            market.outcomes,
            market.clob_token_ids
        )
        
        market.best_asks = prices
        market.timestamp = datetime.now(timezone.utc)
        
        return prices
    
    def get_cached_market(self, event_title: str) -> Optional[PolymarketMarket]:
        """Get a cached market by event title."""
        return self.markets_cache.get(event_title)
    
    # City to team name mapping for NBA/NHL
    CITY_TO_TEAM = {
        # NBA
        "los angeles c": "clippers", "la clippers": "clippers", "lac": "clippers",
        "los angeles l": "lakers", "la lakers": "lakers", "lal": "lakers",
        "cleveland": "cavaliers", "cle": "cavaliers",
        "philadelphia": "76ers", "phi": "76ers", "philly": "76ers",
        "indiana": "pacers", "ind": "pacers",
        "new orleans": "pelicans", "nop": "pelicans",
        "chicago": "bulls", "chi": "bulls",
        "brooklyn": "nets", "bkn": "nets",
        "toronto": "raptors", "tor": "raptors",
        "minnesota": "timberwolves", "min": "timberwolves",
        "houston": "rockets", "hou": "rockets",
        "washington": "wizards", "was": "wizards",
        "sacramento": "kings", "sac": "kings",
        "miami": "heat", "mia": "heat",
        "boston": "celtics", "bos": "celtics",
        "atlanta": "hawks", "atl": "hawks",
        "orlando": "magic", "orl": "magic",
        "utah": "jazz", "uta": "jazz",
        "dallas": "mavericks", "dal": "mavericks",
        "phoenix": "suns", "phx": "suns",
        "memphis": "grizzlies", "mem": "grizzlies",
        "denver": "nuggets", "den": "nuggets",
        "golden state": "warriors", "gsw": "warriors",
        "portland": "trail blazers", "por": "trail blazers",
        "oklahoma city": "thunder", "okc": "thunder",
        "san antonio": "spurs", "sas": "spurs",
        "detroit": "pistons", "det": "pistons",
        "milwaukee": "bucks", "mil": "bucks",
        "charlotte": "hornets", "cha": "hornets",
        "new york": "knicks", "nyk": "knicks",
        # NHL
        "tampa bay": "lightning", "tb": "lightning",
        "st. louis": "blues", "stl": "blues",
        "florida": "panthers", "fla": "panthers",
        "carolina": "hurricanes", "car": "hurricanes",
        "san jose": "sharks", "sj": "sharks", "sharks": "sharks",
        "detroit": "red wings", "det": "red wings", "red wings": "red wings",
        "nashville": "predators", "nsh": "predators",
        "colorado": "avalanche", "col": "avalanche",
        "anaheim": "ducks", "ana": "ducks",
        "los angeles k": "kings",
        "buffalo": "sabres", "buf": "sabres",
        "new york r": "rangers", "nyr": "rangers",
        "new york i": "islanders", "nyi": "islanders",
        "calgary": "flames", "cgy": "flames",
        "seattle": "kraken", "sea": "kraken",
        "winnipeg": "jets", "wpg": "jets",
        "columbus": "blue jackets", "cbj": "blue jackets",
        "pittsburgh": "penguins", "pit": "penguins",
        "montreal": "canadiens", "mtl": "canadiens",
        "ottawa": "senators", "ott": "senators",
        "new jersey": "devils", "njd": "devils",
        "edmonton": "oilers", "edm": "oilers",
        "vancouver": "canucks", "van": "canucks",
    }
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name to standard form."""
        name_lower = name.lower().strip()
        # Check if it's a city name that maps to a team
        if name_lower in self.CITY_TO_TEAM:
            return self.CITY_TO_TEAM[name_lower]
        # Check partial matches for city names
        for city, team in self.CITY_TO_TEAM.items():
            if city in name_lower or name_lower in city:
                return team
        return name_lower
    
    def find_market_by_teams(self, team1: str, team2: str) -> Optional[PolymarketMarket]:
        """
        Find a market by team names (fuzzy match with city-to-team mapping).
        
        Args:
            team1: First team name (can be city name like "Cleveland" or team name like "Cavaliers")
            team2: Second team name
            
        Returns:
            PolymarketMarket if found, None otherwise
        """
        # Normalize team names (convert city names to team names)
        team1_norm = self._normalize_team_name(team1)
        team2_norm = self._normalize_team_name(team2)
        
        for title, market in self.markets_cache.items():
            title_lower = title.lower()
            outcomes_lower = [o.lower() for o in market.outcomes]
            
            # Check if both normalized teams appear in outcomes
            team1_in_outcomes = any(team1_norm in o for o in outcomes_lower)
            team2_in_outcomes = any(team2_norm in o for o in outcomes_lower)
            
            if team1_in_outcomes and team2_in_outcomes:
                return market
            
            # Also check title
            if team1_norm in title_lower and team2_norm in title_lower:
                return market
            
            # Check original names in title/outcomes as fallback
            team1_lower = team1.lower()
            team2_lower = team2.lower()
            if team1_lower in title_lower and team2_lower in title_lower:
                return market
        
        return None
    
    def print_stats(self):
        """Print fetcher statistics."""
        print(f"\n=== Polymarket Price Fetcher Stats ===")
        print(f"API calls: {self.stats['api_calls']}")
        print(f"Cache hits: {self.stats['cache_hits']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Markets cached: {len(self.markets_cache)}")


async def test_fetcher():
    """Test the price fetcher."""
    fetcher = PolymarketPriceFetcher()
    await fetcher.start()
    
    print("Discovering sports markets...")
    markets = await fetcher.discover_sports_markets()
    print(f"Found {len(markets)} markets")
    
    # Get prices for first few markets
    for title, market in list(markets.items())[:3]:
        print(f"\n{title}")
        print(f"  Outcomes: {market.outcomes}")
        print(f"  Cached prices: {market.outcome_prices}")
        
        # Fetch real-time best asks
        prices = await fetcher.refresh_prices(title)
        print(f"  Best asks: {prices}")
    
    fetcher.print_stats()
    await fetcher.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_fetcher())
