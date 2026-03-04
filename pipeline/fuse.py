"""
Emotion Fusion — Extract and fuse emotional signals from transcript and visuals.

Features:
  - Multi-word phrase detection with confidence scoring
  - Negation-aware parsing ("not surprised" ≠ "surprised")
  - Intensifier boosting ("very surprised" > "surprised")
  - Visual emotion cues from frame captions
  - Combined emotion intensity scoring
"""

from __future__ import annotations


# ── Emotion Keyword Map (single-word, with confidence) ──────────────────────
EMOTION_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "surprise": [
        ("shocked", 0.95), ("stunned", 0.90), ("astonished", 0.90),
        ("wow", 0.70), ("really", 0.50), ("seriously", 0.60),
        ("what", 0.40), ("whoa", 0.75),
    ],
    "laughter": [
        ("haha", 0.90), ("lol", 0.85), ("laugh", 0.80),
        ("funny", 0.75), ("hilarious", 0.90), ("chuckle", 0.70),
        ("giggle", 0.70),
    ],
    "concern": [
        ("worried", 0.80), ("concerned", 0.80), ("anxious", 0.75),
        ("expensive", 0.60), ("problem", 0.55), ("issue", 0.50),
    ],
    "disbelief": [
        ("impossible", 0.85), ("ridiculous", 0.80), ("insane", 0.95),
        ("unbelievable", 0.90),
    ],
    "agreement": [
        ("yes", 0.50), ("exactly", 0.70), ("right", 0.40),
        ("agree", 0.75), ("absolutely", 0.80), ("correct", 0.65),
    ],
    "disagreement": [
        ("wrong", 0.70), ("disagree", 0.80), ("false", 0.65),
    ],
}


# ── Multi-word Phrases (higher priority, checked first) ─────────────────────
EMOTION_PHRASES: dict[str, list[tuple[str, float]]] = {
    "surprise": [
        ("are you kidding me", 0.95),
        ("you're joking", 0.90),
        ("i can't believe", 0.95),
        ("holy shit", 0.98),
        ("oh my god", 0.90),
        ("what the fuck", 0.95),
        ("no way", 0.85),
        ("are you sure", 0.70),
    ],
    "disbelief": [
        ("no fucking way", 0.98),
        ("that's insane", 0.95),
        ("can't believe", 0.90),
    ],
    "laughter": [
        ("cracked up", 0.90),
        ("burst out laughing", 0.95),
    ],
}


# ── Negation Patterns ───────────────────────────────────────────────────────
NEGATION_PATTERNS = frozenset([
    "not", "never", "don't", "doesn't", "didn't", "won't",
    "isn't", "aren't", "wasn't", "weren't", "no", "neither",
    "hardly", "barely", "scarcely",
])


# ── Intensifiers ────────────────────────────────────────────────────────────
INTENSIFIERS: dict[str, float] = {
    "very": 1.3,
    "extremely": 1.5,
    "really": 1.2,
    "so": 1.2,
    "absolutely": 1.4,
    "incredibly": 1.5,
    "fucking": 1.4,
    "quite": 1.1,
    "super": 1.3,
    "pretty": 1.1,
}


# ── Visual Emotion Cues ────────────────────────────────────────────────────
VISUAL_CUES: dict[str, float] = {
    "laughing": 0.95,
    "smiling": 0.80,
    "grinning": 0.85,
    "surprised expression": 0.90,
    "shocked": 0.95,
    "wide eyes": 0.85,
    "frowning": 0.80,
    "confused": 0.70,
    "raised eyebrows": 0.70,
    "crying": 0.90,
    "animated": 0.60,
}


# ── Main Extraction Function ───────────────────────────────────────────────
def extract_emotion_signals(
    transcript: str,
    visual_captions: list[str] | None = None,
) -> dict:
    """
    Extract emotional signals from transcript text and visual captions.

    Returns
    -------
    dict with keys:
        detected_emotions : list[str]
        emotion_scores : dict[str, float]
        visual_emotions : list[str]
        visual_scores : dict[str, float]
        emotion_intensity : float
        avg_emotion_confidence : float
    """
    text = transcript.lower()
    words = text.split()

    emotion_scores: dict[str, float] = {}

    # ── Phase 1: Multi-word phrases (highest priority) ──────────────────
    for emotion, phrases in EMOTION_PHRASES.items():
        for phrase, confidence in phrases:
            if phrase in text:
                # Check for negation within 3 words before the phrase
                phrase_pos = text.find(phrase)
                before_text = text[max(0, phrase_pos - 30):phrase_pos]
                before_words = before_text.split()[-3:]
                is_negated = any(w in NEGATION_PATTERNS for w in before_words)

                if not is_negated:
                    emotion_scores[emotion] = max(
                        emotion_scores.get(emotion, 0),
                        confidence,
                    )

    # ── Phase 2: Single-word keywords with negation + intensifiers ──────
    for i, word in enumerate(words):
        # Check if this word is an emotion keyword
        for emotion, keywords in EMOTION_KEYWORDS.items():
            for keyword, base_conf in keywords:
                if word == keyword or (len(keyword) > 4 and keyword in word):
                    # Check negation: look back 3 words
                    context = words[max(0, i - 3):i]
                    is_negated = any(w in NEGATION_PATTERNS for w in context)

                    if is_negated:
                        continue

                    # Check intensifier: look back 2 words
                    conf = base_conf
                    intensifier_context = words[max(0, i - 2):i]
                    for ic_word in intensifier_context:
                        if ic_word in INTENSIFIERS:
                            conf = min(1.0, conf * INTENSIFIERS[ic_word])

                    emotion_scores[emotion] = max(
                        emotion_scores.get(emotion, 0),
                        conf,
                    )

    # ── Phase 3: Visual emotion cues ────────────────────────────────────
    visual_emotions: list[str] = []
    visual_scores: dict[str, float] = {}

    if visual_captions:
        combined_visual = " ".join(visual_captions).lower()
        for cue, confidence in VISUAL_CUES.items():
            if cue in combined_visual:
                visual_emotions.append(cue)
                visual_scores[cue] = confidence

    # ── Aggregate ───────────────────────────────────────────────────────
    detected_emotions = list(emotion_scores.keys())

    all_scores = list(emotion_scores.values()) + list(visual_scores.values())
    emotion_intensity = round(sum(all_scores), 2) if all_scores else 0
    avg_confidence = round(
        sum(all_scores) / len(all_scores), 3
    ) if all_scores else 0

    return {
        "detected_emotions": detected_emotions,
        "emotion_scores": emotion_scores,
        "visual_emotions": visual_emotions,
        "visual_scores": visual_scores,
        "emotion_intensity": emotion_intensity,
        "avg_emotion_confidence": avg_confidence,
    }
