#!/usr/bin/env python3
"""
DeepSeek Judge - Module 2 Component

LLM-based final judge for matching events between Kalshi and Polymarket.
Only called when mechanical pre-filter finds candidates.
"""

import json
import time
import hashlib
import logging
import asyncio
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

CONFIDENCE_THRESHOLD = 0.85
MAX_REQUESTS_PER_MINUTE = 20
CACHE_TTL_SECONDS = 3600

JUDGE_SYSTEM_PROMPT = """You are an expert sports event matcher. Your job is to determine if two events from different betting platforms refer to the SAME real-world sports match.

RULES:
1. Events MUST be the same sport to match
2. Both teams/participants must match (order doesn't matter - home/away can be swapped)
3. The match must be happening at approximately the same time
4. Be VERY careful with similar team names (e.g., "New York Jets" vs "New York Giants" are DIFFERENT teams)
5. Abbreviations are common (e.g., "CLE" = "Cleveland", "PHI" = "Philadelphia")
6. League names may differ but should be compatible

RESPOND ONLY WITH VALID JSON, NO OTHER TEXT:
{
  "match": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation",
  "canonical_pair": {"team1": "...", "team2": "..."}
}"""


@dataclass
class JudgeResult:
    """Result from DeepSeek judge."""
    match: bool
    confidence: float
    reason: str
    canonical_team1: str
    canonical_team2: str
    from_cache: bool = False
    
    @property
    def is_accepted(self) -> bool:
        """Check if match is accepted based on confidence threshold."""
        return self.match and self.confidence >= CONFIDENCE_THRESHOLD


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list = []
    
    async def acquire(self):
        """Wait until we can make a request."""
        now = time.time()
        self.requests = [t for t in self.requests if now - t < self.window_seconds]
        
        if len(self.requests) >= self.max_requests:
            wait_time = self.requests[0] + self.window_seconds - now
            if wait_time > 0:
                logger.debug("Rate limit reached, waiting %.1f seconds", wait_time)
                await asyncio.sleep(wait_time)
        
        self.requests.append(time.time())


class DecisionCache:
    """Cache for judge decisions to avoid redundant API calls."""
    
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[JudgeResult, float]] = {}
    
    def _make_key(self, sport: str, team_a1: str, team_b1: str, team_a2: str, team_b2: str) -> str:
        """Create cache key from event details."""
        teams = sorted([
            sorted([team_a1.lower(), team_b1.lower()]),
            sorted([team_a2.lower(), team_b2.lower()])
        ], key=lambda x: x[0])
        key_str = f"{sport.lower()}:{teams}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, sport: str, team_a1: str, team_b1: str, team_a2: str, team_b2: str) -> Optional[JudgeResult]:
        """Get cached result if available and not expired."""
        key = self._make_key(sport, team_a1, team_b1, team_a2, team_b2)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                result.from_cache = True
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, sport: str, team_a1: str, team_b1: str, team_a2: str, team_b2: str, result: JudgeResult):
        """Cache a judge result."""
        key = self._make_key(sport, team_a1, team_b1, team_a2, team_b2)
        self.cache[key] = (result, time.time())
    
    def clear_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, t) in self.cache.items() if now - t >= self.ttl_seconds]
        for k in expired:
            del self.cache[k]


