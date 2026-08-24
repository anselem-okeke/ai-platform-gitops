# Software Supply Chain Security

## Purpose

This document is the **step-by-step implementation guide** for rebuilding the AI Platform software-supply-chain security controls from source commit to Kubernetes runtime.

It is intentionally written as an **operator runbook**, not as conceptual notes.

A new engineer should be able to follow the steps in order and reproduce the security chain:

```text
source PR
   |
   +--> Lint
   +--> Tests
   +--> E2E
   +--> Gitleaks
   +--> govulncheck
   +--> CodeQL
   |
   v
protected source main
   |
   v
release workflow
   |
   +--> build operator image
   +--> build API image
   +--> Trivy HIGH/CRITICAL gate
   +--> push to GHCR
   +--> generate SPDX JSON SBOM
   +--> create provenance attestation
   +--> create SBOM attestation
   |
   v
immutable image digests
   |
   v
GitHub App installation token
   |
   v
digest-only GitOps PR
   |
   +--> Kustomize render
   +--> kubeconform
   +--> repository allowlist check
   +--> full SHA-256 digest check
   +--> secret-pattern check
   |
   v
protected GitOps main
   |
   v
Argo CD
   |
   v
Native image admission
   |
   v
Sigstore Policy Controller
   |
   v
trusted runtime workload
```

The core rule is:

> **Every security control must be connected to an enforcement point.**

A scanner that reports a failure but does not block merge, release, promotion, or admission is not enough.

---

# 1. Repositories and Working Directories

Use the correct repository for each step.

## Source repository

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

This repository contains:

```text
Go source
Dockerfiles
source CI
security scanning
release workflow
image build/push
SBOM/provenance generation
GitOps update automation
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

This repository contains:

```text
Argo Applications
Kustomize overlays
digest-pinned image desired state
admission policies
Sigstore trust integration
monitoring
namespace labels
```

---

# 2. Implementation Order

Build the supply-chain controls in this order:

```text
1. source CI gates
2. branch protection
3. hardened image builds
4. vulnerability scanning
5. GHCR push
6. SBOM generation
7. provenance/SBOM attestations
8. GitHub App authentication
9. digest-only GitOps promotion
10. GitOps PR validation
11. GitOps branch protection
12. Argo deployment
13. native image admission
14. Sigstore attestation verification
15. observability and alerting
16. end-to-end negative/positive tests
```

Do not start at admission while source/release controls are still unenforced.

---

# 3. Step 1 — Verify Source CI Workflows Exist

Work in:

```bash
cd /mnt/data/ai-platform-operator
```

List workflows:

```bash
find .github/workflows \
  -maxdepth 1 \
  -type f \
  -print \
  | sort
```

Expected workflows:

```text
.github/workflows/lint.yml
.github/workflows/test.yml
.github/workflows/test-e2e.yml
.github/workflows/security.yml
.github/workflows/release-images.yml
.github/workflows/secret-scan.yml
```

If one is missing, stop and restore it before proceeding.

---

# 4. Step 2 — Verify the Required Source Checks

The current protected source branch requires:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

Verify on an existing PR:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-operator
```

Then:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Expected:

```text
all required checks listed
```

Do not continue if security workflows exist but are not required.

---

# 5. Step 3 — Verify Source Ruleset Enforcement

Current validated ruleset:

```text
Name: Source Main Protection
ID: 21120105
State: active
Target: default branch
Bypass actors: none
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Extract relevant fields:

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

Verify:

```text
active
pull request required
required status checks configured
deletion blocked
non-fast-forward updates blocked
no bypass actors
```

---

# 6. Step 4 — Validate Gitleaks Locally

Run:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

Expected:

```text
exit code 0
no findings
```

Run GitOps too:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Expected:

```text
exit code 0
no findings
```

If a real secret is found:

```text
STOP
rotate/revoke the secret first
then clean Git
then re-run Gitleaks
```

Do not continue the supply-chain build while leaked credentials remain valid.

---

# 7. Step 5 — Verify govulncheck

Work in source repo:

```bash
cd /mnt/data/ai-platform-operator
```

Run the project-standard security target or direct command.

Validated govulncheck CLI version:

```text
v1.7.0
```

Representative:

```bash
govulncheck ./...
```

Expected project interpretation:

```text
0 reachable vulnerabilities
```

Important:

Do **not** document this as:

```text
dependency graph contains zero vulnerabilities
```

because imported packages/modules can still contain unreachable issues.

The security gate is specifically:

```text
reachable vulnerability analysis
```

---

# 8. Step 6 — Verify CodeQL

Inspect:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,360p' \
  .github/workflows/security.yml
```

Validated CodeQL action pin:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

Release/version reference:

```text
v4.37.4
```

Confirm CodeQL is:

```text
enabled for pull requests
required by source branch protection
```

