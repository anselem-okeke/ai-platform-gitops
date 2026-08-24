# Runbook: Fixing `ai-platform-api` Readiness Failures Caused by Kubernetes API Egress NetworkPolicy

## Purpose

This runbook documents how to diagnose and fix the `ai-platform-api` readiness failure where:

- `/healthz` returns `200`
- `/readyz` returns `503`
- the API pod stays `0/1 Running`
- the Kubernetes readiness check times out
- host-side `kubectl get modelservices` works quickly
- the `ai-platform-api` ServiceAccount has permission to `get`/`list` `ModelService`
- the root cause is a stale or overly specific NetworkPolicy rule for the Kind control-plane IP

It also includes the full Git workflow: branch creation, validation, commit, push, pull request, CI watch, merge, Argo CD verification, rollout watch, and final readiness validation.

---

# 1. Symptom

Example pod state:

```text
NAME                               READY   STATUS    RESTARTS   AGE
ai-platform-api-79d97c86c9-2l6bf   0/1     Running   0          3m
```

Typical readiness events:

```text
Readiness probe failed: HTTP probe failed with statuscode: 503
Readiness probe failed: context deadline exceeded
```

Application logs may show:

```json
{"method":"GET","path":"/readyz","status":503,"duration_ms":2000}
{"method":"GET","path":"/healthz","status":200,"duration_ms":0}
```

Interpretation:

```text
Process alive            ✅
HTTP server alive        ✅
Kubernetes dependency    ❌
Pod Ready                ❌
```

---

# 2. Confirm RBAC is not the problem

```bash
kubectl auth can-i list modelservices \
  -n ai-platform \
  --as=system:serviceaccount:ai-platform:ai-platform-api

kubectl auth can-i get modelservices \
  -n ai-platform \
  --as=system:serviceaccount:ai-platform:ai-platform-api
```

Expected:

```text
yes
yes
```

Optional:

```bash
kubectl auth can-i get pods \
  -n ai-platform \
  --as=system:serviceaccount:ai-platform:ai-platform-api
```

A result of `no` is acceptable if the API does not need Pod access. Do not add unnecessary Pod or Namespace RBAC just to make readiness pass.

---

# 3. Confirm the Kubernetes API itself is healthy

```bash
time kubectl get modelservices \
  -n ai-platform \
  --as=system:serviceaccount:ai-platform:ai-platform-api
```

If this is fast, Kubernetes, the CRD, and RBAC are healthy.

---

# 4. Bound Kubernetes client requests

File:

```text
internal/api/kubernetes/client.go
```

Add:

```go
import "time"
```

After loading the Kubernetes config, add:

```go
restConfig.Timeout = 2 * time.Second
```

This prevents Kubernetes API requests from hanging for tens of seconds.

Validate:

```bash
gofmt -w internal/api/kubernetes/client.go

go test ./internal/api/kubernetes/... ./internal/api/handlers/...

make test
```

---

# 5. Important local runtime-source cleanup

The sklearn runtime build may temporarily materialize KServe into:

```text
.runtime-src/kserve
```

Do not leave this directory present when running `make test`, because `controller-gen paths="./..."` can scan it and generate unwanted KServe CRDs/webhook manifests.

Safe cleanup:

```bash
rm -rf .runtime-src
```

The real cached KServe source remains at:

```text
$HOME/.cache/ai-platform-operator/kserve
```

Confirm:

```bash
ls "$HOME/.cache/ai-platform-operator/kserve"
```

If accidental untracked KServe CRDs were generated:

```bash
git status --short config/crd/bases

git ls-files 'config/crd/bases/serving.kserve.io_*.yaml'
```

If `git ls-files` returns nothing, remove only those untracked generated CRDs:

```bash
rm -f \
  config/crd/bases/serving.kserve.io_inferenceservices.yaml \
  config/crd/bases/serving.kserve.io_llminferenceserviceconfigs.yaml \
  config/crd/bases/serving.kserve.io_llminferenceservices.yaml
```

