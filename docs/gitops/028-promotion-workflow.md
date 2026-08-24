# Promotion Workflow

## Purpose

This document is the **reproducible implementation guide** for promoting validated AI Platform release artifacts from the source repository into GitOps-managed desired state.

The core promotion principle is:

```text
Build once
Verify once
Attest once
Promote the same immutable digest
```

A new engineer should be able to reproduce, validate, troubleshoot, and operate the promotion workflow using this document and the repository.

The implemented development flow is:

```text
source PR
   |
   v
required checks
   |
   v
merge to source main
   |
   v
release workflow
   |
   +--> build operator image
   +--> build API image
   +--> vulnerability scan
   +--> push GHCR
   +--> generate SBOM
   +--> create attestations
   |
   v
immutable digests
   |
   v
GitHub App bot
   |
   v
GitOps promotion PR
   |
   v
Validate GitOps Manifests
   |
   v
human review / merge
   |
   v
Argo CD
   |
   v
Kubernetes admission
   |
   v
running workload
```

The current implemented environment is:

```text
dev
```

Future environments such as:

```text
staging
prod
```

should reuse the **same already-built image digest**, not rebuild from source.

---

# 1. Repositories

## Source Repository

```text
anselem-okeke/ai-platform-operator
```

Local:

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

## GitOps Repository

```text
anselem-okeke/ai-platform-gitops
```

Local:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

---

# 2. Promotion Is Not Rebuilding

A promotion moves an already-verified artifact identity.

Correct:

```text
dev      -> digest X
staging  -> digest X
prod     -> digest X
```

Incorrect:

```text
dev      -> rebuild source -> digest X
staging  -> rebuild source -> digest Y
prod     -> rebuild source -> digest Z
```

Even if the source commit is identical, separate rebuilds can produce different bytes because of:

```text
base image drift
dependency changes
build timestamp differences
toolchain changes
package repository changes
build environment changes
```

Therefore the platform promotes:

```text
sha256:<digest>
```

not:

```text
source commit -> rebuild again
```

---

# 3. Current Promotion Scope

Implemented:

```text
dev
```

Future:

```text
staging
prod
```

Do not claim staging or production promotion is implemented until those GitOps overlays/environments and approval controls exist.

---

# 4. Promotion Boundary

The release pipeline is allowed to:

```text
build
scan
publish
attest
open a GitOps PR
```

It is not allowed to:

```text
merge its own deployment PR
kubectl apply directly
bypass GitOps branch protection
bypass admission
```

The human-controlled GitOps merge is the current deployment authorization boundary.

---

# 5. Source Main Is the Release Trigger

The release workflow starts after an approved source PR reaches:

```text
main
```

Expected:

```yaml
on:
  push:
    branches:
      - main
```

Before modifying the release logic, inspect:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,360p' \
  .github/workflows/release-images.yml
```

Search:

```bash
grep -nE \
  'on:|branches:|build-operator|build-api|update-gitops|digest|attest|sbom' \
  .github/workflows/release-images.yml
```

---

# 6. Required Source Gates

Before merge, source `main` is protected by required checks.

Validated required checks:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

The release should only run after these controls have already allowed the source commit to reach protected `main`.

See:

```text
027-branch-protection-and-rulesets.md
```

---

# 7. Build Operator Image

The operator image is published under:

```text
ghcr.io/anselem-okeke/ai-platform-operator
```

The build should:

```text
build
scan
push
capture digest
produce SBOM
attest provenance
attest SBOM
```

The final deployment identity is:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

---

# 8. Build API Image

The API image is published under:

```text
ghcr.io/anselem-okeke/ai-platform-api
```

The final deployment identity is:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

---

# 9. Container Hardening Is Completed Before Promotion

Promotion assumes the release artifact has already passed the source release controls.

Current image hardening includes:

```text
Go 1.26.6 builder
CGO_ENABLED=0
trimpath / ldflags
distroless static Debian 13 runtime
non-root user 65532
operator binary /manager
API binary /platform-api
```

See:

```text
020-container-build-and-hardening.md
```

Promotion should not mutate the image after these controls.

---

# 10. Vulnerability Scan Gate

The release uses Trivy to fail on:

```text
HIGH
CRITICAL
```

with:

```text
ignore-unfixed
exit-code 1
```

The exact implementation belongs to the release workflow.

If scanning fails:

```text
no promotion PR should be created
```

Do not override the failure by manually promoting the same failed digest unless there is a documented emergency security exception process.

---

# 11. SBOM and Provenance

For each released image, the pipeline produces:

```text
SPDX JSON SBOM
provenance attestation
SBOM attestation
```

These attestations bind evidence to the same immutable digest that GitOps later promotes.

See:

```text
022-sbom-and-provenance.md
```

---

# 12. Why Attestation Must Precede Promotion

Correct sequence:

```text
build
  |
  v
