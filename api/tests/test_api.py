import os

os.environ["MODEL_BACKEND"] = "mock"

import pytest
from fastapi.testclient import TestClient

from nlp_api.cache import DictCache
from nlp_api.main import app


@pytest.fixture()
def client():
    app.state.cache = DictCache()
    with TestClient(app) as c:
        yield c


def test_health_and_ready(client):
    assert client.get("/healthz").status_code == 200
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_sentiment_labels(client):
    r = client.post("/v1/sentiment", json={"texts": ["I love this, great!", "This is terrible and slow"]})
    assert r.status_code == 200
    labels = [x["label"] for x in r.json()["results"]]
    assert labels == ["positive", "negative"]


def test_second_call_is_cached(client):
    body = {"texts": ["amazing work"]}
    assert client.post("/v1/sentiment", json=body).json()["results"][0]["cached"] is False
    assert client.post("/v1/sentiment", json=body).json()["results"][0]["cached"] is True


def test_validation(client):
    assert client.post("/v1/sentiment", json={"texts": []}).status_code == 422
    assert client.post("/v1/sentiment", json={"texts": ["x" * 2001]}).status_code == 422


def test_metrics_exposed(client):
    client.post("/v1/sentiment", json={"texts": ["nice"]})
    body = client.get("/metrics").text
    assert "nlp_inference_duration_seconds" in body and "http_requests_total" in body