Do not accept a setup where CodeQL only runs after merge.

---

# 9. Step 7 — Verify Go Build Baseline

Validated Go version:

```text
1.26.6
```

Check:

```bash
go version
```

Run:

```bash
make lint-config
```

Then:

```bash
make lint
```

Then:

```bash
make test
```

Then:

```bash
go vet ./...
```

Expected:

```text
all pass
```

A release pipeline should not be used to discover basic compile/lint failures that PR CI should already catch.

---

# 10. Step 8 — Verify Hardened Dockerfiles

Inspect source Dockerfiles.

Representative hardened builder pattern:

```dockerfile
FROM golang:1.26.6 AS builder

WORKDIR /src

COPY go.mod go.sum ./

RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download
```

Representative build pattern:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 \
    go build \
      -trimpath \
      -ldflags="-s -w" \
      -o /out/manager \
      ./cmd/manager
```

Runtime:

```dockerfile
FROM gcr.io/distroless/static-debian13:nonroot

USER 65532:65532

COPY --from=builder /out/manager /manager

ENTRYPOINT ["/manager"]
```

API equivalent:

```dockerfile
COPY --from=builder /out/platform-api /platform-api

ENTRYPOINT ["/platform-api"]
```

Security properties:

```text
minimal runtime
no package manager
no shell
non-root
static Go binary
build toolchain excluded from final image
```

---

# 11. Step 9 — Build Operator Image Locally

Use a disposable local tag:

```bash
cd /mnt/data/ai-platform-operator

docker build \
  -f Dockerfile \
  -t ai-platform-operator:test \
  .
```

If the repository uses a different Dockerfile name, use the actual file.

Inspect runtime user:

```bash
docker inspect \
  ai-platform-operator:test \
  --format '{{.Config.User}}'
```

Expected:

```text
65532
```

or the distroless nonroot equivalent.

---

# 12. Step 10 — Build API Image Locally

Representative:

```bash
docker build \
  -f Dockerfile.api \
  -t ai-platform-api:test \
  .
```

Inspect:

```bash
docker inspect \
  ai-platform-api:test \
  --format '{{.Config.User}}'
```

Expected:

```text
65532
```

Use the actual Dockerfile name from the repository.

---

# 13. Step 11 — Verify Release Workflow Trigger

Inspect:

```bash
sed -n '1,420p' \
  .github/workflows/release-images.yml
```

The release workflow should run on:

```text
push to main
```

Representative:

```yaml
on:
  push:
    branches:
      - main
```

This matters because:

```text
PR checks authorize merge
merge to protected main authorizes release
```

Do not run the production-style release job from arbitrary PR branches.

---

# 14. Step 12 — Verify Release Permissions

Release jobs should receive only the permissions they need.

Representative high-level permission set:

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
  attestations: write
```

Additional permissions may exist for the GitHub App token flow.

Inspect actual workflow permissions.

Do not use:

```yaml
permissions: write-all
```

---

# 15. Step 13 — Verify Operator and API Build Jobs

The release workflow should have independent build jobs such as:

```text
build-operator
build-api
```

Inspect:

```bash
grep -nE \
  '^  build-operator:|^  build-api:|^  update-gitops:' \
  .github/workflows/release-images.yml
```

Both build jobs must succeed before GitOps promotion.

---

# 16. Step 14 — Add Trivy as a Blocking Gate

Validated scanning policy:

```text
severity: HIGH,CRITICAL
ignore-unfixed: true
exit-code: 1
```

Representative workflow snippet:

```yaml
- name: Scan image
  run: |
    trivy image \
      --severity HIGH,CRITICAL \
      --ignore-unfixed \
      --exit-code 1 \
      "${IMAGE_REF}"
```

The important property is:

```text
vulnerability threshold exceeded
    ->
job fails
    ->
promotion does not happen
```

---

# 17. Step 15 — Confirm Scan Failure Blocks Promotion

The GitOps update job must depend on successful builds.

Representative:

```yaml
update-gitops:
  needs:
    - build-operator
    - build-api
```

If operator scanning fails:

```text
build-operator = fail
update-gitops = skipped
```

If API scanning fails:

```text
build-api = fail
update-gitops = skipped
```

That is the required behavior.

---

# 18. Step 16 — Push Images to GHCR

Current first-party image repositories:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

The release workflow pushes only after required release checks pass.

Do not use a mutable tag as the final deployment identity.

Tags can exist for human convenience, but GitOps must deploy:

```text
image@sha256:<digest>
```

---

# 19. Step 17 — Capture the Immutable Digest

The build/push step must expose:

```text
sha256:<64hex>
```

