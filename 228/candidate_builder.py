#!/usr/bin/env python3
"""
Candidate Builder - Module 2 Component

Mechanical pre-filter that finds potential matching candidates
between Kalshi and Polymarket events based on hard criteria.
"""

import time
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from name_normalizer import NameNormalizer, normalize_sport

logger = logging.getLogger(__name__)

ALLOWED_SPORTS: Set[str] = {
    "soccer",
    "basketball",
    "hockey",
    "esports",
    "tennis",
    "football",
    "baseball",
}

SPORT_MAPPING = {
    "soccer": "soccer",
    "football": "soccer",
    "basketball": "basketball",
    "nba": "basketball",
    "hockey": "hockey",
    "nhl": "hockey",
    "esports": "esports",
    "tennis": "tennis",
    "atp": "tennis",
    "wta": "tennis",
    "baseball": "baseball",
    "mlb": "baseball",
}

EVENT_TTL_SECONDS = 3600


@dataclass
class LiveEvent:
    """Normalized live event from either platform."""
    source: str
    event_id: str
    sport: str
    league: str
    team_a: str
    team_b: str
    status: str
    score: Optional[str] = None
    period: Optional[str] = None
    game_time: Optional[str] = None
    start_time: Optional[datetime] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: dict = field(default_factory=dict)
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def normalized_sport(self) -> str:
        """Get normalized sport name."""
        sport_lower = self.sport.lower() if self.sport else ""
        return SPORT_MAPPING.get(sport_lower, sport_lower)
    
    @property
    def is_live(self) -> bool:
        """Check if event is currently live."""
        status_lower = self.status.lower() if self.status else ""
        return status_lower in ("live", "in_progress", "inprogress", "active")
    
    @property
    def age_seconds(self) -> float:
        """Get age of event in seconds."""
        now = datetime.now(timezone.utc)
        return (now - self.last_seen).total_seconds()
    
    def update(self, other: 'LiveEvent'):
        """Update event with new data."""
        self.status = other.status
        self.score = other.score or self.score
        self.period = other.period or self.period
        self.game_time = other.game_time or self.game_time
        self.last_seen = datetime.now(timezone.utc)
        self.raw_data.update(other.raw_data)


@dataclass
class MatchCandidate:
    """A potential match between Kalshi and Polymarket events."""
    kalshi_event: LiveEvent
    polymarket_event: LiveEvent
    mechanical_score: float
    sport_match: bool
    time_proximity: float
    name_similarity: float
    
    @property
    def candidate_id(self) -> str:
        """Unique ID for this candidate pair."""
        return f"{self.kalshi_event.event_id}:{self.polymarket_event.event_id}"


class EventPool:
    """In-memory pool of active live events with TTL."""
    
    def __init__(self, source: str, ttl_seconds: int = EVENT_TTL_SECONDS):
        self.source = source
        self.ttl_seconds = ttl_seconds
        self.events: Dict[str, LiveEvent] = {}
        self._last_cleanup = time.time()
    
    def add_or_update(self, event: LiveEvent):
        """Add new event or update existing one."""
        if event.event_id in self.events:
            self.events[event.event_id].update(event)
        else:
            self.events[event.event_id] = event
        self._maybe_cleanup()
    
    def get(self, event_id: str) -> Optional[LiveEvent]:
        """Get event by ID."""
        return self.events.get(event_id)
    
    def get_all(self) -> List[LiveEvent]:
        """Get all active events."""
        self._maybe_cleanup()
        return list(self.events.values())
    
    def get_by_sport(self, sport: str) -> List[LiveEvent]:
        """Get all events for a specific sport."""
        normalized_sport = SPORT_MAPPING.get(sport.lower(), sport.lower())
        return [
            e for e in self.get_all()
            if e.normalized_sport == normalized_sport and e.is_live
        ]
    
    def remove(self, event_id: str):
        """Remove event from pool."""
        self.events.pop(event_id, None)
    
    def _maybe_cleanup(self):
        """Remove expired events periodically."""
        now = time.time()
        if now - self._last_cleanup < 60:
            return
        
        expired = [
            eid for eid, event in self.events.items()
            if event.age_seconds > self.ttl_seconds
        ]
        for eid in expired:
            del self.events[eid]
        
        if expired:
            logger.debug("Cleaned up %d expired events from %s pool", len(expired), self.source)
        
        self._last_cleanup = now
    
    def __len__(self) -> int:
        return len(self.events)


