# Mission 005 — Readiness probe failure, stalled rollout and roll-forward recovery

**Date:** 2026-11-14  
**Environment:** Windows PowerShell, kind cluster `kind-prod-sim` (Kubernetes v1.37.0), namespace `mission-005`  
**Workload:** `payment-api` (lab simulation using `nginx:alpine`), desired replicas: 2

> Evidence is based on terminal output supplied during the hands-on lab. Production customer traffic and real GitHub Actions deployment were **not** part of this simulation.

## Incident scenario

A Deployment changes its Pod template to include a readiness probe at `/health/ready`, but the NGINX container serves `/`. The newly created container runs, yet readiness fails with HTTP 404. Kubernetes retains the two healthy old Pods during the stalled rolling update.

### 1. Healthy baseline — observed

```text
deployment.apps/payment-api   2/2   2   2
replicaset.apps/payment-api-94b9b79b6   2   2   2
pod/payment-api-94b9b79b6-jm6mg   1/1   Running   0
pod/payment-api-94b9b79b6-t9mr7   1/1   Running   0
```

Created with `kubectl create deployment payment-api --image=nginx:alpine --replicas=2 -n mission-005`. `kubectl rollout status` reported a successful rollout.

### 2. Introduce faulty readiness configuration

The initial inline `kubectl patch -p` command from PowerShell failed with `Error from server (BadRequest): invalid JSON patch`. We used a JSON patch file and `kubectl patch --type=strategic --patch-file` instead (see `broken-readiness-patch.json`).

**Observed during failing rollout:**

```text
deployment.apps/payment-api   2/2   1   2
replicaset.apps/payment-api-65c8ddcd8   1   1   0
replicaset.apps/payment-api-94b9b79b6   2   2   2
pod/payment-api-65c8ddcd8-gxnw9   0/1   Running   0
pod/payment-api-94b9b79b6-jm6mg   1/1   Running   0
pod/payment-api-94b9b79b6-t9mr7   1/1   Running   0
```

The default RollingUpdate settings for two replicas allow an additional Pod (25% `maxSurge` rounds up to one) and require zero desired replicas to be unavailable (25% `maxUnavailable` rounds down to zero). Kubernetes therefore keeps the old healthy Pods until replacements can become available.

### 3. Root-cause evidence — observed

`kubectl describe pod payment-api-65c8ddcd8-gxnw9 -n mission-005` showed:

```text
Node:         prod-sim-worker2/172.18.0.3
Status:       Running
Container:    nginx
Image:        nginx:alpine
State:        Running
Ready:        False
Restart Count: 0
Readiness:    http-get http://:80/health/ready delay=3s timeout=1s period=5s #success=1 #failure=3

Conditions:
  PodReadyToStartContainers True
  Initialized               True
  Ready                     False
  ContainersReady           False
  PodScheduled              True

Warning Unhealthy  2m32s (x25 over 4m32s)  kubelet
  Readiness probe failed: HTTP probe failed with statuscode: 404
```

**Root cause:** The configured readiness endpoint does not exist in this lab workload. HTTP 404 makes the container and Pod unready. A failed *readiness* probe does **not** restart the container; this explains `Running`, `0/1 Ready`, and `RESTARTS=0`. The readiness failure alone does not demonstrate that users experienced HTTP 503s: two old Pods were still Ready.

### 4. Recovery decision: roll forward

**Chosen response:** Correct the readiness probe path to `/` using `fixed-readiness-patch.json` and apply a new Deployment Pod template. Since two old Pods were available and the fault was identified, a small roll-forward was appropriate in this lab. For an actual serious outage or uncertain fix, prefer the safest rapid recovery (often rollback), subject to release and data compatibility.

**Observed after the corrected patch:**

```text
deployment.apps/payment-api   2/2   2   2
replicaset.apps/payment-api-65c8ddcd8    0   0   0
replicaset.apps/payment-api-6c97fdd64b   2   2   2
replicaset.apps/payment-api-94b9b79b6    0   0   0
pod/payment-api-6c97fdd64b-7pbt7   1/1   Running   0
pod/payment-api-6c97fdd64b-rtnwq   1/1   Running   0
```

**Assessment:** Kubernetes Deployment and ReplicaSet health recovered; updated and available replicas were 2/2, with zero container restarts in the two new Pods. The two historical ReplicaSets were scaled to zero. This is roll-forward, *not* rollout undo.

## Reproduce in an isolated namespace

```powershell
kubectl config use-context kind-prod-sim
kubectl create namespace mission-005
kubectl create deployment payment-api --image=nginx:alpine --replicas=2 -n mission-005
kubectl rollout status deployment/payment-api -n mission-005 --timeout=120s
kubectl patch deployment payment-api -n mission-005 --type=strategic --patch-file .\broken-readiness-patch.json
kubectl get deployments,replicasets,pods -n mission-005
kubectl describe pod -l app=payment-api -n mission-005
kubectl patch deployment payment-api -n mission-005 --type=strategic --patch-file .\fixed-readiness-patch.json
kubectl rollout status deployment/payment-api -n mission-005 --timeout=120s
kubectl get deployments,replicasets,pods -n mission-005
```

Run the patch-file commands from this directory (or supply the absolute paths). The reproducible manifest `deployment.yaml` represents the **corrected** application configuration.

## What we learned

- Pod **phase** `Running` is different from the Pod `Ready` condition.
- Successful container startup does not prove readiness.
- Probe configuration changes alter the Pod template and drive a Deployment rollout.
- A healthy old ReplicaSet can protect availability during a failing rolling update.
- **UP-TO-DATE** counts Pods on the updated template; **AVAILABLE** counts available Pods; desired readiness alone cannot prove request success.
- A roll-forward fix generates a new template revision and can leave older ReplicaSets retained at zero.
- `kubectl apply` success means the API accepted the manifest, not that all new Pods are healthy.
- In GitOps or GitHub Actions workflows, commit the corrected desired-state manifest to the source of truth; imperative patches alone can create configuration drift.

## Pending validation — not claimed complete

1. Create a temporary Service selecting `app=payment-api`; inspect its EndpointSlice ready addresses and test HTTP response through the Service.
2. Capture actual `kubectl rollout history` output (not supplied yet).
3. Optionally capture `kubectl get deployment payment-api -o yaml` to compare the exported live definition with the reusable manifest.
4. Cleanup after evidence is complete: `kubectl delete namespace mission-005`, verify deletion.

This lab intentionally **does not** claim a demonstrated HTTP 503 outage, live GitHub Actions execution, or network-level traffic verification.
