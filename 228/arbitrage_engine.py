"""
Module 3: Arbitrage Signal Engine

Monitors matched events from Module 2 and detects TRUE ARBITRAGE opportunities.
Only outputs signals - NO EXECUTION.

Key rules:
- Only TRUE ARB (locked profit regardless of outcome)
- Only BUY (use best ASK prices)
- TargetTotal = total budget for both stakes + fees
- Signal only if net ROI >= 5%
- Only 2-outcome markets (Team A / Team B)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)


@dataclass
class MarketQuote:
    """Quote data for a single outcome."""
    outcome: str
    ask_price: float
    ask_size: float
    bid_price: float
    bid_size: float
    timestamp: datetime
    source: str
    
    @property
    def decimal_odds(self) -> float:
        """Convert ask price to decimal odds. Price 0.40 = odds 2.5"""
        if self.ask_price <= 0 or self.ask_price >= 1:
            return 0
        return 1.0 / self.ask_price
    
    @property
    def freshness_seconds(self) -> float:
        """How old is this quote in seconds."""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()


@dataclass
class MatchedEvent:
    """A matched event from Module 2 with live quotes."""
    event_id: str
    sport: str
    league: str
    team_a: str
    team_b: str
    live_state: str
    
    polymarket_quotes: Dict[str, MarketQuote] = field(default_factory=dict)
    kalshi_quotes: Dict[str, MarketQuote] = field(default_factory=dict)
    
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_active(self) -> bool:
        """Check if event has recent quotes from both sources."""
        if not self.polymarket_quotes or not self.kalshi_quotes:
            return False
        
        max_age = 30.0
        
        poly_fresh = any(q.freshness_seconds < max_age for q in self.polymarket_quotes.values())
        kalshi_fresh = any(q.freshness_seconds < max_age for q in self.kalshi_quotes.values())
        
        return poly_fresh and kalshi_fresh
    
    @property
    def max_quote_age(self) -> float:
        """Maximum age of any quote in seconds."""
        ages = []
        for q in self.polymarket_quotes.values():
            ages.append(q.freshness_seconds)
        for q in self.kalshi_quotes.values():
            ages.append(q.freshness_seconds)
        return max(ages) if ages else float('inf')


@dataclass
class ArbSignal:
    """Arbitrage signal output."""
    event_id: str
    event_name: str
    sport: str
    live_state: str
    
    buy_polymarket_outcome: str
    buy_polymarket_price: float
    buy_kalshi_outcome: str
    buy_kalshi_price: float
    
    target_total: float
    stake_polymarket: float
    stake_kalshi: float
    
    gross_profit: float
    fees_total: float
    net_profit: float
    net_roi: float
    
    quotes_freshness: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_signal_string(self) -> str:
        """Format as readable signal output."""
        return f"""
================================================================================
                           ARB_SIGNAL DETECTED
================================================================================
event: {self.event_name}
sport: {self.sport}
live_state: {self.live_state}

BUY:
  Polymarket: {self.buy_polymarket_outcome} @ {self.buy_polymarket_price:.4f}
  Kalshi: {self.buy_kalshi_outcome} @ {self.buy_kalshi_price:.4f}

target_total: ${self.target_total:.2f}
stakes:
  Polymarket: ${self.stake_polymarket:.4f}
  Kalshi: ${self.stake_kalshi:.4f}

fees_included: true (total fees: ${self.fees_total:.4f})
net_profit: +${self.net_profit:.4f}
net_roi: {self.net_roi:.2%}