class CandidateBuilder:
    """
    Mechanical pre-filter for finding match candidates.
    Uses hard criteria to narrow down potential matches before LLM.
    """
    
    def __init__(
        self,
        min_name_similarity: float = 0.3,
        max_candidates: int = 5,
    ):
        self.normalizer = NameNormalizer()
        self.min_name_similarity = min_name_similarity
        self.max_candidates = max_candidates
        
        self.kalshi_pool = EventPool("kalshi")
        self.polymarket_pool = EventPool("polymarket")
        
        self.matched_pairs: Set[str] = set()
        
        self.stats = {
            "events_received": 0,
            "candidates_found": 0,
            "sport_mismatches": 0,
            "below_threshold": 0,
        }
    
    def add_kalshi_event(self, event: LiveEvent):
        """Add or update a Kalshi event."""
        self.kalshi_pool.add_or_update(event)
        self.stats["events_received"] += 1
    
    def add_polymarket_event(self, event: LiveEvent):
        """Add or update a Polymarket event."""
        self.polymarket_pool.add_or_update(event)
        self.stats["events_received"] += 1
    
    def find_candidates_for_kalshi(self, kalshi_event: LiveEvent) -> List[MatchCandidate]:
        """Find Polymarket candidates for a Kalshi event."""
        return self._find_candidates(kalshi_event, self.polymarket_pool, "kalshi")
    
    def find_candidates_for_polymarket(self, polymarket_event: LiveEvent) -> List[MatchCandidate]:
        """Find Kalshi candidates for a Polymarket event."""
        return self._find_candidates(polymarket_event, self.kalshi_pool, "polymarket")
    
    def _find_candidates(
        self,
        source_event: LiveEvent,
        target_pool: EventPool,
        source_type: str
    ) -> List[MatchCandidate]:
        """Find matching candidates from target pool."""
        candidates = []
        
        if not source_event.is_live:
            return candidates
        
        source_sport = source_event.normalized_sport
        if source_sport not in ALLOWED_SPORTS:
            return candidates
        
        target_events = target_pool.get_by_sport(source_sport)
        
        for target_event in target_events:
            if not target_event.is_live:
                continue
            
            pair_id = self._get_pair_id(source_event, target_event, source_type)
            if pair_id in self.matched_pairs:
                continue
            
            if source_event.normalized_sport != target_event.normalized_sport:
                self.stats["sport_mismatches"] += 1
                continue
            
            name_score, _ = self.normalizer.calculate_similarity(
                source_event.team_a, source_event.team_b,
                target_event.team_a, target_event.team_b
            )
            
            if name_score < self.min_name_similarity:
                self.stats["below_threshold"] += 1
                continue
            
            time_proximity = self._calculate_time_proximity(source_event, target_event)
            
            mechanical_score = (name_score * 0.7) + (time_proximity * 0.3)
            
            if source_type == "kalshi":
                candidate = MatchCandidate(
                    kalshi_event=source_event,
                    polymarket_event=target_event,
                    mechanical_score=mechanical_score,
                    sport_match=True,
                    time_proximity=time_proximity,
                    name_similarity=name_score,
                )
            else:
                candidate = MatchCandidate(
                    kalshi_event=target_event,
                    polymarket_event=source_event,
                    mechanical_score=mechanical_score,
                    sport_match=True,
                    time_proximity=time_proximity,
                    name_similarity=name_score,
                )
            
            candidates.append(candidate)
            self.stats["candidates_found"] += 1
        
        candidates.sort(key=lambda c: c.mechanical_score, reverse=True)
        return candidates[:self.max_candidates]
    
    def _get_pair_id(self, event1: LiveEvent, event2: LiveEvent, source_type: str) -> str:
        """Get unique ID for an event pair."""
        if source_type == "kalshi":
            return f"{event1.event_id}:{event2.event_id}"
        else:
            return f"{event2.event_id}:{event1.event_id}"
    
    def _calculate_time_proximity(self, event1: LiveEvent, event2: LiveEvent) -> float:
        """Calculate time proximity score (0-1)."""
        if event1.start_time and event2.start_time:
            diff = abs((event1.start_time - event2.start_time).total_seconds())
            if diff < 300:
                return 1.0
            elif diff < 1800:
                return 0.8
            elif diff < 3600:
                return 0.5
            else:
                return 0.2
        
        if event1.is_live and event2.is_live:
            return 0.9
        
        return 0.5
    
    def mark_matched(self, kalshi_event_id: str, polymarket_event_id: str):
        """Mark a pair as matched to avoid re-matching."""
        pair_id = f"{kalshi_event_id}:{polymarket_event_id}"
        self.matched_pairs.add(pair_id)
    
    def get_stats(self) -> dict:
        """Get builder statistics."""
        return {
            **self.stats,
            "kalshi_pool_size": len(self.kalshi_pool),
            "polymarket_pool_size": len(self.polymarket_pool),
            "matched_pairs": len(self.matched_pairs),
        }


