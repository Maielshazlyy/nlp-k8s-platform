# syntax=docker/dockerfile:1.7
# WITH_ML=true  -> production image, model weights baked in (no runtime download, offline-safe)
# WITH_ML=false -> slim image used by CI e2e together with MODEL_BACKEND=mock

FROM python:3.11-slim AS builder
ARG WITH_ML=true
ARG MODEL_NAME=distilbert-base-uncased-finetuned-sst-2-english
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/models
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt \
 && if [ "$WITH_ML" = "true" ]; then pip install -r requirements-ml.txt; fi
RUN mkdir -p /models && if [ "$WITH_ML" = "true" ]; then \
      python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='${MODEL_NAME}')"; fi

FROM python:3.11-slim
ARG WITH_ML=true
LABEL org.opencontainers.image.source="https://github.com/OWNER/nlp-k8s-platform" \
      org.opencontainers.image.description="NLP sentiment inference API"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /models /models
WORKDIR /srv
COPY nlp_api ./nlp_api
ENV PATH=/opt/venv/bin:$PATH HF_HOME=/models PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8080
CMD ["uvicorn", "nlp_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