scan
  |
  v
push
  |
  v
capture digest
  |
  +--> provenance attestation
  |
  +--> SBOM attestation
  |
  v
promotion PR
```

Avoid:

```text
promote digest
  |
  v
try to attest later
```

because admission may evaluate the artifact before trusted evidence exists.

---

# 13. Image Digest Contract

The promotion workflow should handle digest values as:

```text
sha256:<64 hexadecimal characters>
```

Example:

```text
sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Validate before use:

```bash
validate_digest() {
  local digest="$1"

  if [[ ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "ERROR: invalid digest: ${digest}" >&2
    return 1
  fi
}
```

---

# 14. Build Job Outputs

The release jobs must expose the digests to:

```text
update-gitops
```

Conceptually:

```yaml
outputs:
  digest: ${{ steps.<build-step>.outputs.digest }}
```

Then:

```yaml
${{ needs.build-operator.outputs.digest }}
${{ needs.build-api.outputs.digest }}
```

Inspect the actual workflow rather than assuming output names:

```bash
grep -nE \
  'outputs:|needs\.build-operator\.outputs|needs\.build-api\.outputs' \
  .github/workflows/release-images.yml
```

---

# 15. Promotion Requires Both Images

The update job depends on both:

```yaml
needs:
  - build-operator
  - build-api
```

This means:

```text
operator FAIL -> no promotion PR
API FAIL      -> no promotion PR
```

This avoids partial coordinated promotion.

---

# 16. GitHub App Machine Identity

The release workflow does not use a developer PAT to update the GitOps repository.

It uses:

```text
ai-platform-gitops-bot[bot]
```

through a GitHub App installation token.

See:

```text
024-github-app-gitops-automation.md
```

---

# 17. GitOps Promotion Branch

Implemented convention:

```text
automation/image-<source-sha>
```

The branch links:

```text
source commit
```

to:

```text
GitOps promotion PR
```

Example:

```bash
SOURCE_SHA="${GITHUB_SHA}"
BRANCH="automation/image-${SOURCE_SHA}"
```

---

# 18. GitOps Files Updated

Current dev promotion changes exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

The promotion job should not change unrelated platform topology.

---

# 19. Operator Desired-State Update

The final rendered operator image must become:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<new-digest>
```

Inspect current overlay:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,220p' \
  platform/operator/overlays/dev/kustomization.yaml
```

---

# 20. API Desired-State Update

The final rendered API image must become:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<new-digest>
```

Inspect:

```bash
sed -n '1,220p' \
  platform/api/overlays/dev/kustomization.yaml
```

---

# 21. Validate Promotion Diff

Run:

```bash
git diff -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Expected semantic diff:

```text
operator digest old -> new
API digest old      -> new
```

No unrelated field should change.

---

# 22. Validate Changed Files

```bash
git diff --name-only | sort
```

Expected exactly:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

Anything else should fail the automated promotion job.

---

# 23. Render Operator Overlay

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-promotion.yaml
```

Expected:

```text
exit code 0
```

---

# 24. Render API Overlay

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-promotion.yaml
```

---

# 25. Verify Final Images

```bash
grep -n 'image:' \
  /tmp/operator-promotion.yaml \
  /tmp/api-promotion.yaml
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<operator-digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<api-digest>
```

---

# 26. Verify Exact Promotion Digests

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}" \
  /tmp/operator-promotion.yaml
```

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}" \
  /tmp/api-promotion.yaml
```

