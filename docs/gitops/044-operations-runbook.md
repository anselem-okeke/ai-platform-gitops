# Operations Runbook

## Purpose

This document is the **day-to-day operations runbook** for the AI Platform.

It is written for an engineer who needs to operate the platform safely after Phase 7 is already implemented.

It focuses on the commands and operating sequences used to:

```text
check platform health
inspect Argo CD
verify GitOps state
verify live image digests
inspect Policy Controller
test admission controls
inspect monitoring
verify alerts
operate Keycloak/Argo access
review source and GitOps delivery
rotate credentials
perform safe rollbacks
recover from drift
prepare for maintenance
verify the platform after upgrades
```

The operating principle is:

> **Git remains the deployment source of truth, and security controls remain enabled during normal operations.**

Do not normalize:

```text
direct kubectl deployment
mutable image tags
manual cluster drift
disabled admission
long-lived cross-repository tokens
plaintext secrets in Git
```

---

# 1. Working Directories

## Source repository

```text
/mnt/data/ai-platform-operator
```

Use for:

```text
application source
operator source
source CI
release workflow
container builds
security scans
GitHub App promotion automation
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

Use for:

```text
desired deployment state
Argo Applications
Kustomize overlays
admission policy
monitoring
namespace configuration
rollback
```

---

# 2. Core Environment

Validated development cluster:

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

Core platform endpoints:

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

# 3. Start-of-Day Platform Check

Run:

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

Then:

```bash
kubectl get nodes
```

Expected:

```text
all nodes Ready
```

Then:

```bash
kubectl get pods -A
```

Scan for:

```text
CrashLoopBackOff
ImagePullBackOff
ErrImagePull
Pending
Error
```

Do not assume one failing Pod is harmless until its component is identified.

---

# 4. Fast Namespace Health Check

Run:

```bash
kubectl get pods \
  -n ai-platform
```

Then:

```bash
kubectl get pods \
  -n ai-platform-operator-system
```

Then:

```bash
kubectl get pods \
  -n argocd
```

Then:

```bash
kubectl get pods \
  -n cosign-system
```

Then:

```bash
kubectl get pods \
  -n monitoring
```

Then:

```bash
kubectl get pods \
  -n keycloak
```

Expected:

```text
core platform pods Running/Ready
```

---

# 5. Argo CD Daily Health Check

List applications:

```bash
argocd app list
```

Inspect:

```text
SYNC STATUS
HEALTH STATUS
REVISION
```

Expected for child applications:

```text
Synced
Healthy
```

The root Application is intentionally more privileged and remains manually controlled.

---

# 6. Inspect Root Application

```bash
argocd app get \
  ai-platform-root \
  --refresh
```

The root Application manages topology.

Review its diff before syncing:

```bash
argocd app diff \
  ai-platform-root
```

Do not automatically sync topology changes without review.

---

# 7. Inspect API Application

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Expected:

```text
Synced
Healthy
```

If OutOfSync:

```bash
argocd app diff \
  ai-platform-api
```

---

# 8. Inspect Operator Application

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

Then:

```bash
argocd app diff \
  ai-platform-operator
```

Expected:

```text
no unintended drift
```

---

# 9. Inspect Policy Controller Application

```bash
argocd app get \
  policy-controller \
  --refresh
```

Expected:

```text
Synced
Healthy
```

If OutOfSync, inspect the diff before changing anything.

The known acceptable controller-managed webhook mutation involves:

```text
webhooks.knative.dev/exclude
```

Only that exact field should be ignored where configured.

---

# 10. Inspect Trust Policies Application

```bash
argocd app get \
  trust-policies \
  --refresh
```

Expected:

```text
Synced
Healthy
```

Validated trust-policy chart:

```text
v0.7.0
```

---

# 11. Inspect Monitoring Application

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

Use the actual current Application name if it differs.

Expected:

```text
Synced
Healthy
```

---

# 12. Verify Live API Digest

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected format:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>
```

Mutable tags are not acceptable as final deployment identity.

---

# 13. Verify Live Operator Digest

Discover exact Deployment:

```bash
kubectl get deployment \
  -n ai-platform-operator-system
```

Then:

```bash
kubectl get deployment \
  <OPERATOR_DEPLOYMENT> \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<64hex>
```

---

# 14. Compare GitOps to Live API

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/ops-api.yaml
```

Inspect:

```bash
grep -n \
  'image:' \
  /tmp/ops-api.yaml
```

Compare to live:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

They must match.

---

# 15. Compare GitOps to Live Operator

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/ops-operator.yaml
```

Inspect:

```bash
grep -n \
  'image:' \
  /tmp/ops-operator.yaml
```

Compare to live Deployment image.

---

# 16. Verify Argo Revision

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

Compare with:

```bash
cd /mnt/data/ai-platform-gitops

git rev-parse origin/main
```

