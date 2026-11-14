# Mission 004 — OOMKilled and Deployment recovery

## Environment
- Windows PowerShell; kind cluster `kind-prod-sim`
- Namespace: `oom-lab`
- Node observed: `prod-sim-worker2`
- Image: `python:3.11-alpine`

## Failure reproduction
A Python process allocated a `bytearray(200 * 1024 * 1024)` while its container was limited to `64Mi` memory (`32Mi` requested).

The initial standalone Pod `oom-demo` produced the following **observed** diagnosis from `kubectl describe pod oom-demo -n oom-lab`:

```text
State: Terminated
  Reason: OOMKilled
  Exit Code: 137
Last State: Terminated
  Reason: OOMKilled
  Exit Code: 137
Ready: False
Restart Count: 3
Limits:
  memory: 64Mi
Requests:
  memory: 32Mi
```

The user then deleted the standalone Pod and reproduced the failure in a **two-replica Deployment**, `oom-api`. The failing Deployment Pods were reported OOMKilled; raw pre-recovery Deployment status was not captured.

## Deployment reproduction manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oom-api
  namespace: oom-lab
spec:
  replicas: 2
  selector:
    matchLabels:
      app: oom-api
  template:
    metadata:
      labels:
        app: oom-api
    spec:
      containers:
        - name: app
          image: python:3.11-alpine
          resources:
            requests:
              memory: "32Mi"
            limits:
              memory: "64Mi"
          command:
            - python
            - -c
            - |
              import time
              print("Starting application", flush=True)
              data = bytearray(200 * 1024 * 1024)
              time.sleep(3600)
```

## Recovery performed

Instead of deleting individual Deployment Pods, the Deployment Pod template was updated:

```powershell
kubectl set resources deployment/oom-api -n oom-lab --containers=app --requests=memory=32Mi --limits=memory=384Mi
```

Observed response:

```text
deployment.apps/oom-api resource requirements updated
```

Verified with `kubectl get deployments,replicasets,pods -n oom-lab`:

```text
deployment.apps/oom-api   2/2   2   2
replicaset.apps/oom-api-59595dfd68   0   0   0
replicaset.apps/oom-api-5b58f445df   2   2   2
pod/oom-api-5b58f445df-dqqxq   1/1   Running   0
pod/oom-api-5b58f445df-tz2fz   1/1   Running   0
```

`kubectl describe deployment oom-api -n oom-lab` confirmed:
- Deployment revision 2, 2 desired / 2 updated / 2 available / 0 unavailable
- RollingUpdate, 25% maxUnavailable, 25% maxSurge
- New template limit `384Mi`, request `32Mi`
- Old ReplicaSet `oom-api-59595dfd68` scaled to zero
- New ReplicaSet `oom-api-5b58f445df` scaled to two
- Events: old RS 0→2; new RS 0→1; old 2→1; new 1→2; old 1→0

`kubectl rollout history deployment/oom-api -n oom-lab` showed revisions 1 and 2, both with no change-cause annotation.

## Production lessons
- Container OOMKilled (exit code 137 here) can trigger kubelet restarts and backoff; the Pod object may remain.
- Updating the Deployment Pod template creates a new ReplicaSet for a controlled rollout; deleting individual Pods would not fix the bad template.
- With two replicas, default 25% maxSurge rounds up to 1 and 25% maxUnavailable rounds down to 0; these settings do not guarantee uptime if existing Pods are already unhealthy.
- Kubernetes rollout history is distinct from Git commits and image build history.
- In GitOps, restore a known-good image/configuration in Git and let Argo CD reconcile; `kubectl rollout undo` directly changes live state and may conflict with GitOps reconciliation.
- An OOM fix requires verifying legitimate memory needs, node capacity and application behavior, not just increasing limits blindly.

## Remaining / not yet verified
- No bad-release rollback simulation executed.
- No Argo CD sync was exercised in this lab.
- Namespace cleanup has **not yet been confirmed**. When finished: `kubectl delete namespace oom-lab`.
