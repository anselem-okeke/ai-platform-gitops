# GitOps Pull-Request Validation

## Purpose

This document is the **reproducible implementation guide** for the GitOps pull-request validation workflow used by the AI Platform.

The workflow protects changes to:

```text
/mnt/data/ai-platform-gitops
```

before they can be merged into the GitOps `main` branch and reconciled by Argo CD.

A new engineer should be able to rebuild, validate, troubleshoot, and recover the GitOps PR validation pipeline using only this document and the repository.

The validated workflow protects the following chain:

```text
GitOps branch
    |
    v
Pull Request
    |
    v
Validate GitOps Manifests
    |
    +--> Kustomize render
    +--> kubeconform
    +--> image repository validation
    +--> immutable digest validation
    +--> mutable image rejection
    +--> lightweight secret-pattern check
    +--> whitespace validation
    |
    v
required branch check
    |
    v
human merge
    |
    v
Argo CD reconciliation
```

---

# 1. Implementation Context

## GitOps Repository

Local:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

## Validation Workflow

Expected file:

```text
.github/workflows/validate.yml
```

Expected GitHub Actions workflow name:

```text
Validate GitOps
```

Expected required check/job:

```text
Validate GitOps Manifests
```

Before changing or rebuilding this workflow, inspect the actual file:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,360p' \
  .github/workflows/validate.yml
```

Search for the important controls:

```bash
grep -nE \
  'permissions:|checkout|kubeconform|kubectl kustomize|sha256|image:|secret|git diff --check|Validate GitOps Manifests' \
  .github/workflows/validate.yml
```

---

# 2. Why GitOps Needs an Independent PR Validation Pipeline

The source repository validates:

```text
Go code
tests
lint
security
image build
image scanning
SBOM
attestations
```

The GitOps repository validates something different:

```text
deployment desired state
```

A source artifact can be valid while a GitOps PR is invalid.

Examples:

```text
wrong namespace
broken Kustomize patch
malformed Application manifest
wrong image repository
floating image tag
bad image digest
accidental secret
invalid Kubernetes YAML
whitespace corruption
```

Therefore GitOps needs its own independent validation boundary.

---

# 3. Trigger

The workflow should run on pull requests affecting GitOps desired state.

Canonical shape:

```yaml
on:
  pull_request:
    branches:
      - main
```

It may also run on:

```yaml
push:
  branches:
    - main
```

to validate the merged state.

The exact trigger configuration must match the repository.

Inspect:

```bash
sed -n '1,80p' \
  .github/workflows/validate.yml
```

---

# 4. Workflow Permissions

The validated workflow uses:

```yaml
permissions: {}
```

This is intentional.

The validation job:

```text
reads repository content
renders manifests
runs local/static checks
```

It does not need default write permissions.

If checkout requires access to a private repository, use the minimum token permissions required by the repository configuration.

Do not grant:

```text
contents: write
pull-requests: write
actions: write
packages: write
id-token: write
```

unless a future validation requirement explicitly needs them.

---

# 5. Pin GitHub Actions to Full Commit SHAs

The workflow should not rely on mutable action tags such as:

```yaml
uses: actions/checkout@v4
```

The AI Platform hardening standard is:

```yaml
uses: actions/checkout@<full-commit-sha>
```

Reason:

```text
tag can move
commit SHA is immutable
```

Inspect:

```bash
grep -n 'uses:' \
  .github/workflows/validate.yml
```

Every third-party action should be reviewed and pinned.

---

# 6. Runner

Expected runner:

```yaml
runs-on: ubuntu-latest
```

If exact runner immutability is required later, pin an approved runner image strategy.

For the current project, the important security controls are:

```text
minimal workflow permissions
pinned actions
checksum-verified external tools
no deployment credentials
```

---

# 7. Repository Checkout

Canonical step:

```yaml
- name: Checkout
  uses: actions/checkout@<PINNED_SHA>
```

The checkout step should not persist credentials unnecessarily if later steps do not push.

Recommended:

```yaml
with:
  persist-credentials: false