The current Argo revision should correspond to GitOps desired state.

---

# 17. Routine GitOps Repository Update

Before editing:

```bash
cd /mnt/data/ai-platform-gitops

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Create a feature branch:

```bash
git switch -c feat/<DESCRIPTION>
```

Make only intended changes.

---

# 18. Render Before Every GitOps Commit

For API:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

For operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

For monitoring:

```bash
kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

For policies:

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

---

# 19. Validate Rendered Manifests

Use validated kubeconform version:

```text
0.7.0
```

Run:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/api.yaml
```

Repeat for changed components.

Then:

```bash
git diff --check
```

---

# 20. Use Server Dry-Run for Cluster-Aware Validation

For installed APIs/CRDs:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml
```

Do the same for other rendered output when useful.

This detects:

```text
invalid fields
missing CRDs
admission rejection
API compatibility issues
```

before merge.

---

# 21. Open GitOps Pull Request

After commit/push:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head <BRANCH> \
  --title "<TITLE>" \
  --body "<DESCRIPTION>"
```

Check:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --watch
```

Required check:

```text
Validate GitOps Manifests
```

---

# 22. Merge GitOps Change

Merge only when:

```text
render correct
kubeconform passes
GitOps CI passes
diff reviewed
```

Then:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

Argo will reconcile child Applications automatically.

---

# 23. Observe Argo After GitOps Merge

Refresh:

```bash
argocd app get \
  <CHILD_APP> \
  --refresh
```

Wait:

```bash
argocd app wait \
  <CHILD_APP> \
  --sync \
  --health \
  --timeout 300
```

If it fails, inspect:

```bash
argocd app diff \
  <CHILD_APP>
```

and Kubernetes events.

---

# 24. Routine Source Repository Update

```bash
cd /mnt/data/ai-platform-operator

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Create branch:

```bash
git switch -c feat/<DESCRIPTION>
```

Run local source checks before push.

---

# 25. Run Source Validation Locally

```bash
make lint-config
make lint
make test
go vet ./...
govulncheck ./...
gitleaks git --redact
```

Expected:

```text
all pass
```

Interpret govulncheck correctly:

```text
0 reachable vulnerabilities
```

---

# 26. Open Source Pull Request

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-operator \
  --base main \
  --head <BRANCH> \
  --title "<TITLE>" \
  --body "<DESCRIPTION>"
```

Wait for:

```text
Gitleaks
Lint
E2E
Tests
govulncheck
CodeQL
```

---

# 27. Verify Source PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator \
  --watch
```

Do not merge if any required check fails.

---

# 28. Verify Source Ruleset Periodically

Validated ruleset:

```text
Source Main Protection
ID 21120105
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Expected:

```text
active
PR required
no bypass
deletion blocked
non-fast-forward blocked
required checks present
```

---

# 29. Merge Source Change

After checks pass:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator \
  --merge
```

This triggers the release workflow on main push.

---

# 30. Monitor Release Workflow

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --workflow release-images.yml \
  --limit 10
```

Inspect:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

Watch:

```bash
gh run watch <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

---

# 31. Confirm Release SHA

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --json headSha,event,status,conclusion
```

Expected:

```text
event = push
headSha = merged main SHA
```

---

# 32. Confirm Trivy Gate

Validated release policy:

```text
HIGH,CRITICAL
ignore-unfixed
exit code 1
```

If Trivy fails:

```text
release should stop
GitOps promotion should not occur
```

Do not weaken the gate for convenience.

---

# 33. Confirm SBOM and Attestation

Inspect release logs for:

```text
SPDX JSON SBOM
provenance attestation
SBOM attestation
```

Validated attestation action:

```text
actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

The subject digest must match the pushed image digest.

---

# 34. Confirm GitHub App Promotion

Expected bot:

```text
ai-platform-gitops-bot[bot]
```

Expected branch:

```text
automation/image-<SOURCE_SHA>
```

Expected GitOps files updated:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Expected PR title:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 35. Inspect Release-Created GitOps PR

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --head "automation/image-${SOURCE_SHA}"
```

Then:

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Review:

```text
exact source SHA
operator digest
API digest
only two expected files
```

---

# 36. Never Auto-Merge Promotion PR

The current operating model is:

```text
automation creates PR
human reviews
human merges
```

This is the promotion authorization boundary.

Do not merge automatically unless governance changes intentionally.

---

# 37. Verify Promotion Diff

Fetch branch:

```bash
cd /mnt/data/ai-platform-gitops

git fetch origin \
  "automation/image-${SOURCE_SHA}"
```

Run:

```bash
git diff \
  --name-only \
  origin/main...FETCH_HEAD \
  | sort
```

Expected exactly two files.

---

# 38. Verify Digests Before Merge

Inspect:

```bash
git show \
  FETCH_HEAD:platform/operator/overlays/dev/kustomization.yaml
```

