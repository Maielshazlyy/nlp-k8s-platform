from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP latency", ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
INFERENCE_LATENCY = Histogram(
    "nlp_inference_duration_seconds", "Model inference time per batch",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
CACHE_HITS = Counter("nlp_cache_hits_total", "Cache hits")
CACHE_MISSES = Counter("nlp_cache_misses_total", "Cache misses")
INFLIGHT = Gauge("nlp_inflight_inferences", "Inferences currently running")
MODEL_READY = Gauge("nlp_model_ready", "1 when model is loaded")