```

for a pure validation workflow.

The GitOps validation job must never push changes back to the PR branch.

---

# 8. Install kubeconform

Validated kubeconform version:

```text
0.7.0
```

Do not download:

```text
latest
```

or resolve release assets dynamically without pinning.

The installation should:

```text
download exact version
download/check known checksum
verify checksum
extract binary
install binary
print version
```

A canonical Linux amd64 implementation is:

```bash
KUBECONFORM_VERSION="0.7.0"

curl -fsSLo /tmp/kubeconform.tar.gz \
  "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz"
```

Checksum verification must use the exact approved checksum for that release artifact.

Example structure:

```bash
echo "<APPROVED_SHA256>  /tmp/kubeconform.tar.gz" \
  | sha256sum -c -
```

Then:

```bash
tar -xzf /tmp/kubeconform.tar.gz \
  -C /tmp \
  kubeconform

sudo install \
  -m 0755 \
  /tmp/kubeconform \
  /usr/local/bin/kubeconform
```

Verify:

```bash
kubeconform -v
```

Expected:

```text
v0.7.0
```

## Important

Do not copy an invented checksum from documentation.

Use the checksum currently pinned in:

```text
.github/workflows/validate.yml
```

or verify it against the official kubeconform v0.7.0 release before rebuilding.

Inspect current workflow:

```bash
grep -n -A20 -B10 \
  'kubeconform' \
  .github/workflows/validate.yml
```

---

# 9. Why Checksum Verification Matters

A version pin alone is not enough if CI blindly downloads a release asset.

Without checksum verification:

```text
workflow requests v0.7.0
        |
        v
downloads bytes
        |
        v
executes bytes
```

With checksum verification:

```text
workflow requests v0.7.0
        |
        v
downloads bytes
        |
        v
verify SHA-256
        |
        +--> mismatch -> FAIL
        |
        v
execute approved artifact
```

This protects the CI tool bootstrap path.

---

# 10. Render Paths

The validated workflow renders these GitOps paths:

```text
platform/operator/overlays/dev
platform/api/overlays/dev
platform/gateway/overlays/dev
platform/monitoring/overlays/dev
platform/policies/overlays/dev
modelservices/overlays/dev
clusters/dev/apps
```

These represent the current dev environment and Argo child Application set.

The validation should fail if any required render fails.

---

# 11. Render Operator

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml
```

Expected:

```text
exit code 0
```

---

# 12. Render API

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

Expected:

```text
exit code 0
```

---

# 13. Render Gateway

```bash
kubectl kustomize \
  platform/gateway/overlays/dev \
  >/tmp/gateway.yaml
```

---

# 14. Render Monitoring

```bash
kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

---

# 15. Render Policies

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

---

# 16. Render ModelServices

```bash
kubectl kustomize \
  modelservices/overlays/dev \
  >/tmp/modelservices.yaml
```

---

# 17. Render Argo Child Applications

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

This validates the child Application set consumed by the root App-of-Apps Application.

---

# 18. Why Rendered Manifests Are the Security Boundary

The raw reusable bases intentionally contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

That does **not** mean the deployed dev environment may use those values.

The actual invariant is:

```text
final rendered dev workload
    must use
approved registry + immutable SHA-256 digest
```

Therefore validate:

```text
rendered overlays
```

rather than rejecting reusable base placeholders.

---

# 19. Do Not Validate Raw Bases as Final Deployment Identity

An earlier approach could incorrectly reject:

```text
platform/operator/base
platform/api/base
```

because the base contains placeholder values.

That is a false positive if the dev overlay replaces those values with immutable approved images.

Correct approach:

```text
base
  +
overlay
  |
  v
rendered manifest
  |
  v
security validation
```

Do not weaken the final digest requirement.

Fix the validation target.

---

# 20. kubeconform Validation Strategy

After rendering, run kubeconform on the generated manifests.

Canonical shape:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/operator.yaml
```

Repeat for each rendered bundle.

The validated workflow uses strict/summary behavior while tolerating missing schemas for third-party CRDs where upstream JSON schemas are unavailable.

---