and:

```bash
git show \
  FETCH_HEAD:platform/api/overlays/dev/kustomization.yaml
```

Expected:

```text
digest: sha256:<64hex>
```

Do not accept final `newTag:` deployment identity.

---

# 39. Verify Admission Infrastructure

Native policies:

```bash
kubectl get validatingadmissionpolicies
```

Bindings:

```bash
kubectl get validatingadmissionpolicybindings
```

Sigstore:

```bash
kubectl get trustroots.policy.sigstore.dev
```

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Expected:

```text
TrustRoot github
ClusterImagePolicy github-policy
```

---

# 40. Verify Policy Controller Version

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

# 41. Verify Trust Policies Version

```bash
helm list \
  -n cosign-system
```

Expected:

```text
trust-policies v0.7.0
```

If Argo manages it:

```bash
argocd app get \
  trust-policies
```

---

# 42. Verify Protected Namespace Labels

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

---

# 43. Routine Positive Admission Test

Use live trusted API image:

```bash
API_IMAGE="$(kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}')"
```

Test:

```bash
kubectl run ops-positive \
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

# 44. Routine Mutable-Tag Negative Test

```bash
kubectl run ops-bad-tag \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Run this after policy changes or upgrades.

---

# 45. Routine Public-Image Negative Test

```bash
kubectl run ops-nginx \
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

# 46. Routine Fake-Digest Negative Test

```bash
kubectl run ops-fake-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Validated trust failure:

```text
no valid bundles exist in registry
```

---

# 47. Periodic Init-Container Negative Test

Create:

```bash
cat >/tmp/ops-bad-init.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: ops-bad-init
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

Test:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/ops-bad-init.yaml
```

Expected:

```text
DENIED
```

---

# 48. Periodic Ephemeral-Container Test

Create disposable trusted Pod:

```bash
kubectl run ops-debug-base \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never
```

Attempt:

```bash
kubectl debug \
  -n ai-platform \
  ops-debug-base \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Cleanup:

```bash
kubectl delete pod \
  ops-debug-base \
  -n ai-platform
```

---

# 49. Verify Policy Controller Metrics Service

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

Validated metrics port:

```text
9090
```

---

# 50. Direct Metrics Inspection

Port-forward:

```bash
kubectl port-forward \
  -n cosign-system \
  svc/policy-controller-webhook-metrics \
  9090:9090
```

Then:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_' \
  | head -n 80
```

Expected:

```text
metrics present
```

---

# 51. Verify Prometheus Target

Query:

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

This has already been validated in the current implementation.

---

# 52. Verify Reconcile Metrics

Query:

```promql
policy_controller_reconcile_count
```

Expected:

```text
non-empty
```

For recent failures:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

---

# 53. Verify Webhook Certificate Health

Query:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

Healthy:

```text
0
```

Any sustained failure deserves immediate investigation.

---

# 54. Verify PrometheusRule

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Expected label:

```yaml
metadata:
  labels:
    release: kps
```

Expected alert rules:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

---

# 55. Inspect Policy Controller Logs

Discover Pod:

```bash
kubectl get pods \
  -n cosign-system
```

Then:

```bash
kubectl logs \
  -n cosign-system \
  <POLICY_CONTROLLER_POD> \
  --tail=300
```

Use this for:

```text
trust failures
reconciliation problems
webhook certificate errors
```

---

# 56. Inspect API Logs

```bash
kubectl get pods \
  -n ai-platform
```

Then:

```bash
kubectl logs \
  -n ai-platform \
  <API_POD> \
  --tail=300
```

For restarting Pods:

```bash
kubectl logs \
  -n ai-platform \
  <API_POD> \
  --previous
```

---

# 57. Inspect Operator Logs

```bash
kubectl get pods \
  -n ai-platform-operator-system
```

Then:

```bash
kubectl logs \
  -n ai-platform-operator-system \
  <OPERATOR_POD> \
  --tail=300
```

Use for reconciliation failures.

---

# 58. Inspect Kubernetes Events

