# Command Reference

## Purpose

This document is the **practical command reference** for operating, validating, troubleshooting, and recovering the AI Platform.

It is intentionally command-first.

Use it when you already know **what you want to do** and need the exact command sequence quickly.

Primary repositories:

```text
SOURCE REPO
/mnt/data/ai-platform-operator

GITOPS REPO
/mnt/data/ai-platform-gitops
```

Core cluster:

```text
kind cluster:
ai-platform-policy

kubectl context:
kind-ai-platform-policy

Kubernetes:
v1.36.1
```

Core namespaces:

```text
ai-platform
ai-platform-operator-system
argocd
cosign-system
monitoring
gateway-system
envoy-gateway-system
keycloak
```

Core endpoints:

```text
Keycloak:
https://auth.ai-platform.local

Argo CD:
https://argocd.ai-platform.local

API:
https://api.ai-platform.local

Vault:
https://vault.platform.local:8200
```

---

# 1. Cluster Context

Show current context:

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

List contexts:

```bash
kubectl config get-contexts
```

Switch:

```bash
kubectl config use-context \
  kind-ai-platform-policy
```

Cluster info:

```bash
kubectl cluster-info
```

Version:

```bash
kubectl version
```

Nodes:

```bash
kubectl get nodes -o wide
```

---

# 2. kind Cluster

List clusters:

```bash
kind get clusters
```

Create cluster with project config:

```bash
kind create cluster \
  --name ai-platform-policy \
  --config <ACTUAL_KIND_CONFIG>
```

Delete cluster:

```bash
kind delete cluster \
  --name ai-platform-policy
```

Do not delete the active cluster during normal operations.

---

# 3. Namespace Operations

List namespaces:

```bash
kubectl get ns
```

Show protected labels:

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

Inspect one namespace:

```bash
kubectl get ns \
  ai-platform \
  -o yaml
```

---

# 4. Pod Health

All pods:

```bash
kubectl get pods -A
```

AI Platform:

```bash
kubectl get pods \
  -n ai-platform
```

Operator:

```bash
kubectl get pods \
  -n ai-platform-operator-system
```

Argo:

```bash
kubectl get pods \
  -n argocd
```

Policy Controller:

```bash
kubectl get pods \
  -n cosign-system
```

Monitoring:

```bash
kubectl get pods \
  -n monitoring
```

Keycloak:

```bash
kubectl get pods \
  -n keycloak
```

Watch pods:

```bash
kubectl get pods \
  -n ai-platform \
  -w
```

---

# 5. Pod Details

Describe:

```bash
kubectl describe pod \
  -n <NAMESPACE> \
  <POD>
```

Logs:

```bash
kubectl logs \
  -n <NAMESPACE> \
  <POD>
```

Tail logs:

```bash
kubectl logs \
  -n <NAMESPACE> \
  <POD> \
  --tail=300
```

Previous container logs:

```bash
kubectl logs \
  -n <NAMESPACE> \
  <POD> \
  --previous
```

All containers:

```bash
kubectl logs \
  -n <NAMESPACE> \
  <POD> \
  --all-containers=true \
  --tail=300
```

---

# 6. Events

All cluster events:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp
```

Namespace:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

Recent failure-focused view:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp \
  | grep -Ei \
    'Failed|BackOff|Error|Denied|Unhealthy'
```

---

# 7. Deployments

List AI Platform deployments:

```bash
kubectl get deployment \
  -n ai-platform
```

Operator deployments:

```bash
kubectl get deployment \
  -n ai-platform-operator-system
```

Describe:

```bash
kubectl describe deployment \
  <DEPLOYMENT> \
  -n <NAMESPACE>
```

Rollout status:

```bash
kubectl rollout status \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE> \
  --timeout=300s
```

Restart:

```bash
kubectl rollout restart \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE>
```

Use restart only when runtime reload is actually required.

---

# 8. Live Image References

API:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Operator:

```bash
kubectl get deployment \
  <OPERATOR_DEPLOYMENT> \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Pod image IDs:

```bash
kubectl get pods \
  -n ai-platform \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{range .status.containerStatuses[*]}{.imageID}{"\n"}{end}{end}'
```

Expected deployment form:

```text
ghcr.io/anselem-okeke/...@sha256:<64hex>
```

---

# 9. Services

AI Platform:

```bash
kubectl get svc \
  -n ai-platform
