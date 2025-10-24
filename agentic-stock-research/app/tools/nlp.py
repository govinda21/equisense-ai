from __future__ import annotations

from typing import List
import json
import http.client
from urllib.parse import urlparse

from app.config import get_settings

try:
    from transformers import pipeline  # type: ignore
except Exception:
    pipeline = None  # type: ignore


def _ollama_chat(prompt: str) -> str:
    settings = get_settings()
    if settings.llm_provider.lower() != "ollama":
        return ""
    try:
        u = urlparse(settings.ollama_base_url)
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=30)
        body = json.dumps({
            "model": settings.ollama_model, 
            "prompt": prompt, 
            "stream": False,
            "options": {
                "num_predict": 1000,  # Limit response length
                "temperature": 0.1,   # More deterministic
                "top_p": 0.9
            }
        })
        conn.request("POST", "/api/generate", body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        
        if resp.status != 200:
            print(f"Ollama API error: {resp.status} - {resp.reason}")
            return ""
            
        # Get non-streaming response
        content = resp.read().decode("utf-8")
        try:
            # Parse single JSON response
            data = json.loads(content)
            return data.get("response", "")
        except Exception:
            # If streaming response, parse each line and combine
            lines = content.strip().split('\n')
            full_response = ""
            for line in lines:
                try:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        full_response += chunk["response"]
                except Exception:
                    continue
            return full_response if full_response else content
    except ConnectionRefusedError:
        print("Ollama connection refused - Ollama server not running")
        return ""
    except Exception as e:
        print(f"Ollama error: {e}")
        return ""


async def summarize_texts(texts: List[str], max_words: int = 120) -> str:
    if not texts:
        return ""
    # Prefer Ollama if configured (offload blocking IO)
    import asyncio
    res = await asyncio.to_thread(
        _ollama_chat,
        "Summarize the following bullet list of finance headlines in one paragraph, reflecting the overall sentiment:\n- "
        + "\n- ".join(texts),
    )
    if res:
        return res[: max_words * 6]
    if pipeline is None:
        return "; ".join(texts)[: max_words * 6]
    import asyncio

    def _summ() -> str:
        try:
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
            res = summarizer("\n".join(texts), max_length=180, min_length=60, do_sample=False)
            return res[0]["summary_text"]
        except Exception:
            return "; ".join(texts)[: max_words * 6]

    return await asyncio.to_thread(_summ)


async def sentiment_score(texts: List[str]) -> float:
    if not texts:
        return 0.5
    # Try Ollama first: ask for a 0-1 normalized score (offload blocking IO)
    import asyncio
    res = await asyncio.to_thread(
        _ollama_chat,
        "On a scale from 0 (very negative) to 1 (very positive), provide a single numeric sentiment score for: "
        + "; ".join(texts)
        + ". Only return the number.",
    )
    if res:
        try:
            val = float(res.strip().split()[0])
            return max(0.0, min(1.0, val))
        except Exception:
            pass
    if pipeline is None:
        return 0.5
    import asyncio

    def _sent() -> float:
        try:
            clf = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")
            results = clf(texts)
            scores = [r.get("score", 0.5) * (1 if r.get("label", "POSITIVE").upper().startswith("POS") else -1) for r in results]
            val = (sum(scores) / max(len(scores), 1) + 1.0) / 2.0
            return max(0.0, min(1.0, val))
        except Exception:
            return 0.5

    return await asyncio.to_thread(_sent)