Cluster-wide:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp
```

Namespace-specific:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

Look for:

```text
FailedCreate
FailedMount
admission denied
ImagePullBackOff
CrashLoopBackOff
```

---

# 59. Operate Argo Access Securely

Bootstrap/local access:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

Routine access should use:

```text
https://argocd.ai-platform.local
```

through Gateway + TLS + Keycloak OIDC.

Do not convert Argo server to public LoadBalancer exposure.

---

# 60. Verify Keycloak Group Model

Expected groups:

```text
platform-viewer
platform-deployer
platform-admin
```

Verify users/groups with the project KCADM wrapper/scripts.

Do not manage routine access through local Argo users.

---

# 61. Verify Argo OIDC Client

Validated client:

```text
ai-platform-argocd
```

Characteristics:

```text
public client
standard flow enabled
direct access grants disabled
PKCE S256
groups claim
```

This client intentionally does not depend on a client secret.

---

# 62. Operate CLI PKCE Login

Validated CLI client:

```text
ai-platform-cli
```

Redirect:

```text
http://127.0.0.1:18080/callback
```

Use the existing:

```text
infrastructure/keycloak/scripts/pkce-login.py
```

if present in the current source tree.

Do not switch to password/direct grants for convenience.

---

# 63. Secret Handling During Operations

Vault remains the runtime secret source of truth:

```text
https://vault.platform.local:8200
```

Do not store secret values in Git.

Kubernetes workloads may consume:

```text
Kubernetes Secret
```

objects provisioned outside Git.

Do not claim External Secrets or Vault CSI automation unless installed and verified.

---

# 64. Verify Secret Presence Without Printing Values

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

Avoid:

```bash
kubectl get secret -o yaml
```

in logs.

---

# 65. Rotate Runtime Secret

Generic sequence:

```text
1. create/rotate value in Vault
2. update Kubernetes Secret
3. restart/reload workload if required
4. verify authentication
5. revoke old credential
```

If dual credentials are supported:

```text
add new
deploy
verify
revoke old
```

---

# 66. Update Kubernetes Secret Without Writing YAML to Disk

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

Do not commit this generated Secret.

---

# 67. Restart Workload After Secret Rotation

If the application reads secrets only on startup:

```bash
kubectl rollout restart \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE>
```

Then:

```bash
kubectl rollout status \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE> \
  --timeout=300s
```

---

# 68. Rotate GitHub App Private Key

Sequence:

```text
1. generate new key in GitHub App settings
2. update exact GitHub Actions Secret
3. run controlled release/token test
4. verify GitOps branch + PR creation
5. revoke old key
6. remove local copies
```

Do not revoke old key before validating the new one.

---

# 69. Verify GitHub App Token Flow After Rotation

Run a controlled source release.

Expected:

```text
token creation succeeds
GitOps clone succeeds
automation branch created
PR opened
```

Do not print the token.

---

# 70. Run Secret Scans Periodically

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

# 71. Check Sensitive Extensions

Source:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Review any matches manually.

---

# 72. Check `.env` Files

```bash
git ls-files \
  | grep -E '(^|/)\.env($|\.)'
```

Real secret-bearing `.env` files should not be tracked.

---

# 73. Inspect GitOps `.gitignore`

```bash
cd /mnt/data/ai-platform-gitops

cat .gitignore
```

Expected protective patterns include:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

Do not broadly ignore:

```text
*.crt
```

without need.

---

# 74. Daily Gateway Check

Inspect:

```bash
kubectl get gateway \
  -A
```

Then:

```bash
kubectl get httproute \
  -A
```

Validated Gateway LB:

```text
172.19.255.200
```

---

# 75. Verify API Route

Use the actual health/status endpoint.

Representative:

```bash
curl -vk \
  https://api.ai-platform.local/
```

Prefer a real health endpoint if implemented.

Check:

```text
DNS
TLS
Gateway
HTTPRoute
Service
Pod
```

---

# 76. Verify Argo Route

```text
https://argocd.ai-platform.local
```

Expected:

```text
TLS valid
Keycloak login
group-based authorization
```

Do not use insecure TLS flags in routine operation.

---

# 77. Verify Keycloak Route

```text
https://auth.ai-platform.local
```

Check:

```text
TLS
realm availability
login page
OIDC endpoints
```

---

# 78. Verify Gateway TLS

Inspect Gateway listener:

```bash
kubectl get gateway \
  -A \
  -o yaml
```

Confirm:

```text
hostname
TLS mode
certificateRef
```

Do not disable TLS verification to work around certificate errors.

---

# 79. Routine Rollout Inspection

API:

```bash
kubectl rollout status \
  deployment/ai-platform-api \
  -n ai-platform \
  --timeout=300s
```

Operator:

```bash
kubectl rollout status \
  deployment/<OPERATOR_DEPLOYMENT> \
  -n ai-platform-operator-system \
  --timeout=300s
```

---

# 80. Routine Pod Resource Inspection

```bash
kubectl top pods \
  -n ai-platform
```

If metrics server is available.

Also:

```bash
kubectl top pods \
  -n ai-platform-operator-system
```

Use this to spot obvious resource pressure.

---

# 81. Inspect Deployment Replica Health

API:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform
```

Expected:

```text
READY == desired replicas
AVAILABLE == desired replicas
```

Operator:

```bash
kubectl get deployment \
  -n ai-platform-operator-system
```

---

# 82. Operate Drift Recovery