If either command fails:

```text
do not create the PR
```

---

# 27. Validate Whitespace

```bash
git diff --check
```

Expected:

```text
no output
```

---

# 28. Promotion Commit

Expected commit:

```text
chore(dev): deploy images from <source-sha>
```

Example:

```bash
git commit \
  -m "chore(dev): deploy images from ${SOURCE_SHA}"
```

Commit identity should be:

```text
ai-platform-gitops-bot[bot]
```

---

# 29. Promotion Pull Request

Expected:

```text
base: main
head: automation/image-<source-sha>
author: ai-platform-gitops-bot[bot]
title: chore(dev): deploy images from <source-sha>
```

The PR must remain subject to:

```text
Validate GitOps Manifests
```

---

# 30. Recommended PR Body

Include:

```text
source commit SHA
operator digest
API digest
target environment
automation identity
manual-merge reminder
```

Example:

```markdown
## Automated dev promotion

Source commit:

`<source-sha>`

Operator:

`ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>`

API:

`ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>`

Target:

`dev`

This PR was created by `ai-platform-gitops-bot[bot]`.

It is not auto-merged. GitOps validation and human merge are required.
```

---

# 31. GitOps Validation Gate

The promotion PR must pass:

```text
Validate GitOps Manifests
```

This validates:

```text
Kustomize rendering
kubeconform
approved image repository
full digest pinning
mutable image rejection
lightweight secret checks
git diff --check
```

See:

```text
026-gitops-pr-validation.md
```

---

# 32. Human Authorization

Current promotion requires human merge.

This means:

```text
artifact production
```

is not the same as:

```text
deployment authorization
```

The human-controlled GitOps merge is a deliberate separation of duties.

---

# 33. Why the Bot Must Not Auto-Merge

If the bot:

```text
builds artifact
opens PR
merges PR
```

then the same automation path both:

```text
produces
and
authorizes
```

the deployment.

The current design intentionally stops at:

```text
open validated PR
```

---

# 34. Post-Merge Argo Reconciliation

Once the GitOps PR is merged:

```text
GitOps main changes
      |
      v
Argo detects new revision
      |
      v
child Application reconciles
```

Because operator/API are existing child Applications, root sync is not required for a normal image digest update.

---

# 35. Verify API Argo State

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Expected:

```text
Sync Status: Synced
Health Status: Healthy
```

After reconciliation.

---

# 36. Verify Operator Argo State

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

---

# 37. Wait for Reconciliation

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

---

# 38. Verify Live API Image

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<promoted-digest>
```

---

# 39. Verify Live Operator Image

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<promoted-digest>
```

---

# 40. Verify Rollout

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
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  --timeout=300s
```

---

# 41. Admission Is the Final Runtime Trust Check

Even after an approved GitOps merge, Kubernetes admission can reject the artifact.

Current controls include:

```text
native image validation
Sigstore Policy Controller
GitHub artifact-attestation trust
namespace enforcement
```

A fake but syntactically valid digest has been rejected with:

```text
no valid bundles exist in registry
```

Therefore:

```text
GitOps approval
```

does not bypass:

```text
runtime artifact trust
```

---

# 42. Promotion Traceability Chain

A valid promotion should be traceable end to end:

```text
source commit SHA
     |
     v
source PR
     |
     v
required checks
     |
     v
release run ID
     |
     v
operator digest
API digest
     |
     v
GHCR
     |
     v
SBOM / provenance attestations
     |
     v
GitOps automation branch
     |
     v
GitOps PR
     |
     v
GitOps validation run
     |
     v
GitOps merge commit
     |
     v
Argo revision
     |
     v
Kubernetes live digest
```

---

# 43. Promotion Review Checklist

Before merging a promotion PR, review:

```text
source SHA
old operator digest
new operator digest
old API digest
new API digest
image repositories
target environment
source CI result
image scan result
attestation result
GitOps validation result
unexpected file changes
```

---

# 44. Validate Source SHA

The PR should identify:

```text
<source-sha>
```

Compare to the source release run:

```bash
cd /mnt/data/ai-platform-operator

git show \
  --no-patch \
  --oneline \
  <source-sha>
