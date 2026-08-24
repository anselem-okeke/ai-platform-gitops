# Troubleshooting Guide

## Purpose

This document is the **implementation-focused troubleshooting runbook** for the AI Platform.

It is written for engineers who need to identify **where the delivery or runtime chain is broken**, fix the actual root cause, and restore the platform without bypassing security controls.

The platform delivery path is:

```text
Source PR
    |
    v
Required CI checks
    |
    v
Protected source main
    |
    v
Release workflow
    |
    +--> Build
    +--> Trivy
    +--> GHCR
    +--> SBOM
    +--> Attestations
    |
    v
GitHub App
    |
    v
GitOps PR
    |
    v
GitOps validation
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
Sigstore
    |
    v
Kubernetes workload
    |
    v
Prometheus observability
```

The correct troubleshooting method is:

```text
find the first broken layer
fix that layer
re-run from that point
do not disable downstream controls
```

---

# 1. Troubleshooting Order

Always diagnose in this order:

```text
1. local repository state
2. source CI
3. source branch protection
4. release workflow
5. image build
6. Trivy
7. GHCR push
8. SBOM/provenance
9. GitHub App authentication
10. GitOps branch creation
11. GitOps PR
12. GitOps validation
13. GitOps branch protection
14. Argo CD
15. native admission
16. Sigstore trust
17. Kubernetes rollout
18. Gateway/routing
19. observability
20. secrets
```

Do not start by changing admission or Argo if the actual problem is in source CI or release automation.

---

# 2. Quick Environment Check

Verify cluster context:

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

Verify cluster:

```bash
kubectl cluster-info
```

Verify Kubernetes:

```bash
kubectl version
```

Validated version:

```text
v1.36.1
```

If the context is wrong, stop immediately.

---

# 3. Quick Source Repository Check

```bash
cd /mnt/data/ai-platform-operator

git status --short
git branch --show-current
git remote -v
```

Expected:

```text
correct source repo
expected branch
no unrelated local changes
```

Refresh:

```bash
git fetch --all --prune
```

---

# 4. Quick GitOps Repository Check

```bash
cd /mnt/data/ai-platform-gitops

git status --short
git branch --show-current
git remote -v
```

Expected GitOps remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Refresh:

```bash
git fetch --all --prune
```

---

# 5. Problem — Source PR Checks Are Missing

Symptom:

```text
PR opened
but one or more expected checks do not appear
```

Expected required checks:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

Inspect workflows:

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

# 6. Fix — PR Workflow Trigger Missing

Inspect workflow:

```bash
sed -n '1,140p' \
  .github/workflows/<WORKFLOW>.yml
```

Verify:

```yaml
on:
  pull_request:
```

or equivalent.

If the workflow only runs on:

```text
push to main
```

it cannot protect PR merge.

Fix in Git, push PR, and re-check.

---

# 7. Problem — Check Runs but Merge Still Allowed

This means the check is informational, not enforced.

Inspect source ruleset:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Validated ruleset:

```text
Source Main Protection
ID 21120105
active
no bypass
```

Verify the exact check is listed under required status checks.

---

# 8. Fix — Required Check Name Mismatch

GitHub branch protection matches the exact status-check name.

A workflow/job rename can break enforcement.

Inspect actual PR check names:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Compare to ruleset.

If different:

```text
update ruleset to exact live check name
```

Do not assume workflow filename equals status-check name.

---

# 9. Problem — Gitleaks Fails

Run locally:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

Then GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Determine:

```text
file
commit
rule ID
secret type
```

Do not paste the full secret into tickets or chat.

---

# 10. Fix — Real Secret Found

If real:

```text
1. revoke/rotate immediately
2. remove from current Git
3. clean history if necessary
4. re-run Gitleaks
5. inspect CI logs
6. inspect GitHub activity
```

Rotation comes before history cleanup.

---

# 11. Problem — Gitleaks False Positive

Classify carefully.

Possible false positives:

```text
public key
fake test value
hash
digest
documentation placeholder
random identifier
```

Do not disable the rule globally.

Use a narrow allowlist only if the value is provably harmless.

---

# 12. Problem — govulncheck Fails

Run:

```bash
cd /mnt/data/ai-platform-operator

govulncheck ./...
```

Validated CLI version:

```text
v1.7.0
```

Determine whether finding is:

```text
reachable
unreachable/imported
```

The current project validation target is:

```text
0 reachable vulnerabilities
```

---

# 13. Fix — Reachable Vulnerability

Identify:

```text
module
package
symbol
fixed version
call path
```

Update dependency if a compatible fixed version exists.

Then:

```bash
go mod tidy
go test ./...
govulncheck ./...
```

Do not suppress reachable vulnerabilities without documented risk acceptance.

---

# 14. Problem — CodeQL Fails

Inspect security workflow:

```bash
sed -n '1,360p' \
  .github/workflows/security.yml
```

Validated CodeQL action pin:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

Check GitHub PR annotations and workflow logs.

Fix the reported code path.

Do not remove CodeQL from required checks to proceed.

---

# 15. Problem — Release Workflow Does Not Start

After merge:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --workflow release-images.yml \
  --limit 10
```

Inspect trigger:

```bash
sed -n '1,120p' \
  .github/workflows/release-images.yml
```

Expected:

```text
push to main
```

Verify the PR actually merged to `main`.

---

# 16. Problem — Release Runs for Wrong SHA

Inspect run:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --json headSha,event,status,conclusion
```

Compare:

```bash
git rev-parse origin/main
```

Expected:

```text
run headSha equals merged source SHA
```

If not, you are looking at the wrong run.

---

# 17. Problem — Operator Build Fails

Inspect logs:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --log \
  | grep -nEi \
    'build-operator|error|failed|Dockerfile'
