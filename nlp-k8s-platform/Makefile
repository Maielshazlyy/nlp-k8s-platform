IMAGE      ?= nlp-api
TAG        ?= dev
KUSTOMIZE  ?= kubectl kustomize
.DEFAULT_GOAL := help

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

test: ## Run unit tests + lint
	cd api && pip install -q -r requirements-dev.txt && ruff check . && pytest -q

build: ## Build the production image (model weights baked in)
	docker build -t $(IMAGE):$(TAG) api

build-slim: ## Build the slim image (no torch), use with MODEL_BACKEND=mock
	docker build --build-arg WITH_ML=false -t $(IMAGE):$(TAG) api

cluster: ## Create kind cluster + ingress-nginx
	kind create cluster --config kind/kind-config.yaml
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml
	kubectl -n ingress-nginx wait --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=180s

load: ## Load the image into kind
	kind load docker-image $(IMAGE):$(TAG) --name nlp

deploy: ## Deploy the dev overlay
	kubectl apply -k k8s/overlays/dev
	kubectl -n nlp rollout status deploy/nlp-api --timeout=300s

render: ## Render prod manifests
	$(KUSTOMIZE) k8s/overlays/prod

validate: ## Schema-validate all overlays with kubeconform
	for o in dev ci prod; do $(KUSTOMIZE) k8s/overlays/$$o | kubeconform -strict -summary -ignore-missing-schemas -; done

smoke: ## End-to-end smoke test through the ingress
	./scripts/smoke-test.sh

loadtest: ## Generate load with k6 and watch the HPA
	k6 run tests/load/k6.js & kubectl -n nlp get hpa -w

clean: ## Delete the kind cluster
	kind delete cluster --name nlp

.PHONY: help test build build-slim cluster load deploy render validate smoke loadtest clean