```

---

# 45. Validate Digests Exist in GHCR

At minimum, confirm the release workflow successfully pushed both images.

If using GitHub CLI/API, query package metadata where authenticated.

Do not manually type a digest into GitOps unless you have verified its origin.

---

# 46. Validate Attestations Exist

The promoted digest should have trusted evidence produced by the release workflow.

The release uses GitHub artifact attestations.

Before production promotion in a future environment, consider adding an explicit pre-promotion attestation verification command.

The current admission layer already verifies trusted evidence at runtime.

---

# 47. Current Dev Promotion Is Automatic-to-PR, Manual-to-Merge

Current behavior:

```text
source main
   |
   v
release
   |
   v
GitOps PR automatically created
   |
   v
manual merge
```

This is distinct from:

```text
fully automatic deployment
```

---

# 48. Future Staging Promotion

A future staging environment should likely introduce:

```text
platform/.../overlays/staging
clusters/staging/...
```

and promotion should move:

```text
the same dev-tested digest
```

into staging.

Example concept:

```text
dev:
sha256:X

staging:
sha256:X
```

Do not rebuild image X for staging.

---

# 49. Future Production Promotion

Production should similarly promote:

```text
sha256:X
```

after:

```text
dev validation
staging validation
approval
```

A future production PR should ideally include:

```text
source commit
artifact digest
SBOM/provenance verification
staging evidence
change ticket / approval if applicable
rollback target
```

---

# 50. Environment Promotion Should Change Desired State Only

Promotion from dev to staging/prod should change:

```text
Git desired state
```

not:

```text
artifact bytes
```

This is the central invariant.

---

# 51. Failure Scenario — Release Builds but No GitOps PR Appears

Check source workflow:

```bash
cd /mnt/data/ai-platform-operator

gh run list \
  --workflow release-images.yml \
  --limit 10
```

Inspect:

```bash
gh run view <RUN_ID>
```

Check:

```text
build-operator
build-api
update-gitops
```

---

# 52. Failure Scenario — update-gitops Skipped

Expected when:

```text
build-operator failed
or
build-api failed
```

This is correct behavior.

Fix the failed release stage.

Do not manually force promotion of partially validated artifacts.

---

# 53. Failure Scenario — GitHub App Token Fails

See:

```text
024-github-app-gitops-automation.md
```

Check:

```text
App installed
GitOps repository selected
correct owner
correct repository
correct Client/App ID
correct private key
Contents write
Pull requests write
```

---

# 54. Failure Scenario — Promotion Updates Wrong Files

Run:

```bash
git diff --name-only
```

Expected only:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

If more files changed:

```text
FAIL
```

---

# 55. Failure Scenario — Promotion Uses Mutable Tag

If final render shows:

```text
:latest
:dev
:main
:v1
```

the promotion is invalid.

Fix the Kustomize image transform to use:

```text
digest: sha256:...
```

---

# 56. Failure Scenario — GitOps PR Fails Validation

Check:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Do not merge until:

```text
Validate GitOps Manifests = pass
```

---

# 57. Failure Scenario — PR Merged but Argo OutOfSync

Refresh:

```bash
argocd app get ai-platform-api --refresh
argocd app get ai-platform-operator --refresh
```

Inspect:

```bash
argocd app diff ai-platform-api
```

and:

```bash
argocd app diff ai-platform-operator
```

---

# 58. Failure Scenario — Argo Healthy but Live Digest Is Wrong

Compare:

```text
GitOps overlay digest
rendered manifest digest
Argo revision
Kubernetes deployment image
```

Commands:

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

---

# 59. Failure Scenario — Admission Rejects Promoted Image

Inspect events:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

and:

```bash
kubectl get events \
  -n ai-platform-operator-system \
  --sort-by=.lastTimestamp