Then:

```bash
make test
```

---

# 6. Git workflow for the API timeout fix

```bash
git switch -c fix/platform-api-readiness-timeout

git add internal/api/kubernetes/client.go

git status --short
git diff --check
git diff --cached

git commit -m "fix(api): bound Kubernetes client requests"

git push -u origin fix/platform-api-readiness-timeout
```

Create the PR:

```bash
gh pr create \
  --base main \
  --head fix/platform-api-readiness-timeout \
  --title "fix(api): bound Kubernetes readiness requests" \
  --body "Bound Kubernetes API client requests to 2 seconds so /readyz cannot hang for tens of seconds when Kubernetes API calls stall."
```

Watch checks:

```bash
gh pr checks --watch
```

Merge only when required checks pass:

```bash
gh pr merge --squash --delete-branch
```

Then:

```bash
git switch main
git pull --ff-only
git log -1 --oneline
```

---

# 7. Watch post-merge workflows

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
echo "$SOURCE_SHA"

gh run list \
  --commit "$SOURCE_SHA" \
  --limit 20
```

Watch Release Images:

```bash
gh run list \
  --workflow="Release Images" \
  --commit "$SOURCE_SHA" \
  --limit 1

gh run watch <RUN_ID>
```

Watch promotion:

```bash
gh run list --limit 20

gh run watch <PROMOTION_RUN_ID>
```

Expected promotion stages:

```text
verify promotion gates       ✅
resolve exact digests        ✅
validate promotion inputs    ✅
GitHub App token             ✅
GitOps mutation              ✅
GitOps validation            ✅
GitOps PR                    ✅
```

---

# 8. Verify the promoted API pod

```bash
kubectl get pods -n ai-platform -w
```

If a new API pod remains `0/1 Running`:

```bash
kubectl describe pod <NEW_API_POD> \
  -n ai-platform

kubectl logs \
  -n ai-platform \
  <NEW_API_POD> \
  --tail=200
```

If `/readyz` now fails around 2 seconds instead of 45+ seconds, the timeout fix is working. The remaining issue is the Kubernetes dependency/network path.

---

# 9. Inspect the API NetworkPolicy

```bash
kubectl get networkpolicy ai-platform-api \
  -n ai-platform \
  -o yaml
```

Typical Kubernetes API egress rules:

```yaml
egress:
  - to:
      - ipBlock:
          cidr: 10.96.0.1/32
    ports:
      - protocol: TCP
        port: 443

  - to:
      - ipBlock:
          cidr: 172.19.0.X/32
    ports:
      - protocol: TCP
        port: 6443
```

The first rule permits the Kubernetes Service ClusterIP. The second covers the real Kind control-plane endpoint after Service DNAT.

---

# 10. Determine the real Kubernetes API endpoint

```bash
kubectl get svc kubernetes \
  -n default \
  -o wide

kubectl get endpoints kubernetes \
  -n default \
  -o wide

kubectl get nodes -o wide
```

Example:

```text
kubernetes service      10.96.0.1:443
actual API endpoint     172.19.0.5:6443
control-plane node      172.19.0.5
worker                  172.19.0.7
worker2                 172.19.0.3
```

If the NetworkPolicy allows `172.19.0.3/32` but the control plane is `172.19.0.5`, the policy is allowing the wrong Kind node.

---

# 11. Why a single `/32` is brittle

A rule like:

```yaml
cidr: 172.19.0.5/32
```

allows exactly one IPv4 address.

Kind nodes run as Docker containers. Their IPs can change when the cluster or containers are recreated. This can produce recurring control-plane addresses such as:

```text
172.19.0.7
172.19.0.3
172.19.0.5
```

Do not keep chasing a single control-plane `/32` address.

---

# 12. Determine the Kind Docker subnet

```bash
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
```

Example:

```text
fc00:f853:ccd:e793::/64
172.19.0.0/16
```

For the IPv4 Kubernetes API path, use:

```text
172.19.0.0/16
```

Important:

```text
172.19.0.0/32
```

means only the single IP `172.19.0.0`. It does **not** include `172.19.0.5`, `172.19.0.7`, or `172.19.0.3`.

---

# 13. Correct NetworkPolicy fix

File:

```text
platform/api/base/networkpolicy.yaml
```

Keep the Kubernetes Service ClusterIP rule:

```yaml
- to:
    - ipBlock:
        cidr: 10.96.0.1/32
  ports:
    - protocol: TCP
      port: 443