If Argo detects manual drift:

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
fix Git
merge PR
let Argo reconcile
```

Do not preserve manual live-state changes as permanent state.

---

# 83. Safe Manual Drift Test

Use a non-security-critical field of a disposable or low-risk resource.

Do not test drift by changing:

```text
admission policy
image trust
webhook certificates
secret values
```

Observe:

```text
OutOfSync
self-heal
Synced
```

---

# 84. Operate Git Rollback

Identify promotion history:

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Create rollback branch:

```bash
git switch -c \
  rollback/<DESCRIPTION>
```

Revert:

```bash
git revert <BAD_COMMIT>
```

Render, validate, open PR, merge.

---

# 85. Verify Rollback Before Merge

Render:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/rollback-api.yaml
```

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/rollback-operator.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/rollback-api.yaml \
  /tmp/rollback-operator.yaml
```

Then:

```bash
git diff --check
```

---

# 86. Verify Rollback After Merge

API:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
previous trusted digest
```

Admission must remain enabled during rollback.

---

# 87. Do Not Use Manual Image Rollback

Avoid:

```bash
kubectl set image
```

for normal rollback.

Avoid mutable historical tags.

Correct rollback:

```text
Git revert
-> GitOps PR
-> merge
-> Argo
```

---

# 88. Operate Policy Controller Upgrade

Before upgrade, record:

```bash
helm list \
  -n cosign-system
```

Record current:

```text
policy-controller 0.10.6
```

Check:

```text
CRDs
webhook configs
TrustRoot
ClusterImagePolicy
metrics
```

---

# 89. Validate Policy Controller Upgrade in Git First

Update Argo Application target revision in GitOps.

Render App-of-Apps:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps-upgrade.yaml
```

Validate.

Open GitOps PR.

Do not run an ad hoc second Helm release.

---

# 90. Observe Policy Controller Upgrade

Watch:

```bash
kubectl get pods \
  -n cosign-system \
  -w
```

Then:

```bash
argocd app get \
  policy-controller \
  --refresh
```

Verify:

```text
Synced
Healthy
```

---

# 91. Re-run Admission Tests After Policy Upgrade

Run:

```text
trusted digest -> allow
mutable tag -> deny
nginx:latest -> deny
fake digest -> deny
bad init -> deny
ephemeral nginx -> deny
```

Do not assume an upgrade preserved behavior.

---

# 92. Re-run Metrics Validation After Policy Upgrade

Check:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

Port:

```text
9090
```

Query:

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

# 93. Check Metrics Names After Upgrade

Inspect:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_'
```

Verify:

```text
policy_controller_reconcile_count
success label
reconciler label
WebhookCertificates value
```

Update Prometheus rules only if upstream changed metrics.

---

# 94. Operate Trust Policy Upgrade

Before changing:

```bash
kubectl get trustroot \
  github \
  -o yaml
```

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Record current behavior with positive/negative admission tests.

Then update the GitOps-managed chart version.

---

# 95. Verify Trust Policy Image Scope After Upgrade

Expected first-party scope:

```text
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**
```

Do not broaden trust unintentionally.

---

# 96. Operate Monitoring Changes

Edit:

```text
platform/monitoring/
```

Render:

```bash
kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring-change.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/monitoring-change.yaml
```

Server dry-run if CRDs exist.

---

# 97. Verify ServiceMonitor After Monitoring Change

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Confirm:

```text
namespaceSelector = cosign-system
selector matches metrics Service
port name correct
```

---

# 98. Verify PrometheusRule After Monitoring Change

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Confirm:

```text
release: kps
```

and three current alerts.

---

# 99. Operate AppProject Changes

AppProject is bootstrap-managed.

Edit:

```text
argocd/projects/ai-platform.yaml
```

Validate:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Apply manually:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Do not wait for Argo to reconcile the AppProject itself.

---

# 100. Keep AppProject Permissions Narrow

When adding a new resource type, allow only the exact:

```text
group
kind
destination
repository
```

Avoid:

```yaml
group: '*'
kind: '*'
```

unless explicitly justified.

---

# 101. Operate Root Topology Changes

Changes under:

```text
clusters/dev/apps/
clusters/dev/root-application.yaml
```

are privileged.

Render:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Review all new/deleted Applications.

Root remains manual sync.

---

# 102. Inspect Root Diff Before Sync

```bash
argocd app diff \
  ai-platform-root
```

Review:

```text
Application added
Application removed
repoURL changed
targetRevision changed
destination changed
Helm chart changed
```

Then sync only after approval:

```bash
argocd app sync \
  ai-platform-root
```

---

# 103. Operate Namespace Changes

Namespace definitions are GitOps-managed.

Before changing enforcement labels, understand security impact.

Example:

```yaml
policy.sigstore.dev/include: "true"
```

Removing this from:

```text
ai-platform
ai-platform-operator-system
```

weakens Sigstore enforcement.

Treat as security-sensitive.

---

# 104. Routine Repository Traceability Check

Source:

