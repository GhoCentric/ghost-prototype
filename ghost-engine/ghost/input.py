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


def _normalize_numeric_text(text: str) -> str:
    """
    Normalize spacing and punctuation without translating digits.

    General text normalization intentionally supports leetspeak,
    including digit-to-letter replacements. Numeric extraction must
    preserve literal integer tokens such as ``20`` and ``50``.
    """

    raw = (text or "").lower().strip()
    cleaned = []

    for character in raw:
        if character.isalnum() or character.isspace():
            cleaned.append(character)
        else:
            cleaned.append(" ")

    return " ".join("".join(cleaned).split())


def extract_mentioned_number(text: str):
    """
    Return the first literal integer found in text.

    Returns None if no integer is found.
    """

    raw = _normalize_numeric_text(text)

    for word in raw.split():
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

    raw = _normalize_numeric_text(text)

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

    for index, word in enumerate(words):
        if not word.isdigit():
            continue

        value = int(word)

        previous_word = (
            words[index - 1]
            if index > 0
            else ""
        )
        next_word = (
            words[index + 1]
            if index + 1 < len(words)
            else ""
        )

        if next_word in money_words:
            return value

        if previous_word in price_context:
            return value

    return None