```

Reproduce locally:

```bash
cd /mnt/data/ai-platform-operator

docker build \
  -f Dockerfile \
  -t ai-platform-operator:debug \
  .
```

Use actual Dockerfile name.

---

# 18. Problem — API Build Fails

Inspect release workflow for API Dockerfile:

```bash
grep -nA20 -B10 \
  'ai-platform-api' \
  .github/workflows/release-images.yml
```

Then reproduce:

```bash
docker build \
  -f <API_DOCKERFILE> \
  -t ai-platform-api:debug \
  .
```

---

# 19. Problem — Distroless Container Fails at Runtime

The runtime image:

```text
gcr.io/distroless/static-debian13:nonroot
```

does not provide:

```text
shell
package manager
common troubleshooting tools
```

Do not try:

```bash
kubectl exec ... -- sh
```

and assume image is broken.

Instead inspect:

```bash
kubectl logs
kubectl describe pod
kubectl get pod -o yaml
```

Use an approved debug strategy if deeper inspection is required.

---

# 20. Problem — Container Runs as Root

Inspect image:

```bash
docker inspect \
  <IMAGE> \
  --format '{{.Config.User}}'
```

Validated expected user:

```text
65532
```

Inspect Dockerfile final stage.

Expected:

```dockerfile
USER 65532:65532
```

or equivalent distroless nonroot configuration.

---

# 21. Problem — Trivy Blocks Release

Inspect logs:

```bash
gh run view <RUN_ID> \
  --repo anselem-okeke/ai-platform-operator \
  --log \
  | grep -nEi \
    'Trivy|HIGH|CRITICAL'
```

Validated policy:

```text
HIGH,CRITICAL
ignore-unfixed
exit code 1
```

Determine:

```text
package
installed version
fixed version
base image or app dependency
```

---

# 22. Fix — Trivy Finding in Base Image

Inspect Dockerfile base:

```bash
grep -n '^FROM' \
  Dockerfile*
```

If fix exists:

```text
update base image intentionally
rebuild
rescan
```

Do not switch to a larger/less secure image just to remove one finding without evaluating risk.

---

# 23. Problem — Trivy Failure Still Creates GitOps PR

This is a pipeline-design failure.

Inspect job dependencies:

```bash
grep -nE \
  '^  build-operator:|^  build-api:|^  update-gitops:|needs:' \
  .github/workflows/release-images.yml
```

Expected:

```text
update-gitops requires both successful image jobs
```

Fix `needs:` or conditional logic.

---

# 24. Problem — GHCR Push Fails

Check release logs for:

```text
authentication
permission denied
repository not found
package write denied
```

Inspect workflow permissions.

Expected concept:

```yaml
permissions:
  contents: read
  packages: write