Validate in shell:

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
validate_digest "${OPERATOR_DIGEST}"
validate_digest "${API_DIGEST}"
```

Do not proceed if either value is empty or malformed.

---

# 20. Step 18 — Generate SPDX JSON SBOM

Validated SBOM tooling:

```text
Anchore
```

Validated output format:

```text
SPDX JSON
```

Representative conceptual command:

```bash
syft \
  "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}" \
  -o spdx-json \
  > /tmp/api.spdx.json
```

Use the exact tool/action implementation from the release workflow.

Validate file:

```bash
test -s /tmp/api.spdx.json
```

Do the same for the operator image.

---

# 21. Step 19 — Create Provenance Attestation

Validated action:

```text
actions/attest
```

Pinned SHA:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Representative:

```yaml
- name: Attest API provenance
  uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
  with:
    subject-name: ghcr.io/anselem-okeke/ai-platform-api
    subject-digest: ${{ steps.<BUILD_STEP>.outputs.digest }}
    push-to-registry: true
```

The exact build step ID must come from the repository.

---

# 22. Step 20 — Create SBOM Attestation

Representative:

```yaml
- name: Attest API SBOM
  uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
  with:
    subject-name: ghcr.io/anselem-okeke/ai-platform-api
    subject-digest: ${{ steps.<BUILD_STEP>.outputs.digest }}
    sbom-path: /tmp/api.spdx.json
    push-to-registry: true
```

Repeat for operator.

Invariant:

```text
subject digest
==
pushed image digest
==
GitOps promoted digest
```

---

# 23. Step 21 — Verify Attestation Happens Before Promotion

Inspect job dependency:

```bash
grep -nE \
  'attest|update-gitops|needs:' \
  .github/workflows/release-images.yml
```

Required sequence:

```text
build
scan
push
SBOM
attest
    |
    v
update-gitops
```

Do not create the GitOps PR before attestation succeeds.

---

# 24. Step 22 — Configure GitHub App Authentication

The release workflow authenticates to the separate GitOps repository using:

```text
ai-platform-gitops-bot[bot]
```

Do not use a long-lived developer PAT.

GitHub App repository access should be limited to:

```text
anselem-okeke/ai-platform-gitops
```

Required permissions:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

---

# 25. Step 23 — Mint Short-Lived GitHub App Token

Validated action:

```text
actions/create-github-app-token
```

Pinned SHA:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Representative:

```yaml
- name: Create GitOps App token
  id: app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
  with:
    app-id: ${{ vars.<ACTUAL_APP_ID_VARIABLE> }}
    private-key: ${{ secrets.<ACTUAL_PRIVATE_KEY_SECRET> }}
    owner: anselem-okeke
    repositories: ai-platform-gitops
```

The exact variable/secret names must be read from the actual workflow.

---

# 26. Step 24 — Clone GitOps with the Short-Lived Token

The release job must clone:

```text
anselem-okeke/ai-platform-gitops
```

using the App installation token.

Do not embed the token in logs.

Expected workflow behavior:

```text
token created
clone succeeds
automation branch created
```

---

# 27. Step 25 — Create Promotion Branch

Current branch convention:

```text
automation/image-<source-sha>
```

Representative shell:

```bash
SOURCE_SHA="${GITHUB_SHA}"

git switch \
  -c "automation/image-${SOURCE_SHA}"
```

This links the GitOps PR directly to the source commit.

---

# 28. Step 26 — Update Only the Two Dev Overlays

The release automation must modify exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

No other files should change during normal image promotion.

---

# 29. Step 27 — Use Digest, Not `newTag`

Representative Kustomize image snippet:

```yaml
images:
  - name: controller
    newName: ghcr.io/anselem-okeke/ai-platform-operator
    digest: sha256:<OPERATOR_DIGEST>
```

API:

```yaml
images:
  - name: ai-platform-api
    newName: ghcr.io/anselem-okeke/ai-platform-api
    digest: sha256:<API_DIGEST>
```

The base may contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

That is acceptable only because the overlay must replace them.

The **rendered final state** is the security boundary.

---

# 30. Step 28 — Validate Changed Files

Run:

```bash
git diff --name-only | sort
```

Expected exactly:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

If anything else changes:

```text
FAIL THE AUTOMATION
```

---

# 31. Step 29 — Render Operator Overlay

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rendered.yaml
```

Expected:

```text
exit code 0
```

---

# 32. Step 30 — Render API Overlay

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rendered.yaml
```

---

# 33. Step 31 — Verify Exact Rendered Operator Digest

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}" \
  /tmp/operator-rendered.yaml
```

Expected:

```text
match found
```

---

# 34. Step 32 — Verify Exact Rendered API Digest

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}" \
  /tmp/api-rendered.yaml
```

Expected:

```text
match found
```

---

# 35. Step 33 — Reject Mutable Final Images

The GitOps validation workflow must reject final rendered images using:

```text
:latest
:dev
:main
:v1
newTag
```

as the final deployment identity.

Allowed final form:

```text
ghcr.io/anselem-okeke/...@sha256:<64hex>
```

---

# 36. Step 34 — Run kubeconform

Validated kubeconform version:

```text
0.7.0
```

The workflow downloads the binary and verifies its checksum.

Render and validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/operator-rendered.yaml
```

