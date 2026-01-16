#!/usr/bin/env python3
"""
Name Normalizer - Module 2 Component

Normalizes team/event names for matching between Kalshi and Polymarket.
Removes noise words, handles abbreviations, and provides similarity scoring.
"""

import re
from typing import Set, Tuple, List, Optional
from difflib import SequenceMatcher


NOISE_WORDS: Set[str] = {
    "fc", "cf", "sc", "bc", "ac", "afc", "ssc", "rcd", "cd", "ud", "sd",
    "esports", "esport", "gaming", "team", "club", "united", "city",
    "women", "mens", "men", "w", "m",
    "u19", "u21", "u23", "youth", "junior", "reserve", "reserves",
    "de", "la", "el", "the", "of", "and", "vs", "versus",
    "international", "intl", "national",
}

TEAM_ALIASES = {
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "man utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "manchester c": "manchester city",
    "real": "real madrid",
    "barca": "barcelona",
    "fcb": "barcelona",
    "bayern": "bayern munich",
    "bayern munchen": "bayern munich",
    "juve": "juventus",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "ac milan": "milan",
    "atletico": "atletico madrid",
    "atleti": "atletico madrid",
    "spurs": "tottenham",
    "tottenham hotspur": "tottenham",
    "arsenal fc": "arsenal",
    "chelsea fc": "chelsea",
    "liverpool fc": "liverpool",
    "lakers": "los angeles lakers",
    "la lakers": "los angeles lakers",
    "celtics": "boston celtics",
    "warriors": "golden state warriors",
    "gsw": "golden state warriors",
    "knicks": "new york knicks",
    "ny knicks": "new york knicks",
    "nets": "brooklyn nets",
    "heat": "miami heat",
    "bulls": "chicago bulls",
    "cavs": "cleveland cavaliers",
    "sixers": "philadelphia 76ers",
    "philly": "philadelphia 76ers",
    "mavs": "dallas mavericks",
    "clips": "los angeles clippers",
    "la clippers": "los angeles clippers",
    "wolves": "minnesota timberwolves",
    "twolves": "minnesota timberwolves",
    "blazers": "portland trail blazers",
    "thunder": "oklahoma city thunder",
    "okc": "oklahoma city thunder",
    "spurs": "san antonio spurs",
    "suns": "phoenix suns",
    "kings": "sacramento kings",
    "jazz": "utah jazz",
    "pels": "new orleans pelicans",
    "pacers": "indiana pacers",
    "hawks": "atlanta hawks",
    "magic": "orlando magic",
    "pistons": "detroit pistons",
    "hornets": "charlotte hornets",
    "wizards": "washington wizards",
    "raptors": "toronto raptors",
    "grizzlies": "memphis grizzlies",
    "rockets": "houston rockets",
    "nuggets": "denver nuggets",
    "bruins": "boston bruins",
    "rangers": "new york rangers",
    "canadiens": "montreal canadiens",
    "habs": "montreal canadiens",
    "leafs": "toronto maple leafs",
    "maple leafs": "toronto maple leafs",
    "penguins": "pittsburgh penguins",
    "pens": "pittsburgh penguins",
    "blackhawks": "chicago blackhawks",
    "hawks": "chicago blackhawks",
    "red wings": "detroit red wings",
    "wings": "detroit red wings",
    "oilers": "edmonton oilers",
    "flames": "calgary flames",
    "canucks": "vancouver canucks",
    "sharks": "san jose sharks",
    "ducks": "anaheim ducks",
    "kings": "los angeles kings",
    "la kings": "los angeles kings",
    "lightning": "tampa bay lightning",
    "bolts": "tampa bay lightning",
    "panthers": "florida panthers",
    "hurricanes": "carolina hurricanes",
    "canes": "carolina hurricanes",
    "capitals": "washington capitals",
    "caps": "washington capitals",
    "flyers": "philadelphia flyers",
    "devils": "new jersey devils",
    "islanders": "new york islanders",
    "isles": "new york islanders",
    "sabres": "buffalo sabres",
    "senators": "ottawa senators",
    "sens": "ottawa senators",
    "jets": "winnipeg jets",
    "wild": "minnesota wild",
    "predators": "nashville predators",
    "preds": "nashville predators",
    "blues": "st louis blues",
    "stl blues": "st louis blues",
    "avalanche": "colorado avalanche",
    "avs": "colorado avalanche",
    "stars": "dallas stars",
    "coyotes": "arizona coyotes",
    "kraken": "seattle kraken",
    "golden knights": "vegas golden knights",
    "vgk": "vegas golden knights",
    "sf": "san francisco",
    "sf 49ers": "san francisco 49ers",
    "niners": "san francisco 49ers",
    "kc": "kansas city",
    "kc chiefs": "kansas city chiefs",
    "ne": "new england",
    "ne patriots": "new england patriots",
    "pats": "new england patriots",
    "gb": "green bay",
    "gb packers": "green bay packers",
    "pack": "green bay packers",
    "dal": "dallas",
    "dal cowboys": "dallas cowboys",
    "buf": "buffalo",
    "buf bills": "buffalo bills",
    "den": "denver",
    "den broncos": "denver broncos",
    "hou": "houston",
    "hou texans": "houston texans",
    "sea": "seattle",
    "sea seahawks": "seattle seahawks",
    "chi": "chicago",
    "chi bears": "chicago bears",
    "det": "detroit",
    "det lions": "detroit lions",
    "phi": "philadelphia",
    "phi eagles": "philadelphia eagles",
    "atl": "atlanta",
    "atl falcons": "atlanta falcons",
    "tb": "tampa bay",
    "tb bucs": "tampa bay buccaneers",
    "bucs": "tampa bay buccaneers",
    "la rams": "los angeles rams",
    "la chargers": "los angeles chargers",
    "lv": "las vegas",
    "lv raiders": "las vegas raiders",
    "nyg": "new york giants",
    "nyj": "new york jets",
    "min": "minnesota",
    "min vikings": "minnesota vikings",
    "vikes": "minnesota vikings",
    "car": "carolina",
    "car panthers": "carolina panthers",
    "no": "new orleans",
    "no saints": "new orleans saints",
    "ari": "arizona",
    "ari cardinals": "arizona cardinals",
    "ind": "indianapolis",
    "ind colts": "indianapolis colts",
    "jax": "jacksonville",
    "jax jaguars": "jacksonville jaguars",
    "jags": "jacksonville jaguars",
    "ten": "tennessee",
    "ten titans": "tennessee titans",
    "cin": "cincinnati",
    "cin bengals": "cincinnati bengals",
    "cle": "cleveland",
    "cle browns": "cleveland browns",
    "bal": "baltimore",
    "bal ravens": "baltimore ravens",
    "pit": "pittsburgh",
    "pit steelers": "pittsburgh steelers",
    "mia": "miami",
    "mia dolphins": "miami dolphins",
    "fins": "miami dolphins",
    "was": "washington",
    "was commanders": "washington commanders",
    "nyy": "new york yankees",
    "yanks": "new york yankees",
    "nym": "new york mets",
    "bos": "boston",
    "bos red sox": "boston red sox",
    "sox": "boston red sox",
    "lad": "los angeles dodgers",
    "dodgers": "los angeles dodgers",
    "chc": "chicago cubs",
    "cubs": "chicago cubs",
    "chw": "chicago white sox",
    "white sox": "chicago white sox",
    "hou astros": "houston astros",
    "stros": "houston astros",
    "atl braves": "atlanta braves",
    "phi phillies": "philadelphia phillies",
    "sd": "san diego",
    "sd padres": "san diego padres",
    "sf giants": "san francisco giants",
    "tex": "texas",
    "tex rangers": "texas rangers",
    "tor": "toronto",
    "tor blue jays": "toronto blue jays",
    "jays": "toronto blue jays",
    "sea mariners": "seattle mariners",
    "det tigers": "detroit tigers",
    "cle guardians": "cleveland guardians",
    "min twins": "minnesota twins",
    "kc royals": "kansas city royals",
    "oak": "oakland",
    "oak athletics": "oakland athletics",
    "bal orioles": "baltimore orioles",
    "tb rays": "tampa bay rays",
    "mia marlins": "miami marlins",
    "was nationals": "washington nationals",
    "nats": "washington nationals",
    "ari diamondbacks": "arizona diamondbacks",
    "dbacks": "arizona diamondbacks",
    "col": "colorado",
    "col rockies": "colorado rockies",
    "cin reds": "cincinnati reds",
    "mil": "milwaukee",
    "mil brewers": "milwaukee brewers",
    "pit pirates": "pittsburgh pirates",
    "stl": "st louis",
    "stl cardinals": "st louis cardinals",
    "cards": "st louis cardinals",
    "t1": "t1",
    "geng": "gen g",
    "gen.g": "gen g",
    "drx": "drx",
    "kt": "kt rolster",
    "hle": "hanwha life esports",
    "dk": "dplus kia",
    "damwon": "dplus kia",
    "dwg": "dplus kia",
    "fnc": "fnatic",
    "g2": "g2 esports",
    "mad": "mad lions",
    "rge": "rogue",
    "vit": "vitality",
    "c9": "cloud9",
    "tl": "team liquid",
    "eg": "evil geniuses",
    "100t": "100 thieves",
    "tsm": "tsm",
    "clg": "clg",
    "fly": "flyquest",
    "dig": "dignitas",
    "nrg": "nrg",
    "loud": "loud",
    "furia": "furia",
    "mibr": "mibr",
    "navi": "natus vincere",
    "na'vi": "natus vincere",
    "faze": "faze clan",
    "og": "og",
    "nigma": "nigma galaxy",
    "secret": "team secret",
    "spirit": "team spirit",
    "vp": "virtus pro",
    "virtuspro": "virtus pro",
}

