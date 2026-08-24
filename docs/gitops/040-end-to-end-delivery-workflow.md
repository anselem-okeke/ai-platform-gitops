# End-to-End Delivery Workflow

## Purpose

This document is the **full implementation runbook** for the AI Platform delivery path from an approved source commit to a running Kubernetes workload.

It is written to be executed, not read as architecture notes.

The implementation chain is:

```text
Developer change
    |
    v
Source pull request
    |
    +--> Lint
    +--> Tests
    +--> E2E
    +--> Gitleaks
    +--> govulncheck
    +--> CodeQL
    |
    v
Protected source main
    |
    v
Release workflow
    |
    +--> build operator
    +--> build API
    +--> Trivy HIGH/CRITICAL gate
    +--> push GHCR
    +--> SPDX JSON SBOM
    +--> provenance attestation
    +--> SBOM attestation
    |
    v
Immutable image digests
    |
    v
GitHub App installation token
    |
    v
GitOps automation branch
    |
    v
Digest-only GitOps PR
    |
    +--> Kustomize render
    +--> kubeconform
    +--> approved image validation
    +--> full digest validation
    +--> secret check
    +--> git diff check
    |
    v
Human merge
    |
    v
Argo CD
    |
    v
Native admission
    |
    v
Sigstore Policy Controller
    |
    v
Kubernetes rollout
    |
    v
Live digest verification
```

The core rule is:

> A delivery control is only real if its failure prevents the next stage.

---

# 1. Working Directories

## Source repository

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Use the source repository for:

```text
Go code
Docker builds
source CI
security scanning
release workflow
SBOM/provenance
GitOps update automation
```

Use the GitOps repository for:

```text
deployment desired state
Kustomize overlays
Argo Applications
native admission policy
Sigstore trust
monitoring
```

---

# 2. Delivery Invariants

These must remain true for every release:

```text
source PR cannot merge with failed required checks
release runs from protected main
failed image scan blocks promotion
image identity is digest, not tag
SBOM/provenance refer to exact pushed digest
GitHub App opens PR instead of pushing main
GitOps validation must pass
human merge authorizes deployment
Argo deploys Git state
native admission rejects malformed/mutable images
Sigstore rejects structurally valid but untrusted digests
live workload digest equals GitOps digest
```

---

# 3. Preflight — Kubernetes Context

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

Verify API connectivity:

```bash
kubectl cluster-info
```

Verify Kubernetes version:

```bash
kubectl version
```

Validated cluster version:

```text
v1.36.1
```

Stop if you are pointed at the wrong cluster.

---

# 4. Preflight — Argo CD

```bash
kubectl get pods -n argocd
```

Expected:

```text
Argo CD components Running/Ready
```

List applications:

```bash
argocd app list
```

Relevant child Applications include:

```text
operator
api
gateway
monitoring
modelservices
policies
namespaces
policy-controller
trust-policies
```

Use exact live names if they differ.

---

# 5. Preflight — Policy Controller

```bash
kubectl get pods -n cosign-system
```

Expected:

```text
policy-controller webhook Ready
```

Verify TrustRoot:

```bash
kubectl get trustroots.policy.sigstore.dev
```

Expected:

```text
github
```

Verify ClusterImagePolicy:

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Expected:

```text
github-policy
```

---

# 6. Preflight — Protected Namespace Labels

```bash
kubectl get ns   ai-platform   ai-platform-operator-system   --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

If the label is absent, do not assume Sigstore enforcement is active.

---

# 7. Prepare Source Main

```bash
cd /mnt/data/ai-platform-operator

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Expected:

```text
clean working tree
```

---

# 8. Prepare GitOps Main

```bash
cd /mnt/data/ai-platform-gitops

git fetch --all --prune
git switch main
git pull --ff-only origin main
git status --short
```

Expected:

```text
clean working tree
```

Do not manually create the promotion branch. The source release workflow creates it.

---

# 9. Step 1 — Create a Source Change

```bash
cd /mnt/data/ai-platform-operator

git switch -c feat/e2e-delivery-validation
```

Make a small real code change that causes the normal image release path to run after merge.

Do not modify the release workflow just to force a successful test.

---

# 10. Step 2 — Run Local Source Validation

```bash
make lint-config
make lint
make test
go vet ./...
```

Then:

```bash
govulncheck ./...
```

Validated interpretation:

```text
0 reachable vulnerabilities
```