Then:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/api-rendered.yaml
```

GitOps CI also renders:

```text
platform/gateway/overlays/dev
platform/monitoring/overlays/dev
platform/policies/overlays/dev
modelservices/overlays/dev
clusters/dev/apps
```

---

# 37. Step 35 — Validate Git Diff

Run:

```bash
git diff --check
```

Expected:

```text
no output
exit code 0
```

---

# 38. Step 36 — Run GitOps Secret Check

The GitOps validation workflow also scans for obvious secret material.

Inspect actual implementation:

```bash
grep -nE \
  'secret|password|PRIVATE KEY|token' \
  .github/workflows/validate.yml
```

Do not replace the current regex with an invented one without testing.

---

# 39. Step 37 — Commit as Bot Identity

Expected bot:

```text
ai-platform-gitops-bot[bot]
```

Expected commit title:

```text
chore(dev): deploy images from <source-sha>
```

Representative:

```bash
git commit \
  -m "chore(dev): deploy images from ${SOURCE_SHA}"
```

---

# 40. Step 38 — Push Automation Branch

Push:

```bash
git push \
  -u origin \
  "automation/image-${SOURCE_SHA}"
```

Expected:

```text
branch created successfully
```

The bot should **not** push directly to GitOps `main`.

---

# 41. Step 39 — Open GitOps PR

Expected PR:

```text
base: main
head: automation/image-<source-sha>
author: ai-platform-gitops-bot[bot]
```

The PR should include:

```text
source SHA
operator digest
API digest
target environment = dev
```

It must not auto-merge.

---

# 42. Step 40 — Validate GitOps PR

The required GitOps check is:

```text
Validate GitOps Manifests
```

Inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Expected:

```text
Validate GitOps Manifests = pass
```

Do not merge on failure.

---

# 43. Step 41 — Protect GitOps Main

GitOps main must require:

```text
pull request
Validate GitOps Manifests
no force push
no deletion
human-controlled merge
```

The GitHub App should be able to:

```text
push automation branch
open PR
```

but not:

```text
bypass main protection
merge its own PR
```

---

# 44. Step 42 — Human Merge Is the Promotion Authorization

Current promotion model:

```text
release automation
    |
    v
opens GitOps PR
    |
    v
human merge
```

The human merge separates:

```text
artifact production
```

from:

```text
deployment authorization
```

Do not remove this boundary unless governance explicitly changes.

---

# 45. Step 43 — Verify Argo Child Applications

After GitOps merge:

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

Then:

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

Expected:

```text
Synced
Healthy
```

---

# 46. Step 44 — Verify Live Digests

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
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
the exact digests merged into GitOps
```

---

# 47. Step 45 — Install Native Image Admission Policies

The GitOps policy component lives under:

```text
platform/policies/
```

Native admission should enforce:

```text
approved GHCR repository
@sha256
64 lowercase hex characters
regular containers
init containers
ephemeral containers
direct Pods
```

Representative validation expression:

```yaml
- expression: >-
    object.spec.containers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
  message: >-
    Containers must use approved AI Platform images pinned to a full SHA-256 digest.
```

---

# 48. Step 46 — Enable Init Container Coverage

Representative:

```yaml
- expression: >-
    !has(object.spec.initContainers) ||
    object.spec.initContainers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
```

Do not ship a policy that checks only the main container list.

---

# 49. Step 47 — Enable Ephemeral Container Coverage

Representative:

```yaml
- expression: >-
    !has(object.spec.ephemeralContainers) ||
    object.spec.ephemeralContainers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
```

Also verify the ephemeral-container update/subresource behavior empirically.

---

# 50. Step 48 — Bind Native Policy to Protected Namespaces

Current protected namespaces:

```text
ai-platform
ai-platform-operator-system
```

Representative binding:

```yaml
matchResources:
  namespaceSelector:
    matchLabels:
      policy.sigstore.dev/include: "true"
```

Validation action:

```yaml
validationActions:
  - Deny
```

Policy failure mode:

```yaml
failurePolicy: Fail
```

---

# 51. Step 49 — Install Sigstore Policy Controller

Validated Helm chart:

```text
policy-controller
```

Version:

```text
0.10.6
```

Application version:

```text
0.13.1
```

Namespace:

```text
cosign-system
```

Representative Argo source:

```yaml
source:
  repoURL: ghcr.io/sigstore/helm-charts
  chart: policy-controller
  targetRevision: 0.10.6
```

---

# 52. Step 50 — Verify Policy Controller

```bash
kubectl get pods \
  -n cosign-system
```

Expected:

```text
Policy Controller webhook Pod Ready
```

Check webhooks:

```bash
kubectl get mutatingwebhookconfiguration \
  policy.sigstore.dev
```

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev
```

---

# 53. Step 51 — Install GitHub Attestation Trust Policies

Validated trust-policy chart:

```text
v0.7.0
```

Repository:

```text
ghcr.io/github/artifact-attestations-helm-charts
```

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

# 54. Step 52 — Verify TrustRoot

```bash
kubectl get trustroots.policy.sigstore.dev
```

Expected:

```text
github
```

Inspect:

```bash
kubectl get trustroot \
  github \
  -o yaml
```

---

# 55. Step 53 — Verify ClusterImagePolicy

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Expected:

```text
github-policy
```

Inspect:

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

---

# 56. Step 54 — Label Protected Namespaces

Representative namespace manifest:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-platform
  labels:
    policy.sigstore.dev/include: "true"
```

Operator namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-platform-operator-system
  labels:
    policy.sigstore.dev/include: "true"
```

Verify:

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

---

# 57. Step 55 — Positive Admission Test

Use a real trusted digest:

```bash
kubectl run supply-chain-positive \
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

This proves:

```text
native structure valid
+
Sigstore trust valid
```

---

# 58. Step 56 — Negative Test: Mutable Image

```bash
kubectl run supply-chain-negative-tag \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Native admission should reject before runtime.

---

# 59. Step 57 — Negative Test: Public Image

```bash
kubectl run supply-chain-negative-nginx \
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

# 60. Step 58 — Negative Test: Fake Valid Digest

Use a structurally valid but non-existent/untrusted digest:

```bash
kubectl run supply-chain-fake-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Observed Sigstore error:

```text
no valid bundles exist in registry
```

This is a critical end-to-end trust test.

---

# 61. Step 59 — Negative Test: Bad Init Container

Use a trusted main image and an untrusted init image.

Representative:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: supply-chain-bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>
```

Test:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/supply-chain-bad-init.yaml
```

Expected:

```text
DENIED
```

---

# 62. Step 60 — Negative Test: Ephemeral Container

Create a disposable trusted Pod, then attempt:

```bash
kubectl debug \
  -n ai-platform \
  <TRUSTED_TEST_POD> \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

This validates the debug-container bypass is closed.

---

# 63. Step 61 — Verify Policy Controller Metrics

Metrics service:

```text
policy-controller-webhook-metrics
```

Port:

```text
9090
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
  | grep '^policy_controller_' \
  | head -n 60
```

---

# 64. Step 62 — Install ServiceMonitor

Validated GitOps file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

Representative:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: policy-controller
  namespace: monitoring
  labels:
    release: kps

spec:
  namespaceSelector:
    matchNames:
      - cosign-system

  selector:
    matchLabels:
      app.kubernetes.io/name: policy-controller

  endpoints:
    - port: metrics
      interval: 30s
      scrapeTimeout: 10s
```

Use exact live service labels when rebuilding.

---

# 65. Step 63 — Verify Prometheus Target

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

Do not consider observability complete until the target is actually scraped.

---

# 66. Step 64 — Install PrometheusRule

Validated GitOps file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Required selector label:

```yaml
metadata:
  labels:
    release: kps
```

Without this label, the current Prometheus instance may not select the rule.

---

# 67. Step 65 — Add Target Down Alert

```yaml
- alert: PolicyControllerTargetDown
  expr: |
    up{
      namespace="cosign-system",
      service="policy-controller-webhook-metrics"
    } == 0
  for: 5m
  labels:
    severity: critical
```

---

# 68. Step 66 — Add Reconcile Failure Alert

```yaml
- alert: PolicyControllerReconcileFailures
  expr: |
    sum(
      increase(
        policy_controller_reconcile_count{
          success="false"
        }[10m]
      )
    ) > 5
  for: 5m
  labels:
    severity: warning
```

---

# 69. Step 67 — Add Webhook Certificate Alert

```yaml
- alert: PolicyControllerWebhookCertificateFailures
  expr: |
    increase(
      policy_controller_reconcile_count{
        reconciler="WebhookCertificates",
        success="false"
      }[10m]
    ) > 0
  for: 5m
  labels:
    severity: critical
```

---

# 70. Step 68 — Handle Argo Drift Narrowly

A real drift case occurred on Policy Controller webhooks.

Controller-added selector:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

Do not ignore the entire webhook resource.

Use a narrow `ignoreDifferences` rule targeting only that exact controller-managed selector.

Also enable:

```yaml
syncOptions:
  - RespectIgnoreDifferences=true
```

Only where required.

---

# 71. Step 69 — Verify Argo Is Synced After Drift Fix

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

Then:

```bash
argocd app diff \
  policy-controller