# 21. Why `-ignore-missing-schemas` Is Needed

The GitOps repository contains third-party resources such as:

```text
Argo CD Applications
Prometheus ServiceMonitor
PrometheusRule
Sigstore resources
Gateway API resources
other CRDs
```

kubeconform may not have schemas for every external CRD.

Without:

```text
-ignore-missing-schemas
```

a perfectly valid third-party manifest can fail only because a schema is unavailable to kubeconform.

This option must **not** be interpreted as:

```text
ignore invalid YAML
```

It only skips resources for which no schema is available.

Built-in resources with schemas should still be validated.

---

# 22. Validate All Rendered Bundles

Example:

```bash
for file in \
  /tmp/operator.yaml \
  /tmp/api.yaml \
  /tmp/gateway.yaml \
  /tmp/monitoring.yaml \
  /tmp/policies.yaml \
  /tmp/modelservices.yaml \
  /tmp/apps.yaml
do
  echo "Validating ${file}"

  kubeconform \
    -strict \
    -summary \
    -ignore-missing-schemas \
    "${file}"
done
```

Any nonzero exit code should fail the workflow.

---

# 23. Validate Approved Runtime Registry

The operator and API final rendered images must come from:

```text
ghcr.io/anselem-okeke/
```

Expected images:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

The validation should not permit an arbitrary external registry for these first-party workloads.

---

# 24. Extract Rendered Images

Inspect:

```bash
grep -n 'image:' \
  /tmp/operator.yaml \
  /tmp/api.yaml
```

Expected to find the final operator/API runtime images.

For stronger validation, parse YAML rather than relying solely on unstructured grep.

If the current workflow already implements a tested shell/Python validator, preserve it.

---

# 25. Digest Requirement

The final first-party image identity must contain:

```text
@sha256:
```

and the digest must contain exactly:

```text
64 hexadecimal characters
```

Valid:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:0123456789abcdef...64hex
```

Invalid:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
ghcr.io/anselem-okeke/ai-platform-api:dev
ghcr.io/anselem-okeke/ai-platform-api:v1
ghcr.io/anselem-okeke/ai-platform-api@sha256:1234
docker.io/example/api@sha256:<digest>
```

---

# 26. Recommended Image Validation Logic

A reliable validator should enforce both:

```text
repository allowlist
digest format
```

Conceptually:

```python
allowed = (
    "ghcr.io/anselem-okeke/ai-platform-operator@sha256:",
    "ghcr.io/anselem-okeke/ai-platform-api@sha256:",
)
```

Then verify:

```text
prefix is approved
digest is exactly 64 lowercase/uppercase hex characters
no mutable tag is final identity
```

If the actual workflow uses shell logic, document and preserve that exact implementation.

---

# 27. Validate No Final `newTag` Dependency

Kustomize may support:

```yaml
newTag:
```

but the final deployment identity should not depend on a mutable tag.

Search rendered final state:

```bash
grep -RIn \
  'image:' \
  /tmp/operator.yaml \
  /tmp/api.yaml
```

Then verify the rendered image includes:

```text
@sha256:
```

The strongest invariant is the rendered final image, not whether the source Kustomization happens to contain an unused `newTag` field.

---

# 28. Validate Operator Image Exactly

Expected repository:

```text
ghcr.io/anselem-okeke/ai-platform-operator
```

Recommended test:

```bash
grep -E \
  'image: +ghcr\.io/anselem-okeke/ai-platform-operator@sha256:[0-9a-fA-F]{64}$' \
  /tmp/operator.yaml
```

If not found:

```text
FAIL
```

If your generated YAML contains quoting or different whitespace, use a YAML-aware parser instead of weakening the digest rule.

---

# 29. Validate API Image Exactly

Expected repository:

```text
ghcr.io/anselem-okeke/ai-platform-api
```

Recommended test:

```bash
grep -E \
  'image: +ghcr\.io/anselem-okeke/ai-platform-api@sha256:[0-9a-fA-F]{64}$' \
  /tmp/api.yaml
```

---

# 30. Reject Floating First-Party Images