Do not state that the entire dependency graph contains zero vulnerabilities.

---

# 11. Step 3 — Run Gitleaks

```bash
gitleaks git --redact
```

Expected:

```text
no findings
exit code 0
```

If a real secret is found:

```text
STOP
rotate/revoke the secret
remove it
re-run Gitleaks
```

---

# 12. Step 4 — Commit and Push

Review:

```bash
git diff
```

Stage:

```bash
git add <FILES>
```

Review staged content:

```bash
git diff --cached
```

Commit:

```bash
git commit -m "test: validate end-to-end delivery"
```

Push:

```bash
git push -u origin feat/e2e-delivery-validation
```

---

# 13. Step 5 — Open Source Pull Request

```bash
gh pr create   --repo anselem-okeke/ai-platform-operator   --base main   --head feat/e2e-delivery-validation   --title "test: validate end-to-end delivery"   --body "Validates the protected source-to-GitOps-to-Argo delivery path."
```

Capture the PR number.

---

# 14. Step 6 — Verify Required Source Checks

```bash
gh pr checks <PR_NUMBER>   --repo anselem-okeke/ai-platform-operator   --watch
```

Required checks:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

Do not merge while a required check is failing or pending.

---

# 15. Step 7 — Verify Source Ruleset

Validated ruleset:

```text
Name: Source Main Protection
ID: 21120105
State: active
Bypass: none
```

Inspect:

```bash
gh api   repos/anselem-okeke/ai-platform-operator/rulesets/21120105   --jq '{name,enforcement,target,bypass_actors}'
```

Expected:

```text
active
no bypass actors
```

---

# 16. Step 8 — Merge Source PR

After checks pass:

```bash
gh pr merge <PR_NUMBER>   --repo anselem-okeke/ai-platform-operator   --merge
```

Update local main:

```bash
git switch main
git pull --ff-only origin main
```

Capture source SHA:

```bash
SOURCE_SHA="$(git rev-parse HEAD)"
echo "${SOURCE_SHA}"
```

This SHA is the traceability anchor for the rest of the run.

---

# 17. Step 9 — Locate Release Run

```bash
gh run list   --repo anselem-okeke/ai-platform-operator   --workflow release-images.yml   --limit 10
```

Capture the run associated with `SOURCE_SHA`.

Inspect:

```bash
gh run view <RUN_ID>   --repo anselem-okeke/ai-platform-operator   --json headSha,event,status,conclusion
```

Expected:

```text
headSha == SOURCE_SHA
event == push
```

---

# 18. Step 10 — Verify Release Job Structure

```bash
cd /mnt/data/ai-platform-operator

grep -nE   '^  build-operator:|^  build-api:|^  update-gitops:|needs:'   .github/workflows/release-images.yml
```

Expected:

```text
operator build job
API build job
GitOps update job
update-gitops depends on successful image jobs
```

This dependency is the enforcement point.

---

# 19. Step 11 — Verify Trivy Gate

Validated policy:

```text
HIGH,CRITICAL
ignore-unfixed
exit code 1
```

Inspect:

```bash
grep -nA16 -B6   'trivy'   .github/workflows/release-images.yml
```

Inspect run logs:

```bash
gh run view <RUN_ID>   --repo anselem-okeke/ai-platform-operator   --log   | grep -nEi 'trivy|HIGH|CRITICAL'
```

A failed Trivy gate must prevent GitOps promotion.

---

# 20. Step 12 — Verify GHCR Push

Current repositories:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

Inspect the release run for successful image pushes.

Capture the immutable digests.

---

# 21. Step 13 — Capture Operator Digest

```bash
OPERATOR_DIGEST='sha256:<REAL_OPERATOR_DIGEST>'
```

Validate:

```bash
[[ "${OPERATOR_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]   || {
    echo "invalid operator digest" >&2
    exit 1
  }
```

---

# 22. Step 14 — Capture API Digest

```bash
API_DIGEST='sha256:<REAL_API_DIGEST>'
```

Validate:

```bash
[[ "${API_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]   || {
    echo "invalid API digest" >&2
    exit 1
  }
```

Do not continue with an empty value or mutable tag.

---

# 23. Step 15 — Verify SPDX JSON SBOM

Inspect release workflow:

```bash
grep -nEi   'syft|sbom|spdx'   .github/workflows/release-images.yml
```

Validated format:

```text
SPDX JSON
```

Inspect run:

```bash
gh run view <RUN_ID>   --repo anselem-okeke/ai-platform-operator   --log   | grep -nEi 'SBOM|SPDX|syft'
```

Expected:

```text
operator SBOM generated
API SBOM generated
```

---

# 24. Step 16 — Verify Provenance Attestation

Validated action pin:

```text
actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Inspect:

```bash
grep -nA18 -B6   '508db95dd578ae2727ebd6217d5ba78e4fbda05d'   .github/workflows/release-images.yml
```

Verify:

```text
subject-name = exact GHCR repository
subject-digest = exact pushed digest
```

---

# 25. Step 17 — Verify SBOM Attestation

```bash
grep -nA16 -B6   'sbom-path'   .github/workflows/release-images.yml
```

Required invariant:

```text
pushed digest
==
provenance subject digest
==
SBOM subject digest
```

for both operator and API.

---

# 26. Step 18 — Verify GitHub App Token Step

Validated action pin:

```text
actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Inspect:

```bash
grep -nA20 -B6   'bcd2ba49218906704ab6c1aa796996da409d3eb1'   .github/workflows/release-images.yml
```

Expected target:

```text
owner = anselem-okeke
repository = ai-platform-gitops
```

Do not print the token.

---

# 27. Step 19 — Verify GitHub App Scope

App identity:

```text
ai-platform-gitops-bot[bot]
```

Repository permissions:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

Installation scope:

```text
ai-platform-gitops only
```

---

# 28. Step 20 — Verify Promotion Branch

Expected:

```text
automation/image-<SOURCE_SHA>
```

Query:

```bash
git ls-remote   --heads   https://github.com/anselem-okeke/ai-platform-gitops.git   "refs/heads/automation/image-${SOURCE_SHA}"
```

Expected:

```text
one result
```

---

# 29. Step 21 — Fetch Promotion Branch

```bash
cd /mnt/data/ai-platform-gitops

git fetch origin   "automation/image-${SOURCE_SHA}"
```

Compare:

```bash
git diff   --name-only   origin/main...FETCH_HEAD   | sort
```

Expected exactly:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

Anything else is a promotion failure.

---

# 30. Step 22 — Verify Operator Overlay

```bash
git show   FETCH_HEAD:platform/operator/overlays/dev/kustomization.yaml
```

Expected conceptual shape:

```yaml
images:
  - name: controller
    newName: ghcr.io/anselem-okeke/ai-platform-operator
    digest: sha256:<OPERATOR_DIGEST>
```

Use the actual committed manifest structure.

---

# 31. Step 23 — Verify API Overlay

```bash
git show   FETCH_HEAD:platform/api/overlays/dev/kustomization.yaml
```

Expected:

```yaml
images:
  - name: ai-platform-api
    newName: ghcr.io/anselem-okeke/ai-platform-api
    digest: sha256:<API_DIGEST>
```

---

# 32. Step 24 — Verify Bot Commit

```bash
git show   --no-patch   --format=fuller   FETCH_HEAD
```

Expected author:

```text
ai-platform-gitops-bot[bot]
```

Expected message:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

---

# 33. Step 25 — Locate GitOps PR

```bash
gh pr list   --repo anselem-okeke/ai-platform-gitops   --head "automation/image-${SOURCE_SHA}"
```

Capture `GITOPS_PR`.

Inspect:

```bash
gh pr view <GITOPS_PR>   --repo anselem-okeke/ai-platform-gitops
```

Expected:

```text
base = main
head = automation/image-<SOURCE_SHA>
not auto-merged
```

---

# 34. Step 26 — Render Operator Overlay from PR Branch

```bash
git switch --detach FETCH_HEAD
```

Render:

```bash
kubectl kustomize   platform/operator/overlays/dev   >/tmp/e2e-operator.yaml
```

Expected:

```text
successful render
```

---

# 35. Step 27 — Render API Overlay

```bash
kubectl kustomize   platform/api/overlays/dev   >/tmp/e2e-api.yaml
```

---

# 36. Step 28 — Verify Exact Operator Digest

```bash
grep -F   "ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}"   /tmp/e2e-operator.yaml
```

Expected:

```text
match
```

---

# 37. Step 29 — Verify Exact API Digest

```bash
grep -F   "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}"   /tmp/e2e-api.yaml
```

Expected:

```text
match
```

---

# 38. Step 30 — Verify Full SHA-256 Form

