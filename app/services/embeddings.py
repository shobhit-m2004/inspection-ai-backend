import os
import math
import random
from typing import List
import requests

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")


def _local_embedding(text: str) -> List[float]:
    # Deterministic hash-based fallback for offline demos
    seed = sum(ord(c) for c in text) % 100000
    rnd = random.Random(seed)
    vec = [rnd.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]
    # Normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> List[float]:
    if not GEMINI_API_KEY:
        return _local_embedding(text)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_EMBED_MODEL}:embedContent"
        f"?key={GEMINI_API_KEY}"
    )
    payload = {"content": {"parts": [{"text": text[:8000]}]}}
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        # Fail closed to local embedding for demo continuity
        return _local_embedding(text)

    data = resp.json()
    values = data.get("embedding", {}).get("values", [])
    if not values:
        return _local_embedding(text)

    return values