```

Replace the single Kind control-plane IP rule:

```yaml
- to:
    - ipBlock:
        cidr: 172.19.0.X/32
  ports:
    - protocol: TCP
      port: 6443
```

with:

```yaml
- to:
    - ipBlock:
        cidr: 172.19.0.0/16
  ports:
    - protocol: TCP
      port: 6443
```

Recommended final section:

```yaml
egress:
  # DNS resolution through CoreDNS.
  - to:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: kube-system
        podSelector:
          matchLabels:
            k8s-app: kube-dns
    ports:
      - protocol: UDP
        port: 53
      - protocol: TCP
        port: 53

  # Kubernetes API Service ClusterIP.
  - to:
      - ipBlock:
          cidr: 10.96.0.1/32
    ports:
      - protocol: TCP
        port: 443

  # Kind Kubernetes API backend network.
  # Service DNAT may cause policy enforcement to see the control-plane
  # container IP rather than the Service VIP. Kind node IPs can change,
  # so allow TCP 6443 across the Kind Docker IPv4 subnet.
  - to:
      - ipBlock:
          cidr: 172.19.0.0/16
    ports:
      - protocol: TCP
        port: 6443
```

---

# 14. GitOps PR workflow for the NetworkPolicy fix

Start from current `main`:

```bash
git switch main
git pull --ff-only
```

Create the branch:

```bash
git switch -c fix/api-kind-subnet-egress
```

Edit:

```text
platform/api/base/networkpolicy.yaml
```

Change:

```yaml
cidr: 172.19.0.0/32
```

or any hard-coded `172.19.0.X/32` API backend rule to:

```yaml
cidr: 172.19.0.0/16
```

Verify:

```bash
grep -n "cidr: 172.19" \
  platform/api/base/networkpolicy.yaml
```

Expected:

```text
cidr: 172.19.0.0/16
```

Check Git:

```bash
git status --short

git diff -- platform/api/base/networkpolicy.yaml

git diff --check
```

Validate Kustomize:

```bash
kubectl kustomize platform/api/overlays/dev \
  >/tmp/ai-platform-api-rendered.yaml
```

If the repository uses a different environment overlay path, use the actual overlay path.

Stage only the intended file:

```bash
git add platform/api/base/networkpolicy.yaml

git diff --cached
```

Commit:

```bash
git commit -m "fix(network): allow Kubernetes API across kind subnet"
```

Push:

```bash
git push -u origin fix/api-kind-subnet-egress
```

Create PR:

```bash
gh pr create \
  --base main \
  --head fix/api-kind-subnet-egress \
  --title "fix(network): allow Kubernetes API across kind subnet" \
  --body "Replace the hard-coded Kind control-plane IP with the Kind Docker IPv4 subnet on TCP 6443 so ai-platform-api can continue reaching the Kubernetes API when Kind node container IPs change."
```

Watch CI:

```bash
gh pr checks --watch
```

Review:

```bash
gh pr view
gh pr diff
```

Merge after all required checks pass:

```bash
gh pr merge --squash --delete-branch
```

Return to main:

```bash
git switch main
git pull --ff-only
```

---

# 15. Verify Argo CD applied the NetworkPolicy

Do not assume merge means the live cluster has already changed.

Check:

```bash
kubectl get networkpolicy ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.egress[*].to[*].ipBlock.cidr}{"\n"}'
```

Expected:

```text
10.96.0.1/32 172.19.0.0/16
```

If it still shows a `/32`, Argo has not applied the new Git state yet.

---

# 16. Watch Kubernetes recovery

```bash
kubectl get pods -n ai-platform -w
```

In another terminal:

```bash
kubectl rollout status deployment/ai-platform-api \
  -n ai-platform \
  --watch