Operator:

```bash
grep -E   'image: ghcr\.io/anselem-okeke/ai-platform-operator@sha256:[0-9a-f]{64}$'   /tmp/e2e-operator.yaml
```

API:

```bash
grep -E   'image: ghcr\.io/anselem-okeke/ai-platform-api@sha256:[0-9a-f]{64}$'   /tmp/e2e-api.yaml
```

Both must match.

---

# 39. Step 31 — Reject Floating Final Tags

```bash
grep -nE   'image: .*:(latest|dev|main)$'   /tmp/e2e-operator.yaml   /tmp/e2e-api.yaml
```

Expected:

```text
no matches
```

The raw bases may contain placeholders. The rendered overlays may not.

---

# 40. Step 32 — Run kubeconform

Validated version:

```text
0.7.0
```

Run:

```bash
kubeconform   -strict   -summary   -ignore-missing-schemas   /tmp/e2e-operator.yaml
```

Then:

```bash
kubeconform   -strict   -summary   -ignore-missing-schemas   /tmp/e2e-api.yaml
```

Expected:

```text
valid
```

---

# 41. Step 33 — Validate Git Diff

```bash
git diff   origin/main...HEAD   --check
```

Expected:

```text
no output
```

---

# 42. Step 34 — Verify GitOps CI

```bash
gh pr checks <GITOPS_PR>   --repo anselem-okeke/ai-platform-gitops   --watch
```

Expected required check:

```text
Validate GitOps Manifests
```

Do not merge until it passes.

---

# 43. Step 35 — Verify GitOps Validation Scope

Return to main:

```bash
git switch main
git pull --ff-only origin main
```

Inspect:

```bash
sed -n '1,500p'   .github/workflows/validate.yml
```

It should render/validate:

```text
platform/operator/overlays/dev
platform/api/overlays/dev
platform/gateway/overlays/dev
platform/monitoring/overlays/dev
platform/policies/overlays/dev
modelservices/overlays/dev
clusters/dev/apps
```

And enforce:

```text
approved GHCR repositories
full SHA-256 digest
no final mutable tags
secret patterns
git diff --check
```

---

# 44. Step 36 — Merge GitOps PR

After CI passes and the diff is correct:

```bash
gh pr merge <GITOPS_PR>   --repo anselem-okeke/ai-platform-gitops   --merge
```

This is the deployment authorization point.

The bot proposes the change.

A human merges it.

---

# 45. Step 37 — Capture GitOps Merge SHA

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main
```

Capture:

```bash
GITOPS_SHA="$(git rev-parse HEAD)"
echo "${GITOPS_SHA}"
```

Keep:

```text
SOURCE_SHA
RUN_ID
OPERATOR_DIGEST
API_DIGEST
GITOPS_PR
GITOPS_SHA
```

---

# 46. Step 38 — Refresh Argo Applications

API:

```bash
argocd app get   ai-platform-api   --refresh
```

Operator:

```bash
argocd app get   ai-platform-operator   --refresh
```

Use actual Application names if different.

Expected:

```text
new Git revision observed
```

---

# 47. Step 39 — Wait for API Sync

```bash
argocd app wait   ai-platform-api   --sync   --health   --timeout 300
```

Expected:

```text
Synced
Healthy
```

---

# 48. Step 40 — Wait for Operator Sync

```bash
argocd app wait   ai-platform-operator   --sync   --health   --timeout 300
```

Expected:

```text
Synced
Healthy
```

---

# 49. Step 41 — Verify API Live Digest

```bash
kubectl get deployment   ai-platform-api   -n ai-platform   -o jsonpath='{.spec.template.spec.containers[*].image}{"
"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}
```

---

# 50. Step 42 — Verify Operator Live Digest

Discover Deployment:

```bash
kubectl get deployment   -n ai-platform-operator-system
```

Then:

```bash
kubectl get deployment   <OPERATOR_DEPLOYMENT>   -n ai-platform-operator-system   -o jsonpath='{.spec.template.spec.containers[*].image}{"
"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}
```

---

# 51. Step 43 — Verify Rollout Status

API:

```bash
kubectl rollout status   deployment/ai-platform-api   -n ai-platform   --timeout=300s
```

Operator:

```bash
kubectl rollout status   deployment/<OPERATOR_DEPLOYMENT>   -n ai-platform-operator-system   --timeout=300s
```

Expected:

```text
successfully rolled out
```

---

# 52. Step 44 — Verify Runtime ImageID

For API Pods:

```bash
kubectl get pods   -n ai-platform   -o jsonpath='{range .items[*]}{.metadata.name}{"
"}{range .status.containerStatuses[*]}{.imageID}{"
"}{end}{end}'
```

This confirms the runtime-resolved image identity.

---

# 53. Step 45 — Positive Admission Test

```bash
kubectl run e2e-trusted-image   -n ai-platform   --image="ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}"   --restart=Never   --dry-run=server   -o yaml
```

Expected:

```text
allowed
```

The exact released digest passes structural and Sigstore trust checks.

---

# 54. Step 46 — Deny Mutable Tag

```bash
kubectl run e2e-bad-tag   -n ai-platform   --image='ghcr.io/anselem-okeke/ai-platform-api:latest'   --restart=Never   --dry-run=server
```

Expected:

```text
DENIED
```

---

# 55. Step 47 — Deny Public Image

```bash
kubectl run e2e-nginx   -n ai-platform   --image=nginx:latest   --restart=Never   --dry-run=server
```

Expected:

```text
DENIED
```

---

# 56. Step 48 — Deny Fake Valid Digest

```bash
kubectl run e2e-fake-digest   -n ai-platform   --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'   --restart=Never   --dry-run=server
```

Expected:

```text
DENIED
```

Validated Sigstore failure:

```text
no valid bundles exist in registry
```

This proves digest syntax alone is insufficient.

---

# 57. Step 49 — Deny Bad Init Container

Create:

```bash
cat >/tmp/e2e-bad-init.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: e2e-bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: untrusted-init
      image: nginx:latest

  containers:
    - name: api
      image: ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}
