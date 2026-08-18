import re
from typing import Iterable, List

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "had", "has", "have", "he", "her", "his", "i", "if", "in", "into", "is",
    "it", "its", "of", "on", "or", "she", "that", "the", "their", "them",
    "they", "this", "to", "was", "were", "will", "with", "you", "your",
    "we", "our", "us", "what", "when", "where", "why", "who", "how", "do",
    "does", "did", "than", "then", "there", "about", "after", "before",
    "again", "against", "because", "between", "during", "over", "under",
    "without", "through", "while", "should", "could", "would", "can't",
    "cannot", "n't", "not"
}

_TRANSLATIONS = {
    "hi": {
        "hello": "नमस्ते", "world": "दुनिया", "love": "प्यार", "family": "परिवार",
        "happy": "खुश", "sad": "उदास", "friend": "दोस्त", "water": "पानी",
        "food": "भोजन", "home": "घर", "time": "समय", "day": "दिन", "night": "रात",
        "music": "संगीत", "voice": "आवाज़", "language": "भाषा", "story": "कहानी"
    },
    "es": {
        "hello": "hola", "world": "mundo", "love": "amor", "family": "familia",
        "happy": "feliz", "sad": "triste", "friend": "amigo", "water": "agua",
        "food": "comida", "home": "hogar", "time": "tiempo", "day": "día",
        "night": "noche", "music": "música", "voice": "voz", "language": "idioma",
        "story": "historia"
    },
    "fr": {
        "hello": "bonjour", "world": "monde", "love": "amour", "family": "famille",
        "happy": "heureux", "sad": "triste", "friend": "ami", "water": "eau",
        "food": "nourriture", "home": "maison", "time": "temps", "day": "jour",
        "night": "nuit", "music": "musique", "voice": "voix", "language": "langue",
        "story": "histoire"
    },
    "de": {
        "hello": "hallo", "world": "welt", "love": "liebe", "family": "familie",
        "happy": "glücklich", "sad": "traurig", "friend": "freund", "water": "wasser",
        "food": "essen", "home": "heim", "time": "zeit", "day": "tag",
        "night": "nacht", "music": "musik", "voice": "stimme", "language": "sprache",
        "story": "geschichte"
    },
    "it": {
        "hello": "ciao", "world": "mondo", "love": "amore", "family": "famiglia",
        "happy": "felice", "sad": "triste", "friend": "amico", "water": "acqua",
        "food": "cibo", "home": "casa", "time": "tempo", "day": "giorno",
        "night": "notte", "music": "musica", "voice": "voce", "language": "lingua",
        "story": "storia"
    },
    "pt": {
        "hello": "olá", "world": "mundo", "love": "amor", "family": "família",
        "happy": "feliz", "sad": "triste", "friend": "amigo", "water": "água",
        "food": "comida", "home": "casa", "time": "tempo", "day": "dia",
        "night": "noite", "music": "música", "voice": "voz", "language": "idioma",
        "story": "história"
    },
    "ja": {
        "hello": "こんにちは", "world": "世界", "love": "愛", "family": "家族",
        "happy": "幸せ", "sad": "悲しい", "friend": "友達", "water": "水",
        "food": "食べ物", "home": "家", "time": "時間", "day": "日", "night": "夜",
        "music": "音楽", "voice": "声", "language": "言語", "story": "物語"
    },
    "ko": {
        "hello": "안녕하세요", "world": "세계", "love": "사랑", "family": "가족",
        "happy": "행복", "sad": "슬픔", "friend": "친구", "water": "물",
        "food": "음식", "home": "집", "time": "시간", "day": "날", "night": "밤",
        "music": "음악", "voice": "목소리", "language": "언어", "story": "이야기"
    },
    "ar": {
        "hello": "مرحبا", "world": "العالم", "love": "حب", "family": "عائلة",
        "happy": "سعيد", "sad": "حزين", "friend": "صديق", "water": "ماء",
        "food": "طعام", "home": "منزل", "time": "وقت", "day": "يوم", "night": "ليل",
        "music": "موسيقى", "voice": "صوت", "language": "لغة", "story": "قصة"
    }
}


def extract_keywords(text: str) -> List[str]:
    if not text:
        return []
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+", text.lower())
    keywords: List[str] = []
    seen = set()

    for word in words:
        cleaned = word.strip("'")
        if len(cleaned) < 2 or cleaned in _STOPWORDS:
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            keywords.append(cleaned)

    return keywords


def translate_keywords(keywords: Iterable[str], target_language: str) -> List[str]:
    if not keywords:
        return []

    normalized = str(target_language or "en").lower().strip()
    language_map = _TRANSLATIONS.get(normalized, {})
    translated: List[str] = []
    seen = set()

    for keyword in keywords:
        key = str(keyword).strip().lower()
        if not key:
            continue
        translated_word = language_map.get(key, key)
        if translated_word not in seen:
            seen.add(translated_word)
            translated.append(str(translated_word))

    return translated
