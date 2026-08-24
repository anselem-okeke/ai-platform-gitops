# Validation and Security Tests

## Purpose

This document is the **implementation runbook for validating the AI Platform security controls**.

It is not a generic test catalog.

The goal is to prove, with repeatable commands, that the controls implemented in Phase 7 actually enforce the intended behavior.

The validation sequence is:

```text
source controls
    |
    v
release controls
    |
    v
GitOps controls
    |
    v
Argo reconciliation
    |
    v
native admission
    |
    v
Sigstore trust
    |
    v
runtime verification
    |
    v
observability validation
```

The focus is on tests that answer:

```text
Can bad source merge?
Can a release continue after a failed security gate?
Can mutable or malformed images enter GitOps?
Can an untrusted digest run in Kubernetes?
Can init or ephemeral containers bypass policy?
Can Git drift be detected and repaired?
Can admission health be observed?
```

A control is considered validated only when both of these are demonstrated:

```text
positive case succeeds
negative case fails in the expected place
```

---

# 1. Working Directories

## Source repository

```text
/mnt/data/ai-platform-operator
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

Use source for:

```text
CI
security scans
release workflow
image build
attestation
```

Use GitOps for:

```text
desired state
digest promotion
Argo
admission policy
monitoring
```

---

# 2. Test Environment

Validated development cluster:

```text
context:
kind-ai-platform-policy

Kubernetes:
v1.36.1
```

Verify before testing:

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

Then:

```bash
kubectl cluster-info
```

---

# 3. Test Safety Rules

Use:

```text
--dry-run=server
```

whenever admission behavior can be tested without persisting resources.

Prefer disposable test objects.

Do not intentionally break:

```text
Policy Controller
webhook certificates
Argo control plane
Prometheus
```

in the main development environment unless running a planned failure exercise.

Use synthetic credentials only.

Never use a real secret as a negative-test fixture.

---

# 4. Test 1 — Source Lint Gate

Work in:

```bash
cd /mnt/data/ai-platform-operator
```

Run:

```bash
make lint-config
```

Then:

```bash
make lint
```

Expected:

```text
exit code 0
```

A failing lint command should also fail the corresponding PR job.

To validate enforcement on a disposable branch, introduce a controlled lint violation.

Push the branch and inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Expected:

```text
Lint check = failed
PR merge blocked
```

Remove the test violation before continuing.

---

# 5. Test 2 — Unit Test Gate

Run:

```bash
make test
```

Expected:

```text
pass
```

To prove enforcement, introduce a temporary failing test on a disposable branch.

Open/update a PR.

Expected:

```text
Tests / Run on Ubuntu (pull_request) = failed
merge blocked
```

The important result is not only that the test fails, but that:

```text
the repository ruleset prevents merge
```

---

# 6. Test 3 — E2E Gate

Inspect the E2E workflow:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,360p' \
  .github/workflows/test-e2e.yml
```

Run the local project E2E path if one is provided by the Makefile.

Inspect targets:

```bash
grep -nE \
  '^([a-zA-Z0-9_-]+):' \
  Makefile
```

On PR, expected required check:

```text
E2E Tests / Run on Ubuntu (pull_request)
```

A controlled E2E failure must block merge.

---

# 7. Test 4 — `go vet`

Run:

```bash
go vet ./...
```

Expected:

```text
exit code 0
```

If the CI workflow includes `go vet`, verify the exact step:

```bash
grep -RIn \
  'go vet' \
  .github/workflows
```

Do not assume a local-only validation is enforced unless CI also runs it.

---

# 8. Test 5 — govulncheck

Validated CLI version:

```text
v1.7.0
```

Run:

```bash
govulncheck ./...
```

Expected interpretation:

```text
0 reachable vulnerabilities
```

Important distinction:

```text
reachable vulnerabilities = 0
```

does not mean:

```text
all imported dependency vulnerabilities = 0
```

The test passes when no reachable vulnerability is reported.

---

# 9. Test 6 — CodeQL Required Check

Inspect source security workflow:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,360p' \
  .github/workflows/security.yml