```

Expected:

```text
no unintended drift
```

---

# 72. Step 70 — Perform End-to-End Supply Chain Validation

Use this final chain:

```text
source PR
  -> required checks pass
  -> merge
  -> release succeeds
  -> Trivy passes
  -> GHCR push succeeds
  -> SBOM exists
  -> provenance attestation exists
  -> SBOM attestation exists
  -> GitHub App token created
  -> digest-only GitOps PR created
  -> GitOps validation passes
  -> human merge
  -> Argo sync
  -> native admission passes
  -> Sigstore passes
  -> workload runs
```

Do not call Phase 7 supply-chain security complete until every stage has been validated.

---

# 73. Negative End-to-End Test — Gitleaks

Create a synthetic secret-like value on a disposable PR branch.

Expected:

```text
Gitleaks fails
merge blocked
release never runs
```

Delete/revert the test.

Do not use a real credential.

---

# 74. Negative End-to-End Test — Source Test Failure

Break a test intentionally on a disposable branch.

Expected:

```text
Tests fails
merge blocked
release never runs
```

---

# 75. Negative End-to-End Test — Trivy Gate

Use only a controlled test image/environment.

Expected:

```text
Trivy HIGH/CRITICAL finding
release job fails
GitOps PR not created
```

Do not weaken Trivy to make the test pass.

---

# 76. Negative End-to-End Test — Bad GitOps Digest

Create a test GitOps PR with:

```text
:latest
```

or malformed digest.

Expected:

```text
Validate GitOps Manifests fails
merge blocked
Argo never receives bad desired state
```

---

# 77. Negative End-to-End Test — Fake Valid Digest

Use:

```text
approved repo
valid sha256 syntax
untrusted digest
```

Expected:

```text
native policy may pass structure
Sigstore denies trust
```

This proves the deeper attestation gate works.

---

# 78. Failure Scenario — Security Check Fails but Merge Still Allowed

This means branch protection is incomplete.

Fix:

```text
required status checks
```

Do not treat CI success/failure alone as the enforcement boundary.

---

# 79. Failure Scenario — Release Runs on PR

If release workflow can publish from untrusted PR context, fix the trigger.

The release should be tied to:

```text
protected main
```

unless a separate preview-image architecture is explicitly designed.

---

# 80. Failure Scenario — Image Uses Mutable Tag in GitOps

Reject it.

Correct:

```text
image@sha256:<digest>
```

Incorrect:

```text
image:latest
image:dev
image:v1
```

---

# 81. Failure Scenario — Attestation Missing

Do not promote the image.

Check:

```text
actions/attest step
id-token permission
attestations permission
subject-name
subject-digest
registry push
```

---

# 82. Failure Scenario — GitHub App `Not Found`

Known real failure:

```text
repository installation lookup returned Not Found
```

Check:

```text
App installed on GitOps repository
correct repository selected
correct owner
correct App/Client ID
correct private key
required permissions
```

Do not replace App auth with a PAT as the first workaround.

---

# 83. Failure Scenario — GitOps Validation Passes Raw Base Placeholder

This is not automatically a problem.

The base may contain:

```text
controller:latest
ai-platform-api:dev
```

if the overlay replaces them.

Validate:

```text
final rendered state
```

not raw base alone.

---

# 84. Failure Scenario — GitOps PR Changes Extra Files

Fail the promotion job.

Expected changed files are exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

---

# 85. Failure Scenario — Argo Deploys Wrong Digest

Compare:

```text
GitOps overlay
rendered manifest
Argo revision
live Deployment image
```

Do not troubleshoot admission until the desired-state digest is confirmed.

---

# 86. Failure Scenario — Trusted Image Denied

Check in order:

```text
namespace label
image digest
TrustRoot/github
ClusterImagePolicy/github-policy
GitHub attestation existence
organization scope
image-pattern scope
Policy Controller readiness
webhook certificate health
```

---

# 87. Failure Scenario — Public Image Allowed

This is a security failure.

Check:

```text
native policy binding
namespace selector
Sigstore namespace opt-in
webhook health
policy resources
```

Add a regression test after repair.

---

# 88. Rollback Strategy

Rollback must preserve the immutable supply-chain model.

Correct:

```text
Git revert to previous known-good digest
```

Not:

```text
kubectl set image
rebuild old source
switch to old mutable tag
```

See:

```text
029-rollback-strategy.md
```

---

# 89. Known-Good Rollback Target

A valid rollback target should have:

```text
previous successful release
immutable digest
successful GitOps validation
trusted attestation
previous successful admission
known healthy runtime behavior
```

---

# 90. Supply Chain Audit Record

For each release, retain or reconstruct:

```text
source SHA
source PR
required-check result
release run ID
operator digest
API digest
Trivy result
SBOM artifact/evidence
provenance attestation
SBOM attestation
GitOps automation branch
GitOps PR
GitOps validation result
GitOps merge commit
Argo revision
live runtime digest
```

---

# 91. Implementation Checklist — Source

```text
[ ] lint workflow exists
[ ] test workflow exists
[ ] E2E workflow exists
[ ] security workflow exists
[ ] secret-scan workflow exists
[ ] release workflow exists
[ ] source main protected
[ ] Gitleaks required
[ ] Lint required
[ ] E2E required
[ ] Tests required
[ ] govulncheck required
[ ] CodeQL required
[ ] no bypass actors
[ ] direct push blocked
[ ] force push blocked
```

---

# 92. Implementation Checklist — Build and Release

```text
[ ] Go 1.26.6 used
[ ] distroless runtime used
[ ] USER 65532 used
[ ] operator image built
[ ] API image built
[ ] Trivy HIGH/CRITICAL gate enabled
[ ] ignore-unfixed enabled
[ ] exit-code 1 enabled
[ ] images pushed to GHCR
[ ] exact digest captured
[ ] SPDX JSON SBOM generated
[ ] provenance attestation created
[ ] SBOM attestation created
[ ] promotion waits for both builds
```

---

# 93. Implementation Checklist — GitOps Promotion

```text
[ ] GitHub App installed only on GitOps repo
[ ] Contents read/write granted
[ ] Pull requests read/write granted
[ ] Metadata read granted
[ ] short-lived token created
[ ] branch = automation/image-<source-sha>
[ ] operator overlay digest updated
[ ] API overlay digest updated
[ ] only two expected files changed
[ ] overlays render
[ ] final images use exact digests
[ ] git diff --check passes
[ ] bot identity used
[ ] PR opened
[ ] no auto-merge
```

---

# 94. Implementation Checklist — GitOps Enforcement

```text
[ ] validate.yml exists
[ ] permissions: {} or least privilege
[ ] checkout action pinned
[ ] kubeconform 0.7.0 pinned
[ ] checksum verified
[ ] all key overlays rendered
[ ] approved GHCR repositories validated
[ ] full SHA-256 digest validated
[ ] mutable final tags rejected
[ ] secret-pattern check enabled
[ ] git diff --check enabled
[ ] GitOps main protected
[ ] Validate GitOps Manifests required
```

---

# 95. Implementation Checklist — Runtime Admission

```text
[ ] native ValidatingAdmissionPolicy installed
[ ] Binding installed
[ ] failurePolicy = Fail
[ ] validationActions = Deny
[ ] regular containers covered
[ ] init containers covered
[ ] ephemeral containers covered
[ ] direct Pods covered
[ ] protected namespaces labelled
[ ] Policy Controller chart 0.10.6 installed
[ ] trust-policies chart v0.7.0 installed
[ ] TrustRoot github exists
[ ] ClusterImagePolicy github-policy exists
[ ] trusted API digest allowed
[ ] trusted operator digest allowed
[ ] nginx:latest denied
[ ] fake digest denied
[ ] bad init denied
[ ] bad ephemeral denied
```

---

# 96. Implementation Checklist — Observability

```text
[ ] policy-controller metrics service exists
[ ] port 9090 reachable
[ ] ServiceMonitor exists
[ ] Prometheus target up = 1
[ ] policy_controller_reconcile_count present
[ ] PrometheusRule exists
[ ] release: kps label present
[ ] TargetDown alert exists
[ ] ReconcileFailures alert exists
[ ] WebhookCertificateFailures alert exists
[ ] no broad Argo ignoreDifferences
```

---

# 97. Security Invariants

At all times, these must remain true:

```text
untrusted source cannot merge
failed security check cannot merge
failed release scan cannot promote
unattested image cannot promote successfully
mutable final image cannot merge into GitOps
bot cannot bypass GitOps main protection
Git is deployment source of truth
unapproved image cannot pass native admission
fake digest cannot pass Sigstore
manual cluster drift is self-healed
```

---

# 98. What Not to Do

Do not:

```text
treat scanners as informational only
allow release workflow to ignore failures
deploy mutable tags
rebuild separately per environment
store GitOps bot PAT
store GitHub App private key in Git
auto-merge bot promotion PRs
bypass GitOps validation
kubectl apply directly from source CI
disable admission to make a release deploy
broad-ignore webhook drift
claim zero vulnerabilities when only reachable issues are zero
```

---

# 99. Rebuild from Zero — Full Sequence

Follow in this exact order:

```text
[ ] clone source repo
[ ] clone GitOps repo
[ ] install/verify Go 1.26.6
[ ] run lint/tests/vet
[ ] configure Gitleaks
[ ] configure govulncheck
[ ] configure CodeQL
[ ] configure source branch ruleset
[ ] harden operator Dockerfile
[ ] harden API Dockerfile
[ ] configure Trivy gate
[ ] configure GHCR push
[ ] capture digests
[ ] generate SPDX SBOMs
[ ] add provenance attestations
[ ] add SBOM attestations
[ ] create GitHub App
[ ] install App only on GitOps repo
[ ] store App private key in Actions Secrets
[ ] mint installation token
[ ] update digest-only overlays
[ ] validate only expected files change
[ ] render Kustomize overlays
[ ] configure kubeconform
[ ] configure GitOps image validation
[ ] configure GitOps secret checks
[ ] protect GitOps main
[ ] validate bot cannot bypass merge
[ ] configure Argo Applications
[ ] configure native image admission
[ ] install Policy Controller
[ ] install GitHub trust policy
[ ] label protected namespaces
[ ] test trusted digest
[ ] test mutable tag denial
[ ] test public image denial
[ ] test fake digest denial
[ ] test init container denial
[ ] test ephemeral container denial
[ ] configure ServiceMonitor
[ ] configure PrometheusRule
[ ] verify target up = 1
[ ] perform end-to-end release
[ ] verify live digests
[ ] perform rollback test
```

---

# 100. Acceptance Test

Phase 7 supply-chain security is acceptable only if a new engineer can prove all of the following:

```text
1. bad source PR cannot merge
2. secret leak cannot merge
3. reachable vulnerability gate can block
4. CodeQL is required
5. Trivy can stop release promotion
6. images are immutable by digest
7. SBOM/provenance are created for exact digest
8. GitHub App opens a GitOps PR
9. GitOps bot cannot merge directly
10. GitOps validation blocks bad image references
11. human merge triggers Argo reconciliation
12. native policy denies malformed/mutable images
13. Sigstore denies fake valid digest
14. init/ephemeral bypasses are denied
15. Policy Controller metrics are scraped
16. alerts are loaded
17. rollback restores a known-good digest through Git
```

If any item cannot be demonstrated, document it as incomplete instead of assuming success.

---

# 101. Known Validated Implementation Facts

```text
Go:
1.26.6