def create_live_event_from_kalshi(raw_data: dict) -> Optional[LiveEvent]:
    """Create LiveEvent from Kalshi raw data."""
    try:
        ticker = raw_data.get("market_ticker", "") or raw_data.get("ticker", "")
        title = raw_data.get("title", "")
        
        sport = "unknown"
        if "NBA" in ticker or "NBA" in title.upper():
            sport = "basketball"
        elif "NFL" in ticker or "NFL" in title.upper():
            sport = "football"
        elif "NHL" in ticker or "NHL" in title.upper():
            sport = "hockey"
        elif "MLB" in ticker or "MLB" in title.upper():
            sport = "baseball"
        elif "TENNIS" in ticker or "ATP" in ticker or "WTA" in ticker:
            sport = "tennis"
        elif "SOCCER" in ticker or "FOOTBALL" in ticker:
            sport = "soccer"
        elif any(x in ticker.upper() for x in ["ESPORT", "LOL", "DOTA", "CSGO", "VALORANT"]):
            sport = "esports"
        
        teams = title.split(" vs ") if " vs " in title else title.split(" at ")
        team_a = teams[0].strip() if len(teams) > 0 else ""
        team_b = teams[1].strip() if len(teams) > 1 else ""
        
        return LiveEvent(
            source="kalshi",
            event_id=ticker,
            sport=sport,
            league=raw_data.get("event_ticker", ""),
            team_a=team_a,
            team_b=team_b,
            status="live",
            raw_data=raw_data,
        )
    except Exception as e:
        logger.error("Failed to create LiveEvent from Kalshi data: %s", e)
        return None


def create_live_event_from_polymarket(raw_data: dict) -> Optional[LiveEvent]:
    """Create LiveEvent from Polymarket raw data."""
    try:
        event_state = raw_data.get("eventState", {})
        
        sport = event_state.get("type", "").lower()
        if not sport:
            sport = raw_data.get("sport", "unknown")
        
        competitors = event_state.get("competitors", [])
        team_a = competitors[0].get("name", "") if len(competitors) > 0 else ""
        team_b = competitors[1].get("name", "") if len(competitors) > 1 else ""
        
        score = None
        if competitors:
            scores = [str(c.get("score", "")) for c in competitors if c.get("score") is not None]
            if scores:
                score = "-".join(scores)
        
        period = event_state.get("period", "")
        game_time = event_state.get("gameClock", "")
        
        return LiveEvent(
            source="polymarket",
            event_id=raw_data.get("gameId", str(raw_data.get("id", ""))),
            sport=sport,
            league=event_state.get("league", raw_data.get("league", "")),
            team_a=team_a,
            team_b=team_b,
            status="live" if raw_data.get("live") else "scheduled",
            score=score,
            period=period,
            game_time=game_time,
            raw_data=raw_data,
        )
    except Exception as e:
        logger.error("Failed to create LiveEvent from Polymarket data: %s", e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    builder = CandidateBuilder()
    
    kalshi_event = LiveEvent(
        source="kalshi",
        event_id="KXNBAGAME-26JAN16CLEPHI-CLE",
        sport="basketball",
        league="NBA",
        team_a="Cleveland Cavaliers",
        team_b="Philadelphia 76ers",
        status="live",
    )
    
    polymarket_event = LiveEvent(
        source="polymarket",
        event_id="pm-nba-cle-phi-123",
        sport="basketball",
        league="NBA",
        team_a="Cavs",
        team_b="Sixers",
        status="live",
    )
    
    builder.add_kalshi_event(kalshi_event)
    builder.add_polymarket_event(polymarket_event)
    
    candidates = builder.find_candidates_for_kalshi(kalshi_event)
    
    print("=== Candidate Builder Test ===")
    print(f"Found {len(candidates)} candidates")
    for c in candidates:
        print(f"  Kalshi: {c.kalshi_event.team_a} vs {c.kalshi_event.team_b}")
        print(f"  Polymarket: {c.polymarket_event.team_a} vs {c.polymarket_event.team_b}")
        print(f"  Score: {c.mechanical_score:.2f}, Name Sim: {c.name_similarity:.2f}")
        print()
    
    print("Stats:", builder.get_stats())