The workflow should reject rendered first-party images such as:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
ghcr.io/anselem-okeke/ai-platform-api:main
ghcr.io/anselem-okeke/ai-platform-api:dev
ghcr.io/anselem-okeke/ai-platform-operator:v1.2.3
```

Even semantic version tags are mutable registry references.

The immutable identity is:

```text
repository@sha256:digest
```

---

# 31. Lightweight Secret Pattern Check

The GitOps workflow includes an additional lightweight secret-pattern scan.

This is:

```text
defense in depth
```

It does **not** replace Gitleaks.

Search likely dangerous values in tracked GitOps files.

Examples of patterns worth flagging:

```text
BEGIN PRIVATE KEY
BEGIN RSA PRIVATE KEY
password:
token:
client_secret:
.aws_secret_access_key
private_key:
```

But pattern design must minimize false positives from documentation keys or Kubernetes references.

The exact pattern in the current workflow should be preserved unless deliberately improved.

Inspect:

```bash
grep -n -A30 -B10 \
  -Ei 'secret|private.key|password|token' \
  .github/workflows/validate.yml
```

---

# 32. What GitOps May Legitimately Contain

GitOps may contain references such as:

```yaml
secretKeyRef:
  name: example-secret
  key: password
```

This is not the same as storing:

```yaml
password: actual-secret-value
```

Therefore secret validation must distinguish:

```text
secret references
```

from:

```text
secret material
```

Do not create a simplistic check that rejects every appearance of the word:

```text
password
```

---

# 33. Gitleaks Remains the Primary Secret Scanner

The lightweight workflow pattern is an additional safety net.

Repository secret-history validation should still use Gitleaks separately.

The controls complement each other:

```text
lightweight PR pattern check
         +
Gitleaks repository/history scan
```

---

# 34. Whitespace Validation

Run:

```bash
git diff --check
```

Expected:

```text
no output
exit code 0
```

This catches:

```text
trailing whitespace
space-before-tab problems
merge artifact whitespace issues
```

---

# 35. Validate the GitOps Application Set

The path:

```text
clusters/dev/apps
```

contains child Argo CD Applications.

Render:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Inspect:

```bash
grep -nE \
  '^kind: Application$|^  name:' \
  /tmp/apps.yaml
```

Expected child applications include the current platform components such as:

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

Exact names must match the repository.

---

# 36. Validate Kustomize from Repository Root

Always run local reproduction from:

```bash
cd /mnt/data/ai-platform-gitops
```

because paths are repository-relative.

Do not document commands that require an unexplained working directory.

---

# 37. Complete Local Reproduction

Run:

```bash
cd /mnt/data/ai-platform-gitops

set -euo pipefail

kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml

kubectl kustomize \
  platform/gateway/overlays/dev \
  >/tmp/gateway.yaml

kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml

kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml

kubectl kustomize \
  modelservices/overlays/dev \
  >/tmp/modelservices.yaml

kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Then:

```bash
for file in \
  /tmp/operator.yaml \
  /tmp/api.yaml \
  /tmp/gateway.yaml \
  /tmp/monitoring.yaml \
  /tmp/policies.yaml \
  /tmp/modelservices.yaml \
  /tmp/apps.yaml
do
  kubeconform \
    -strict \
    -summary \
    -ignore-missing-schemas \
    "${file}"
done
```

Then:

```bash
grep -n 'image:' \
  /tmp/operator.yaml \
  /tmp/api.yaml
```

Finally:

```bash
git diff --check
```

---

# 38. Server-Side Dry Run

When testing from an engineer workstation with access to the development cluster, use server-side dry run for resources whose CRDs are installed.