```

Validated CodeQL action pin:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

Check PR status:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Expected:

```text
CodeQL = pass
```

Then verify branch ruleset still requires CodeQL:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

The validation is incomplete if CodeQL runs but is not required.

---

# 10. Test 7 — Gitleaks Current and History Scan

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
no findings
```

This validates current reachable Git history.

---

# 11. Test 8 — Gitleaks Blocking Negative Test

Use a disposable branch.

Do **not** use a real credential.

Add a synthetic secret-like value that Gitleaks is expected to detect.

Commit and push.

Open a PR.

Expected:

```text
Gitleaks = failed
merge blocked
```

Then remove/revert the synthetic test data.

Re-run:

```bash
gitleaks git --redact
```

Expected:

```text
clean
```

---

# 12. Test 9 — Source Branch Protection

Validated ruleset:

```text
Source Main Protection
ID 21120105
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  --jq '{
    name,
    enforcement,
    target,
    bypass_actors,
    rules
  }'
```

Expected:

```text
active
default branch protected
deletion blocked
non-fast-forward blocked
PR required
no bypass
required checks configured
```

---

# 13. Test 10 — Direct Push to Source Main

Do not use destructive commands on a shared working tree.

On a disposable clone or controlled branch-protection test, attempt a direct push to protected `main`.

Expected:

```text
rejected by GitHub
```

This proves the control is enforced at the repository boundary.

---

# 14. Test 11 — Release Trigger

Inspect:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,140p' \
  .github/workflows/release-images.yml
```

Expected release trigger:

```text
push to main
```

After a protected PR merge:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --workflow release-images.yml \
  --limit 10
```

Expected:

```text
release run associated with merge commit
```

---

# 15. Test 12 — Release Runs Against Expected SHA

Capture:

```bash
SOURCE_SHA="$(git rev-parse origin/main)"
```

Inspect run:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --json headSha,event,status,conclusion
```

Expected:

```text
headSha == SOURCE_SHA
event == push
```

---

# 16. Test 13 — Trivy Gate

Validated policy:

```text
severity:
HIGH,CRITICAL

ignore-unfixed:
true

exit code:
1
```

Inspect workflow:

```bash
grep -nA18 -B6 \
  'trivy' \
  .github/workflows/release-images.yml
```

Expected:

```text
scan configured to fail release on matched fixed HIGH/CRITICAL findings
```

---

# 17. Test 14 — Trivy Failure Stops Promotion

Inspect job dependency:

```bash
grep -nE \
  '^  build-operator:|^  build-api:|^  update-gitops:|needs:' \
  .github/workflows/release-images.yml
```

Expected:

```text
update-gitops depends on successful image build jobs
```

For a controlled negative test, use a disposable test image with a known matching vulnerability.

Expected:

```text
Trivy fails
image promotion job does not run
GitOps PR is not created
```

Do not weaken the Trivy threshold to make the test pass.

---

# 18. Test 15 — Image Runtime User

Build operator locally:

```bash
cd /mnt/data/ai-platform-operator

docker build \
  -f Dockerfile \
  -t ai-platform-operator:test \
  .
```

Inspect:

```bash
docker inspect \
  ai-platform-operator:test \
  --format '{{.Config.User}}'
```

Expected:

```text
65532
```

Repeat for API using the actual API Dockerfile.

---

# 19. Test 16 — Distroless Runtime

Inspect final image metadata:

```bash
docker history \
  ai-platform-operator:test