```

Possible causes:

```text
missing attestation
wrong digest
untrusted image source
bad signature/trust evidence
policy mismatch
```

Do not disable admission as the first fix.

---

# 60. Failure Scenario — New Artifact Is Bad at Runtime

If an approved/trusted artifact deploys but fails functionally:

```text
rollback through Git
```

Do not mutate live deployments outside Git as the normal recovery method.

---

# 61. Rollback Principle

A previous GitOps commit contains known-good digests.

Therefore rollback is:

```text
Git revert
```

not:

```text
rebuild old source
```

---

# 62. Identify the Bad Promotion Commit

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Locate:

```text
chore(dev): deploy images from <source-sha>
```

---

# 63. Create Rollback Branch

```bash
git switch main
git pull --ff-only origin main

git switch -c rollback/dev-images-<short-description>
```

---

# 64. Revert Bad Promotion

```bash
git revert <bad-gitops-commit>
```

This restores the previous digest state in Git.

---

# 65. Validate Rollback Render

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rollback.yaml
```

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rollback.yaml
```

Inspect:

```bash
grep -n 'image:' \
  /tmp/operator-rollback.yaml \
  /tmp/api-rollback.yaml
```

---

# 66. Open Rollback PR

Use the normal protected GitOps flow.

Example:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head rollback/dev-images-<description> \
  --title "revert(dev): restore previous image digests" \
  --body "Rollback of GitOps promotion <bad-commit>."
```

---

# 67. Validate and Merge Rollback

Require:

```text
Validate GitOps Manifests
```

Then human merge.

Argo restores the previous immutable images.

---

# 68. Why `kubectl set image` Is Not the Primary Rollback

Manual command:

```bash
kubectl set image ...
```

creates cluster state that disagrees with Git.

Because Argo self-heal is enabled, Git may overwrite the emergency change.

Use Git rollback for durable recovery.

---

# 69. Emergency Manual Recovery

If the cluster is severely impacted and immediate temporary action is necessary:

```text
1. use the narrowest emergency change
2. record exact action
3. immediately create matching Git correction
4. restore Git as source of truth
5. review incident
```

Do not normalize out-of-band kubectl changes.

---

# 70. Promotion Security Invariants

```text
[ ] source main is protected
[ ] release only starts from approved main
[ ] operator/API builds both succeed
[ ] images are scanned
[ ] images are pushed to approved GHCR repos
[ ] image digests are immutable
[ ] SBOM/provenance generated for exact digest
[ ] bot uses short-lived GitHub App token
[ ] bot modifies only expected GitOps files
[ ] GitOps render passes
[ ] promotion PR is not auto-merged
[ ] GitOps required check passes
[ ] human merge occurs
[ ] Argo reconciles Git
[ ] admission verifies runtime trust
```

---

# 71. Operational Promotion Checklist

Before merge:

```text
[ ] source SHA known
[ ] source CI green
[ ] release run green
[ ] operator digest valid
[ ] API digest valid
[ ] GHCR push successful
[ ] attestations created
[ ] GitOps bot PR opened
[ ] only intended files changed
[ ] Kustomize render valid
[ ] GitOps validation green
```

After merge:

```text
[ ] Argo detects revision
[ ] API Synced/Healthy
[ ] Operator Synced/Healthy
[ ] API rollout complete
[ ] Operator rollout complete
[ ] live API digest matches Git
[ ] live operator digest matches Git
[ ] admission did not reject trusted artifacts
```

---

# 72. Promotion Audit Record

For each promotion, record or be able to reconstruct:

```text
source repository
source SHA
source PR
release workflow run ID
operator image digest
API image digest
SBOM/provenance evidence
GitOps branch
GitOps PR
GitOps validation result
GitOps merge commit
Argo application revision
live Kubernetes digest
rollback target
```

---

# 73. Rebuild the Dev Promotion Flow from Zero

```text
[ ] protect source main
[ ] configure required checks
[ ] create release workflow
[ ] build operator
[ ] build API
[ ] scan both images
[ ] push to GHCR
[ ] capture exact digests
[ ] generate SBOMs
[ ] create attestations
[ ] expose build digests as outputs
[ ] make update-gitops depend on both builds
[ ] configure GitHub App
[ ] install App on ai-platform-gitops
[ ] create short-lived installation token
[ ] clone GitOps
[ ] create automation/image-<source-sha>
[ ] update operator digest
[ ] update API digest
[ ] validate changed files
[ ] render Kustomize
[ ] validate exact digests
[ ] git diff --check
[ ] commit as ai-platform-gitops-bot[bot]
[ ] push branch
[ ] open PR
[ ] run Validate GitOps Manifests
[ ] require human merge
[ ] let Argo reconcile
[ ] verify live digests
[ ] test rollback using Git revert
```

