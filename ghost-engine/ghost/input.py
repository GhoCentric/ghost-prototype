"""
Deterministic input utilities for Ghost.

This module does not use AI.
It does not decide dialogue.
It only normalizes and extracts small public signals from text.
"""


def normalize_text(text: str) -> str:
    """
    Normalize text for deterministic matching.

    This is intentionally simple and dependency-free.
    """
    t = (text or "").lower().strip()

    replacements = {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
    }

    for old, new in replacements.items():
        t = t.replace(old, new)

    cleaned = []

    for ch in t:
        if ch.isalnum() or ch.isspace():
            cleaned.append(ch)
        else:
            cleaned.append(" ")

    t = " ".join("".join(cleaned).split())

    typo_fixes = {
        "pkease": "please",
        "pleas": "please",
        "plese": "please",
        "plz": "please",
        "pls": "please",
        "takwe": "take",
        "coina": "coins",
        "buisness": "business",
        "valuble": "valuable",
        "juat": "just",
    }

    words = []

    for word in t.split():
        words.append(typo_fixes.get(word, word))

    return " ".join(words)


def contains_any(text: str, terms) -> bool:
    t = normalize_text(text)

    return any(term in t for term in terms)


def extract_mentioned_number(text: str):
    """
    Returns the first integer found in text.
    Returns None if no integer is found.
    """
    t = normalize_text(text)

    for word in t.split():
        if word.isdigit():
            return int(word)

    return None


def extract_mentioned_gold_price(text: str):
    """
    Extract a numeric gold / coin price from player text.

    Examples:
    - "I'll buy it for 20 gold" -> 20
    - "20 gold" -> 20
    - "pay 50 coins" -> 50
    """
    raw = normalize_text(text)

    if not raw:
        return None

    words = raw.split()

    money_words = ("gold", "coin", "coins")
    price_context = (
        "for",
        "at",
        "pay",
        "paid",
        "price",
        "cost",
        "buy",
        "purchase",
        "trade",
    )

    for i, word in enumerate(words):
        if not word.isdigit():
            continue

        value = int(word)

        prev_word = words[i - 1] if i > 0 else ""
        next_word = words[i + 1] if i + 1 < len(words) else ""

        if next_word in money_words:
            return value

        if prev_word in price_context:
            return value

        if prev_word in price_context and next_word in money_words:
            return value

    return None