Example:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/monitoring.yaml
```

This validates against the live API server and installed CRDs.

Do **not** require the GitHub Actions validation workflow to hold broad cluster credentials just for this check.

The CI pipeline remains primarily static/offline by design.

---

# 39. Server-Side Dry Run Limitations

A server dry run can fail if:

```text
required CRD is not installed
webhook dependency is unavailable
namespace prerequisite is absent
cluster version differs
```

This makes it useful for environment validation but unsuitable as the only portable GitOps CI control.

Use:

```text
kubeconform + render
```

for repository CI and:

```text
server dry-run
```

for environment-specific validation.

---

# 40. GitHub Branch Protection Integration

The validation workflow only becomes an enforcement control if GitHub requires it before merge.

Required check:

```text
Validate GitOps Manifests
```

The GitOps `main` branch should require:

```text
pull request
required validation check
no force push
no branch deletion
human-controlled merge
```

See:

```text
027-branch-protection-and-rulesets.md
```

---

# 41. Verify the Required Check in Practice

Create a pull request with an intentional validation failure.

For example, temporarily change the rendered API image to:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
```

Expected:

```text
Validate GitOps Manifests = FAIL
merge = BLOCKED
```

Restore the valid digest before merging.

Do this only in a controlled test branch.

---

# 42. Positive Image Validation Test

Use a valid digest:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>
```

Expected:

```text
image validation PASS
```

---

# 43. Negative Mutable Tag Test

Set:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
```

Expected:

```text
workflow FAIL
```

The failure should clearly state that the final rendered first-party image is not digest pinned.

---

# 44. Negative Wrong Registry Test

Set:

```text
docker.io/example/ai-platform-api@sha256:<64hex>
```

Expected:

```text
workflow FAIL
```

A syntactically valid digest is not enough.

Repository trust matters.

---

# 45. Negative Short Digest Test

Set:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:1234
```

Expected:

```text
workflow FAIL
```

---

# 46. Negative Broken Kustomize Test

Introduce an invalid Kustomize resource reference.

Expected failure at:

```text
kubectl kustomize
```

The workflow should stop before kubeconform/image validation.

---

# 47. Negative Invalid Kubernetes Manifest Test

Create a built-in Kubernetes resource with an invalid field.

Expected:

```text
kubeconform FAIL
```

This verifies schema validation.

---

# 48. Negative Secret Material Test

In a controlled test branch, add an obvious private-key marker:

```text
-----BEGIN PRIVATE KEY-----
```

Expected:

```text
secret-pattern validation FAIL
```

Remove immediately after confirming the control.

Do not use a real private key.

---

# 49. Negative Whitespace Test

Add trailing whitespace intentionally.

Run:

```bash
git diff --check
```

Expected:

```text
failure
```

This verifies the workflow check is wired correctly.

---

# 50. Troubleshooting: kubeconform Not Found

Symptom:

```text
kubeconform: command not found
```

Check installation step logs.

Verify:

```bash
which kubeconform
kubeconform -v
```

If checksum validation failed, do not bypass it.

Confirm:

```text
version
asset filename
architecture
expected checksum
```

---

# 51. Troubleshooting: kubeconform Checksum Mismatch

Symptom:

```text
FAILED
sha256sum: WARNING
```

Possible causes:

```text
wrong asset
wrong version
wrong architecture
incorrect documented checksum
upstream asset changed unexpectedly
download proxy corruption
```

Do not proceed.

Re-verify the official release checksum and pinned artifact.

---

# 52. Troubleshooting: Missing CRD Schema

Symptom:

```text
could not find schema for ...
```

If the resource is a legitimate third-party CRD:

```text
use -ignore-missing-schemas
```

Do not add a fake schema just to make CI green.

If the resource is a built-in Kubernetes kind and schema is unexpectedly missing, investigate the kubeconform Kubernetes schema/version configuration.

---

# 53. Troubleshooting: Raw Base `latest` False Positive

Symptom:

```text
validation rejects controller:latest
```

but final dev overlay renders a digest.

Root cause:

```text
validator scanned reusable raw base instead of final render
```

Fix:

```text
validate /tmp/operator.yaml
validate /tmp/api.yaml
```

Do not weaken the runtime digest requirement.

---

# 54. Troubleshooting: Final Render Still Contains Mutable Tag

This is a real failure.

Inspect:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  | grep -n 'image:'
```

Then inspect:

```bash
sed -n '1,220p' \
  platform/api/overlays/dev/kustomization.yaml
```

