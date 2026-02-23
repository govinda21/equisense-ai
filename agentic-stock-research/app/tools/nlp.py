"""
NLP utilities: text summarization and sentiment scoring.
Uses Ollama (if configured) → HuggingFace transformers → plain-text fallback.
"""
from __future__ import annotations

import asyncio
import http.client
import json
from typing import List
from urllib.parse import urlparse

from app.config import get_settings

try:
    from transformers import pipeline as hf_pipeline  # type: ignore
except Exception:
    hf_pipeline = None


# ---------- Ollama helper ----------

def _ollama(prompt: str) -> str:
    """Send a prompt to a local Ollama server; return raw text or empty string."""
    s = get_settings()
    if s.llm_provider.lower() != "ollama":
        return ""
    try:
        u = urlparse(s.ollama_base_url)
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=30)
        body = json.dumps({
            "model": s.ollama_model, "prompt": prompt, "stream": False,
            "options": {"num_predict": 1000, "temperature": 0.1, "top_p": 0.9},
        })
        conn.request("POST", "/api/generate", body, {"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status_code != 200:
            return ""
        content = resp.read().decode()
        # Handle both single-object and streaming-line responses
        try:
            return json.loads(content).get("response", "")
        except Exception:
            return "".join(
                chunk.get("response", "")
                for line in content.strip().split("\n")
                for chunk in [json.loads(line)]
                if "response" in chunk
            )
    except ConnectionRefusedError:
        return ""
    except Exception as e:
        print(f"Ollama error: {e}")
        return ""


# ---------- public functions ----------

async def summarize_texts(texts: List[str], max_words: int = 120) -> str:
    """
    Summarise a list of headlines/text snippets into one paragraph.
    Falls back: Ollama → BART → join with semicolons.
    """
    if not texts:
        return ""

    prompt = ("Summarize the following bullet list of finance headlines in one paragraph, "
              "reflecting the overall sentiment:\n- " + "\n- ".join(texts))
    result = await asyncio.to_thread(_ollama, prompt)
    if result:
        return result[:max_words * 6]

    if hf_pipeline is None:
        return "; ".join(texts)[:max_words * 6]

    def _bart() -> str:
        try:
            summarizer = hf_pipeline("summarization", model="facebook/bart-large-cnn")
            out = summarizer("\n".join(texts), max_length=180, min_length=60, do_sample=False)
            return out[0]["summary_text"]
        except Exception:
            return "; ".join(texts)[:max_words * 6]

    return await asyncio.to_thread(_bart)


async def sentiment_score(texts: List[str]) -> float:
    """
    Return a 0–1 sentiment score for a list of text snippets (0 = negative, 1 = positive).
    Falls back: Ollama → RoBERTa → 0.5 neutral.
    """
    if not texts:
        return 0.5

    prompt = ("On a scale from 0 (very negative) to 1 (very positive), provide a single "
              "numeric sentiment score for: " + "; ".join(texts) + ". Only return the number.")
    result = await asyncio.to_thread(_ollama, prompt)
    if result:
        try:
            return max(0.0, min(1.0, float(result.strip().split()[0])))
        except Exception:
            pass

    if hf_pipeline is None:
        return 0.5

    def _roberta() -> float:
        try:
            clf = hf_pipeline("sentiment-analysis",
                               model="cardiffnlp/twitter-roberta-base-sentiment-latest")
            scores = [
                r["score"] * (1 if r.get("label", "").upper().startswith("POS") else -1)
                for r in clf(texts)
            ]
            return max(0.0, min(1.0, (sum(scores) / len(scores) + 1.0) / 2.0))
        except Exception:
            return 0.5

    return await asyncio.to_thread(_roberta)