SPORT_NORMALIZATIONS = {
    "football": "soccer",
    "futbol": "soccer",
    "fussball": "soccer",
    "calcio": "soccer",
    "nba": "basketball",
    "ncaa basketball": "basketball",
    "college basketball": "basketball",
    "nhl": "hockey",
    "ice hockey": "hockey",
    "nfl": "football_american",
    "american football": "football_american",
    "mlb": "baseball",
    "atp": "tennis",
    "wta": "tennis",
    "table tennis": "tennis",
    "lol": "esports",
    "league of legends": "esports",
    "dota": "esports",
    "dota2": "esports",
    "csgo": "esports",
    "cs2": "esports",
    "counter strike": "esports",
    "valorant": "esports",
    "overwatch": "esports",
}


def normalize_text(text: str) -> str:
    """Basic text normalization: lowercase, remove special chars."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def remove_noise_words(text: str) -> str:
    """Remove common noise words from text."""
    words = text.split()
    filtered = [w for w in words if w not in NOISE_WORDS]
    return ' '.join(filtered)


def apply_aliases(text: str) -> str:
    """Apply known team aliases to normalize names."""
    text_lower = text.lower().strip()
    if text_lower in TEAM_ALIASES:
        return TEAM_ALIASES[text_lower]
    for alias, canonical in TEAM_ALIASES.items():
        if alias in text_lower:
            text_lower = text_lower.replace(alias, canonical)
    return text_lower


def normalize_team_name(name: str) -> str:
    """Full normalization pipeline for a team name."""
    if not name:
        return ""
    normalized = normalize_text(name)
    normalized = apply_aliases(normalized)
    normalized = remove_noise_words(normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def normalize_sport(sport: str) -> str:
    """Normalize sport name to canonical form."""
    if not sport:
        return ""
    sport_lower = sport.lower().strip()
    return SPORT_NORMALIZATIONS.get(sport_lower, sport_lower)


def get_tokens(text: str) -> Set[str]:
    """Get set of tokens from normalized text."""
    if not text:
        return set()
    return set(text.split())


def get_ngrams(text: str, n: int = 2) -> Set[str]:
    """Get character n-grams from text."""
    if not text or len(text) < n:
        return set()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def token_similarity(tokens1: Set[str], tokens2: Set[str]) -> float:
    """Calculate Jaccard similarity between token sets."""
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def string_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity using SequenceMatcher."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1, s2).ratio()


def ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """Calculate n-gram similarity between strings."""
    ngrams1 = get_ngrams(s1, n)
    ngrams2 = get_ngrams(s2, n)
    return token_similarity(ngrams1, ngrams2)


def normalize_team_pair(team_a: str, team_b: str) -> Tuple[str, str]:
    """
    Normalize and sort team pair for order-invariant comparison.
    Returns (team1, team2) in alphabetical order.
    """
    norm_a = normalize_team_name(team_a)
    norm_b = normalize_team_name(team_b)
    return tuple(sorted([norm_a, norm_b]))


def calculate_match_score(
    team_a1: str, team_b1: str,
    team_a2: str, team_b2: str
) -> Tuple[float, str]:
    """
    Calculate overall match score between two team pairs.
    Returns (score, match_type) where match_type is 'direct' or 'swapped'.
    """
    norm_a1 = normalize_team_name(team_a1)
    norm_b1 = normalize_team_name(team_b1)
    norm_a2 = normalize_team_name(team_a2)
    norm_b2 = normalize_team_name(team_b2)
    
    direct_score_a = max(
        string_similarity(norm_a1, norm_a2),
        token_similarity(get_tokens(norm_a1), get_tokens(norm_a2)),
        ngram_similarity(norm_a1, norm_a2)
    )
    direct_score_b = max(
        string_similarity(norm_b1, norm_b2),
        token_similarity(get_tokens(norm_b1), get_tokens(norm_b2)),
        ngram_similarity(norm_b1, norm_b2)
    )
    direct_score = (direct_score_a + direct_score_b) / 2
    
    swapped_score_a = max(
        string_similarity(norm_a1, norm_b2),
        token_similarity(get_tokens(norm_a1), get_tokens(norm_b2)),
        ngram_similarity(norm_a1, norm_b2)
    )
    swapped_score_b = max(
        string_similarity(norm_b1, norm_a2),
        token_similarity(get_tokens(norm_b1), get_tokens(norm_a2)),
        ngram_similarity(norm_b1, norm_a2)
    )
    swapped_score = (swapped_score_a + swapped_score_b) / 2
    
    if direct_score >= swapped_score:
        return (direct_score, "direct")
    else:
        return (swapped_score, "swapped")


class NameNormalizer:
    """
    Name Normalizer class for team/event name normalization.
    Provides methods for normalizing and comparing team names.
    """
    
    def __init__(self):
        self.custom_aliases = {}
    
    def add_alias(self, alias: str, canonical: str):
        """Add a custom alias mapping."""
        self.custom_aliases[alias.lower()] = canonical.lower()
    
    def normalize_team(self, name: str) -> str:
        """Normalize a team name."""
        if not name:
            return ""
        normalized = normalize_text(name)
        if normalized in self.custom_aliases:
            normalized = self.custom_aliases[normalized]
        normalized = apply_aliases(normalized)
        normalized = remove_noise_words(normalized)
        return normalized.strip()
    
    def normalize_sport(self, sport: str) -> str:
        """Normalize a sport name."""
        return normalize_sport(sport)
    
    def get_normalized_pair(self, team_a: str, team_b: str) -> Tuple[str, str]:
        """Get normalized and sorted team pair."""
        norm_a = self.normalize_team(team_a)
        norm_b = self.normalize_team(team_b)
        return tuple(sorted([norm_a, norm_b]))
    
    def calculate_similarity(
        self,
        team_a1: str, team_b1: str,
        team_a2: str, team_b2: str
    ) -> Tuple[float, str]:
        """Calculate similarity score between two team pairs."""
        return calculate_match_score(team_a1, team_b1, team_a2, team_b2)
    
    def is_likely_match(
        self,
        team_a1: str, team_b1: str,
        team_a2: str, team_b2: str,
        threshold: float = 0.5
    ) -> bool:
        """Check if two team pairs are likely the same match."""
        score, _ = self.calculate_similarity(team_a1, team_b1, team_a2, team_b2)
        return score >= threshold


if __name__ == "__main__":
    normalizer = NameNormalizer()
    
    test_cases = [
        ("Manchester United FC", "Man Utd"),
        ("Paris Saint-Germain", "PSG"),
        ("Los Angeles Lakers", "LA Lakers"),
        ("Golden State Warriors", "GSW"),
        ("Tampa Bay Lightning", "TB Lightning"),
        ("Team Liquid", "TL"),
        ("Fnatic", "FNC"),
    ]
    
    print("=== Name Normalizer Test ===")
    for name1, name2 in test_cases:
        norm1 = normalizer.normalize_team(name1)
        norm2 = normalizer.normalize_team(name2)
        sim = string_similarity(norm1, norm2)
        print(f"{name1} -> {norm1}")
        print(f"{name2} -> {norm2}")
        print(f"Similarity: {sim:.2f}")
        print()
    
    print("=== Match Score Test ===")
    match_tests = [
        ("Cleveland Cavaliers", "Philadelphia 76ers", "Cavs", "Sixers"),
        ("San Francisco 49ers", "Seattle Seahawks", "SF", "SEA"),
        ("Real Madrid", "Barcelona", "Real", "Barca"),
    ]
    
    for a1, b1, a2, b2 in match_tests:
        score, match_type = normalizer.calculate_similarity(a1, b1, a2, b2)
        print(f"{a1} vs {b1} <-> {a2} vs {b2}")
        print(f"Score: {score:.2f}, Type: {match_type}")
        print()