```

Policy Controller:

```bash
kubectl get svc \
  -n cosign-system
```

Monitoring:

```bash
kubectl get svc \
  -n monitoring
```

Detailed:

```bash
kubectl get svc \
  <SERVICE> \
  -n <NAMESPACE> \
  -o yaml
```

Endpoints:

```bash
kubectl get endpoints \
  <SERVICE> \
  -n <NAMESPACE>
```

---

# 10. Gateway API

Gateways:

```bash
kubectl get gateway \
  -A
```

HTTPRoutes:

```bash
kubectl get httproute \
  -A
```

Detailed Gateway:

```bash
kubectl get gateway \
  <GATEWAY> \
  -n <NAMESPACE> \
  -o yaml
```

Detailed route:

```bash
kubectl get httproute \
  <ROUTE> \
  -n <NAMESPACE> \
  -o yaml
```

Validated Gateway LB address:

```text
172.19.255.200
```

---

# 11. API Route Test

Representative:

```bash
curl -vk \
  https://api.ai-platform.local/
```

Prefer the real health endpoint if implemented.

For production-like validation, do not routinely disable TLS verification.

---

# 12. Argo CD CLI Access

Port-forward bootstrap access:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

Routine endpoint:

```text
https://argocd.ai-platform.local
```

Argo server remains:

```text
ClusterIP
```

---

# 13. Argo Applications

List:

```bash
argocd app list
```

Get app:

```bash
argocd app get \
  <APP> \
  --refresh
```

Diff:

```bash
argocd app diff \
  <APP>
```

Wait:

```bash
argocd app wait \
  <APP> \
  --sync \
  --health \
  --timeout 300
```

Sync child:

```bash
argocd app sync \
  <APP>
```

Root sync:

```bash
argocd app sync \
  ai-platform-root
```

Use root sync only after reviewing topology changes.

---

# 14. Argo Revision

API:

```bash
argocd app get \
  ai-platform-api \
  -o json \
  | jq -r '.status.sync.revision'
```

Operator:

```bash
argocd app get \
  ai-platform-operator \
  -o json \
  | jq -r '.status.sync.revision'
```

---

# 15. AppProject

Inspect:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd \
  -o yaml
```

Validate bootstrap file:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Apply:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

AppProject is bootstrap-managed.

---

# 16. Root Application

Inspect file:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,320p' \
  clusters/dev/root-application.yaml
```

Server dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f clusters/dev/root-application.yaml
```

Apply:

```bash
kubectl apply \
  -f clusters/dev/root-application.yaml
```

---

# 17. App-of-Apps Render

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Inspect:

```bash
grep -n \
  'kind: Application' \
  /tmp/apps.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/apps.yaml
```

---

# 18. GitOps Render Commands

Operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

API:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

Gateway:

```bash
kubectl kustomize \
  platform/gateway/overlays/dev \
  >/tmp/gateway.yaml
```

Monitoring:

```bash
kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

Policies:

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

ModelServices:

```bash
kubectl kustomize \
  modelservices/overlays/dev \
  >/tmp/modelservices.yaml
```

Applications:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

---

# 19. kubeconform

Validated version:

```text
0.7.0
```

Validate one rendered file:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/api.yaml
```

Validate multiple:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/operator.yaml \
  /tmp/api.yaml \
  /tmp/gateway.yaml \
  /tmp/monitoring.yaml \
  /tmp/policies.yaml
```

---

# 20. Server Dry-Run

Policies:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml
```

Monitoring:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/monitoring.yaml
```

Generic:

```bash
kubectl apply \
  --dry-run=server \
  -f <FILE>
```

---

# 21. Git Diff Validation

```bash
git diff --check
```

Changed files:

```bash
git diff --name-only
```

Staged:

```bash
git diff --cached
```

Compare branches:

```bash
git diff \
  --name-only \
  origin/main...HEAD \
  | sort
```

---

# 22. SOURCE REPO — Update Main

```bash
cd /mnt/data/ai-platform-operator

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Create branch:

```bash
git switch -c \
  feat/<DESCRIPTION>
```

---

# 23. GITOPS REPO — Update Main

```bash
cd /mnt/data/ai-platform-gitops

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Create branch:

```bash
git switch -c \
  feat/<DESCRIPTION>
```

---

# 24. Source Local Validation

```bash
cd /mnt/data/ai-platform-operator

