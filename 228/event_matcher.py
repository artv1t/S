#!/usr/bin/env python3
"""
Event Matcher - Module 2 Main Orchestrator

Combines CandidateBuilder and DeepSeekJudge to match events
between Kalshi and Polymarket in real-time.
"""

import json
import hashlib
import logging
import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from candidate_builder import (
    CandidateBuilder, LiveEvent, MatchCandidate,
    create_live_event_from_kalshi, create_live_event_from_polymarket
)
from deepseek_judge import DeepSeekJudge, JudgeResult

logger = logging.getLogger(__name__)

OUT_DIR = Path("out")
MATCHED_PAIRS_FILE = OUT_DIR / "matched_pairs.jsonl"
QUEUE_FOR_MODULE3_FILE = OUT_DIR / "queue_for_module3.jsonl"


@dataclass
class MatchedEvent:
    """A confirmed match between Kalshi and Polymarket events."""
    matched_id: str
    sport: str
    confidence: float
    timestamp: str
    canonical_team1: str
    canonical_team2: str
    kalshi: dict
    polymarket: dict
    judge_reason: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class FileSender:
    """Sends matched events to files for Module 3."""
    
    def __init__(self, matched_file: Path, queue_file: Path):
        self.matched_file = matched_file
        self.queue_file = queue_file
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Ensure output directories exist."""
        self.matched_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
    
    def send(self, matched_event: MatchedEvent):
        """Send matched event to output files."""
        json_line = matched_event.to_json() + "\n"
        
        with open(self.matched_file, "a") as f:
            f.write(json_line)
        
        with open(self.queue_file, "a") as f:
            f.write(json_line)
        
        logger.info(
            "MATCHED | %s | %s vs %s | confidence=%.2f",
            matched_event.sport,
            matched_event.canonical_team1,
            matched_event.canonical_team2,
            matched_event.confidence,
        )


class EventMatcher:
    """
    Main Module 2 orchestrator.
    Combines mechanical pre-filter with LLM judge for accurate matching.
    """
    
    def __init__(
        self,
        deepseek_api_key: str,
        min_mechanical_score: float = 0.4,
        confidence_threshold: float = 0.85,
        max_candidates: int = 5,
    ):
        self.candidate_builder = CandidateBuilder(
            min_name_similarity=0.3,
            max_candidates=max_candidates,
        )
        
        self.judge = DeepSeekJudge(
            api_key=deepseek_api_key,
            confidence_threshold=confidence_threshold,
        )
        
        self.sender = FileSender(MATCHED_PAIRS_FILE, QUEUE_FOR_MODULE3_FILE)
        
        self.min_mechanical_score = min_mechanical_score
        self.confidence_threshold = confidence_threshold
        
        self.matched_events: Dict[str, MatchedEvent] = {}
        
        self.stats = {
            "kalshi_events": 0,
            "polymarket_events": 0,
            "candidates_evaluated": 0,
            "llm_calls": 0,
            "matches_found": 0,
            "matches_rejected": 0,
            "high_confidence_mechanical": 0,
        }
        
        self._callbacks: List[Callable[[MatchedEvent], Any]] = []
    
    def add_callback(self, callback: Callable[[MatchedEvent], Any]):
        """Add callback for new matches."""
        self._callbacks.append(callback)
    
    async def close(self):
        """Close resources."""
        await self.judge.close()
    
    async def process_kalshi_event(self, raw_data: dict) -> Optional[MatchedEvent]:
        """Process a Kalshi event and try to find matches."""
        event = create_live_event_from_kalshi(raw_data)
        if not event:
            return None
        
        self.stats["kalshi_events"] += 1
        self.candidate_builder.add_kalshi_event(event)
        
        candidates = self.candidate_builder.find_candidates_for_kalshi(event)
        
        if not candidates:
            return None
        
        return await self._evaluate_candidates(candidates)
    
    async def process_polymarket_event(self, raw_data: dict) -> Optional[MatchedEvent]:
        """Process a Polymarket event and try to find matches."""
        event = create_live_event_from_polymarket(raw_data)
        if not event:
            return None
        
        self.stats["polymarket_events"] += 1
        self.candidate_builder.add_polymarket_event(event)
        
        candidates = self.candidate_builder.find_candidates_for_polymarket(event)
        
        if not candidates:
            return None
        
        return await self._evaluate_candidates(candidates)
    
    async def _evaluate_candidates(self, candidates: List[MatchCandidate]) -> Optional[MatchedEvent]:
        """Evaluate candidates and return best match if found."""
        for candidate in candidates:
            self.stats["candidates_evaluated"] += 1
            
            pair_id = candidate.candidate_id
            if pair_id in self.matched_events:
                continue
            
            if candidate.mechanical_score >= 0.8:
                self.stats["high_confidence_mechanical"] += 1
                logger.info(
                    "HIGH MECHANICAL SCORE (%.2f) | %s vs %s <-> %s vs %s",
                    candidate.mechanical_score,
                    candidate.kalshi_event.team_a,
                    candidate.kalshi_event.team_b,
                    candidate.polymarket_event.team_a,
                    candidate.polymarket_event.team_b,
                )
            
            if candidate.mechanical_score < self.min_mechanical_score:
                continue
            
            self.stats["llm_calls"] += 1
            
            kalshi = candidate.kalshi_event
            poly = candidate.polymarket_event
            
            result = await self.judge.judge(
                sport=kalshi.normalized_sport,
                kalshi_title=f"{kalshi.team_a} vs {kalshi.team_b}",
                polymarket_title=f"{poly.team_a} vs {poly.team_b}",
                kalshi_team_a=kalshi.team_a,
                kalshi_team_b=kalshi.team_b,
                polymarket_team_a=poly.team_a,
                polymarket_team_b=poly.team_b,
                kalshi_league=kalshi.league,
                polymarket_league=poly.league,
                kalshi_status=kalshi.status,
                polymarket_status=poly.status,
                kalshi_score=kalshi.score or "",
                polymarket_score=poly.score or "",
            )
            
            if result.is_accepted:
                matched = self._create_matched_event(candidate, result)
                self.matched_events[pair_id] = matched
                self.stats["matches_found"] += 1
                
                self.candidate_builder.mark_matched(kalshi.event_id, poly.event_id)
                
                self.sender.send(matched)
                
                for callback in self._callbacks:
                    try:
                        callback(matched)
                    except Exception as e:
                        logger.error("Callback error: %s", e)
                
                return matched
            else:
                self.stats["matches_rejected"] += 1
                logger.debug(
                    "REJECTED | %s vs %s <-> %s vs %s | confidence=%.2f | reason=%s",
                    kalshi.team_a, kalshi.team_b,
                    poly.team_a, poly.team_b,
                    result.confidence,
                    result.reason,
                )
        
        return None
    
    def _create_matched_event(self, candidate: MatchCandidate, result: JudgeResult) -> MatchedEvent:
        """Create MatchedEvent from candidate and judge result."""
        kalshi = candidate.kalshi_event
        poly = candidate.polymarket_event
        
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        teams_str = f"{result.canonical_team1}:{result.canonical_team2}"
        hash_input = f"{kalshi.normalized_sport}:{teams_str}:{date_str}"
        matched_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]
        
        return MatchedEvent(
            matched_id=matched_id,
            sport=kalshi.normalized_sport,
            confidence=result.confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            canonical_team1=result.canonical_team1,
            canonical_team2=result.canonical_team2,
            kalshi={
                "event_id": kalshi.event_id,
                "team_a": kalshi.team_a,
                "team_b": kalshi.team_b,
                "league": kalshi.league,
                "status": kalshi.status,
                "score": kalshi.score,
                "raw": kalshi.raw_data,
            },
            polymarket={
                "event_id": poly.event_id,
                "team_a": poly.team_a,
                "team_b": poly.team_b,
                "league": poly.league,
                "status": poly.status,
                "score": poly.score,
                "raw": poly.raw_data,
            },
            judge_reason=result.reason,
        )
    
    def get_stats(self) -> dict:
        """Get matcher statistics."""
        return {
            **self.stats,
            "builder_stats": self.candidate_builder.get_stats(),
            "judge_stats": self.judge.get_stats(),
        }
    
    def print_stats(self):
        """Print statistics to console."""
        stats = self.get_stats()
        print("\n=== Event Matcher Statistics ===")
        print(f"Kalshi events received: {stats['kalshi_events']}")
        print(f"Polymarket events received: {stats['polymarket_events']}")
        print(f"Candidates evaluated: {stats['candidates_evaluated']}")
        print(f"LLM calls made: {stats['llm_calls']}")
        print(f"Matches found: {stats['matches_found']}")
        print(f"Matches rejected: {stats['matches_rejected']}")
        print(f"High confidence mechanical: {stats['high_confidence_mechanical']}")
        print(f"\nBuilder stats: {stats['builder_stats']}")
        print(f"Judge stats: {stats['judge_stats']}")


async def test_matcher():
    """Test the event matcher with sample data."""
    import os
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-f1b0fc04db5a4beca73ed8b0803210cf")
    
    matcher = EventMatcher(deepseek_api_key=api_key)
    
    kalshi_events = [
        {
            "market_ticker": "KXNBAGAME-26JAN16CLEPHI-CLE",
            "title": "Cleveland at Philadelphia",
            "event_ticker": "NBA",
        },
        {
            "market_ticker": "KXNHLGAME-26JAN16TBSTL-TB",
            "title": "Tampa Bay at St. Louis",
            "event_ticker": "NHL",
        },
    ]
    
    polymarket_events = [
        {
            "gameId": "pm-nba-cle-phi-123",
            "live": True,
            "eventState": {
                "type": "basketball",
                "league": "NBA",
                "competitors": [
                    {"name": "Cavaliers", "score": 45},
                    {"name": "76ers", "score": 42},
                ],
                "period": "2Q",
            },
        },
        {
            "gameId": "pm-nhl-tb-stl-456",
            "live": True,
            "eventState": {
                "type": "hockey",
                "league": "NHL",
                "competitors": [
                    {"name": "Lightning", "score": 2},
                    {"name": "Blues", "score": 1},
                ],
                "period": "2P",
            },
        },
    ]
    
    print("=== Event Matcher Test ===")
    
    for event in polymarket_events:
        await matcher.process_polymarket_event(event)
    
    for event in kalshi_events:
        result = await matcher.process_kalshi_event(event)
        if result:
            print(f"\nMatch found!")
            print(f"  ID: {result.matched_id}")
            print(f"  Sport: {result.sport}")
            print(f"  Teams: {result.canonical_team1} vs {result.canonical_team2}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Reason: {result.judge_reason}")
    
    matcher.print_stats()
    
    await matcher.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    asyncio.run(test_matcher())