```

Verify runtime is based on:

```text
gcr.io/distroless/static-debian13:nonroot
```

Inspect source Dockerfile directly.

The test is to prove:

```text
Go toolchain does not remain in final image
runtime is non-root
```

---

# 20. Test 17 — Image Digest Format

Capture release digest.

Example variable:

```bash
API_DIGEST='sha256:<REAL_API_DIGEST>'
```

Validate:

```bash
[[ "${API_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]] \
  || {
    echo "invalid digest" >&2
    exit 1
  }
```

Repeat for operator.

---

# 21. Test 18 — SBOM Exists

Inspect release workflow:

```bash
grep -nEi \
  'sbom|spdx|syft' \
  .github/workflows/release-images.yml
```

Validated output format:

```text
SPDX JSON
```

Inspect release run logs:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --log \
  | grep -nEi 'SBOM|SPDX|syft'
```

Expected:

```text
SBOM generated for both images
```

---

# 22. Test 19 — Provenance Attestation Exists in Release Flow

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

Expected:

```text
subject-name references exact image repository
subject-digest references exact build output digest
```

---

# 23. Test 20 — SBOM Attestation Uses Exact Digest

Inspect:

```bash
grep -nA18 -B6 \
  'sbom-path' \
  .github/workflows/release-images.yml
```

Verify the same digest output is used for:

```text
image push
provenance
SBOM attestation
GitOps promotion
```

This is the identity chain.

---

# 24. Test 21 — GitHub App Token Generation

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
grep -nA20 -B6 \
  'bcd2ba49218906704ab6c1aa796996da409d3eb1' \
  .github/workflows/release-images.yml
```

Expected:

```text
target owner = anselem-okeke
target repo = ai-platform-gitops
```

Do not print the generated token.

---

# 25. Test 22 — GitHub App Installation Scope

Verify in GitHub App settings that the installation includes:

```text
ai-platform-gitops
```

and does not need broad access to unrelated repositories.

Required permissions:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

---

# 26. Test 23 — Promotion Branch Name

Expected:

```text
automation/image-<SOURCE_SHA>
```

Query:

```bash
git ls-remote \
  --heads \
  https://github.com/anselem-okeke/ai-platform-gitops.git \
  "refs/heads/automation/image-${SOURCE_SHA}"
```

Expected:

```text
branch exists after successful release
```

---

# 27. Test 24 — Promotion Changes Exactly Two Files

Fetch:

```bash
cd /mnt/data/ai-platform-gitops

git fetch origin \
  "automation/image-${SOURCE_SHA}"
```

Compare:

```bash
git diff \
  --name-only \
  origin/main...FETCH_HEAD \
  | sort
```

Expected exactly:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

Any additional file is a failed validation.

---

# 28. Test 25 — Bot Commit Identity

```bash
git show \
  --no-patch \
  --format=fuller \
  FETCH_HEAD
```

Expected author:

```text
ai-platform-gitops-bot[bot]
```

Expected commit:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 29. Test 26 — GitOps PR Exists

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --head "automation/image-${SOURCE_SHA}"
```

Expected:

```text
one PR
```

Verify it targets:

```text
main
```

and is not auto-merged.

---

# 30. Test 27 — GitOps Kustomize Render

Checkout the PR branch or detach at `FETCH_HEAD`.

Operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/test-operator.yaml
```

API:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/test-api.yaml
```

Expected:

```text
both render successfully
```

---

# 31. Test 28 — GitOps kubeconform

Validated version:

```text
0.7.0
```

Run:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/test-operator.yaml
```

Then:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/test-api.yaml
```

Expected:

```text
valid
```

---

# 32. Test 29 — Final Operator Image Is Digest-Pinned

```bash
grep -E \
  'image: ghcr\.io/anselem-okeke/ai-platform-operator@sha256:[0-9a-f]{64}$' \
  /tmp/test-operator.yaml
```

Expected:

```text
one or more valid operator image references
```

---

# 33. Test 30 — Final API Image Is Digest-Pinned

```bash
grep -E \
  'image: ghcr\.io/anselem-okeke/ai-platform-api@sha256:[0-9a-f]{64}$' \
  /tmp/test-api.yaml
```

Expected:

```text
valid API reference
```

---

# 34. Test 31 — No Floating Tag in Final Render

```bash
grep -nE \
  'image: .*:(latest|dev|main)$' \
  /tmp/test-operator.yaml \
  /tmp/test-api.yaml
```

Expected:

```text
no matches
```

The raw base placeholders are not the enforcement target.

The final rendered state is.

---

# 35. Test 32 — GitOps CI Check

```bash
gh pr checks <GITOPS_PR> \
  --repo anselem-okeke/ai-platform-gitops
```

Expected:

```text
Validate GitOps Manifests = pass
```

Do not merge if it fails.

---

# 36. Test 33 — Bad GitOps Mutable Tag

On a disposable GitOps branch, intentionally set:

```text
:latest
```

or:

```text
newTag:
```

as the final rendered image identity.

Open a PR.

Expected:

```text
Validate GitOps Manifests fails
merge blocked
```

Revert the test.

---

# 37. Test 34 — Malformed Digest

Use:

```text
sha256:1234
```

in a disposable GitOps test branch.

Expected:

```text
GitOps validation fails
```

or the rendered admission path rejects later if the PR validation does not catch it.

The preferred outcome is:

```text
fail before merge
```

---

# 38. Test 35 — GitOps Secret Pattern

Use a synthetic secret-like value in a disposable GitOps PR.

Expected:

```text
validation fails
```

Do not use a real credential.

Remove the fixture after the test.

---

# 39. Test 36 — Git Whitespace Validation

Run:

```bash
git diff --check
```

Expected:

```text
no output
```

The GitOps workflow also enforces this.

---

# 40. Test 37 — Human Merge Boundary

Verify GitHub App behavior:

```text
bot pushes automation branch
bot opens PR
bot does not merge main
```

Confirm the GitOps PR remains open until human action.

This proves promotion is not fully autonomous.

---

# 41. Test 38 — Argo Detects GitOps Merge

After GitOps merge:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Then:

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

Expected:

```text
new Git revision observed
```

---

# 42. Test 39 — Argo Reaches Synced/Healthy

API:

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

Operator:

```bash
argocd app wait \
  ai-platform-operator \
  --sync \
  --health \
  --timeout 300
```

Expected:

```text
Synced
Healthy
```

---

# 43. Test 40 — Live API Digest

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
exact API digest from GitOps
```

---

# 44. Test 41 — Live Operator Digest

Discover Deployment:

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
exact operator digest from GitOps
```

---

# 45. Test 42 — Argo Drift Detection

Create a safe, reversible manual drift on a non-security-critical field of a test workload.

Example concept:

```text
replica count
```

Do not change image or policy fields for this test.

Observe:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Expected:

```text
OutOfSync detected
```

Because child Applications have self-heal enabled, Argo should restore Git state.

Verify:

```bash
argocd app diff \
  ai-platform-api
```

Expected after reconciliation:

```text
no unintended diff
```

---

# 46. Test 43 — Git Rollback

Identify previous GitOps promotion:

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Create a rollback branch and revert the promotion commit.

Render and validate.

Open PR.

After merge, verify Argo deploys the previous trusted digest.

This proves rollback is:

```text
Git-driven
digest-preserving
admission-preserving
```

Do not use a manual `kubectl set image` rollback.

---

# 47. Test 44 — Native Admission Positive Case

Use a real trusted API digest:

```bash
kubectl run admission-good \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
allowed
```

This proves the image is structurally acceptable.

It must also pass Sigstore.

---

# 48. Test 45 — Native Admission Rejects Mutable Tag

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

# 49. Test 46 — Native Admission Rejects Public Image

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

# 50. Test 47 — Malformed Digest

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

Depending on the exact request path, the image parser or native policy may reject first.

---

# 51. Test 48 — Fake Valid Digest

Use a full 64-character fake digest:

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

Validated Sigstore error:

```text
no valid bundles exist in registry
```

This proves:

```text
valid syntax != trusted artifact
```

---

# 52. Test 49 — Bad Init Container

Use a real trusted main image.

Create:

```bash
cat >/tmp/security-bad-init.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: security-bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>
EOF
```

Run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/security-bad-init.yaml
```

Expected:

```text
DENIED
```

This proves `initContainers[]` cannot bypass policy.

---

# 53. Test 50 — Multi-Container Pod with Bad Sidecar

Create:

```bash
cat >/tmp/security-bad-sidecar.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: security-bad-sidecar
  namespace: ai-platform
spec:
  restartPolicy: Never

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>

    - name: sidecar
      image: nginx:latest
EOF
```

Run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/security-bad-sidecar.yaml
```

Expected:

```text
DENIED
```

This validates `.all(...)` behavior.

---

# 54. Test 51 — Ephemeral Container Bypass

Create a disposable trusted Pod:

```bash
kubectl run security-debug-base \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never
```

Attempt:

```bash
kubectl debug \
  -n ai-platform \
  security-debug-base \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Cleanup:

```bash
kubectl delete pod \
  security-debug-base \
  -n ai-platform
```

This validates the ephemeral-container path.

---

# 55. Test 52 — Direct Pod Bypass

```bash
kubectl run direct-pod-bypass \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

This proves users cannot bypass controller-level policy by creating Pods directly.

---

# 56. Test 53 — Deployment Template Negative Test

Create:

```bash
cat >/tmp/security-bad-deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: security-bad-deployment
  namespace: ai-platform
spec:
  replicas: 1

  selector:
    matchLabels:
      app: security-bad-deployment

  template:
    metadata:
      labels:
        app: security-bad-deployment

    spec:
      containers:
        - name: app
          image: nginx:latest
EOF
```

Server-side dry run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/security-bad-deployment.yaml
```

Expected:

```text
DENIED
```

if Deployment-template policy is explicitly implemented.

If only resulting Pods are validated, document that behavior precisely instead of claiming earlier rejection.

---

# 57. Test 54 — TrustRoot Exists

```bash
kubectl get trustroot \
  github \
  -o yaml
```

Expected:

```text
resource exists
```

Do not edit it manually during validation.

---

# 58. Test 55 — ClusterImagePolicy Exists

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Expected:

```text
resource exists
image scope includes AI Platform first-party repositories
```

Validated image patterns:

```text
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**
```

---

# 59. Test 56 — Protected Namespace Scope

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

Test an untrusted image in a protected namespace.

Expected:

```text
DENIED
```

Do not infer enforcement from the label alone.

---

# 60. Test 57 — Policy Controller Webhook

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Also:

```bash
kubectl get mutatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Verify:

```text
webhook configuration exists
service reference is valid
caBundle exists
```

---

# 61. Test 58 — Known Webhook Drift Exception

Inspect webhook selector:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml \
  | grep -nA6 -B6 \
    'webhooks.knative.dev/exclude'
```

Validated controller-managed selector:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

The Argo ignore must be narrow.

Do not validate success by broadly ignoring the whole webhook resource.

---

# 62. Test 59 — Policy Controller Metrics Endpoint

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

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
  | head -n 50
```

Expected:

```text
Prometheus metrics output
```

---

# 63. Test 60 — Reconcile Metrics Present

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_reconcile_count'
```

Expected:

```text
non-empty series
```

---

# 64. Test 61 — Prometheus Target Is Up

Query:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Validated result:

```text
1
```

This proves the ServiceMonitor is functioning, not merely present.

---

# 65. Test 62 — ServiceMonitor Exists

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Check:

```text
namespaceSelector includes cosign-system
selector matches metrics service
endpoint references correct metrics port
```

---

# 66. Test 63 — PrometheusRule Exists

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Expected metadata includes:

```yaml
labels:
  release: kps
```

This label was required to make the rule selected by the current stack.

---

# 67. Test 64 — TargetDown Rule Loaded

Expected rule:

```text
PolicyControllerTargetDown
```

Expression:

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

Validate the expression directly.

Do not intentionally stop Policy Controller in the main dev environment just to fire this alert.

---

# 68. Test 65 — ReconcileFailures Rule Loaded

Expected:

```text
PolicyControllerReconcileFailures
```

Expression:

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

Validate the raw query:

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

# 69. Test 66 — Webhook Certificate Rule Loaded

Expected:

```text
PolicyControllerWebhookCertificateFailures
```

Expression:

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

Do not corrupt certificates in the primary dev environment merely to force a firing state.

---

# 70. Test 67 — Rule Selector Is Correct

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

Compare against PrometheusRule:

```yaml
metadata:
  labels:
    release: kps
```

The rule must be selected by the actual Prometheus instance.

---

# 71. Test 68 — ServiceMonitor Selector Is Correct

Inspect metrics Service labels:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

Inspect ServiceMonitor:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

The selectors must match exactly.

---

# 72. Test 69 — GitOps Monitoring Render

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/security-monitoring.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/security-monitoring.yaml
```

Expected:

```text
render succeeds
validation succeeds
```

---

# 73. Test 70 — GitOps Policies Render

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/security-policies.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/security-policies.yaml
```

Then:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/security-policies.yaml
```

Expected:

```text
server accepts policy manifests
```

---

# 74. Test 71 — AppProject Allows Required Security Resources

Inspect:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,360p' \
  argocd/projects/ai-platform.yaml
```

Verify explicit allowlist for:

```text
TrustRoot
ClusterImagePolicy
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
admission webhook configurations
```

Avoid wildcard cluster-resource permissions.

---

# 75. Test 72 — Root Application Remains Manual

Inspect:

```bash
argocd app get ai-platform-root
```

Expected design:

```text
root Application is manual
child Applications use automated sync/self-heal/prune
```

Do not convert the root topology/bootstrap layer to automatic sync casually.

---

# 76. Test 73 — Child Self-Heal

For a safe child resource:

```text
create harmless manual drift
observe OutOfSync
wait for self-heal
```

Verify:

```bash
argocd app get <CHILD_APP> --refresh
```

Expected:

```text
returns to Synced
```

---

# 77. Test 74 — Git Rollback

Use an actual previous promotion commit.

Run:

```bash
git show <PREVIOUS_GITOPS_COMMIT>
```

Create a revert branch.

Run:

```bash
git revert <PROMOTION_COMMIT>
```

Render overlays.

Run GitOps validation.

Open PR.

Merge.

Expected:

```text
Argo deploys previous trusted digests
```

This is the validated rollback model.

---

# 78. Test 75 — Traceability from Source to Runtime

Capture:

```text
source PR
SOURCE_SHA
release RUN_ID
operator digest
API digest
GitOps branch
GitOps PR
GitOps merge SHA
Argo revision
live Deployment digest
```

Verify the chain manually.

Example:

```bash
git log -1 \
  --format='%H %s' \
  /mnt/data/ai-platform-operator
```

Then inspect GitOps promotion commit and live image.

The exact digest should be traceable end-to-end.

---

# 79. Test 76 — No Secret Files Tracked

Source:

```bash
cd /mnt/data/ai-platform-operator

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Expected:

```text
no real sensitive files
```

Review any documentation/example matches manually.

---

# 80. Test 77 — No Real `.env` Tracked

```bash
git ls-files \
  | grep -E '(^|/)\.env($|\.)'
```

Expected:

```text
no secret-bearing .env file
```

Templates with placeholders must be reviewed.

---

# 81. Test 78 — No Private Key Block

Source:

```bash
git grep -nE \
  'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git grep -nE \
  'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
```

Expected:

```text
no real key material
```

---

# 82. Test 79 — Kubernetes Secret References Only

Inspect workloads:

```bash
grep -RIn \
  'secretKeyRef\|secretName\|kind: Secret' \
  platform \
  clusters \
  argocd \
  2>/dev/null
```

Review matches.

Allowed:

```text
Secret references
metadata
templates with placeholders
```

Not allowed:

```text
real secret values
real private keys
base64-encoded production credentials
```

---

# 83. Test 80 — GitHub App Private Key Is Not in Git

Source:

```bash
cd /mnt/data/ai-platform-operator

git grep -nE \
  'BEGIN (RSA )?PRIVATE KEY'
```

Expected:

```text
no match for real App key
```

The private key belongs in GitHub Actions Secrets.

---

# 84. Test 81 — GitHub App Token Is Short-Lived

Verify release workflow mints a token during each run.

Do not store the generated installation token in:

```text
repository secret
artifact
cache
Git
```

The test is architectural:

```text
private key -> installation token per run
```

not:

```text
static PAT -> permanent cross-repo access
```

---

# 85. Test 82 — Argo Does Not Deploy from Source CI Directly

Inspect source workflows for direct `kubectl apply` or `argocd app sync` against platform workloads:

```bash
cd /mnt/data/ai-platform-operator

grep -RInE \
  'kubectl apply|kubectl set image|argocd app sync' \
  .github/workflows
```

Expected:

```text
no direct production-style deployment path from source CI
```

Deployment should flow through GitOps.

---

# 86. Test 83 — GitOps Is Deployment Source of Truth

Compare:

```text
GitOps overlay
Kustomize render
Argo revision
live image
```

They must align.

If live state differs, Argo should report drift.

---

# 87. Test 84 — Admission Fails Closed

Inspect native policy:

```bash
kubectl get validatingadmissionpolicies \
  -o yaml
```

Verify relevant policy uses:

```yaml
failurePolicy: Fail
```

Inspect Binding:

```bash
kubectl get validatingadmissionpolicybindings \
  -o yaml
```

Verify:

```yaml
validationActions:
  - Deny
```

Use exact policy names once read from the repository.

---

# 88. Test 85 — Policy Alone Is Not Mistaken for Enforcement

Verify both resources exist:

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
```

A policy without a binding is not enough.

The test passes only if the binding is active for intended namespaces.

---

# 89. Test 86 — Protected Namespaces Are Correct

Verify:

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

Then inspect other namespaces.

Do not accidentally apply the first-party image allowlist globally to:

```text
kube-system
argocd
monitoring
cosign-system
```

unless intentionally designed.

---

# 90. Test 87 — Policy Controller Helm Version

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

Verify live chart before upgrades.

---

# 91. Test 88 — Trust Policy Helm Version

```bash
helm list \
  -n cosign-system
```

Expected trust-policies release:

```text
v0.7.0
```

If managed by Argo, also inspect:

```bash
argocd app get trust-policies
```

Use the exact Application name if different.

---

# 92. Test 89 — Trust Policy Image Scope

Inspect:

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Expected scope includes:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

Do not broaden trust to unrelated repositories.

---

# 93. Test 90 — Policy Controller Prometheus Target

If Prometheus UI/API is available, query:

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

If result is absent rather than `0`, troubleshoot ServiceMonitor discovery.

---

# 94. Test 91 — Recent Reconcile Failures

Query:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

Expected healthy result:

```text
0
```

or low transient value.

Investigate sustained growth.

---

# 95. Test 92 — Webhook Certificate Failures

Query:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

Expected:

```text
0
```

Any sustained failure is security-critical availability degradation.

---

# 96. Test 93 — Monitoring Rule Selector

Inspect:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o jsonpath='{.metadata.labels}{"\n"}'
```

Expected:

```text
release:kps
```

This is required by the current monitoring selector.

---

# 97. Test 94 — Monitoring GitOps Drift

Make a harmless temporary manual metadata change to the ServiceMonitor or PrometheusRule only in a controlled test.

Refresh monitoring Application:

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

Expected:

```text
OutOfSync
```

Then verify self-heal returns the Git state.

Do not modify alert expressions destructively in the primary environment.

---

# 98. Test 95 — End-to-End Positive Release

A complete successful validation run should prove:

```text
source PR passes
source merge succeeds
release succeeds
Trivy passes
images pushed
digests captured
SBOM generated
attestations created
GitOps PR created
GitOps validation passes
human merge
Argo syncs
admission allows exact digest
workload rolls out
live digest matches Git
metrics target up
```

Record:

```text
SOURCE_SHA
RUN_ID
OPERATOR_DIGEST
API_DIGEST
GITOPS_PR
GITOPS_SHA
```

---

# 99. Test 96 — End-to-End Negative Source Path

Controlled disposable PR:

```text
introduce failing source test
```

Expected chain:

```text
source check fails
merge blocked
release absent
GitOps PR absent
cluster unchanged
```

This validates the first enforcement boundary.

---

# 100. Test 97 — End-to-End Negative Release Path

Controlled test image or branch:

```text
Trivy gate fails
```

Expected:

```text
release image job fails
update-gitops skipped
GitOps PR absent
cluster unchanged
```

---

# 101. Test 98 — End-to-End Negative GitOps Path

Create disposable GitOps PR with:

```text
mutable tag
```

Expected:

```text
Validate GitOps Manifests fails
merge blocked
Argo unchanged
cluster unchanged
```

---

# 102. Test 99 — End-to-End Negative Admission Path

Use:

```text
approved repository
valid full SHA-256 syntax
fake digest
```

Expected:

```text
native structural policy may accept
Sigstore denies
workload not admitted
```

Validated failure:

```text
no valid bundles exist in registry
```

---

# 103. Test 100 — End-to-End Rollback

Use a known-good previous GitOps digest.

Flow:

```text
Git revert
  ->
GitOps PR
  ->
validation
  ->
human merge
  ->
Argo
  ->
previous trusted digest
```

Verify the previous digest is running.

Do not rebuild the old source to roll back.

Do not use a mutable historical tag.

---

# 104. Interpreting Failures

When a test fails unexpectedly, identify the failing layer before changing anything.

Use this order:

```text
1. source CI
2. source branch protection
3. release workflow
4. image scan
5. attestation
6. GitHub App
7. GitOps render/validation
8. GitOps branch protection
9. Argo
10. native admission
11. Sigstore
12. runtime
13. Prometheus
```

Do not disable a downstream security control to compensate for an upstream defect.

---

# 105. Common Failure — Security Workflow Runs but Merge Is Allowed

Cause:

```text
check is not required by branch ruleset
```

Fix:

```text
add exact status check to required checks
```

Re-test with a controlled failure.

---

# 106. Common Failure — GitOps PR Is Created Even Though Build Failed

Cause:

```text
update-gitops job dependency is wrong
```

Inspect:

```bash
grep -nE \
  '^  update-gitops:|needs:' \
  .github/workflows/release-images.yml
```

Promotion must depend on both successful image jobs.

---

# 107. Common Failure — Trusted Image Denied

Check:

```text
exact digest
TrustRoot
ClusterImagePolicy
trust-policy organization
image scope
attestation existence
namespace label
Policy Controller health
webhook TLS
```

Do not broaden trust policy first.

Find the exact failing condition.

---

# 108. Common Failure — Untrusted Image Allowed

Treat as security-critical.

Check immediately:

```text
ValidatingAdmissionPolicy exists
Binding exists
Deny enabled
namespace selected
Sigstore include label present
webhook ready
trust policy installed
```

Stop normal promotion until fixed.

---

# 109. Common Failure — PrometheusRule Exists but Is Not Loaded

Check:

```text
release: kps
Prometheus ruleSelector
ruleNamespaceSelector
```

This exact label mismatch occurred previously and was corrected.

---

# 110. Common Failure — ServiceMonitor Exists but Target Missing

Check:

```text
Service selector
service labels
namespaceSelector
endpoint port name
Prometheus ServiceMonitor selectors
```

Do not change Policy Controller just because the target is missing.

The metrics endpoint may be healthy while discovery is broken.

---

# 111. What Must Be Read from the Actual Repositories

Before claiming exact parity, inspect actual files for:

```text
workflow job names
step IDs
action SHAs
Gitleaks version
kubeconform checksum
GitOps secret regex
native policy names
CEL expressions
binding selector
Argo child Application names
Pod label selectors
```

Source:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,520p' \
  .github/workflows/release-images.yml

sed -n '1,360p' \
  .github/workflows/security.yml

sed -n '1,320p' \
  .github/workflows/secret-scan.yml
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,500p' \
  .github/workflows/validate.yml

find platform/policies \
  -maxdepth 3 \
  -type f \
  -print \
  | sort

sed -n '1,320p' \
  platform/monitoring/base/policy-controller-servicemonitor.yaml

sed -n '1,360p' \
  platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Use the committed files as the exact implementation source of truth.

---

# 112. References

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

Kubernetes ValidatingAdmissionPolicy:

```text
https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Prometheus alerting:

```text
https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
```
