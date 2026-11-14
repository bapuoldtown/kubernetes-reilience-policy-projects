# Mission 003 — ImagePullBackOff

## Goal
Reproduce a container image pull failure, diagnose the ownership chain, and restore the Pod.

**Environment:** kind cluster `kind-prod-sim`, temporary namespace `imagepull-lab`.

## Reproduction manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: imagepull-demo
  namespace: imagepull-lab
spec:
  containers:
    - name: nginx
      image: nginx:nonexistent-tag-999
```

Apply and investigate:

```powershell
kubectl create namespace imagepull-lab
# Apply the manifest above
kubectl get pod imagepull-demo -n imagepull-lab
kubectl describe pod imagepull-demo -n imagepull-lab
kubectl logs imagepull-demo -n imagepull-lab
```

## Observations reported during the lab

- User reported investigating with `get`, `describe`, and `logs`, and diagnosing an image pull failure.
- User explained the correct execution chain: kubelet on the worker requests the pull through CRI; containerd attempts to fetch the image from a registry; the requested image cannot be fetched.
- User subsequently confirmed the workload was **Running and Ready** after the recovery instruction.
- Exact terminal output of the failure events, image pull error, recovery command, and recovered Pod status **was not pasted**, so this document does not invent them.
- The user also examined the distinction between a Pod's `READY` column and a configured readiness probe; a running container may be considered ready without an explicit readiness probe.

## Recovery instruction used

```powershell
kubectl set image pod/imagepull-demo nginx=nginx:1.27-alpine -n imagepull-lab
kubectl get pod imagepull-demo -n imagepull-lab
```

**Reported result:** Running and Ready. The exact output was not provided.

## Production lessons

- `ErrImagePull` / `ImagePullBackOff`: image acquisition fails before the application container starts.
- Kubelet supervises the assigned Pod and requests image operations; containerd executes image pulls and container runtime operations.
- `kubectl describe pod` events are particularly useful when the application has never started and cannot produce application logs.
- Check image reference/tag, registry reachability, authentication/authorization, and pull secrets as applicable.
- For Deployment-managed workloads, update the Deployment template through the normal delivery pipeline rather than relying on edits to an individual Pod.
- A Pod displaying `1/1 Running` does not prove application health if no readiness probe is configured.

## Cleanup — not yet verified

```powershell
kubectl delete namespace imagepull-lab
kubectl get namespace imagepull-lab
```

Do not mark namespace cleanup complete until deletion is confirmed.