EOF
```

Run:

```bash
kubectl apply   --dry-run=server   -f /tmp/e2e-bad-init.yaml
```

Expected:

```text
DENIED
```

---

# 58. Step 50 — Deny Bad Ephemeral Container

Create disposable trusted Pod:

```bash
kubectl run e2e-debug-base   -n ai-platform   --image="ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}"   --restart=Never
```

Attempt:

```bash
kubectl debug   -n ai-platform   e2e-debug-base   --image=nginx:latest
```

Expected:

```text
DENIED
```

Cleanup:

```bash
kubectl delete pod   e2e-debug-base   -n ai-platform
```

---

# 59. Step 51 — Verify Policy Controller Metrics

Port-forward:

```bash
kubectl port-forward   -n cosign-system   svc/policy-controller-webhook-metrics   9090:9090
```

In another terminal:

```bash
curl -s   http://127.0.0.1:9090/metrics   | grep '^policy_controller_'   | head -n 80
```

Expected:

```text
metrics present
```

---

# 60. Step 52 — Verify Prometheus Target

Query:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Validated healthy value:

```text
1
```

---

# 61. Step 53 — Verify Reconcile Metric

Query:

```promql
policy_controller_reconcile_count
```

Expected:

```text
non-empty series
```

---

# 62. Step 54 — Verify Prometheus Rules

```bash
kubectl get prometheusrule   policy-controller   -n monitoring   -o yaml
```

Expected alerts:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

Do not claim these were all intentionally forced to fire.

---

# 63. Step 55 — Verify No Argo Drift

API:

```bash
argocd app diff   ai-platform-api
```

Operator:

```bash
argocd app diff   ai-platform-operator
```

Expected:

```text
no unintended drift
```

---

# 64. Step 56 — Compare Git Render to Live State

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize   platform/api/overlays/dev   >/tmp/final-api.yaml

kubectl kustomize   platform/operator/overlays/dev   >/tmp/final-operator.yaml
```

Inspect:

```bash
grep -n 'image:'   /tmp/final-api.yaml   /tmp/final-operator.yaml
```

Compare those references with the live Deployment image fields.

They must match.

---

# 65. Step 57 — Verify Argo Revision

API:

```bash
argocd app get   ai-platform-api   -o json   | jq -r '.status.sync.revision'
```

Operator:

```bash
argocd app get   ai-platform-operator   -o json   | jq -r '.status.sync.revision'
```

The revision should correspond to the GitOps main state containing the promotion.

---

# 66. Step 58 — Prove Traceability

You should now be able to reconstruct:

```text
Source PR
  |
SOURCE_SHA
  |
Release RUN_ID
  |
  +--> OPERATOR_DIGEST
  +--> API_DIGEST
  |
automation/image-SOURCE_SHA
  |
GitOps PR
  |
GITOPS_SHA
  |
Argo revision
  |
live Kubernetes digest
```

If a link is missing, traceability is incomplete.

---

# 67. Failure — Source Check Fails

Expected behavior:

```text
merge blocked
release does not start
```

Fix the actual problem.

Do not remove the required check or bypass the ruleset.

---

# 68. Failure — Release Does Not Start

Check:

```bash
gh run list   --repo anselem-okeke/ai-platform-operator   --workflow release-images.yml
```

Inspect the trigger:

```bash
sed -n '1,100p'   .github/workflows/release-images.yml
```

Expected:

```text
push to main
```

---

# 69. Failure — Trivy Blocks Release

This is expected when the threshold is violated.

Investigate:

```text
vulnerable package
severity
fix availability
base image
application dependency
```

Do not lower the gate just to continue.

---

# 70. Failure — Attestation Fails

Check:

```text
id-token permission
attestations permission
subject-name
subject-digest
registry push
```

Do not promote if the release contract requires successful attestations.

---

# 71. Failure — GitHub App Returns `Not Found`

Known real failure.

Check:

```text
App installed
GitOps repo selected in installation
owner correct
repository correct
App/Client ID correct
private key belongs to same App
Contents permission
Pull requests permission
```

Do not switch to a long-lived PAT as the default fix.

---

# 72. Failure — Promotion Branch Missing

Check:

```text
update-gitops job ran
GitHub App token succeeded
GitOps clone succeeded
digests populated
git push succeeded
```

Inspect:

```bash
gh run view <RUN_ID>   --repo anselem-okeke/ai-platform-operator   --log
```

---

# 73. Failure — Promotion Changed Extra Files

Normal image promotion must change exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Anything else:

```text
stop
do not merge
fix automation
```

---

# 74. Failure — GitOps Validation Rejects Image

Render:

```bash
kubectl kustomize   platform/api/overlays/dev   | grep 'image:'
```

Check:

```text
approved GHCR repo
@sha256:
64 hex characters
```

---

# 75. Failure — Argo OutOfSync

Refresh:

```bash
argocd app get   ai-platform-api   --refresh
```

Diff:

```bash
argocd app diff   ai-platform-api
```

Determine whether the difference is:

```text
new Git commit
manual drift
admission failure
controller mutation
```

Do not patch live state blindly.

---

# 76. Failure — Argo Sync Rejected by Admission

Inspect:

```bash
kubectl get events   -n ai-platform   --sort-by=.lastTimestamp
```

Common causes:

```text
bad digest syntax
wrong registry
missing attestation
fake digest
Policy Controller unavailable
webhook TLS problem
```

---

# 77. Failure — Trusted Digest Denied

Check in order:

```text
exact image reference
namespace label
TrustRoot github
ClusterImagePolicy github-policy
GitHub trust-policy image scope
attestation existence
Policy Controller readiness
webhook certificate health
```

---

# 78. Failure — Public Image Allowed

Treat as a security-control failure.

Check:

```text
ValidatingAdmissionPolicy
Binding
validationActions: Deny
namespace selector
Sigstore namespace opt-in
Policy Controller webhook
```

Repair before continuing normal delivery.

---

# 79. Failure — Fake Digest Allowed

Treat as critical.

Native policy may accept the syntax.

Sigstore must reject a digest without trusted evidence.

Inspect:

```text
TrustRoot
ClusterImagePolicy
trust-policies release
Policy Controller webhook
namespace enforcement
```

---

# 80. Failure — Init Container Allowed

Inspect native policy for:

```text
spec.initContainers
```

and verify full Pod image coverage.

Use `034-pod-init-and-ephemeral-container-policy.md` for the deeper implementation.

---

# 81. Failure — Ephemeral Container Allowed

Check:

```text
UPDATE operation
pods/ephemeralcontainers
spec.ephemeralContainers
binding scope
webhook behavior
```

Do not allow arbitrary debug images in protected namespaces.

---

# 82. Failure — Live Digest Does Not Match Git

Compare in this order:

```text
GitOps overlay
Kustomize render
Argo revision
live Deployment image
```

Commands:

```bash
git show   HEAD:platform/api/overlays/dev/kustomization.yaml
```

```bash
kubectl kustomize   platform/api/overlays/dev   | grep 'image:'
```