Source required checks:
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL

Source ruleset:
Source Main Protection
ID 21120105
active
no bypass

Trivy:
HIGH,CRITICAL
ignore-unfixed
exit 1

SBOM:
SPDX JSON

Attestation action:
actions/attest
508db95dd578ae2727ebd6217d5ba78e4fbda05d

GitHub App token action:
actions/create-github-app-token
bcd2ba49218906704ab6c1aa796996da409d3eb1

Images:
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api

Promotion:
digest only

Bot:
ai-platform-gitops-bot[bot]

Policy Controller:
chart 0.10.6
app v0.13.1
namespace cosign-system

Trust policy:
v0.7.0

TrustRoot:
github

ClusterImagePolicy:
github-policy

Protected namespaces:
ai-platform
ai-platform-operator-system

Metrics service:
policy-controller-webhook-metrics

Prometheus target:
up = 1 validated
```

---

# 102. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact current secret/variable names
exact source workflow step IDs
exact checkout action SHA in each workflow
exact kubeconform checksum
exact GitOps secret regex
exact CEL policy expressions
exact current Argo Application names if changed
exact current live trusted image digest
```

Inspect these files before claiming exact parity:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,460p' \
  .github/workflows/release-images.yml

sed -n '1,360p' \
  .github/workflows/security.yml

