# Mission 006 — FastAPI + Redis + Ingress platform

## Goal
Build and troubleshoot a production-style FastAPI service with Redis, Kubernetes Services and EndpointSlices, local Ingress, GitHub Actions CI/CD, and a later AWS EKS + ALB architecture mapping.

## Lab environment
- Windows PowerShell and WSL2
- kind cluster: `kind-prod-sim`
- Kubernetes v1.37.0; one control-plane node and three workers
- Temporary namespace: `mission-006`

## Verified checkpoints (2026-11-14)
1. **Cluster context:** `kind-prod-sim`; all four nodes reported `Ready`.
2. **Namespace:** `kubectl create namespace mission-006` returned `namespace/mission-006 created`; `kubectl get namespace mission-006` showed `Active`.
3. **Local FastAPI:** User confirmed `GET /health/live` returns `alive` and `GET /health/ready` returns `ready`. Exact terminal output not captured.

## Architecture decision
Keep FastAPI process health and readiness separate from optional Redis dependency health. An unavailable Redis cache should not automatically make all FastAPI Pods unready if useful fallback behavior is possible. Add a separate dependency diagnostic endpoint later and explicitly test degraded-mode behavior.

## In progress
Checkpoint 004: build a non-root FastAPI container and verify the image locally. Docker build and runtime results **not yet provided**.

## Next stages
- Container test and kind image load
- FastAPI Deployment and ClusterIP Service
- Redis Deployment and internal Service, DNS, connection resilience
- Ingress routing and failure simulations
- GitHub Actions delivery pipeline
- AWS EKS, ALB controller, IAM/OIDC, DNS/TLS architecture mapping
- Evidence, interview tradeoffs, namespace cleanup

> This document records only reported/observed results. No Kubernetes workload, Redis integration, Ingress, or AWS deployment has yet been verified.