```

Attestation steps may also require:

```text
id-token: write
attestations: write
```

Use actual workflow.

---

# 25. Problem — Image Digest Missing

Promotion requires:

```text
sha256:<64hex>
```

Inspect build/push step outputs.

Validate:

```bash
[[ "${DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]
```

If empty:

```text
wrong step ID
wrong output reference
push step failed
output not exported
```

Fix workflow output wiring.

---

# 26. Problem — SBOM Generation Fails

Inspect:

```bash
grep -nEi \
  'syft|sbom|spdx' \
  .github/workflows/release-images.yml
```

Check:

```text
tool installation
image reference
registry auth
output path
filesystem permissions
```

Do not skip SBOM generation silently.

---

# 27. Problem — Provenance Attestation Fails

Validated action:

```text
actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Check:

```text
id-token: write
attestations: write
subject-name
subject-digest
push-to-registry
```

The subject digest must be the exact pushed digest.

---

# 28. Problem — SBOM Attestation Fails

Inspect:

```bash
grep -nA16 -B6 \
  'sbom-path' \
  .github/workflows/release-images.yml
```

Check:

```text
SBOM file exists
path is correct
digest matches image
attestation permissions present
```

---

# 29. Problem — GitHub App Token Step Fails

Validated action:

```text
actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Inspect:

```bash
grep -nA24 -B8 \
  'bcd2ba49218906704ab6c1aa796996da409d3eb1' \
  .github/workflows/release-images.yml
```

Check exact:

```text
App ID/Client ID input
private-key secret reference
owner
repositories
```

---

# 30. Problem — GitHub App Returns `Not Found`

This is a known real failure.

The GitHub API error occurred when looking up the repository installation.

Check in this order:

```text
1. App exists
2. App installed on the account
3. ai-platform-gitops included in installation
4. owner is anselem-okeke
5. repository name is ai-platform-gitops
6. App ID/Client ID belongs to same App
7. private key belongs to same App
8. permissions include Contents + Pull requests
```

Do not rotate random values until installation scope is verified.

---

# 31. Fix — App Not Installed on Repository

Open GitHub App installation settings.

Ensure repository selection includes:

```text
ai-platform-gitops
```

Then rerun the workflow.

No workflow change is required if configuration was the only issue.

---

# 32. Problem — GitOps Branch Is Not Created

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

If missing, inspect release logs after token creation.

---

# 33. Problem — Git Push Permission Denied

Verify GitHub App permissions:

```text
Contents: Read & write
```

Verify token is used for the GitOps clone/push.

Do not use the default `GITHUB_TOKEN` for a different repository unless architecture explicitly supports it.

---

# 34. Problem — GitOps PR Not Created

Check:

```text
branch push succeeded
Pull requests permission exists
PR creation command/action succeeded
base branch main exists
head branch exists
```

Inspect workflow logs.

---

# 35. Problem — GitOps Promotion Changes Extra Files

Expected exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Check:

```bash
git diff \
  --name-only \
  origin/main...FETCH_HEAD \
  | sort
```

If additional files appear:

```text
stop
do not merge
inspect update script
```

---

# 36. Problem — Wrong Digest Written to Operator Overlay

Inspect:

```bash
git show \
  FETCH_HEAD:platform/operator/overlays/dev/kustomization.yaml
```

Compare with release output.

Expected:

```text
operator digest from build-operator
```

Possible cause:

```text
variable mix-up
step output name mismatch
copy/paste error
```

---

# 37. Problem — Wrong Digest Written to API Overlay

Inspect:

```bash
git show \
  FETCH_HEAD:platform/api/overlays/dev/kustomization.yaml
```

Compare against API build output.

Do not merge if digest provenance is unclear.

---

# 38. Problem — GitOps PR Validation Fails

Inspect:

```bash
gh pr checks <GITOPS_PR> \
  --repo anselem-okeke/ai-platform-gitops
```

Open failed run.

Then reproduce locally.

---

# 39. GitOps Troubleshooting — Render Operator

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

If render fails, inspect:

```text
kustomization path
patch target
resource path
image transform
YAML syntax
```

---

# 40. GitOps Troubleshooting — Render API

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

Same approach.

---

# 41. Problem — Kustomize Patch Target Not Found

Typical error:

```text
no resource matches strategic merge patch
failed to find unique target
```

This occurred previously in Argo OIDC bootstrap work.

Check:

```text
resource kind
name
namespace
apiVersion
whether base actually contains target
```

Do not keep adding patches until the target identity is correct.

---

# 42. Problem — kubeconform Fails

Run:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/operator.yaml
```

Check:

```text
invalid Kubernetes field
wrong apiVersion
wrong kind
bad schema
bad indentation
```

CRD resources may rely on:

```text
-ignore-missing-schemas
```

but core resource failures should still be investigated.

---

# 43. Problem — GitOps Validation Rejects Base Placeholder

Bases may contain:

```text
controller:latest
ai-platform-api:dev
```

The final overlay must replace them.

Validate:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  | grep 'image:'
```

Do not scan raw base only and assume it is final deployment state.

---

# 44. Problem — Final Render Still Contains `:latest`

Inspect Kustomize `images:` block.

Expected conceptual form:

```yaml
images:
  - name: controller
    newName: ghcr.io/anselem-okeke/ai-platform-operator
    digest: sha256:<64hex>
```

If `newTag:` is present in the final overlay, replace with digest-based configuration.

---

# 45. Problem — GitOps Secret Check Fails on `secretKeyRef`

A safe reference may include words like:

```text
password
token
secret
```

Inspect the exact regex in:

```text
.github/workflows/validate.yml
```

The check should reject values, not normal references.

Do not weaken the regex broadly.

---

# 46. Problem — GitOps `git diff --check` Fails

Run:

```bash
git diff --check
```

Typical causes:

```text
trailing whitespace
space-before-tab
bad conflict markers
```

Fix file formatting.

---

# 47. Problem — GitOps PR Passed but Merge Is Blocked

Check branch ruleset.

Possible causes:

```text
required review
required check stale
Code Owner review missing
branch out of date
```

Inspect GitHub PR merge box and ruleset.

Do not bypass protection with admin force merge.

---

# 48. Problem — Argo Root Application Is Missing

Check:

```bash
argocd app list
```

If missing:

```bash
kubectl apply \
  -f /mnt/data/ai-platform-gitops/clusters/dev/root-application.yaml
```

Root remains manual sync by design.

---

# 49. Problem — AppProject Missing

Check:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd
```

If absent:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml

kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

---

# 50. Problem — Argo Application Is OutOfSync

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

Classify the diff:

```text
new Git commit not yet applied
manual cluster drift
controller mutation
admission rejection
missing secret
resource ownership problem
```

---

# 51. Problem — Argo Application Is Degraded

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

Look for:

```text
FailedCreate
ImagePullBackOff
CrashLoopBackOff
admission denied
Secret not found
```

---

# 52. Problem — Argo Self-Heal Does Not Restore Drift

Inspect Application:

```bash
argocd app get \
  <APP> \
  -o yaml
```

Expected child policy concept:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

If absent in Git, fix Git.

Do not manually patch live resources permanently.

---

# 53. Problem — Argo Keeps Reverting a Required Controller Mutation

First determine whether the field is controller-owned.

Known case:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

from Policy Controller webhook behavior.

Use narrow `ignoreDifferences`.

Do not ignore the whole resource.

---

# 54. Problem — Policy Controller Argo App OutOfSync

Inspect:

```bash
argocd app diff \
  policy-controller
```

If diff is only the known Knative selector, verify the exact narrow ignore.

If other fields differ, do not assume they are harmless.

Investigate separately.

---

# 55. Problem — Policy Controller Helm Install Fails with CRD Ownership Error

Known error pattern:

```text
CRD already exists
ownership annotation points to another release namespace
cannot import into current release
```

The project previously attempted installation into:

```text
artifact-attestations
```

while CRDs were already owned by:

```text
release-name: policy-controller
release-namespace: cosign-system
```

Correct target:

```text
cosign-system
```

Do not install a second release.

---

# 56. Fix — Standardize Policy Controller Release

Check:

```bash
helm list -A \
  | grep policy-controller
```

Expected:

```text
one release
namespace cosign-system
chart 0.10.6
```

If a stale second release exists, remove only after confirming resource ownership.

---

# 57. Problem — Policy Controller Pod Not Ready

Check:

```bash
kubectl get pods \
  -n cosign-system
```

Describe:

```bash
kubectl describe pod \
  -n cosign-system \
  <POD>
```

Logs:

```bash
kubectl logs \
  -n cosign-system \
  <POD> \
  --tail=300
```

Investigate:

```text
CRD missing
webhook cert issue
invalid config
RBAC
image pull
```

---

# 58. Problem — ValidatingWebhookConfiguration Missing

Check:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev
```

If missing:

```text
Policy Controller install incomplete
Argo/Helm reconciliation failed
```

Restore controller rather than creating webhook manually.

---

# 59. Problem — Webhook TLS Error

Inspect:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Check:

```text
service namespace
service name
caBundle
```

Inspect Policy Controller logs.

Query reconciliation metric:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

---

# 60. Problem — Admission Rejects Trusted API Digest

Start with exact image:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

Expected form:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>
```

Then check native policy, Sigstore trust, namespace label, and attestation.

---

# 61. Problem — Native Admission Rejects Correct Digest Format

Inspect exact policy:

```bash
kubectl get validatingadmissionpolicies \
  -o yaml
```

Check:

```text
regex
repository allowlist
optional-field handling
resource rules
namespace scope
```

If regex is too strict, fix in GitOps and re-test.

---

# 62. Problem — Native Admission Allows `nginx:latest`

Treat as security-critical.

Check:

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
```

Verify Binding uses:

```yaml
validationActions:
  - Deny
```

Verify namespace is selected.

---

# 63. Problem — Native Policy Exists but Does Nothing

Likely cause:

```text
Binding missing
Binding references wrong policy
namespace selector mismatch
resourceRules wrong
```

Policy alone is not enforcement.

Inspect Binding:

```bash
kubectl get validatingadmissionpolicybindings \
  -o yaml
```

---

# 64. Problem — Init Container Bypasses Policy

Test:

```yaml
spec:
  initContainers:
    - image: nginx:latest
```

If allowed, inspect CEL for:

```text
object.spec.initContainers
```

and workload template equivalents.

Fix in GitOps.

Re-run negative test.

---

# 65. Problem — Ephemeral Container Bypasses Policy

Attempt:

```bash
kubectl debug \
  -n ai-platform \
  <TRUSTED_POD> \
  --image=nginx:latest
```

If allowed, inspect:

```text
UPDATE operations
pods/ephemeralcontainers resource rule
object.spec.ephemeralContainers
webhook coverage
```

Do not disable debug restrictions globally.

---

# 66. Problem — Deployment Is Accepted but ReplicaSet Pod Is Denied

This means Pod-level enforcement works, but workload-template validation may be missing.

Security still blocks runtime creation.

For better developer feedback, add template validation if intended.

Do not falsely document Deployment rejection if only Pod rejection is implemented.

---

# 67. Problem — Fake Digest Passes Native Policy but Fails Sigstore

This is expected.

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaa...64
```

Native layer:

```text
structure may pass
```

Sigstore:

```text
must deny
```

Validated error:

```text
no valid bundles exist in registry
```

This is correct defense in depth.

---

# 68. Problem — Fake Digest Is Allowed

Treat as critical.

Check:

```bash
kubectl get trustroot \
  github \
  -o yaml

kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Check namespace label.

Check Policy Controller webhook health.

Do not continue releases until fixed.

---

# 69. Problem — TrustRoot Missing

Check:

```bash
kubectl get trustroots.policy.sigstore.dev
```

If missing:

```bash
argocd app sync \
  trust-policies
```

Use actual Application name.

Expected:

```text
github
```

---

# 70. Problem — ClusterImagePolicy Missing

Check:

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Expected:

```text
github-policy
```

Restore trust-policies child Application.

---

# 71. Problem — Trust Policy Scope Too Narrow

Inspect:

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

Validated images:

```text
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**
```

If a new first-party image is introduced, update trust policy deliberately.

Do not broaden to:

```text
ghcr.io/anselem-okeke/**
```

unless required and reviewed.

---

# 72. Problem — Trust Policy Scope Too Broad

Reduce scope to exact first-party repositories.

Broad trust weakens admission.

Test after change:

```text
trusted first-party digest -> allow
unrelated repo -> deny
```

---

# 73. Problem — Namespace Not Protected

Check:

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

If missing, restore through GitOps namespace manifests.

---

# 74. Problem — ImagePullBackOff

Inspect Pod:

```bash
kubectl describe pod \
  -n <NAMESPACE> \
  <POD>
```

Check:

```text
image digest exists
GHCR access
registry auth
network
```

Important:

```text
admission accepted
```

does not guarantee:

```text
registry pull succeeds
```

These are different layers.

---

# 75. Problem — ErrImagePull After Digest Promotion

Verify digest exists in GHCR.

Compare:

```text
release output digest
GitOps digest
live Deployment digest
```

If GitOps digest contains typo or wrong image digest, fix GitOps promotion.

Do not change to a mutable tag.

---

# 76. Problem — CrashLoopBackOff

Inspect:

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

Possible causes:

```text
missing runtime config
missing secret
invalid command
application regression
dependency unavailable
```

This is after supply-chain admission, so do not blame Sigstore automatically.

---

# 77. Problem — Secret Not Found

Events may show:

```text
secret "<NAME>" not found
```

Check:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE>
```

If missing, restore from Vault.

Do not create secret values in Git.

---

# 78. Problem — Secret Exists but Key Missing

List keys only:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE> \
  -o json \
  | jq -r '.data | keys[]'
```

Compare to:

```text
secretKeyRef.key
```

Fix secret provisioning.

---

# 79. Problem — Application Authentication Fails After Secret Rotation

Possible causes:

```text
old Secret value still mounted
application reads only at startup
wrong credential pair
upstream credential revoked too early
```

If restart required:

```bash
kubectl rollout restart \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE>
```

Verify no persistent Git drift is introduced.

---

# 80. Problem — Vault Unreachable

Check address:

```text
https://vault.platform.local:8200
```

Test network/TLS according to the approved environment.

Do not replace Vault with plaintext Git secrets as a temporary workaround.

Restore Vault connectivity or use documented break-glass secret recovery.

---

# 81. Problem — GitHub App Private Key Lost

Generate new App key.

Store in exact GitHub Actions Secret referenced by:

```text
release-images.yml
```

Validate token creation.

Then revoke unknown/old key.

Do not commit the new key.

---

# 82. Problem — Argo OIDC Login Fails

Verify Keycloak:

```text
https://auth.ai-platform.local
```

Argo:

```text
https://argocd.ai-platform.local
```

Check:

```text
realm
client
redirect URI
PKCE
group mapper
Argo OIDC config
```

Validated client:

```text
ai-platform-argocd
```

---

# 83. Problem — Argo User Authenticates but Has Wrong Role

Check Keycloak group membership:

```text
platform-viewer
platform-deployer
platform-admin
```

Check token groups claim.

Then inspect Argo RBAC group mappings.

Do not add broad default admin access.

---

# 84. Problem — Argo Local Admin Still Enabled

After OIDC is restored, verify routine local admin is disabled.

Break-glass access should be documented separately.

Do not leave local admin enabled indefinitely after recovery.

---

# 85. Problem — API Route Is Unreachable

Check Gateway:

```bash
kubectl get gateway \
  -A
```

Check HTTPRoute:

```bash
kubectl get httproute \
  -A
```

Check API Service:

```bash
kubectl get svc \
  -n ai-platform
```

Check API Pods:

```bash
kubectl get pods \
  -n ai-platform
```

Trace:

```text
DNS
TLS
Gateway
HTTPRoute
Service
Pod
```

---

# 86. Problem — TLS Certificate Error

Check:

```text
certificate SAN
certificate chain
TLS Secret
Gateway listener
Vault PKI issuance
```

Do not disable TLS verification as a workaround.

Validated design explicitly avoids:

```text
disabled TLS verification
```

---

# 87. Problem — `api.ai-platform.local` Does Not Resolve

Check local DNS/CoreDNS/environment host mapping.

Validated CoreDNS service:

```text
10.96.0.10
```

Gateway LB:

```text
172.19.255.200
```

Determine whether name resolution failure is:

```text
host machine
cluster DNS
Gateway
```

---

# 88. Problem — Prometheus Target Missing

Check ServiceMonitor:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Check service:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

Likely causes:

```text
selector mismatch
namespaceSelector wrong
port name wrong
Prometheus selector mismatch
```

---

# 89. Problem — Prometheus Target Exists but `up == 0`

Query:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

If `0`, inspect:

```bash
kubectl get endpoints \
  policy-controller-webhook-metrics \
  -n cosign-system
```

Then direct port-forward.

---

# 90. Problem — `/metrics` Works but Prometheus Target Is Missing

This proves:

```text
Policy Controller metrics endpoint works
Prometheus discovery is broken
```

Focus on:

```text
ServiceMonitor selector
namespaceSelector
release label
Prometheus ServiceMonitor selectors
```

Do not restart Policy Controller unnecessarily.

---

# 91. Problem — PrometheusRule Exists but Alerts Missing

Inspect label:

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

This exact selector mismatch occurred before.

---

# 92. Problem — Alert Rule Shows Error

Inspect Prometheus rules API or UI.

Look for:

```text
health
lastError
```

Common causes:

```text
bad PromQL
metric renamed
label changed
syntax error
```

Evaluate the underlying query directly.

---

# 93. Problem — `PolicyControllerTargetDown` Never Fires

Current expression:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
} == 0
```

Important:

```text
target exists but scrape fails -> up=0
target disappears entirely -> series may be absent
```

The current validated rule does not claim absent-target detection.

Do not silently change semantics without testing.

---

# 94. Problem — Reconcile Alert Is Noisy

Current expression:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
) > 5
```

Investigate by reconciler:

```promql
sum by (reconciler) (
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

Fix recurring reconciliation failure before raising threshold.

---

# 95. Problem — Webhook Certificate Alert Fires

Query:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

Then inspect:

```text
Policy Controller logs
webhook service
caBundle
certificate reconciliation
```

Treat as critical.

---

# 96. Problem — Git Rollback Does Not Restore Previous Version

Compare:

```text
reverted GitOps commit
rendered digest
Argo revision
live digest
```

If Git revert only changed one image but both need paired rollback, review promotion commit.

The source release normally updates both operator and API digests together.

---

# 97. Problem — Rollback Is Blocked by Admission

This means the old digest is no longer trusted or available.

Check:

```text
GHCR artifact exists
attestation still exists
trust policy still includes repository
```

Do not bypass admission.

If old artifact cannot be trusted, produce a new safe release.

---

# 98. Problem — Argo Prunes Unexpectedly

Stop and inspect:

```text
Git commit
Application prune setting
resource removed from rendered output
owner/reference behavior
```

The project has **not** exhaustively validated destructive whole-resource prune scenarios.

Do not assume all prune behavior is safe.

---

# 99. Problem — Root Application Auto-Sync Was Enabled

The root is intentionally manual.

Restore Git:

```text
remove automated sync from root Application
```

Reason:

```text
root controls topology, destinations, repositories, permissions, child Applications
```

Child Applications may remain automated.

---

# 100. Problem — AppProject Permission Denied

Argo may report:

```text
resource ... is not permitted in project
destination ... is not permitted
repository ... is not permitted
```

Inspect:

```bash
sed -n '1,360p' \
  /mnt/data/ai-platform-gitops/argocd/projects/ai-platform.yaml
```

Add only the exact required repository/destination/resource kind.

Do not replace with wildcards.

---

# 101. Problem — Trust Policies Cannot Create ClusterImagePolicy

Check AppProject cluster resource allowlist.

Expected resource:

```text
policy.sigstore.dev
ClusterImagePolicy
```

Also:

```text
TrustRoot
```

Apply AppProject manually because it is bootstrap-managed.

---

# 102. Problem — Monitoring App Cannot Create ServiceMonitor

Check CRD exists:

```bash
kubectl get crd \
  servicemonitors.monitoring.coreos.com
```

If absent:

```text
kube-prometheus-stack not installed/healthy
```

Restore monitoring stack first.

---

# 103. Problem — Secret Scanner Flags Documentation

Use placeholders like:

```text
<SECRET>
<TOKEN>
<PRIVATE_KEY>
```

Avoid realistic secret-looking examples.

If scanner still flags a safe example, use narrow allowlisting.

Do not disable scanning for the entire docs directory.

---

# 104. Problem — Release Uses a Mutable Tag Instead of Digest

Inspect:

```text
build output
promotion script
GitOps overlay
```

Correct final state:

```text
image@sha256:<64hex>
```

Tags may exist for convenience, but are not deployment identity.

---

# 105. Problem — Source CI Deploys Directly to Kubernetes

Search:

```bash
cd /mnt/data/ai-platform-operator

grep -RInE \
  'kubectl apply|kubectl set image|argocd app sync' \
  .github/workflows
```

If direct deployment exists, remove or isolate it unless explicitly intended.

The validated architecture is:

```text
source CI
-> GitOps PR
-> merge
-> Argo
```

---

# 106. Problem — GitOps Bot Can Merge Its Own PR

Treat as governance failure.

The bot should:

```text
push automation branch
open PR
```

A human should merge.

Review repository ruleset and App permissions.

Do not grant merge bypass casually.

---

# 107. Problem — GitOps Bot Pushes Directly to `main`

Treat as security failure.

Fix workflow branch target:

```text
automation/image-<source-sha>
```

Restore main protection.

Review Git history for unauthorized direct changes.

---

# 108. Problem — Source Ruleset Has a Bypass Actor

Validated state:

```text
no bypass actors
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Remove unintended bypass.

Document any emergency bypass mechanism separately.

---

# 109. Problem — Required Check Is Stuck Pending

Check workflow run:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --limit 20
```

Possible causes:

```text
workflow not triggered
job skipped by condition
renamed job/check
concurrency lock
GitHub Actions outage
```

Do not merge by bypass until cause is understood.

---

# 110. Problem — Workflow Uses Wrong Action Revision

Security-sensitive actions should be SHA-pinned.

Known validated pins:

```text
CodeQL:
<COMMIT_SHA>

actions/attest:
<COMMIT_SHA>

create-github-app-token:
<COMMIT_SHA>
```

Inspect workflows before upgrades.

---

# 111. Problem — Kind Cluster Is Missing

Check:

```bash
kind get clusters
```

If absent, follow:

```text
042-disaster-recovery-and-rebuild.md
```

Do not manually recreate random resources one by one.

---

# 112. Problem — Local Repo Is Corrupted

Reclone from remote.

Source:

```bash
git clone \
  git@github.com:anselem-okeke/ai-platform-operator.git \
  /mnt/data/ai-platform-operator
```

GitOps:

```bash
git clone \
  https://github.com/anselem-okeke/ai-platform-gitops.git \
  /mnt/data/ai-platform-gitops
```

Then verify local branch and remote state.

---

# 113. Problem — GHCR Digest Referenced by Git No Longer Exists

Do not switch to a tag.

If artifact is unavailable:

```text
restore artifact if possible
or rebuild from exact source SHA
create new digest
create new attestations
promote through GitOps
```

A rebuild produces a new identity.

---

# 114. Problem — Attestation Exists for Wrong Digest

Treat as release-workflow wiring bug.

Check:

```text
build step output
subject-digest input
GitOps promotion variable
```

All must refer to the same digest.

Fix workflow before future releases.

---

# 115. Problem — API Deployment Is Healthy but Route Fails

Trace:

```text
Pod
Service
HTTPRoute
Gateway
TLS
DNS
```

Commands:

```bash
kubectl get pods \
  -n ai-platform

kubectl get svc \
  -n ai-platform

kubectl get httproute \
  -A

kubectl get gateway \
  -A
```

Do not redeploy application image unless backend health is actually broken.

---

# 116. Problem — Argo Login Works Only Through Port-Forward

Check whether Envoy Gateway exposure is restored.

Validated secure target:

```text
Browser
-> Envoy Gateway HTTPS
-> HTTPRoute
-> Argo CD
```

Argo server remains:

```text
ClusterIP
```

Do not replace this with public LoadBalancer exposure just to restore convenience.

---

# 117. Problem — Keycloak Group Claim Missing

Verify Keycloak client scope:

```text
groups
```

Mapper:

```text
oidc-group-membership-mapper
```

Ensure scope attached to:

```text
ai-platform-argocd
ai-platform-cli
```

Then re-authenticate to obtain a fresh token.

---

# 118. Problem — PKCE Login Fails

Validated CLI client:

```text
ai-platform-cli
```

Redirect:

```text
http://127.0.0.1:18080/callback
```

If connection refused:

```text
local callback listener not running
wrong redirect URI
port conflict
```

Do not enable Resource Owner Password/direct grants as workaround.

---

# 119. Problem — Argo Reports Permission Denied After OIDC Login

Check token groups.

Then compare with Argo RBAC mapping.

Expected platform groups:

```text
platform-viewer
platform-deployer
platform-admin
```

Fix group membership or mapping.

Do not grant everyone admin.

---

# 120. Problem — Policy Controller Metrics Service Missing

Check Helm release:

```bash
helm list -A \
  | grep policy-controller
```

Check services:

```bash
kubectl get svc \
  -n cosign-system
```

Expected:

```text
policy-controller-webhook-metrics
```

If missing after upgrade, inspect chart values/version changes.

---

# 121. Problem — Metrics Port Changed

Inspect Service:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  -o yaml
```

Validated current port:

```text
9090
```

If upstream chart changes it, update ServiceMonitor based on live service, not memory.

---

# 122. Problem — PrometheusRule Label Missing After Refactor

Check:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Ensure:

```yaml
metadata:
  labels:
    release: kps
```

This exact issue previously prevented rule selection.

---

# 123. Problem — PrometheusRule Selected but Alert Query Returns No Series

Evaluate underlying metric first.

For reconcile failures:

```promql
policy_controller_reconcile_count
```

If empty:

```text
metrics scrape problem
metric renamed
controller version changed
```

Do not tune alert threshold until metric availability is understood.

---

# 124. Problem — Upgrade Changes Metric Labels

Inspect raw metrics:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_'
```

Compare labels used in PromQL:

```text
success
reconciler
namespace_name
```

Update queries only after verifying actual new labels.

---

# 125. Problem — Documentation Command Does Not Match Repo

Use the repository as source of truth.

Inspect exact files before changing production behavior.

Source:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,520p' \
  .github/workflows/release-images.yml
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,500p' \
  .github/workflows/validate.yml
```

If documentation differs:

```text
correct the documentation
do not blindly modify working code to match stale docs
```

---

# 126. Problem — Unsure Which Layer Denied an Image

Native-policy denial usually references:

```text
ValidatingAdmissionPolicy
CEL message
```

Sigstore denial usually references:

```text
Policy Controller
ClusterImagePolicy
attestation/bundle
```

Malformed image parser errors may occur before either.

Read the actual API server error carefully.

---

# 127. Problem — Need to Isolate Native Policy from Sigstore

Use test cases deliberately.

Case 1:

```text
nginx:latest
```

Expected native structural denial.

Case 2:

```text
approved repo + fake full digest
```

Native structure may pass.

Sigstore should deny.

This separates layers cleanly.

---

# 128. Problem — Need to Isolate Init-Container Rule

Use:

```text
trusted main image
untrusted init image
```

Then:

```bash
kubectl apply \
  --dry-run=server \
  -f <TEST_YAML>
```

If denied, init coverage works.

If main image is also untrusted, the test does not isolate the init rule.

---

# 129. Problem — Need to Isolate Ephemeral-Container Rule

Start with a real trusted Pod.

Then:

```bash
kubectl debug \
  -n ai-platform \
  <TRUSTED_POD> \
  --image=nginx:latest
```

This isolates the ephemeral path better than testing a completely untrusted Pod.

---

# 130. Problem — Need to Verify GitOps vs Live Digest

Run:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  | grep 'image:'
```

Then:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

They should match exactly.

---

# 131. Problem — Need to Verify Argo Revision

```bash
argocd app get \
  ai-platform-api \
  -o json \
  | jq -r '.status.sync.revision'
```

Compare to:

```bash
cd /mnt/data/ai-platform-gitops

git rev-parse origin/main
```

If different, Argo has not reconciled to latest Git main.

---

# 132. Problem — Need to Verify Source-to-GitOps Traceability

Inspect promotion commit:

```bash
cd /mnt/data/ai-platform-gitops

git log \
  --oneline \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Expected message:

```text
chore(dev): deploy images from <source-sha>
```

Then verify source commit exists:

```bash
cd /mnt/data/ai-platform-operator

git show \
  --no-patch \
  <SOURCE_SHA>
```

---

# 133. Problem — Need to Verify GitHub App Bot Identity

Inspect GitOps commit:

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

If human developer identity appears unexpectedly, inspect release automation.

---

# 134. Problem — Secret Accidentally Added to GitOps

Immediately:

```text
1. revoke/rotate
2. remove value
3. inspect Git history
4. re-run Gitleaks
```

Do not simply add the file to `.gitignore` after it was already committed.

---

# 135. Problem — `.gitignore` Does Not Prevent Secret Commit

Remember:

```text
.gitignore does not protect tracked files
```

Check:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Run Gitleaks.

---

# 136. Problem — `.crt` Is Flagged as Sensitive

A public certificate is usually not secret.

Do not add broad:

```text
*.crt
```

ignore rules unless required.

Review whether the file contains:

```text
certificate only
or private key too
```

---

# 137. Problem — ServiceAccount/Permission Error in Workload

Inspect:

```bash
kubectl describe pod \
  -n <NAMESPACE> \
  <POD>
```

Check ServiceAccount:

```bash
kubectl get sa \
  -n <NAMESPACE>
```

Check RBAC:

```bash
kubectl auth can-i \
  <VERB> \
  <RESOURCE> \
  --as=system:serviceaccount:<NAMESPACE>:<SA>
```

Apply least privilege.

---

# 138. Problem — Argo Cannot Create Cluster-Scoped Resource

Check AppProject:

```text
clusterResourceWhitelist
```

Add exact kind only.

Do not use:

```yaml
- group: '*'
  kind: '*'
```

unless unavoidable and explicitly reviewed.

---

# 139. Problem — Gateway Certificate Does Not Match Host

Check host:

```text
api.ai-platform.local
argocd.ai-platform.local
auth.ai-platform.local
```

Inspect certificate SAN/CN.

Do not disable TLS verification.

Issue/restore correct certificate through the intended PKI path.

---

# 140. Problem — API Service Works Internally but Not Through Gateway

Test Service directly with port-forward.

Then test Gateway.

If direct works:

```text
application healthy
routing/TLS problem
```

If direct fails:

```text
application/service problem
```

Isolate before changing image or policy.

---

# 141. Problem — Argo Application Uses Wrong Repository Revision

Inspect:

```bash
argocd app get \
  <APP> \
  -o yaml
```

Check:

```text
repoURL
targetRevision
path/chart
```

For GitOps children, target should point to the intended GitOps repository state.

---

# 142. Problem — Root Application Changes Child Topology Unexpectedly

Because root is manual, inspect diff before sync:

```bash
argocd app diff \
  ai-platform-root
```

Review:

```text
new child app
deleted child app
repo changes
destination changes
permissions
```

Only sync after review.

---

# 143. Problem — Promotion PR Uses Wrong Source SHA

Compare:

```text
source merge SHA
release run headSha
branch name
PR title
commit message
```

All should point to the same source SHA.

If not, release traceability is broken.

---

# 144. Problem — Two Releases Race

Potential symptom:

```text
two automation/image-* branches
later release supersedes earlier release
```

Inspect GitOps PR order.

Do not merge an older digest after a newer validated release unless intentionally rolling back.

Use source SHA and digest to decide.

---

# 145. Problem — Old GitOps PR Is Still Open

Check whether a newer promotion exists.

If obsolete:

```text
close stale PR
```

Do not merge stale digest accidentally.

Document supersession in PR comment if useful.

---

# 146. Problem — Argo Reports Resource Pruned Unexpectedly

Inspect Git commit that removed resource.

Check Kustomize render.

If resource disappeared unintentionally:

```text
restore in Git
merge
let Argo recreate
```

Avoid manual recreation unless needed for emergency availability.

---

# 147. Problem — AppProject Change Breaks All Child Apps

Because AppProject is bootstrap-managed:

```text
fix argocd/projects/ai-platform.yaml
server dry-run
apply manually
```

Then refresh children.

Do not wait for Argo to repair a project it does not manage itself.

---

# 148. Problem — `kubectl apply --dry-run=server` Fails for CRD Resource

Check CRD exists first.

Example:

```bash
kubectl get crd \
  clusterimagepolicies.policy.sigstore.dev
```

If absent:

```text
install/restore Policy Controller CRDs first
```

Then re-run server dry-run.

---

# 149. Problem — Helm Chart Version Drift

Check:

```bash
helm list -A
```

Expected:

```text
policy-controller 0.10.6
trust-policies v0.7.0
```

If live version differs from Git:

```text
inspect Argo
inspect targetRevision
do not upgrade implicitly
```

---

# 150. Problem — Prometheus Version Differs

Validated current:

```text
v3.13.2-distroless
```

If changed, verify:

```text
ServiceMonitor discovery
PrometheusRule selection
PromQL compatibility
metric label behavior
```

Do not assume monitoring still works after upgrade.

---

# 151. Problem — Alert Exists but Alertmanager Does Not Notify

This guide validates PrometheusRule evaluation.

Do not assume notification routing exists.

Check separately:

```text
Alertmanager receivers
routes
silences
network
credentials
```

Current project does not claim all notification routes are fully validated.

---

# 152. Problem — Need to Recover from Unknown State

If multiple layers are inconsistent:

```text
1. freeze changes
2. record source main SHA
3. record GitOps main SHA
4. record Argo revisions
5. record live image digests
6. inspect admission health
7. inspect secrets availability
8. choose Git as desired-state authority
9. reconcile deliberately
```

Do not make multiple simultaneous fixes.

---

# 153. Problem — Need to Prove Platform Is Healthy After Fix

Run these minimum checks:

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

Then positive/negative admission tests.

Then Prometheus target check.

---

# 154. Minimum Positive Admission Validation

Use exact live trusted API image:

```bash
API_IMAGE="$(kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}')"

kubectl run troubleshoot-good \
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

# 155. Minimum Negative Admission Validation

```bash
kubectl run troubleshoot-bad \
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

# 156. Minimum Sigstore Validation

```bash
kubectl run troubleshoot-fake \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

with trust-related failure.

---

# 157. Minimum Monitoring Validation

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

Then:

```promql
policy_controller_reconcile_count
```

Expected:

```text
non-empty
```

---

# 158. Minimum Secret Validation

Check tracked sensitive files:

```bash
cd /mnt/data/ai-platform-gitops

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Then:

```bash
gitleaks git \
  --redact
```

Expected:

```text
clean
```

---

# 159. When to Roll Back Instead of Debugging Forward

Prefer rollback when:

```text
new release causes runtime regression
previous digest is known good
security controls are healthy
root cause is not immediately obvious
```

Rollback through Git.

Do not leave a degraded release running while debugging indefinitely.

---

# 160. When Not to Roll Back

Do not roll back if:

```text
previous digest no longer exists
previous digest no longer has valid trust evidence
issue is cluster-wide and unrelated to release
issue is secret/configuration outage affecting all versions
```

Fix the actual dependency instead.

---

# 161. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact GitHub Actions secret names
exact workflow job IDs
exact Kustomize patch names
exact native admission policy names
exact CEL expressions
exact Argo Application names
exact Gateway resource names
exact Vault secret paths
```

Inspect source:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,520p' \
  .github/workflows/release-images.yml

sed -n '1,360p' \
  .github/workflows/security.yml

sed -n '1,320p' \
  .github/workflows/secret-scan.yml
```

Inspect GitOps:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,500p' \
  .github/workflows/validate.yml

find argocd \
  clusters \
  platform \
  modelservices \
  -maxdepth 4 \
  -type f \
  -print \
  | sort
```

Use the repository and live cluster as the exact troubleshooting source of truth.

---

# 162. References

Argo CD troubleshooting:

```text
https://argo-cd.readthedocs.io/
```

Kubernetes debugging:

```text
https://kubernetes.io/docs/tasks/debug/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Prometheus troubleshooting:

```text
https://prometheus.io/docs/prometheus/latest/troubleshooting/
```

GitHub Actions troubleshooting:

```text
https://docs.github.com/actions/monitoring-and-troubleshooting-workflows
```