Check that the `images:` transform correctly matches the base image name and supplies the digest.

---

# 55. Troubleshooting: Wrong Image Repository

If render shows:

```text
ghcr.io/someone-else/...
```

check:

```text
newName
Kustomize image selector
base Deployment image
overlay
automation update script
```

The final first-party images must remain under the approved organization repository path.

---

# 56. Troubleshooting: Validation Workflow Does Not Run

Check:

```text
workflow filename
YAML syntax
on.pull_request
target branch
path filters
GitHub Actions enabled
```

Use:

```bash
gh workflow list \
  --repo anselem-okeke/ai-platform-gitops
```

Then:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-gitops \
  --limit 20
```

---

# 57. Troubleshooting: Check Runs but Merge Is Not Blocked

A passing/failing workflow is not automatically a branch gate.

Check repository ruleset/branch protection.

The exact required check must be:

```text
Validate GitOps Manifests
```

or the current exact job/check context GitHub reports.

A name mismatch means branch protection may be waiting for or ignoring the wrong check.

---

# 58. Troubleshooting: Required Check Stuck `Expected`

Typical causes:

```text
workflow trigger excludes PR
job renamed
branch protection references old check name
workflow skipped by path filter
job condition evaluates false
```

Inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Compare the emitted check name with the configured required check.

---

# 59. Troubleshooting: Secret Scan False Positive

Do not immediately delete the control.

First identify whether the match is:

```text
real secret material
secret reference
documentation/example
field name only
```

If false-positive handling is needed:

```text
narrow the regex
exclude known safe structural references
keep actual credential patterns blocked
```

Never broadly disable the scan because one benign manifest contains `secretKeyRef`.

---

# 60. Troubleshooting: `git diff --check` Fails

Run locally:

```bash
git diff --check
```

Git prints the offending file and line.

Fix whitespace.

Do not hide the failure with:

```text
|| true
```

---

# 61. Troubleshooting: `clusters/dev/apps` Render Fails

Inspect:

```bash
cat clusters/dev/apps/kustomization.yaml
```

Verify every listed resource exists.

Example:

```bash
find clusters/dev/apps \
  -maxdepth 1 \
  -type f \
  -print \
  | sort
```

If a new child Application was added, ensure:

```text
its YAML exists
it is included in kustomization.yaml
its syntax is valid
AppProject permits its destination/resources
```

---

# 62. Adding a New Platform Component

Example future component:

```text
KServe
```

When Phase 8 adds:

```text
platform/kserve/...
clusters/dev/apps/kserve.yaml
```

the validation workflow should be updated deliberately.

Likely new render:

```bash
kubectl kustomize \
  platform/kserve/overlays/dev \
  >/tmp/kserve.yaml
```

Then include:

```text
/tmp/kserve.yaml
```

in kubeconform validation.

The component should not be considered integrated until CI validates its desired state.

---

# 63. Adding a New First-Party Image

If the platform later creates another first-party runtime image, do not rely on the current operator/API checks.

Extend the approved image validation explicitly.

For example:

```text
ghcr.io/anselem-okeke/new-runtime@sha256:<digest>
```

Add:

```text
approved repository
full digest requirement
negative mutable-tag test
```

---

# 64. Adding New Third-Party Helm-Managed Applications

External Helm applications such as:

```text
policy-controller
trust-policies
```

may be represented as Argo Applications rather than rendered local Helm manifests.

Validation should still confirm:

```text
Application YAML syntax
repo URL
chart
target revision pinned
destination namespace
AppProject compatibility
```

For external chart contents, use separate dependency/version review.

---

# 65. Validating Helm Chart Version Pins

For Argo Application resources using Helm charts, avoid:

```text
targetRevision: latest
targetRevision: HEAD
```

Use an explicit chart version, such as:

```text
0.10.6
v0.7.0
```

where appropriate.

A future enhancement can add a validation check for unpinned external chart revisions.

---

# 66. GitOps CI Does Not Replace Admission Control

GitOps validation answers:

```text
is desired state structurally/policy-valid before merge?
```

Admission answers:

```text
may this exact workload enter the cluster now?
```

Both are required.

The security chain is:

```text
GitOps PR validation
        |
        v