sed -n '1,320p' \
  .github/workflows/secret-scan.yml
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,420p' \
  .github/workflows/validate.yml

find platform/policies \
  -type f \
  -maxdepth 3 \
  -print \
  | sort

sed -n '1,280p' \
  platform/monitoring/base/policy-controller-servicemonitor.yaml

sed -n '1,360p' \
  platform/monitoring/base/policy-controller-prometheusrule.yaml
```

---

# 103. Official References

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

GitHub Artifact Attestations:

```text
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
```

GitHub Container Registry:

```text
https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
```

Gitleaks:

```text
https://github.com/gitleaks/gitleaks
```

govulncheck:

```text
https://go.dev/security/vuln/
```

CodeQL:

```text
https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
```

Trivy:

```text
https://trivy.dev/
```

Kubernetes image digests:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

Kubernetes ValidatingAdmissionPolicy:

```text
https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

OpenGitOps:

```text
https://opengitops.dev/
```

---

# 104. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
020-container-build-and-hardening.md
021-container-vulnerability-scanning.md
022-sbom-and-provenance.md
023-github-container-registry.md
024-github-app-gitops-automation.md
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
028-promotion-workflow.md
029-rollback-strategy.md
030-argocd-sync-selfheal-and-prune.md
031-sigstore-policy-controller.md
032-github-attestation-trust.md
033-image-admission-policies.md
034-pod-init-and-ephemeral-container-policy.md
035-policy-controller-observability.md
036-prometheus-alerting.md
037-secret-management-strategy.md
038-secret-scanning.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-rebuild-and-disaster-recovery.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
