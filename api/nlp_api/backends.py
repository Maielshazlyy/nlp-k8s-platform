"""Pluggable inference backends.

`hf`   -> real Hugging Face transformer (used in the container image)
`mock` -> tiny lexicon model (used in unit tests and CI e2e, no torch needed)
"""
from __future__ import annotations

from typing import Protocol


class Backend(Protocol):
    name: str

    def predict(self, texts: list[str]) -> list[dict]: ...


class MockBackend:
    name = "mock-lexicon"
    _POS = {"good", "great", "love", "excellent", "amazing", "happy", "wonderful", "best", "nice"}
    _NEG = {"bad", "terrible", "hate", "awful", "worst", "sad", "poor", "horrible", "slow"}

    def predict(self, texts: list[str]) -> list[dict]:
        out = []
        for t in texts:
            words = {w.strip(".,!?").lower() for w in t.split()}
            score = len(words & self._POS) - len(words & self._NEG)
            label = "positive" if score >= 0 else "negative"
            out.append({"label": label, "score": round(min(0.99, 0.6 + 0.1 * abs(score)), 4)})
        return out


class HFBackend:
    def __init__(self, model_name: str) -> None:
        from transformers import pipeline  # imported lazily: heavy

        self.name = model_name
        self._pipe = pipeline("sentiment-analysis", model=model_name, device=-1)

    def predict(self, texts: list[str]) -> list[dict]:
        res = self._pipe(texts, truncation=True, max_length=256)
        return [{"label": r["label"].lower(), "score": round(float(r["score"]), 4)} for r in res]


def load_backend(kind: str, model_name: str) -> Backend:
    if kind == "mock":
        return MockBackend()
    if kind == "hf":
        return HFBackend(model_name)
    raise ValueError(f"unknown MODEL_BACKEND: {kind!r}")