---

# 74. Future Multi-Environment Design

Recommended future structure:

```text
platform/operator/overlays/
├── dev
├── staging
└── prod

platform/api/overlays/
├── dev
├── staging
└── prod
```

Promotion then becomes:

```text
digest X
  |
  +--> dev
  |
  +--> staging
  |
  +--> prod
```

Each environment gets independent:

```text
Git review
policy validation
deployment evidence
```

without changing artifact identity.

---

# 75. Future Promotion Policy

A future enterprise promotion policy can require:

```text
dev:
automatic PR

staging:
manual promotion PR after dev health

prod:
manual promotion PR
independent approval
change record
staging evidence
rollback target
```

The exact process should match organizational governance.

---

# 76. Future Artifact Promotion Metadata

A promotion PR can eventually include machine-generated metadata such as:

```text
source commit
build run
digest
SBOM attestation URL/reference
provenance attestation
Trivy result
previous environment result
deployment target
```

Avoid duplicating secret data.

---

# 77. No Rebuild Between Environments

This rule should remain explicit:

```text
NEVER rebuild the same release separately for staging/prod
```

unless the organization intentionally defines environment-specific binaries, which would be a different architecture.

---

# 78. Relationship to Phase 8 Model Promotion

Later, model promotion should follow a similar principle:

```text
register model version
validate model version
promote same approved version/artifact reference
```

Do not confuse:

```text
container image promotion
```

with:

```text
ML model version promotion
```

but both benefit from immutable identity and traceability.

---

# 79. Useful Commands

## Source Release Runs

```bash
cd /mnt/data/ai-platform-operator

gh run list \
  --workflow release-images.yml \
  --limit 10
```

## Inspect Release

```bash
gh run view <RUN_ID>
```

## Inspect Failed Steps

```bash
gh run view <RUN_ID> \
  --log-failed
```

## GitOps PRs

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

## GitOps PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

## Argo API State

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

## Argo Operator State

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

## Live API Digest

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

## Live Operator Digest

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

---

# 80. What Must Never Be Done

Do not:

```text
promote mutable tags as final identity
rebuild the same release per environment
use a developer PAT for GitOps bot automation
auto-merge deployment PRs without explicit governance
write directly to GitOps main
kubectl apply from source CI as normal deployment
disable admission to fix promotion failures
replace Git rollback with undocumented manual drift
```

---

# 81. Known Implementation Facts

Validated project facts:

```text
Current environment:
dev

Source release trigger:
push to main

Images:
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api

Promotion identity:
sha256 digest

GitOps bot:
ai-platform-gitops-bot[bot]

GitOps branch:
automation/image-<source-sha>

Files updated:
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml

Commit/PR convention:
chore(dev): deploy images from <source-sha>

GitOps merge:
manual

Argo:
automated child reconciliation after Git merge

Rollback:
Git revert of known-good digest state
```

---

# 82. What Must Be Verified from the Actual Repository

Do not invent:

```text
exact build-job output names
exact current source workflow step names
exact current Actions secret names
exact current bot token step inputs
exact current GitOps ruleset ID
exact current PR-body text
```

Verify from:

```text
/mnt/data/ai-platform-operator/.github/workflows/release-images.yml
/mnt/data/ai-platform-gitops/.github/workflows/validate.yml
GitHub repository settings/rulesets
```

---

# 83. Official References

OpenGitOps principles:

```text
https://opengitops.dev/
```

Kubernetes image digests:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

GitHub Actions:

```text
https://docs.github.com/actions
```

GitHub artifact attestations:

```text
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
```

GitHub Container Registry:

```text
https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

Kustomize:

```text
https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
```

---

# 84. Related AI Platform Documentation

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
029-rollback-strategy.md
030-argocd-sync-selfheal-and-prune.md
031-sigstore-policy-controller.md
032-github-attestation-trust.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