```

Success:

```text
deployment "ai-platform-api" successfully rolled out
```

Expected pod:

```text
ai-platform-api-...   1/1   Running
```

---

# 17. Confirm the deployed API image digest

```bash
kubectl get deployment ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Expected form:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<DIGEST>
```

---

# 18. Final `/readyz` verification

Check whether port `8090` is already occupied:

```bash
ss -ltnp | grep 8090 || true
```

Use a fresh local port if necessary:

```bash
kubectl port-forward \
  -n ai-platform \
  deployment/ai-platform-api \
  8091:8080
```

In another terminal:

```bash
time curl -i \
  --max-time 5 \
  http://127.0.0.1:8091/readyz
```

Success:

```text
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ready"}
```

Expected response time should be fast, not a 2-second `503` and not a 45+ second hang.

---

# 19. Final live verification checklist

```bash
kubectl get pods -n ai-platform
```

Expected:

```text
ai-platform-api-...   1/1   Running
fraud-model-...       1/1   Running
```

Check readiness logs:

```bash
kubectl logs \
  -n ai-platform \
  deployment/ai-platform-api \
  --tail=100 \
  | grep readyz
```

Expected:

```text
"path":"/readyz","status":200
```

Check policy:

```bash
kubectl get networkpolicy ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.egress[*].to[*].ipBlock.cidr}{"\n"}'
```

Expected:

```text
10.96.0.1/32 172.19.0.0/16
```

Check current Kubernetes API endpoint:

```bash
kubectl get endpoints kubernetes \
  -n default \
  -o wide
```

The endpoint may change between Kind recreations, but it should remain inside the permitted Kind subnet while that Docker network stays `172.19.0.0/16`.

---

# 20. Root cause summary

Original brittle design:

```yaml
cidr: 172.19.0.X/32
```

When the Kind control-plane container IP changed, the Platform API could still start and answer `/healthz`, but its Kubernetes API requests were blocked by NetworkPolicy.

Traffic path:

```text
ai-platform-api
      |
      v
kubernetes.default.svc
10.96.0.1:443
      |
      | Service DNAT
      v
Kind control plane
172.19.0.X:6443
      |
      X  stale /32 NetworkPolicy rule
      |
      v
request timeout -> /readyz 503
```

The Go timeout fix changed failure behavior from long hangs to bounded 2-second failures.

The NetworkPolicy fix addresses the actual connectivity problem:

```text
10.96.0.1/32:443
+
172.19.0.0/16:6443
```

---

# 21. Design note

Using `172.19.0.0/16` is durable for the current Kind Docker network, but it is not universally permanent.

If Docker recreates the `kind` network with a different subnet, re-check:

```bash
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
```

For this homelab, subnet-based TCP/6443 egress is much more stable than pinning one Kind control-plane container IP.

The policy remains constrained by source pod selection, destination subnet, TCP, and port `6443`; it is not unrestricted pod egress.

---

# Quick Recovery Commands

```bash
# Actual Kubernetes API backend
kubectl get endpoints kubernetes -n default -o wide

# Kind Docker subnet
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'

# Live NetworkPolicy
kubectl get networkpolicy ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.egress[*].to[*].ipBlock.cidr}{"\n"}'

# Expected:
# 10.96.0.1/32 172.19.0.0/16

# Watch pods
kubectl get pods -n ai-platform -w

# Watch rollout
kubectl rollout status deployment/ai-platform-api \
  -n ai-platform \
  --watch

# Port-forward
kubectl port-forward \
  -n ai-platform \
  deployment/ai-platform-api \
  8091:8080

# Another terminal
time curl -i \
  --max-time 5 \
  http://127.0.0.1:8091/readyz
```