merge
        |
        v
Argo
        |
        v
Kubernetes admission
```

---

# 67. GitOps CI Does Not Replace Argo Health

A manifest can pass static validation and still fail at runtime.

Examples:

```text
image pull error
readiness failure
missing Secret
bad DNS
TLS dependency
operator reconcile error
insufficient resources
```

Therefore post-merge validation must also inspect:

```text
Argo Sync
Argo Health
Kubernetes rollout/status
events
```

---

# 68. GitOps CI Does Not Replace Gitleaks

The lightweight secret-pattern scan:

```text
helps catch obvious mistakes
```

but repository and history scanning should still use Gitleaks.

Do not describe the lightweight regex check as a complete secret scanner.

---

# 69. GitOps CI Does Not Need Target-Cluster Admin Credentials

A key architectural principle is:

```text
validate Git
without making CI a deployment actor
```

Avoid storing:

```text
cluster-admin kubeconfig
long-lived Kubernetes bearer token
admin client certificate
```

in the GitOps validation workflow.

Argo CD remains the deployment actor.

---

# 70. Workflow Rebuild Template

A conceptual workflow skeleton:

```yaml
name: Validate GitOps

on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

permissions: {}

jobs:
  validate:
    name: Validate GitOps Manifests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_SHA>
        with:
          persist-credentials: false

      - name: Install kubeconform
        run: |
          set -euo pipefail

          KUBECONFORM_VERSION="0.7.0"

          # Download exact release asset.
          # Verify against exact approved SHA-256 from repository workflow.
          # Install to /usr/local/bin.
          # Print version.

      - name: Render Kustomize
        run: |
          set -euo pipefail

          kubectl kustomize \
            platform/operator/overlays/dev \
            >/tmp/operator.yaml

          kubectl kustomize \
            platform/api/overlays/dev \
            >/tmp/api.yaml

          kubectl kustomize \
            platform/gateway/overlays/dev \
            >/tmp/gateway.yaml

          kubectl kustomize \
            platform/monitoring/overlays/dev \
            >/tmp/monitoring.yaml

          kubectl kustomize \
            platform/policies/overlays/dev \
            >/tmp/policies.yaml

          kubectl kustomize \
            modelservices/overlays/dev \
            >/tmp/modelservices.yaml

          kubectl kustomize \
            clusters/dev/apps \
            >/tmp/apps.yaml

      - name: Validate Kubernetes manifests
        run: |
          set -euo pipefail

          for file in \
            /tmp/operator.yaml \
            /tmp/api.yaml \
            /tmp/gateway.yaml \
            /tmp/monitoring.yaml \
            /tmp/policies.yaml \
            /tmp/modelservices.yaml \
            /tmp/apps.yaml
          do
            kubeconform \
              -strict \
              -summary \
              -ignore-missing-schemas \
              "${file}"
          done

      - name: Validate immutable first-party images
        run: |
          set -euo pipefail

          # Use the repository's tested image validation implementation.
          # Required invariants:
          #
          # ghcr.io/anselem-okeke/...
          # @sha256:
          # exactly 64 hex digest characters

      - name: Scan for accidental secret material
        run: |
          set -euo pipefail

          # Preserve tested project patterns.
          # This does not replace Gitleaks.

      - name: Validate whitespace
        run: |
          git diff --check