class DeepSeekJudge:
    """
    LLM-based judge for final matching decisions.
    Uses DeepSeek API with caching and rate limiting.
    """
    
    def __init__(
        self,
        api_key: str,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        max_requests_per_minute: int = MAX_REQUESTS_PER_MINUTE,
    ):
        self.api_key = api_key
        self.confidence_threshold = confidence_threshold
        self.rate_limiter = RateLimiter(max_requests_per_minute)
        self.cache = DecisionCache()
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.stats = {
            "api_calls": 0,
            "cache_hits": 0,
            "matches_accepted": 0,
            "matches_rejected": 0,
            "errors": 0,
        }
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _build_prompt(
        self,
        sport: str,
        kalshi_title: str,
        polymarket_title: str,
        kalshi_team_a: str,
        kalshi_team_b: str,
        polymarket_team_a: str,
        polymarket_team_b: str,
        kalshi_league: str = "",
        polymarket_league: str = "",
        kalshi_status: str = "",
        polymarket_status: str = "",
        kalshi_score: str = "",
        polymarket_score: str = "",
    ) -> str:
        """Build the prompt for the judge."""
        prompt = f"""Compare these two sports events and determine if they are the SAME match:

SPORT: {sport}

EVENT 1 (Kalshi):
- Title: {kalshi_title}
- Team A: {kalshi_team_a}
- Team B: {kalshi_team_b}
- League: {kalshi_league or 'N/A'}
- Status: {kalshi_status or 'LIVE'}
- Score: {kalshi_score or 'N/A'}

EVENT 2 (Polymarket):
- Title: {polymarket_title}
- Team A: {polymarket_team_a}
- Team B: {polymarket_team_b}
- League: {polymarket_league or 'N/A'}
- Status: {polymarket_status or 'LIVE'}
- Score: {polymarket_score or 'N/A'}

Are these the SAME real-world sports match? Respond with JSON only."""
        return prompt
    
    async def judge(
        self,
        sport: str,
        kalshi_title: str,
        polymarket_title: str,
        kalshi_team_a: str,
        kalshi_team_b: str,
        polymarket_team_a: str,
        polymarket_team_b: str,
        kalshi_league: str = "",
        polymarket_league: str = "",
        kalshi_status: str = "",
        polymarket_status: str = "",
        kalshi_score: str = "",
        polymarket_score: str = "",
    ) -> JudgeResult:
        """
        Judge if two events are the same match.
        Returns JudgeResult with match decision and confidence.
        """
        cached = self.cache.get(
            sport, kalshi_team_a, kalshi_team_b, polymarket_team_a, polymarket_team_b
        )
        if cached:
            self.stats["cache_hits"] += 1
            logger.debug("Cache hit for %s vs %s", kalshi_title, polymarket_title)
            return cached
        
        await self._ensure_session()
        await self.rate_limiter.acquire()
        
        prompt = self._build_prompt(
            sport=sport,
            kalshi_title=kalshi_title,
            polymarket_title=polymarket_title,
            kalshi_team_a=kalshi_team_a,
            kalshi_team_b=kalshi_team_b,
            polymarket_team_a=polymarket_team_a,
            polymarket_team_b=polymarket_team_b,
            kalshi_league=kalshi_league,
            polymarket_league=polymarket_league,
            kalshi_status=kalshi_status,
            polymarket_status=polymarket_status,
            kalshi_score=kalshi_score,
            polymarket_score=polymarket_score,
        )
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 200,
            }
            
            async with self.session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                self.stats["api_calls"] += 1
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("DeepSeek API error %d: %s", response.status, error_text)
                    self.stats["errors"] += 1
                    return JudgeResult(
                        match=False,
                        confidence=0.0,
                        reason=f"API error: {response.status}",
                        canonical_team1="",
                        canonical_team2="",
                    )
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                
                result = self._parse_response(content)
                
                self.cache.set(
                    sport, kalshi_team_a, kalshi_team_b, polymarket_team_a, polymarket_team_b, result
                )
                
                if result.is_accepted:
                    self.stats["matches_accepted"] += 1
                else:
                    self.stats["matches_rejected"] += 1
                
                return result
                
        except asyncio.TimeoutError:
            logger.error("DeepSeek API timeout")
            self.stats["errors"] += 1
            return JudgeResult(
                match=False,
                confidence=0.0,
                reason="API timeout",
                canonical_team1="",
                canonical_team2="",
            )
        except Exception as e:
            logger.error("DeepSeek API error: %s", e)
            self.stats["errors"] += 1
            return JudgeResult(
                match=False,
                confidence=0.0,
                reason=f"Error: {str(e)}",
                canonical_team1="",
                canonical_team2="",
            )
    
    def _parse_response(self, content: str) -> JudgeResult:
        """Parse LLM response into JudgeResult."""
        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            canonical = data.get("canonical_pair", {})
            
            return JudgeResult(
                match=bool(data.get("match", False)),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", "")),
                canonical_team1=str(canonical.get("team1", "")),
                canonical_team2=str(canonical.get("team2", "")),
            )
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response: %s", e)
            logger.debug("Raw response: %s", content)
            return JudgeResult(
                match=False,
                confidence=0.0,
                reason=f"Parse error: {str(e)}",
                canonical_team1="",
                canonical_team2="",
            )
    
    def get_stats(self) -> dict:
        """Get judge statistics."""
        return {
            **self.stats,
            "cache_size": len(self.cache.cache),
        }


async def test_judge():
    """Test the DeepSeek judge."""
    import os
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-f1b0fc04db5a4beca73ed8b0803210cf")
    
    judge = DeepSeekJudge(api_key)
    
    test_cases = [
        {
            "sport": "basketball",
            "kalshi_title": "Cleveland at Philadelphia",
            "polymarket_title": "Cavaliers vs 76ers",
            "kalshi_team_a": "Cleveland Cavaliers",
            "kalshi_team_b": "Philadelphia 76ers",
            "polymarket_team_a": "Cavs",
            "polymarket_team_b": "Sixers",
            "kalshi_league": "NBA",
            "polymarket_league": "NBA",
        },
        {
            "sport": "hockey",
            "kalshi_title": "Tampa Bay at St. Louis",
            "polymarket_title": "Lightning vs Blues",
            "kalshi_team_a": "Tampa Bay Lightning",
            "kalshi_team_b": "St. Louis Blues",
            "polymarket_team_a": "TB Lightning",
            "polymarket_team_b": "STL Blues",
            "kalshi_league": "NHL",
            "polymarket_league": "NHL",
        },
        {
            "sport": "basketball",
            "kalshi_title": "New York Knicks vs Brooklyn Nets",
            "polymarket_title": "Los Angeles Lakers vs Golden State Warriors",
            "kalshi_team_a": "New York Knicks",
            "kalshi_team_b": "Brooklyn Nets",
            "polymarket_team_a": "LA Lakers",
            "polymarket_team_b": "GSW",
            "kalshi_league": "NBA",
            "polymarket_league": "NBA",
        },
    ]
    
    print("=== DeepSeek Judge Test ===")
    
    for i, tc in enumerate(test_cases):
        print(f"\nTest {i+1}:")
        print(f"  Kalshi: {tc['kalshi_title']}")
        print(f"  Polymarket: {tc['polymarket_title']}")
        
        result = await judge.judge(**tc)
        
        print(f"  Match: {result.match}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Accepted: {result.is_accepted}")
        print(f"  Reason: {result.reason}")
        print(f"  Canonical: {result.canonical_team1} vs {result.canonical_team2}")
        print(f"  From cache: {result.from_cache}")
    
    print("\nStats:", judge.get_stats())
    
    await judge.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_judge())