```bash
cd /mnt/data/ai-platform-operator

git log -1 \
  --oneline
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git log -1 \
  --oneline
```

Promotion commit should link back to source SHA:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 105. Verify Bot Commit Identity

```bash
git show \
  --no-patch \
  --format=fuller \
  <PROMOTION_COMMIT>
```

Expected:

```text
ai-platform-gitops-bot[bot]
```

If not, inspect release automation.

---

# 106. Review Open Promotion PRs

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

Look for stale:

```text
automation/image-*
```

branches.

Do not merge an older promotion after a newer release unless intentionally rolling back.

---

# 107. Close Superseded Promotion PR

If an older PR is obsolete:

```bash
gh pr close <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Leave clear reason:

```text
superseded by newer release
```

if useful.

---

# 108. Operate Release Failure

If release fails:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

Logs:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --log
```

Identify first failed job.

Do not rerun blindly before understanding whether source, scan, attestation, or GitOps automation failed.

---

# 109. Re-run Failed Workflow

After fixing the cause, prefer a new source commit when code/workflow changed.

If failure was transient infrastructure and rerun is appropriate:

```bash
gh run rerun <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator
```

Confirm resulting image digest and GitOps PR still correspond to intended source SHA.

---

# 110. Operate GitOps CI Failure

Inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Reproduce locally:

```text
Kustomize
kubeconform
image validation
secret check
git diff --check
```

Fix Git, not the CI gate.

---

# 111. Operate Argo Sync Failure

Inspect:

```bash
argocd app get \
  <APP>
```

Then:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp
```

Identify:

```text
admission denial
Secret missing
image pull failure
schema error
resource permission issue
```

---

# 112. Do Not Disable Admission for Failed Sync

If Argo sync is blocked by admission:

```text
fix the image/policy/trust problem
```

Do not disable:

```text
ValidatingAdmissionPolicy
Policy Controller
namespace enforcement
```

to force the rollout.

---

# 113. Operate ImagePullBackOff

Describe Pod:

```bash
kubectl describe pod \
  -n <NAMESPACE> \
  <POD>
```

Check:

```text
digest exists
GHCR pull access
registry credentials
network
```

Admission success and registry pull success are separate checks.

---

# 114. Operate CrashLoopBackOff

Logs:

```bash
kubectl logs \
  -n <NAMESPACE> \
  <POD> \
  --previous
```

Describe:

```bash
kubectl describe pod \
  -n <NAMESPACE> \
  <POD>
```

Decide whether issue is:

```text
application regression
missing Secret
bad config
dependency outage
```

If release regression, prefer Git rollback.

---

# 115. Operate Secret-Related Pod Failure

Events:

```bash
kubectl get events \
  -n <NAMESPACE> \
  --sort-by=.lastTimestamp
```

If Secret missing:

```text
restore from Vault
```

If key missing:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE> \
  -o json \
  | jq -r '.data | keys[]'
```

---

# 116. Operate Vault Availability Issue

Vault:

```text
https://vault.platform.local:8200
```

If unavailable:

```text
do not replace secrets with Git values
```

Restore Vault connectivity or use approved break-glass recovery.

Document any manual temporary secret provisioning.

---

# 117. Operate GitHub App `Not Found`

Known real failure.

Check:

```text
App installation
repo included
owner
repository
App ID/Client ID
private key
Contents permission
PR permission
```

Expected target repo:

```text
ai-platform-gitops
```

---

# 118. Operate Policy Controller CRD Ownership Conflict

Check:

```bash
helm list -A \
  | grep policy-controller
```

Expected:

```text
one release
namespace cosign-system
```

Do not install second release in:

```text
artifact-attestations
```

The CRDs are cluster-scoped and owned by the existing release.

---

# 119. Operate Policy Controller Webhook Drift

Inspect:

```bash
argocd app diff \
  policy-controller
```

Known controller-managed selector:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

Only ignore that exact mutation.

---

# 120. Operate Prometheus Target Failure

Query:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

If `0`:

```bash
kubectl get endpoints \
  policy-controller-webhook-metrics \
  -n cosign-system
```

If no series:

```text
ServiceMonitor discovery may be broken
```

---

# 121. Operate Missing PrometheusRule