```

This is a rebuild template, not a substitute for inspecting the current committed workflow.

---

# 71. Full Rebuild Procedure

If `.github/workflows/validate.yml` is lost:

```text
[ ] create workflow
[ ] trigger on PR to main
[ ] optionally validate pushes to main
[ ] set permissions: {}
[ ] pin checkout action SHA
[ ] disable checkout credential persistence
[ ] pin kubeconform 0.7.0
[ ] checksum-verify kubeconform binary
[ ] render operator overlay
[ ] render API overlay
[ ] render gateway overlay
[ ] render monitoring overlay
[ ] render policies overlay
[ ] render modelservices overlay
[ ] render clusters/dev/apps
[ ] kubeconform all renders
[ ] ignore only missing third-party schemas
[ ] enforce approved first-party GHCR paths
[ ] enforce full sha256 digest
[ ] reject mutable final first-party images
[ ] add lightweight secret-material check
[ ] run git diff --check
[ ] name job Validate GitOps Manifests
[ ] create controlled positive PR
[ ] create controlled negative image-tag PR
[ ] confirm failed check blocks merge
[ ] confirm valid PR passes
[ ] configure GitOps ruleset to require check
```

---

# 72. Validation Evidence to Preserve

For a release/validation audit, preserve:

```text
PR number
PR source branch
PR commit SHA
GitOps validation run ID
check result
render result
kubeconform result
image validation result
merged GitOps commit
Argo revision
```

Do not preserve sensitive tokens in build artifacts.

---

# 73. Security Review Checklist

```text
[ ] workflow permissions are empty/minimal
[ ] actions pinned to full commit SHA
[ ] kubeconform version pinned
[ ] kubeconform checksum verified
[ ] no curl | bash install
[ ] no target-cluster admin credentials
[ ] operator/API images restricted to approved GHCR repositories
[ ] full digest required
[ ] rendered state validated instead of raw base placeholders
[ ] secret-material control exists
[ ] Gitleaks remains separate
[ ] git diff --check enforced
[ ] required check configured in branch protection
[ ] failed check blocks merge
[ ] no workflow step pushes or auto-merges
```

---

# 74. Operational Validation Checklist

```text
[ ] kubectl kustomize operator succeeds
[ ] kubectl kustomize API succeeds
[ ] kubectl kustomize gateway succeeds
[ ] kubectl kustomize monitoring succeeds
[ ] kubectl kustomize policies succeeds
[ ] kubectl kustomize modelservices succeeds
[ ] kubectl kustomize clusters/dev/apps succeeds
[ ] kubeconform succeeds
[ ] final operator image is digest pinned
[ ] final API image is digest pinned
[ ] approved repositories are used
[ ] no unintended secret material detected
[ ] git diff --check passes
[ ] GitHub job reports success
```

---

# 75. Known Implementation Facts

Validated project facts:

```text
Workflow:
.github/workflows/validate.yml

Workflow name:
Validate GitOps

Required job/check:
Validate GitOps Manifests

Workflow permissions:
permissions: {}

kubeconform:
0.7.0

Rendered paths:
platform/operator/overlays/dev
platform/api/overlays/dev
platform/gateway/overlays/dev
platform/monitoring/overlays/dev
platform/policies/overlays/dev
modelservices/overlays/dev
clusters/dev/apps

Image security:
approved GHCR organization path
@sha256:
full SHA-256 digest
no floating final deployment tag

Additional controls:
lightweight secret-pattern check
git diff --check
```

---

# 76. What Must Be Verified from the Actual Repository

The following should not be invented from memory:

```text
exact pinned checkout SHA
exact kubeconform archive checksum
exact secret regex implementation
exact shell/Python image validation implementation
exact trigger/path-filter configuration
exact step names
```

Obtain them from:

```bash
cd /mnt/data/ai-platform-gitops

cat .github/workflows/validate.yml
```

When this guide is updated after direct repository inspection, replace rebuild placeholders with the exact tested implementation.

---

# 77. Official References

GitHub Actions workflow syntax:

```text
https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
```

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

GitHub required status checks:

```text
https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
```

kubeconform:

```text
https://github.com/yannh/kubeconform
```

Kustomize:

```text
https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
```

Kubernetes images:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

---

# 78. Related AI Platform Documentation

```text
011-app-of-apps-bootstrap.md
012-kustomize-layout-and-overlays.md
019-source-ci-pipeline.md
023-github-container-registry.md
024-github-app-gitops-automation.md
025-image-digest-update-workflow.md
027-branch-protection-and-rulesets.md
028-promotion-workflow.md
030-argocd-sync-selfheal-and-prune.md
031-sigstore-policy-controller.md
033-native-image-validation-policy.md
038-secret-scanning.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
