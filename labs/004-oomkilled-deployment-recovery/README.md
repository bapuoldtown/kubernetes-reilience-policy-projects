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

## Deployment change impact — when is a new ReplicaSet created?

**Rule:** For a Deployment, changing `spec.template` (the Pod template) triggers a rollout and normally creates a new ReplicaSet. Changing fields outside `spec.template` does not. An identical or previously retained template may reuse an existing ReplicaSet rather than create another distinct one.

| Action on Deployment | New ReplicaSet? | Effect / what operators should expect |
| --- | --- | --- |
| Create a new Deployment | Yes (initial RS) | Controller creates the first ReplicaSet and desired Pods |
| Change container image tag or digest in `spec.template` | Yes | Rolling update replaces Pods with the new image reference |
| Push new image to registry under the **same tag**, without changing Deployment | **No** | No Pod-template change; existing Pods keep running their existing image; future pulls can vary if tag is mutable |
| Change memory/CPU requests or limits in `spec.template` | Yes | New Pods use updated resources; this was our OOM lab recovery |
| Change environment variables or referenced ConfigMap/Secret **name** in template | Yes | Pod template changes; replacement Pods are created |
| Change a ConfigMap/Secret **data value** without changing Deployment template | **No** | Mounted ConfigMap/Secret volumes may update eventually; environment variables do not update in running containers; no automatic Deployment rollout |
| Change readiness/liveness/startup probe definition | Yes | New Pods use updated probe settings |
| Change container command, args, ports, volumes or mounts in template | Yes | New Pod template triggers rollout |
| Add/change a label or annotation under `spec.template.metadata` | Yes | Pod-template metadata changes; e.g. `kubectl rollout restart` adds/updates a restart annotation |
| Change only Deployment metadata labels/annotations (`metadata`, not `spec.template.metadata`) | No | Deployment metadata changes, Pod template remains identical |
| Scale `spec.replicas` from 2 to 5 | No | Existing ReplicaSet scales to the desired count |
| Change Deployment rollout strategy (`spec.strategy`) | No | Alters rollout policy, not Pod template |
| Change `revisionHistoryLimit` or `progressDeadlineSeconds` | No | Alters history retention or progress tracking, not Pod template |
| Delete a Pod managed by a ReplicaSet | No | ReplicaSet creates a replacement Pod using its current template |
| `kubectl rollout undo` to a retained previous template | Rollout yes; **not necessarily a distinct new RS** | Deployment reuses an existing matching ReplicaSet when retained, and advances the rollout revision |
| Apply the exact same Deployment manifest again | No | No Pod-template change, so no new rollout |

### How to inspect the impact before and after a change

```powershell
kubectl diff -f deployment.yaml
kubectl get deployment oom-api -n oom-lab -o yaml
kubectl get rs -n oom-lab
kubectl rollout history deployment/oom-api -n oom-lab
kubectl rollout status deployment/oom-api -n oom-lab
```

Use `kubectl diff` against the intended manifest before applying, then verify actual ReplicaSets and rollout health after synchronization. In GitOps, review the manifest diff in the PR, merge, let Argo CD sync, and verify the live workload. A new ReplicaSet does **not** by itself prove a successful or zero-downtime rollout.

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