make lint-config
make lint
make test
go vet ./...
govulncheck ./...
gitleaks git --redact
```

Validated Go:

```text
1.26.6
```

Validated govulncheck CLI:

```text
v1.7.0
```

---

# 25. Source PR

Create:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-operator \
  --base main \
  --head <BRANCH> \
  --title "<TITLE>" \
  --body "<DESCRIPTION>"
```

Checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator \
  --watch
```

Merge:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator \
  --merge
```

---

# 26. Source Required Checks

Expected:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

---

# 27. Source Ruleset

Validated:

```text
Source Main Protection
ID 21120105
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Compact:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  --jq '{
    name,
    enforcement,
    target,
    bypass_actors
  }'
```

---

# 28. Source Workflow Files

```bash
cd /mnt/data/ai-platform-operator

find .github/workflows \
  -maxdepth 1 \
  -type f \
  -print \
  | sort
```

Expected:

```text
lint.yml
test.yml
test-e2e.yml
security.yml
release-images.yml
secret-scan.yml
```

---

# 29. Inspect Release Workflow

```bash
sed -n '1,520p' \
  .github/workflows/release-images.yml
```

Find jobs:

```bash
grep -nE \
  '^  build-operator:|^  build-api:|^  update-gitops:|needs:' \
  .github/workflows/release-images.yml
```

---

# 30. GitHub Actions Runs

List:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --limit 20
```

Release workflow:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --workflow release-images.yml \
  --limit 10
```

View:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

Watch:

```bash
gh run watch <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

Logs:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --log
```

Re-run:

```bash
gh run rerun <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

---

# 31. Release SHA

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --json headSha,event,status,conclusion
```

---

# 32. Trivy Workflow Inspection

```bash
grep -nA18 -B6 \
  'trivy' \
  .github/workflows/release-images.yml
```

Validated release policy:

```text
severity = HIGH,CRITICAL
ignore-unfixed = true
exit code = 1
```

---

# 33. SBOM Workflow Inspection

```bash
grep -nEi \
  'syft|sbom|spdx' \
  .github/workflows/release-images.yml
```

Validated SBOM:

```text
SPDX JSON
```

---

# 34. Attestation Workflow Inspection

Validated action:

```text
actions/attest
```

Pinned SHA:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Inspect:

```bash
grep -nA18 -B6 \
  '508db95dd578ae2727ebd6217d5ba78e4fbda05d' \
  .github/workflows/release-images.yml
```

---

# 35. GitHub App Token Workflow Inspection

Validated action:

```text
actions/create-github-app-token
```

Pinned SHA:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Inspect:

```bash
grep -nA22 -B6 \
  'bcd2ba49218906704ab6c1aa796996da409d3eb1' \
  .github/workflows/release-images.yml
```

---

# 36. GitHub App Promotion Branch

Expected:

```text
automation/image-<SOURCE_SHA>
```

Check:

```bash
git ls-remote \
  --heads \
  https://github.com/anselem-okeke/ai-platform-gitops.git \
  "refs/heads/automation/image-${SOURCE_SHA}"
```

---

# 37. Fetch Promotion Branch

```bash
cd /mnt/data/ai-platform-gitops

git fetch origin \
  "automation/image-${SOURCE_SHA}"
```

Changed files:

```bash
git diff \
  --name-only \
  origin/main...FETCH_HEAD \
  | sort
```

Expected:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

---

# 38. Inspect Promotion Commit

```bash
git show \
  --no-patch \
  --format=fuller \
  FETCH_HEAD
```

Expected identity:

```text
ai-platform-gitops-bot[bot]
```

Expected message:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 39. Inspect Promotion Overlay Files

Operator:

```bash
git show \
  FETCH_HEAD:platform/operator/overlays/dev/kustomization.yaml
```

API:

```bash
git show \
  FETCH_HEAD:platform/api/overlays/dev/kustomization.yaml
```

Expected:

```text
digest: sha256:<64hex>
```

---

# 40. GitOps PR

List:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

Specific promotion:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --head "automation/image-${SOURCE_SHA}"
```

View:

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --watch
```

Merge:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

---

# 41. GitOps Validation Workflow

Inspect:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,500p' \
  .github/workflows/validate.yml
```

Search image validation:

```bash
grep -nEi \
  'sha256|newTag|latest|ghcr|image' \
  .github/workflows/validate.yml