quotes_freshness: {self.quotes_freshness:.1f}s
timestamp: {self.timestamp.isoformat()}
================================================================================
"""


class ArbitrageEngine:
    """
    Module 3: Arbitrage Signal Engine
    
    Monitors matched events and detects true arbitrage opportunities.
    Only outputs signals - NO EXECUTION.
    """
    
    POLYMARKET_TAKER_FEE = 0.02
    KALSHI_TAKER_FEE = 0.01
    EXECUTION_BUFFER = 0.01
    
    MIN_NET_ROI = 0.05  # 5% minimum net ROI for signal emission
    MAX_QUOTE_AGE = 10.0
    
    def __init__(self, target_total: float = 1.0):
        """
        Initialize arbitrage engine.
        
        Args:
            target_total: Total budget for both stakes + fees (default $1)
        """
        self.target_total = target_total
        self.matched_events: Dict[str, MatchedEvent] = {}
        self.signals_emitted: List[ArbSignal] = []
        self.running = False
        
        self.stats = {
            "events_tracked": 0,
            "quotes_received": 0,
            "arb_checks": 0,
            "arb_found": 0,
            "signals_emitted": 0,
            "no_arb": 0,
            "stale_quotes": 0,
        }
    
    def add_matched_event(self, match_result: Any) -> str:
        """
        Add a matched event from Module 2 to track.
        
        Args:
            match_result: MatchedEvent from EventMatcher (has kalshi/polymarket dicts)
            
        Returns:
            event_id for tracking
        """
        event_id = f"{match_result.canonical_team1}_vs_{match_result.canonical_team2}"
        
        if event_id not in self.matched_events:
            # Extract league from nested kalshi/polymarket dicts
            league = ""
            if hasattr(match_result, 'kalshi') and isinstance(match_result.kalshi, dict):
                league = match_result.kalshi.get('league', '')
            elif hasattr(match_result, 'polymarket') and isinstance(match_result.polymarket, dict):
                league = match_result.polymarket.get('league', '')
            
            event = MatchedEvent(
                event_id=event_id,
                sport=match_result.sport,
                league=league,
                team_a=match_result.canonical_team1,
                team_b=match_result.canonical_team2,
                live_state="LIVE",
            )
            self.matched_events[event_id] = event
            self.stats["events_tracked"] += 1
            # Use print for visibility
            print(f"[ARB_ENGINE] TRACKING | {match_result.sport.upper()} | {match_result.canonical_team1} vs {match_result.canonical_team2}")
            logger.info("TRACKING | %s | %s vs %s", 
                       match_result.sport.upper(), 
                       match_result.canonical_team1, 
                       match_result.canonical_team2)
        
        return event_id
    
    def update_polymarket_quote(self, event_id: str, outcome: str, 
                                 ask_price: float, ask_size: float = 100,
                                 bid_price: float = 0, bid_size: float = 0):
        """Update Polymarket quote for an event outcome."""
        if event_id not in self.matched_events:
            return
        
        event = self.matched_events[event_id]
        event.polymarket_quotes[outcome] = MarketQuote(
            outcome=outcome,
            ask_price=ask_price,
            ask_size=ask_size,
            bid_price=bid_price,
            bid_size=bid_size,
            timestamp=datetime.now(timezone.utc),
            source="polymarket",
        )
        event.last_update = datetime.now(timezone.utc)
        self.stats["quotes_received"] += 1
        
        if self.stats["quotes_received"] % 100 == 1:
            print(f"[ARB_ENGINE] QUOTE | Polymarket | {event_id} | {outcome} @ {ask_price:.4f}")
    
    def update_kalshi_quote(self, event_id: str, outcome: str,
                            ask_price: float, ask_size: float = 100,
                            bid_price: float = 0, bid_size: float = 0):
        """Update Kalshi quote for an event outcome."""
        if event_id not in self.matched_events:
            return
        
        event = self.matched_events[event_id]
        event.kalshi_quotes[outcome] = MarketQuote(
            outcome=outcome,
            ask_price=ask_price,
            ask_size=ask_size,
            bid_price=bid_price,
            bid_size=bid_size,
            timestamp=datetime.now(timezone.utc),
            source="kalshi",
        )
        event.last_update = datetime.now(timezone.utc)
        self.stats["quotes_received"] += 1
        
        if self.stats["quotes_received"] % 100 == 1:
            print(f"[ARB_ENGINE] QUOTE | Kalshi | {event_id} | {outcome} @ {ask_price:.4f}")
    
    def check_arbitrage(self, event: MatchedEvent) -> Optional[ArbSignal]:
        """
        Check if there's a true arbitrage opportunity for this event.
        
        TRUE ARBITRAGE for 2-outcome market:
        - Buy outcome A on one platform, outcome B on other platform
        - If 1/odds_A + 1/odds_B < 1, there's locked profit
        
        Returns:
            ArbSignal if arb found with net ROI >= 5%, else None
        """
        self.stats["arb_checks"] += 1
        
        if event.max_quote_age > self.MAX_QUOTE_AGE:
            self.stats["stale_quotes"] += 1
            return None
        
        if len(event.polymarket_quotes) < 1 or len(event.kalshi_quotes) < 1:
            return None
        
        best_signal = None
        best_roi = 0
        
        for poly_outcome, poly_quote in event.polymarket_quotes.items():
            for kalshi_outcome, kalshi_quote in event.kalshi_quotes.items():
                if self._outcomes_are_opposite(poly_outcome, kalshi_outcome, event):
                    signal = self._calculate_arb(
                        event, 
                        poly_quote, kalshi_quote,
                        "polymarket_A_kalshi_B"
                    )
                    if signal and signal.net_roi > best_roi:
                        best_signal = signal
                        best_roi = signal.net_roi
                    
                    signal = self._calculate_arb(
                        event,
                        kalshi_quote, poly_quote,
                        "kalshi_A_polymarket_B"
                    )
                    if signal and signal.net_roi > best_roi:
                        best_signal = signal
                        best_roi = signal.net_roi
        
        if best_signal:
            self.stats["arb_found"] += 1
        else:
            self.stats["no_arb"] += 1
        
        return best_signal
    
    def _outcomes_are_opposite(self, outcome1: str, outcome2: str, event: MatchedEvent) -> bool:
        """Check if two outcomes are opposite (cover all possibilities)."""
        o1 = outcome1.lower().strip()
        o2 = outcome2.lower().strip()
        
        team_a = event.team_a.lower()
        team_b = event.team_b.lower()
        
        o1_is_a = team_a in o1 or o1 in team_a or o1 == "yes" or o1 == "team_a"
        o1_is_b = team_b in o1 or o1 in team_b or o1 == "no" or o1 == "team_b"
        o2_is_a = team_a in o2 or o2 in team_a or o2 == "yes" or o2 == "team_a"
        o2_is_b = team_b in o2 or o2 in team_b or o2 == "no" or o2 == "team_b"
        
        return (o1_is_a and o2_is_b) or (o1_is_b and o2_is_a)
    
    def _calculate_arb(self, event: MatchedEvent, 
                       quote_a: MarketQuote, quote_b: MarketQuote,
                       strategy: str) -> Optional[ArbSignal]:
        """
        Calculate arbitrage for buying outcome A on one platform, outcome B on other.
        
        TRUE ARB condition: 1/odds_A + 1/odds_B < 1
        
        Args:
            event: The matched event
            quote_a: Quote for outcome A (we buy this)
            quote_b: Quote for outcome B (we buy this)
            strategy: Which platform has which outcome
            
        Returns:
            ArbSignal if profitable, else None
        """
        price_a = quote_a.ask_price
        price_b = quote_b.ask_price
        
        if price_a <= 0 or price_a >= 1 or price_b <= 0 or price_b >= 1:
            return None
        
        implied_prob_sum = price_a + price_b
        
        if implied_prob_sum >= 1.0:
            return None
        
        fee_a = self.POLYMARKET_TAKER_FEE if quote_a.source == "polymarket" else self.KALSHI_TAKER_FEE
        fee_b = self.POLYMARKET_TAKER_FEE if quote_b.source == "polymarket" else self.KALSHI_TAKER_FEE
        
        effective_price_a = price_a * (1 + fee_a)
        effective_price_b = price_b * (1 + fee_b)
        
        effective_sum = effective_price_a + effective_price_b
        
        if effective_sum >= 1.0:
            return None
        
        buffer = self.EXECUTION_BUFFER
        effective_sum_with_buffer = effective_sum * (1 + buffer)
        
        if effective_sum_with_buffer >= 1.0:
            return None
        
        stake_a = self.target_total * effective_price_a / effective_sum_with_buffer
        stake_b = self.target_total * effective_price_b / effective_sum_with_buffer
        
        payout = self.target_total / effective_sum_with_buffer
        
        gross_profit = payout - self.target_total
        
        fees_total = stake_a * fee_a + stake_b * fee_b
        
        net_profit = gross_profit - (self.target_total * buffer)
        
        net_roi = net_profit / self.target_total
        
        if net_roi < self.MIN_NET_ROI:
            return None
        
        if "polymarket_A" in strategy:
            poly_outcome = quote_a.outcome
            poly_price = price_a
            kalshi_outcome = quote_b.outcome
            kalshi_price = price_b
            stake_poly = stake_a
            stake_kalshi = stake_b
        else:
            poly_outcome = quote_b.outcome
            poly_price = price_b
            kalshi_outcome = quote_a.outcome
            kalshi_price = price_a
            stake_poly = stake_b
            stake_kalshi = stake_a
        
        return ArbSignal(
            event_id=event.event_id,
            event_name=f"{event.team_a} vs {event.team_b}",
            sport=f"{event.sport} ({event.league})" if event.league else event.sport,
            live_state=event.live_state,
            buy_polymarket_outcome=poly_outcome,
            buy_polymarket_price=poly_price,
            buy_kalshi_outcome=kalshi_outcome,
            buy_kalshi_price=kalshi_price,
            target_total=self.target_total,
            stake_polymarket=stake_poly,
            stake_kalshi=stake_kalshi,
            gross_profit=gross_profit,
            fees_total=fees_total,
            net_profit=net_profit,
            net_roi=net_roi,
            quotes_freshness=event.max_quote_age,
        )
    
    def emit_signal(self, signal: ArbSignal):
        """Emit an arbitrage signal."""
        self.signals_emitted.append(signal)
        self.stats["signals_emitted"] += 1
        
        print(signal.to_signal_string())
        
        logger.info(
            "ARB_SIGNAL | %s | %s @ %.4f + %s @ %.4f | ROI: %.2f%%",
            signal.event_name,
            signal.buy_polymarket_outcome, signal.buy_polymarket_price,
            signal.buy_kalshi_outcome, signal.buy_kalshi_price,
            signal.net_roi * 100,
        )
    
    async def check_all_events(self):
        """Check all tracked events for arbitrage opportunities."""
        active_count = 0
        for event_id, event in self.matched_events.items():
            if not event.is_active:
                continue
            
            active_count += 1
            signal = self.check_arbitrage(event)
            if signal:
                self.emit_signal(signal)
        
        # Log every 10 checks
        if self.stats["arb_checks"] % 10 == 0 and self.stats["arb_checks"] > 0:
            print(f"[ARB_ENGINE] CHECK | tracked={len(self.matched_events)} | active={active_count} | checks={self.stats['arb_checks']} | found={self.stats['arb_found']}")
    
    async def run_monitor_loop(self, check_interval: float = 1.0):
        """
        Run continuous monitoring loop.
        
        Args:
            check_interval: How often to check for arb (seconds)
        """
        self.running = True
        logger.info("Arbitrage Engine started - monitoring %d events", len(self.matched_events))
        
        while self.running:
            await self.check_all_events()
            await asyncio.sleep(check_interval)
    
    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
    
    def print_stats(self):
        """Print engine statistics."""
        print("\n=== Arbitrage Engine Statistics ===")
        print(f"Events tracked: {self.stats['events_tracked']}")
        print(f"Quotes received: {self.stats['quotes_received']}")
        print(f"Arb checks: {self.stats['arb_checks']}")
        print(f"Arb opportunities found: {self.stats['arb_found']}")
        print(f"Signals emitted: {self.stats['signals_emitted']}")
        print(f"No arb (prices unfavorable): {self.stats['no_arb']}")
        print(f"Stale quotes skipped: {self.stats['stale_quotes']}")


def calculate_simple_arb(price_a: float, price_b: float, 
                         target_total: float = 1.0,
                         fee_a: float = 0.02, fee_b: float = 0.01,
                         buffer: float = 0.01) -> Optional[dict]:
    """
    Simple standalone function to calculate arbitrage.
    
    Args:
        price_a: Ask price for outcome A (0-1)
        price_b: Ask price for outcome B (0-1)
        target_total: Total budget
        fee_a: Fee rate for platform A
        fee_b: Fee rate for platform B
        buffer: Execution buffer
        
    Returns:
        Dict with arb details if profitable, else None
    """
    if price_a <= 0 or price_a >= 1 or price_b <= 0 or price_b >= 1:
        return None
    
    if price_a + price_b >= 1.0:
        return None
    
    eff_a = price_a * (1 + fee_a)
    eff_b = price_b * (1 + fee_b)
    eff_sum = (eff_a + eff_b) * (1 + buffer)
    
    if eff_sum >= 1.0:
        return None
    
    stake_a = target_total * eff_a / eff_sum
    stake_b = target_total * eff_b / eff_sum
    payout = target_total / eff_sum
    net_profit = payout - target_total
    net_roi = net_profit / target_total
    
    if net_roi < 0.05:
        return None
    
    return {
        "stake_a": stake_a,
        "stake_b": stake_b,
        "payout": payout,
        "net_profit": net_profit,
        "net_roi": net_roi,
    }
