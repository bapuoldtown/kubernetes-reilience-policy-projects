# Mission 002 — CrashLoopBackOff

## Scenario
A standalone Pod's application repeatedly exits with code 1. Diagnose container restart backoff, then restore a stable container.

**Environment:** Windows PowerShell, kind context `kind-prod-sim`, namespace `crashloop-lab`.

## Failure reproduction

```powershell
kubectl create namespace crashloop-lab
@'
apiVersion: v1
kind: Pod
metadata:
  name: crash-demo
  namespace: crashloop-lab
spec:
  restartPolicy: Always
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - "echo 'Application starting...'; sleep 2; echo 'FATAL: Configuration missing'; exit 1"
'@ | kubectl apply -f -
kubectl get pods -n crashloop-lab
kubectl describe pod crash-demo -n crashloop-lab
kubectl logs crash-demo -n crashloop-lab --previous
kubectl logs crash-demo -n crashloop-lab --tail=20
```

## Actual user-observed evidence (2026-11-14)

- `kubectl get pods`: `0/1 Error`, restart count increased from 2 to 4.
- `kubectl describe pod`: Pod phase `Running`, container state `Waiting`, reason `CrashLoopBackOff`; last state `Terminated`, reason `Error`, exit code `1`, restart count `6`.
- Kubelet events: `Created` and `Started` x7, `BackOff` x10.
- `kubectl logs --previous` failed: `unable to retrieve container logs for containerd://...`. This does **not** mean the container did not crash.
- `kubectl logs crash-demo -n crashloop-lab --tail=20` returned:
```text
Application starting...
FATAL: Configuration missing
```
- Root cause **in this controlled simulation**: the Pod command explicitly exits with code 1 after printing a synthetic missing-configuration message. No real configuration lookup was attempted.

## Recovery

The user deleted the standalone failing Pod and recreated it with this command:

```yaml
command:
  - sh
  - -c
  - "echo 'Application started successfully'; sleep 3600"
```

Actual verified output:

```text
$ kubectl get pod crash-demo -n crashloop-lab
NAME         READY   STATUS    RESTARTS   AGE
crash-demo   1/1     Running   0          60s
```

**Recovery verified for the simulation.** This demonstrates a running process, not real HTTP health or business functionality. A production Deployment should be repaired by updating its Pod template via the delivery workflow, not manually replacing a managed Pod.

## Tradeoffs and interpretation

- Pod phase `Running` can coexist with a container `Waiting: CrashLoopBackOff`.
- Kubelet reconciles container execution according to `restartPolicy` and requests runtime operations through CRI.
- ReplicaSet maintains Pod object count; it does not create a replacement Pod for every container crash.
- `describe` provides Kubernetes state/events; `logs` provides stdout/stderr when accessible.
- Diagnose the *reason* for the exit rather than simply restarting or scaling Pods.

## Cleanup — pending verification

```powershell
kubectl delete namespace crashloop-lab
kubectl get namespace crashloop-lab
```

Do not mark cleanup complete until the namespace is confirmed absent.
