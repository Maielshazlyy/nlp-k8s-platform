from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from . import __version__, metrics
from .backends import load_backend
from .cache import build_cache

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("nlp_api")


class Settings:
    backend = os.getenv("MODEL_BACKEND", "hf")
    model_name = os.getenv("MODEL_NAME", "distilbert-base-uncased-finetuned-sst-2-english")
    redis_url = os.getenv("REDIS_URL", "")
    cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    max_concurrent = int(os.getenv("MAX_CONCURRENT_INFERENCES", "2"))


class SentimentRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)


class SentimentItem(BaseModel):
    label: str
    score: float
    cached: bool


class SentimentResponse(BaseModel):
    model: str
    results: list[SentimentItem]
    latency_ms: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ready = False
    app.state.sem = asyncio.Semaphore(Settings.max_concurrent)
    if not hasattr(app.state, "cache"):
        app.state.cache = build_cache(Settings.redis_url)
    log.info("loading model backend=%s model=%s", Settings.backend, Settings.model_name)
    # model load is blocking + slow: keep it off the event loop so /healthz stays live
    app.state.backend = await asyncio.to_thread(load_backend, Settings.backend, Settings.model_name)
    app.state.ready = True
    metrics.MODEL_READY.set(1)
    log.info("model ready")
    yield
    metrics.MODEL_READY.set(0)
    app.state.ready = False
    await app.state.cache.close()


app = FastAPI(title="NLP Inference API", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route != "/metrics":
            metrics.HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            metrics.HTTP_LATENCY.labels(route).observe(time.perf_counter() - start)


def _key(model: str, text: str) -> str:
    return "sent:" + hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "alive"}


@app.get("/readyz", include_in_schema=False)
async def readyz():
    if not getattr(app.state, "ready", False):
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ready", "model": app.state.backend.name, "version": __version__}


@app.get("/metrics", include_in_schema=False)
async def prometheus():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/sentiment", response_model=SentimentResponse)
async def sentiment(req: SentimentRequest):
    if not app.state.ready:
        raise HTTPException(status_code=503, detail="model not loaded")
    if any(len(t) > 2000 for t in req.texts):
        raise HTTPException(status_code=422, detail="text longer than 2000 chars")

    start = time.perf_counter()
    backend = app.state.backend
    keys = [_key(backend.name, t) for t in req.texts]
    cached = await app.state.cache.get_many(keys)

    misses = [i for i, c in enumerate(cached) if c is None]
    metrics.CACHE_HITS.inc(len(cached) - len(misses))
    metrics.CACHE_MISSES.inc(len(misses))

    fresh: dict[int, dict] = {}
    if misses:
        async with app.state.sem:
            metrics.INFLIGHT.inc()
            t0 = time.perf_counter()
            try:
                preds = await asyncio.to_thread(backend.predict, [req.texts[i] for i in misses])
            finally:
                metrics.INFLIGHT.dec()
                metrics.INFERENCE_LATENCY.observe(time.perf_counter() - t0)
        fresh = dict(zip(misses, preds, strict=True))
        await app.state.cache.set_many({keys[i]: p for i, p in fresh.items()}, Settings.cache_ttl)

    results = [
        SentimentItem(**(fresh[i] if i in fresh else cached[i]), cached=i not in fresh)
        for i in range(len(req.texts))
    ]
    return SentimentResponse(
        model=backend.name, results=results, latency_ms=round((time.perf_counter() - start) * 1000, 2)
    )