```bash
argocd app get ai-platform-api
```

```bash
kubectl get deployment   ai-platform-api   -n ai-platform   -o jsonpath='{.spec.template.spec.containers[*].image}{"
"}'
```

Find the first point where the values diverge.

---

# 83. Failure — Manual Cluster Patch Exists

If someone used:

```text
kubectl set image
kubectl patch
kubectl edit
```

live state may differ from Git.

Preferred recovery:

```text
fix Git if desired state is wrong
otherwise let Argo restore Git state
```

Manual drift is not the normal operating model.

---

# 84. Narrow Argo Drift Exception

A known Policy Controller webhook mutation added:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

The correct response is a **narrow** `ignoreDifferences` rule targeting only that controller-managed selector.

Use:

```yaml
syncOptions:
  - RespectIgnoreDifferences=true
```

Do not ignore the entire webhook resource.

---

# 85. Rollback — Identify Previous Known-Good State

```bash
cd /mnt/data/ai-platform-gitops

git log   -p   -- platform/api/overlays/dev/kustomization.yaml      platform/operator/overlays/dev/kustomization.yaml
```

Choose a prior commit containing known-good trusted digests.

---

# 86. Rollback — Create Revert Branch

```bash
git switch -c   rollback/revert-${GITOPS_SHA:0:12}
```

Revert:

```bash
git revert "${GITOPS_SHA}"
```

Review:

```bash
git diff HEAD^
```

The revert should restore previous digest state only.

---

# 87. Rollback — Validate Reverted State

Render:

```bash
kubectl kustomize   platform/operator/overlays/dev   >/tmp/rollback-operator.yaml
```

```bash
kubectl kustomize   platform/api/overlays/dev   >/tmp/rollback-api.yaml
```

Run kubeconform and:

```bash
git diff --check
```

Rollback must pass the same GitOps controls as forward delivery.

---

# 88. Rollback — Open PR

```bash
git push   -u origin   "rollback/revert-${GITOPS_SHA:0:12}"
```

Create:

```bash
gh pr create   --repo anselem-okeke/ai-platform-gitops   --base main   --head "rollback/revert-${GITOPS_SHA:0:12}"   --title "revert(dev): rollback deployment ${GITOPS_SHA:0:12}"   --body "Restores the previous known-good digest-pinned deployment."
```

Wait for validation, review, and merge.

Argo then reconciles to the previous trusted digest.

---

# 89. Rollback — Verify Runtime

```bash
kubectl get deployment   ai-platform-api   -n ai-platform   -o jsonpath='{.spec.template.spec.containers[*].image}{"
"}'
```

Expected:

```text
previous known-good digest restored
```

The rollback must still pass native and Sigstore admission.

---

# 90. Minimal Delivery Evidence

Retain:

```text
source PR number
SOURCE_SHA
release RUN_ID
OPERATOR_DIGEST
API_DIGEST
GitOps PR number
GITOPS_SHA
Argo revision
live API digest
live operator digest
```

Do not record credentials.

---

# 91. Example Traceability Record

```text
Source PR:
<PR_NUMBER>

Source SHA:
<SOURCE_SHA>

Release Run:
<RUN_ID>

Operator Digest:
sha256:<64hex>

API Digest:
sha256:<64hex>

GitOps PR:
<PR_NUMBER>

GitOps Merge SHA:
<GITOPS_SHA>

API Live Image:
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>

Operator Live Image:
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<64hex>
```

---

# 92. What Must Be Read from the Actual Repositories

Do not invent:

```text
exact workflow job IDs
exact source workflow step IDs
exact GitHub Actions secret names
exact GitHub Actions variable names
exact checkout action SHAs
exact kubeconform checksum
exact GitOps validation regex
exact Argo Application names
exact native policy names
exact CEL expressions
exact Pod label selectors
```

Inspect source:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,520p'   .github/workflows/release-images.yml

sed -n '1,360p'   .github/workflows/security.yml

sed -n '1,320p'   .github/workflows/secret-scan.yml
```

Inspect GitOps:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,500p'   .github/workflows/validate.yml

find platform/policies   -maxdepth 3   -type f   -print   | sort

find clusters/dev/apps   -maxdepth 1   -type f   -print   | sort
```

Use the committed files as source of truth before claiming exact parity.

---

# 93. References

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

GitHub Artifact Attestations:

```text
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

Kubernetes image digests:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```