Check:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring
```

If resource exists but rules missing from Prometheus:

```text
verify release: kps
verify ruleSelector
verify ruleNamespaceSelector
```

---

# 122. Operate Alert Investigation

For reconcile failures:

```promql
sum by (reconciler) (
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

For webhook cert failures:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

Investigate actual failing reconciler before changing thresholds.

---

# 123. Routine Backup/Recovery Readiness

Git is not enough for secrets.

Recovery planning must include:

```text
Vault backup/recovery
GitHub App key regeneration
GitHub Actions Secrets recreation
TLS private key/certificate recovery
runtime Kubernetes Secret recreation
```

Keep these processes tested and documented.

---

# 124. Rebuild Drill

Periodically perform the documented rebuild in a disposable environment.

Use:

```text
042-disaster-recovery-and-rebuild.md
```

Validate:

```text
Argo
AppProject
root
children
Policy Controller
trust
monitoring
secrets
admission
delivery path
```

---

# 125. Pre-Maintenance Snapshot

Before major change, record:

```bash
kubectl get pods -A
```

```bash
argocd app list
```

```bash
helm list -A
```

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
kubectl get trustroots.policy.sigstore.dev
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Record API/operator digests.

---

# 126. Pre-Upgrade Source State

Source:

```bash
cd /mnt/data/ai-platform-operator

git rev-parse HEAD
git status --short
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git rev-parse HEAD
git status --short
```

Keep both SHAs.

---

# 127. Post-Maintenance Validation

After maintenance:

```text
Argo apps Synced/Healthy
API/operator rollouts healthy
live digests match Git
trusted image allowed
mutable/public image denied
fake digest denied
Policy Controller target up=1
reconcile metrics present
```

Run exact commands from earlier sections.

---

# 128. Change Record

For significant operations, record:

```text
date/time
operator
source SHA
GitOps SHA
component changed
old version/digest
new version/digest
PR number
validation result
rollback target
```

Do not include credentials.

---

# 129. Incident Record

For incidents, capture:

```text
first observed symptom
first failed layer
affected component
Git/source revision
live digest
Argo state
admission result
root cause
fix
rollback performed or not
follow-up action
```

Keep the record factual.

---

# 130. Trace a Release During Incident

Start from GitOps promotion commit:

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Find source SHA from message.

Then:

```bash
cd /mnt/data/ai-platform-operator

git show \
  --no-patch \
  <SOURCE_SHA>
```

Then locate GitHub release run.

---

# 131. Operate Stale Drift

If Argo reports old drift after controller mutations, refresh:

```bash
argocd app get \
  <APP> \
  --refresh
```

Then:

```bash
argocd app diff \
  <APP>
```

Do not rely on cached UI state alone.

---

# 132. Operate Kustomize Patch Failure

If:

```text
no resource matches strategic merge patch
```

inspect:

```text
apiVersion
kind
name
namespace
base content
patch target
```

Do not add broad patches until identity matches.

---

# 133. Operate Server Dry-Run Failure

If:

```bash
kubectl apply \
  --dry-run=server \
  -f <FILE>
```

fails, classify:

```text
schema error
missing CRD
admission denial
RBAC/permission
```

This is a useful pre-merge signal.

---

# 134. Operate AppProject Denial

If Argo reports resource not permitted:

```bash
sed -n '1,360p' \
  /mnt/data/ai-platform-gitops/argocd/projects/ai-platform.yaml
```

Add only exact group/kind/destination.

Apply manually after server dry-run.

---

# 135. Operate Unexpected Prune

If Argo wants to delete a resource unexpectedly:

```bash
argocd app diff \
  <APP>
```

Inspect Git history and rendered output.

Do not approve/sync blindly.

Whole-resource destructive prune has not been exhaustively validated in the current project.

---

# 136. Operate Missing CRD

Check:

```bash
kubectl get crd \
  | grep <NAME>
```

If missing, restore the owning controller/chart first.

Do not apply CRD-dependent custom resources before the CRD exists.

---

# 137. Operate Image Trust Scope Expansion

When adding a new first-party image:

```text
add exact repository to trust policy
add exact native admission allowlist
update GitOps CI image validation
update tests
```

Do not broaden all three controls globally.

---

# 138. Verify New First-Party Image

After adding:

```text
trusted digest -> allow
mutable tag -> deny
fake digest -> deny
unrelated repo -> deny
```

This confirms narrow expansion.

---

# 139. Operate Monitoring Expansion

When adding a new security-critical controller:

```text
identify metrics service
create ServiceMonitor
verify target up
identify failure metrics
create PrometheusRule
validate selector
```

Follow the same model used for Policy Controller.

---

# 140. Operate Source Dependency Upgrade

Before merge:

```bash
go test ./...
go vet ./...
govulncheck ./...
```

Then normal PR CI.

After release:

```text
Trivy
SBOM
attestation
GitOps promotion
admission
runtime
```

must still pass.

---

# 141. Operate Base Image Upgrade

Update Dockerfile intentionally.

Build locally.

Inspect runtime user:

```bash
docker inspect \
  <IMAGE> \
  --format '{{.Config.User}}'
```

Expected:

```text
65532
```

Run Trivy.

Then release normally.

---

# 142. Operate Go Version Upgrade

Current validated:

```text
Go 1.26.6
```

When upgrading:

```text
update CI
update Docker builder
run tests
run govulncheck
verify dependencies
verify reproducible build
```

Keep workflow and Dockerfile aligned.

---

# 143. Operate Security Workflow Change

Changes to:

```text
CodeQL
Gitleaks
govulncheck
Trivy
attestation
GitOps validation
```

are security-sensitive.

Review action pinning and permissions.

Do not merge solely because the workflow YAML parses.

Perform a controlled negative test.

---

# 144. Verify Action Pins

Known validated pins:

```text
CodeQL:
<COMMIT_SHA>

actions/attest:
<COMMIT_SHA>

create-github-app-token:
<COMMIT_SHA>
```

Inspect actual current workflow before changing versions.

---

# 145. Operate GitOps CI Tool Upgrade

Current validated kubeconform:

```text
0.7.0
```

When upgrading:

```text
pin new version
verify checksum
render all existing targets
run current negative image tests
```

Do not remove checksum verification.

---

# 146. Operate Promotion Workflow Change

Any change to `update-gitops` must preserve:

```text
branch = automation/image-<source-sha>
exact two target files
digest-only updates
render validation
bot commit
PR
no auto-merge
```

Test on a non-production release path before relying on it.

---

# 147. Operate GitHub App Permission Change

Keep:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

Do not add administration permissions unless there is a documented requirement.

---

# 148. Operate Branch Protection Change

Before changing:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Record current rules.

After change, create a test PR with a failing required check.

Expected:

```text
merge blocked
```

---

# 149. Operate Keycloak Upgrade

Before upgrade, record:

```text
realm
clients
groups
mappers
redirect URIs
PKCE
```

After upgrade, verify:

```text
Argo login
CLI PKCE login
groups claim
RBAC mapping
```

Do not assume identity survives version changes unchanged.

---

# 150. Operate Argo CD Upgrade

Current validated:

```text
v3.5.1
```

Before upgrade:

```text
record Applications
AppProject
OIDC config
RBAC config
root sync model
ignoreDifferences
```

After upgrade:

```text
login
app list
sync status
diff
self-heal
Policy Controller ignore behavior
```

---

# 151. Keep Argo Server Internal

Validated design:

```text
argocd-server = ClusterIP
```

Access is through:

```text
Envoy Gateway HTTPS
```

Do not switch service type for routine operations.

---

# 152. Operate Emergency Break-Glass Access

If OIDC is unavailable and Argo access is required:

```text
use documented bootstrap/break-glass process
restore OIDC
rotate emergency credentials
disable local admin for routine use again
```

Do not leave the platform permanently in break-glass mode.

---

# 153. Operate Failed Keycloak Login

Check:

```text
Keycloak availability
client redirect URI
PKCE
groups scope
user group membership
Argo OIDC config
```

Do not fall back to static admin as permanent solution.

---

# 154. Operate Gateway Failure

Trace:

```text
DNS
Gateway listener
TLS Secret
HTTPRoute
Service
Pod
```

Commands:

```bash
kubectl get gateway -A
kubectl get httproute -A
kubectl get svc -A
kubectl get pods -A
```

---

# 155. Operate DNS Failure

CoreDNS Service:

```text
10.96.0.10
```

Check cluster DNS:

```bash
kubectl get svc \
  -n kube-system
```

Distinguish:

```text
host DNS issue
cluster DNS issue
Gateway routing issue
```

---

# 156. Operate Gateway LoadBalancer Address

Validated Gateway LB:

```text
172.19.255.200
```

Check:

```bash
kubectl get gateway \
  -A \
  -o wide
```

If address changes, update local DNS/host mapping through the documented mechanism.

---

# 157. Operate API Backend

Validated Kubernetes API backend used in environment examples:

```text
172.19.0.3:6443
```

Do not hardcode this into application manifests unless architecture requires it.

Treat it as environment detail.

---

# 158. Operate Service ClusterIP Awareness

Kubernetes API service:

```text
10.96.0.1
```

CoreDNS:

```text
10.96.0.10
```

Use these only for diagnosis, not application coupling.

---

# 159. End-of-Day Quick Health Check

Run:

```bash
argocd app list
```

Then:

```bash
kubectl get pods -A
```

Then:

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
kubectl get trustroots.policy.sigstore.dev
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

# 160. What Must Be Read from the Actual Repositories

Do not invent:

```text
exact Argo Application names
exact operator Deployment name
exact workload labels
exact Keycloak script locations if moved
exact GitHub Actions secret names
exact GitHub Actions variable names
exact native policy names
exact CEL expressions
exact Gateway object names
exact Vault secret paths
```

Inspect source:

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

Inspect GitOps:

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

Use the repositories and live cluster as the exact operational source of truth.

---

# 161. References

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

Kubernetes operations and debugging:

```text
https://kubernetes.io/docs/tasks/debug/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Prometheus:

```text
https://prometheus.io/docs/
```

HashiCorp Vault:

```text
https://developer.hashicorp.com/vault/docs
```