```

Search secret validation:

```bash
grep -nEi \
  'secret|password|token|PRIVATE KEY' \
  .github/workflows/validate.yml
```

---

# 42. Digest Validation

Shell helper:

```bash
validate_digest() {
  local digest="$1"

  if [[ ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "ERROR: invalid digest: ${digest}" >&2
    return 1
  fi
}
```

Use:

```bash
validate_digest "${API_DIGEST}"
validate_digest "${OPERATOR_DIGEST}"
```

---

# 43. Final Render Image Checks

API:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  | grep 'image:'
```

Operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  | grep 'image:'
```

Reject mutable tags:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  | grep -E \
    'image: .*:(latest|dev|main)$'
```

Expected:

```text
no matches
```

---

# 44. Policy Controller Helm

List:

```bash
helm list \
  -n cosign-system
```

Expected:

```text
policy-controller chart 0.10.6
```

Application version:

```text
0.13.1
```

---

# 45. Trust Policies Helm

List:

```bash
helm list \
  -n cosign-system
```

Expected trust-policies version:

```text
v0.7.0
```

Validated manual install command:

```bash
helm upgrade trust-policies \
  --install \
  --rollback-on-failure \
  --namespace cosign-system \
  oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies \
  --version v0.7.0 \
  -f /tmp/github-attestation-policy-values.yaml
```

Use GitOps-managed install in normal operation.

---

# 46. Trust Policy Values

Validated values:

```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

---

# 47. TrustRoot

List:

```bash
kubectl get trustroots.policy.sigstore.dev
```

Inspect:

```bash
kubectl get trustroot \
  github \
  -o yaml
```

Expected:

```text
github
```

---

# 48. ClusterImagePolicy

List:

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Inspect:

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Expected:

```text
github-policy
```

---

# 49. Native Admission Policies

List:

```bash
kubectl get validatingadmissionpolicies
```

Bindings:

```bash
kubectl get validatingadmissionpolicybindings
```

Detailed:

```bash
kubectl get validatingadmissionpolicies \
  -o yaml
```

Bindings YAML:

```bash
kubectl get validatingadmissionpolicybindings \
  -o yaml
```

Verify intended:

```text
failurePolicy: Fail
validationActions: Deny
```

Use exact committed values.

---

# 50. Positive Admission Test

Use live trusted API image:

```bash
API_IMAGE="$(kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}')"
```

Test:

```bash
kubectl run admission-good \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
allowed
```

---

# 51. Mutable Tag Negative Test

```bash
kubectl run admission-bad-tag \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

---

# 52. Public Image Negative Test

```bash
kubectl run admission-nginx \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

---

# 53. Malformed Digest Test

```bash
kubectl run admission-short-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:1234' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
rejected
```

---

# 54. Fake Valid Digest Test

```bash
kubectl run admission-fake-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Validated Sigstore message:

```text
no valid bundles exist in registry
```

---

# 55. Bad Init Container Test

```bash
cat >/tmp/bad-init.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest

  containers:
    - name: app
      image: ${API_IMAGE}
EOF
```

Run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/bad-init.yaml
```

Expected:

```text
DENIED
```

---

# 56. Bad Sidecar Test

```bash
cat >/tmp/bad-sidecar.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: bad-sidecar
  namespace: ai-platform
spec:
  restartPolicy: Never

  containers:
    - name: app
      image: ${API_IMAGE}

    - name: sidecar
      image: nginx:latest
EOF
```

Run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/bad-sidecar.yaml
```

Expected:

```text
DENIED
```

---

# 57. Ephemeral Container Test

Create trusted disposable Pod:

```bash
kubectl run debug-base \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never
```

Attempt:

```bash
kubectl debug \
  -n ai-platform \
  debug-base \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Cleanup:

```bash
kubectl delete pod \
  debug-base \
  -n ai-platform
```

---

# 58. Policy Controller Webhooks

Validating:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Mutating:

```bash
kubectl get mutatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Known selector:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml \
  | grep -nA6 -B6 \
    'webhooks.knative.dev/exclude'
```

---

# 59. Policy Controller Metrics Service

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

Validated port:

```text
9090
```

Endpoints:

```bash
kubectl get endpoints \
  policy-controller-webhook-metrics \
  -n cosign-system
```

---

# 60. Policy Controller Metrics Port-Forward

```bash
kubectl port-forward \
  -n cosign-system \
  svc/policy-controller-webhook-metrics \
  9090:9090
```

Metrics:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | head -n 50
```

Policy metrics:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_' \
  | head -n 100
```

Reconcile metric:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_reconcile_count'
```

---

# 61. ServiceMonitor

List:

```bash
kubectl get servicemonitor \
  -n monitoring
```

Inspect:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Validated GitOps file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

---

# 62. PrometheusRule

List:

```bash
kubectl get prometheusrule \
  -n monitoring
```

Inspect:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Validated GitOps file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Expected selector label:

```text
release: kps
```

---

# 63. Prometheus Queries

Target health:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Expected:

```text
1
```

Reconcile metric:

```promql
policy_controller_reconcile_count
```

Recent failures:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

By reconciler:

```promql
sum by (reconciler) (
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

Webhook cert failures:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

---

# 64. Prometheus Alerts

Target down:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
} == 0
```

Duration:

```text
5m
```

Severity:

```text
critical
```

Reconcile failures:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
) > 5
```

Duration:

```text
5m
```

Severity:

```text
warning
```

Webhook cert failures:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
) > 0
```

Duration:

```text
5m
```

Severity:

```text
critical
```

---

# 65. PrometheusRule Selector

Inspect Prometheus:

```bash
kubectl get prometheus \
  -n monitoring \
  -o yaml
```

Review:

```text
spec.ruleSelector
spec.ruleNamespaceSelector
```

Compare against:

```text
release: kps
```

---

# 66. Secret Presence

List Secret:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE>
```

List keys only:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE> \
  -o json \
  | jq -r '.data | keys[]'
```

Do not print secret values in shared logs.

---

# 67. Create/Update Runtime Secret

Representative:

```bash
kubectl create secret generic <SECRET_NAME> \
  -n <NAMESPACE> \
  --from-literal=<KEY1>="$VALUE1" \
  --from-literal=<KEY2>="$VALUE2" \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -
```

Values should come from Vault or the approved secure source.

Do not commit generated Secret YAML.

---

# 68. Secret References in Deployment

```bash
kubectl get deployment \
  <DEPLOYMENT> \
  -n <NAMESPACE> \
  -o yaml \
  | grep -A6 -B3 \
    'secretKeyRef\|secretName'
```

---

# 69. Vault Endpoint

Validated:

```text
https://vault.platform.local:8200
```

The exact auth method and secret paths must be read from the actual environment documentation.

Do not invent them.

---

# 70. Gitleaks

Source:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Expected:

```text
clean
```

---

# 71. Sensitive Files

Tracked PEM/key/JWT:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Tracked `.env`:

```bash
git ls-files \
  | grep -E '(^|/)\.env($|\.)'
```

Private key markers:

```bash
git grep -nE \
  'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
```

---

# 72. GitOps `.gitignore`

```bash
cd /mnt/data/ai-platform-gitops

cat .gitignore
```

Validated patterns include:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

No blanket:

```text
*.crt
```

---

# 73. Keycloak Realm Operations

Validated realm:

```text
ai-platform
```

Expected groups:

```text
platform-viewer
platform-deployer
platform-admin
```

Use the existing `kcadm-in-pod` wrapper where present.

Example group listing:

```bash
.local/keycloak/bin/kcadm-in-pod \
  get groups \
  -r ai-platform
```

Use actual wrapper path from the repo.

---

# 74. Keycloak Argo Client

Validated client:

```text
ai-platform-argocd
```

Inspect with KCADM:

```bash
.local/keycloak/bin/kcadm-in-pod \
  get clients \
  -r ai-platform \
  -q clientId=ai-platform-argocd
```

Expected:

```text
publicClient = true
standardFlowEnabled = true
directAccessGrantsEnabled = false
PKCE S256
```

---

# 75. Keycloak CLI Client

Validated:

```text
ai-platform-cli
```

Callback:

```text
http://127.0.0.1:18080/callback
```

PKCE login script:

```bash
python3 \
  infrastructure/keycloak/scripts/pkce-login.py
```

Use actual repo location if changed.

---

# 76. Keycloak Groups Mapper

Inspect client scopes:

```bash
.local/keycloak/bin/kcadm-in-pod \
  get client-scopes \
  -r ai-platform
```

Expected group-membership mapper under:

```text
groups
```

---

# 77. Argo OIDC Troubleshooting Access

If routine ingress access fails, bootstrap port-forward:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

Use break-glass credentials only as documented.

Restore OIDC and disable routine local admin again.

---

# 78. Git Rollback History

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Detailed:

```bash
git log \
  -p \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

---

# 79. Create Rollback Branch

```bash
git switch -c \
  rollback/<DESCRIPTION>
```

Revert:

```bash
git revert \
  <BAD_COMMIT>
```

Validate:

```bash
git diff --check
```

Render affected overlays.

Open GitOps PR.

---

# 80. Rollback PR

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head <ROLLBACK_BRANCH> \
  --title "revert(dev): <DESCRIPTION>" \
  --body "Restores the previous known-good digest-pinned deployment."
```

Checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --watch
```

Merge:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

---

# 81. Argo After Rollback

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Wait:

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

Verify live digest.

---

# 82. Policy Controller Logs

Pods:

```bash
kubectl get pods \
  -n cosign-system
```

Logs:

```bash
kubectl logs \
  -n cosign-system \
  <POLICY_CONTROLLER_POD> \
  --tail=300
```

---

# 83. Webhook Certificate Troubleshooting

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Inspect:

```text
service namespace
service name
caBundle
```

Query:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

---

# 84. Argo Drift

Refresh:

```bash
argocd app get \
  <APP> \
  --refresh
```

Diff:

```bash
argocd app diff \
  <APP>
```

If Git is correct:

```text
allow self-heal
```

If Git is wrong:

```text
fix Git first
```

---

# 85. Known Policy Controller Drift Selector

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

Search live:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml \
  | grep -nA6 -B6 \
    'webhooks.knative.dev/exclude'
```

Use narrow `ignoreDifferences` only.

---

# 86. Helm Inventory

All releases:

```bash
helm list -A
```

Policy Controller:

```bash
helm list \
  -n cosign-system
```

Monitoring:

```bash
helm list \
  -n monitoring
```

---

# 87. CRDs

List:

```bash
kubectl get crd
```

Sigstore:

```bash
kubectl get crd \
  | grep -E \
    'sigstore|policy'
```

Prometheus Operator:

```bash
kubectl get crd \
  | grep -E \
    'servicemonitors|prometheusrules|prometheuses'
```

---

# 88. RBAC Check

Generic:

```bash
kubectl auth can-i \
  <VERB> \
  <RESOURCE> \
  -n <NAMESPACE>
```

ServiceAccount:

```bash
kubectl auth can-i \
  <VERB> \
  <RESOURCE> \
  --as=system:serviceaccount:<NAMESPACE>:<SERVICE_ACCOUNT> \
  -n <NAMESPACE>
```

---

# 89. Resource Usage

If metrics server is available:

```bash
kubectl top nodes
```

Pods:

```bash
kubectl top pods \
  -A
```

AI Platform:

```bash
kubectl top pods \
  -n ai-platform
```

---

# 90. Docker Build

Operator:

```bash
cd /mnt/data/ai-platform-operator

docker build \
  -f Dockerfile \
  -t ai-platform-operator:test \
  .
```

API:

```bash
docker build \
  -f <API_DOCKERFILE> \
  -t ai-platform-api:test \
  .
```

Inspect user:

```bash
docker inspect \
  ai-platform-operator:test \
  --format '{{.Config.User}}'
```

Expected:

```text
65532
```

---

# 91. Docker History

```bash
docker history \
  ai-platform-operator:test
```

Use to verify multi-stage/minimal final image.

Validated runtime base:

```text
gcr.io/distroless/static-debian13:nonroot
```

---

# 92. Go Commands

Version:

```bash
go version
```

Modules:

```bash
go mod tidy
```

Tests:

```bash
go test ./...
```

Vet:

```bash
go vet ./...
```

Vulnerability scan:

```bash
govulncheck ./...
```

---

# 93. Git Traceability

Current SHA:

```bash
git rev-parse HEAD
```

Remote main:

```bash
git rev-parse origin/main
```

Last commit:

```bash
git log -1 \
  --oneline
```

Show source SHA:

```bash
git show \
  --no-patch \
  <SOURCE_SHA>
```

---

# 94. Promotion Traceability

GitOps promotion history:

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/operator/overlays/dev/kustomization.yaml \
     platform/api/overlays/dev/kustomization.yaml
```

Expected commit pattern:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 95. GitHub Commit Lookup

Source:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/commits/<SOURCE_SHA> \
  --jq '{
    sha,
    message: .commit.message,
    author: .commit.author.name
  }'
```

GitOps:

```bash
gh api \
  repos/anselem-okeke/ai-platform-gitops/commits/<GITOPS_SHA> \
  --jq '{
    sha,
    message: .commit.message,
    author: .commit.author.name
  }'
```

---

# 96. Gateway DNS/TLS Quick Checks

Host resolution:

```bash
getent hosts \
  api.ai-platform.local
```

Argo:

```bash
getent hosts \
  argocd.ai-platform.local
```

Keycloak:

```bash
getent hosts \
  auth.ai-platform.local
```

TLS detail:

```bash
openssl s_client \
  -connect api.ai-platform.local:443 \
  -servername api.ai-platform.local
```

Use only if `openssl` is available on the operator workstation.

---

# 97. Kubernetes API Service

```bash
kubectl get svc \
  kubernetes \
  -n default
```

Validated ClusterIP:

```text
10.96.0.1
```

CoreDNS:

```bash
kubectl get svc \
  -n kube-system
```

Validated CoreDNS Service IP:

```text
10.96.0.10
```

These are diagnostic details, not application configuration targets.

---

# 98. GitHub App Known Permissions

Expected:

```text
Contents:
Read & write

Pull requests:
Read & write

Metadata:
Read
```

Installation scope:

```text
ai-platform-gitops
```

Bot identity:

```text
ai-platform-gitops-bot[bot]
```

---

# 99. Known Action Pins

CodeQL:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

actions/attest:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

create-github-app-token:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Verify actual workflows before upgrading.

---

# 100. Quick Platform Health Sequence

Run in order:

```bash
kubectl config current-context
```

```bash
kubectl get nodes
```

```bash
kubectl get pods -A
```

```bash
argocd app list
```

```bash
kubectl get validatingadmissionpolicies
```

```bash
kubectl get validatingadmissionpolicybindings
```

```bash
kubectl get trustroots.policy.sigstore.dev
```

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Then verify:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Expected:

```text
1
```

---

# 101. Quick Release Validation Sequence

```bash
gh pr checks <SOURCE_PR> \
  --repo anselem-okeke/ai-platform-operator
```

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

```bash
gh pr checks <GITOPS_PR> \
  --repo anselem-okeke/ai-platform-gitops
```

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

---

# 102. Quick Admission Validation Sequence

Trusted:

```bash
kubectl run quick-good \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Mutable:

```bash
kubectl run quick-bad-tag \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Public:

```bash
kubectl run quick-nginx \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Fake digest:

```bash
kubectl run quick-fake \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
trusted -> allowed
mutable -> denied
public -> denied
fake digest -> denied
```

---

# 103. Quick Recovery Sequence

Check GitOps main:

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main
```

Render:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/recovery-api.yaml
```

Compare live:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Check Argo:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Rollback through Git if needed.

---

# 104. What Must Be Verified from the Actual Repositories

Do not treat placeholders in this command reference as exact production values.

Verify:

```text
exact operator Deployment name
exact API health endpoint
exact Argo child Application names
exact GitHub Actions secret names
exact GitHub Actions variable names
exact kind config filename
exact Keycloak helper path
exact native policy names
exact Gateway resource names
exact Vault secret paths
```

Source inspection:

```bash
cd /mnt/data/ai-platform-operator

find .github/workflows \
  -maxdepth 1 \
  -type f \
  -print \
  | sort

sed -n '1,520p' \
  .github/workflows/release-images.yml
```

GitOps inspection:

```bash
cd /mnt/data/ai-platform-gitops

find argocd \
  clusters \
  platform \
  modelservices \
  -maxdepth 4 \
  -type f \
  -print \
  | sort

sed -n '1,500p' \
  .github/workflows/validate.yml
```

The repositories and live cluster remain the exact implementation source of truth.

---

# 105. References

kubectl command reference:

```text
https://kubernetes.io/docs/reference/kubectl/
```

Argo CD CLI:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd/
```

GitHub CLI:

```text
https://cli.github.com/manual/
```

Helm:

```text
https://helm.sh/docs/helm/
```

Prometheus query language:

```text
https://prometheus.io/docs/prometheus/latest/querying/basics/
```
