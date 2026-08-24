# Image Digest Update Workflow

## Purpose

This document is the **reproducible implementation guide** for the automated source-to-GitOps image update workflow used by the AI Platform.

The workflow takes the immutable image digests produced by the source release pipeline and updates the development environment in the separate GitOps repository.

A new engineer should be able to rebuild and validate the complete automation path from this document.

The implemented flow is:

```text
source commit merged to main
        |
        v
release workflow starts
        |
        +--> build operator
        |
        +--> build API
        |
        +--> Trivy scans
        |
        +--> push GHCR
        |
        +--> produce digests
        |
        +--> SBOM / provenance attestations
        |
        v
update-gitops job
        |
        +--> create GitHub App installation token
        |
        +--> clone ai-platform-gitops
        |
        +--> create automation branch
        |
        +--> update operator digest
        |
        +--> update API digest
        |
        +--> render Kustomize
        |
        +--> verify only intended files changed
        |
        +--> commit as ai-platform-gitops-bot[bot]
        |
        +--> push branch
        |
        +--> open GitOps PR
        |
        v
Validate GitOps Manifests
        |
        v
human review and merge
        |
        v
Argo CD reconciliation
```

---

# 1. Implementation Context

## Source Repository

Local:

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

## GitOps Repository

Local:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

## Release Workflow

Expected file:

```text
.github/workflows/release-images.yml
```

Before rebuilding or changing the automation, inspect the actual current workflow:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,320p' \
  .github/workflows/release-images.yml
```

Search specifically for:

```bash
grep -nE \
  'build-operator|build-api|update-gitops|digest|create-github-app-token|gh pr create|kustomization.yaml' \
  .github/workflows/release-images.yml
```

---

# 2. Why the Workflow Updates Digests Instead of Tags

The deployment identity is the immutable image digest:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

A tag can move:

```text
v1 -> digest A
later
v1 -> digest B
```

A digest identifies exact image content.

Therefore the workflow does not promote:

```text
latest
main
dev
v1
```

as the final Kubernetes image identity.

It promotes:

```text
sha256:<64-hex-digest>
```

---

# 3. Release Trigger

The release workflow is triggered only when an approved commit reaches:

```text
main
```

Expected pattern:

```yaml
on:
  push:
    branches:
      - main
```

This matters because required pull-request checks protect `main`.

The intended security chain is:

```text
PR required checks
      |
      v
protected main
      |
      v
release workflow
```

The release workflow should not be a substitute for branch protection.

---

# 4. Build Jobs

The release produces two independent images:

```text
ai-platform-operator
ai-platform-api
```

Expected logical jobs:

```text
build-operator
build-api
```

Each job should:

```text
checkout source
authenticate to GHCR
build image
scan image
push image
capture digest
generate SBOM
create attestations
expose digest as job output
```

The exact job names and output names must be taken from the real workflow.

Inspect:

```bash
grep -n -A120 \
  '^  build-operator:' \
  .github/workflows/release-images.yml
```

```bash
grep -n -A120 \
  '^  build-api:' \
  .github/workflows/release-images.yml
```

---

# 5. The GitOps Update Job Must Depend on Both Images

The implemented requirement is:

```yaml
update-gitops:
  needs:
    - build-operator
    - build-api
```

This ensures:

```text
operator build FAIL
    -> update-gitops does not run

API build FAIL
    -> update-gitops does not run
```

This is an important delivery invariant.

The platform should never open a GitOps deployment PR containing only one half of an expected coordinated release when the release is designed to update both images.

## Validate in Workflow

```bash
grep -n -A20 \
  '^  update-gitops:' \
  .github/workflows/release-images.yml
```

Expected:

```text
needs:
  - build-operator
  - build-api
```

---

# 6. Job Outputs Required by update-gitops

The update job needs:

```text
source commit SHA
operator digest
API digest
```

The source SHA is available through:

```yaml
${{ github.sha }}
```

The image digests should come from the image build jobs.

Canonical shape:

```yaml
${{ needs.build-operator.outputs.digest }}
${{ needs.build-api.outputs.digest }}
```

The exact output key names must match the actual workflow.

## Inspect Outputs

```bash
grep -n -A30 \
  'outputs:' \
  .github/workflows/release-images.yml
```

Also inspect references:

```bash
grep -nE \
  'needs\.build-operator\.outputs|needs\.build-api\.outputs' \
  .github/workflows/release-images.yml
```

---

# 7. Validate Digest Shape Before Touching GitOps

Before modifying GitOps state, validate both digests.

A valid SHA-256 digest should match:

```text
sha256:<64 hexadecimal characters>
```

Example shell validation:

```bash
validate_digest() {
  local digest="$1"

  if [[ ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "ERROR: invalid digest: ${digest}" >&2
    return 1
  fi
}
```

Then:

```bash
validate_digest "${OPERATOR_DIGEST}"
validate_digest "${API_DIGEST}"
```

If either validation fails:

```text
FAIL the update-gitops job
```

Do not attempt to create a deployment PR with malformed digest data.

---

# 8. Create the GitHub App Installation Token

The source repository uses the GitHub App documented in:

```text
024-github-app-gitops-automation.md
```

Pinned action:

```text
actions/create-github-app-token
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Expected repository scope:

```text
anselem-okeke/ai-platform-gitops
```

Canonical example:

```yaml
- name: Create GitOps GitHub App token
  id: gitops-app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
  with:
    client-id: ${{ vars.GITOPS_APP_CLIENT_ID }}
    private-key: ${{ secrets.GITOPS_APP_PRIVATE_KEY }}
    owner: anselem-okeke
    repositories: ai-platform-gitops
    permission-contents: write
    permission-pull-requests: write
```

If the existing workflow uses legacy:

```yaml
app-id:
```

preserve it unless intentionally migrating.

The exact secret/variable names must match the real workflow.

---

# 9. Clone the GitOps Repository

Use the short-lived installation token.

Canonical pattern:

```yaml
- name: Clone GitOps repository
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
  run: |
    git clone \
      "https://x-access-token:${GH_TOKEN}@github.com/anselem-okeke/ai-platform-gitops.git" \
      ai-platform-gitops
```

Alternative:

```yaml
actions/checkout
```

can be used with:

```text
repository: anselem-okeke/ai-platform-gitops
token: <GitHub App token>
path: ai-platform-gitops
```

Whichever method is used, confirm:

```text
the GitHub App token, not a developer PAT, authenticates the write operation
```

---

# 10. Check Out the GitOps Default Branch

Inside the cloned repository:

```bash
cd ai-platform-gitops
```

Verify remote:

```bash
git remote -v
```

Verify current branch:

```bash
git branch --show-current
```

If needed:

```bash
git switch main
git pull --ff-only origin main
```

The automation should always branch from the current deployment source of truth.

---

# 11. Create the Automation Branch

Implemented naming convention:

```text
automation/image-<source-sha>
```

Example:

```bash
SOURCE_SHA="${GITHUB_SHA}"
BRANCH="automation/image-${SOURCE_SHA}"

git switch -c "${BRANCH}"
```

Validate:

```bash
git branch --show-current
```

Expected pattern:

```text
automation/image-<40-character-source-sha>
```

The branch name creates traceability from the deployment PR back to the source release.

---

# 12. Target Files

The automation modifies exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

These are the development environment overlays.

The automation should **not** directly modify:

```text
platform/operator/base/*
platform/api/base/*
clusters/dev/apps/*
argocd/*
monitoring/*
policies/*
```

unless the release intentionally changes more than image identity.

---

# 13. Understand the Kustomize Image Representation

Before implementing replacement logic, inspect the real files.

Operator:

```bash
sed -n '1,220p' \
  platform/operator/overlays/dev/kustomization.yaml
```

API:

```bash
sed -n '1,220p' \
  platform/api/overlays/dev/kustomization.yaml
```

Look for the current Kustomize image structure.

Typical forms include:

```yaml
images:
  - name: controller
    newName: ghcr.io/anselem-okeke/ai-platform-operator
    digest: sha256:...
```

or:

```yaml
images:
  - name: ai-platform-api
    newName: ghcr.io/anselem-okeke/ai-platform-api
    digest: sha256:...
```

Do not assume the exact `name` field from documentation alone.

Use the actual repository files.

---

# 14. Update the Operator Digest

The final desired state must resolve to:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
```

If using a YAML-aware tool such as `yq`, prefer structured edits over brittle text replacement.

Example concept:

```bash
yq -i \
  '(.images[] | select(.newName == "ghcr.io/anselem-okeke/ai-platform-operator").digest) = strenv(OPERATOR_DIGEST)' \
  platform/operator/overlays/dev/kustomization.yaml
```

The exact `yq` expression must match the live structure.

If the workflow uses another tool or script, preserve the tested implementation.

---

# 15. Update the API Digest

The final desired state must resolve to:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

Example concept:

```bash
yq -i \
  '(.images[] | select(.newName == "ghcr.io/anselem-okeke/ai-platform-api").digest) = strenv(API_DIGEST)' \
  platform/api/overlays/dev/kustomization.yaml
```

Again, inspect the actual Kustomization before using this command.

---

# 16. Avoid Reintroducing Mutable `newTag`

The implemented GitOps validation intentionally treats digest pinning as the final identity.

Do not update the overlay to:

```yaml
newTag: latest
```

or:

```yaml
newTag: <source-sha>
```

as the final deployment mechanism.

A source SHA tag can still exist as registry metadata, but the Kubernetes desired state should use:

```yaml
digest: sha256:...
```

---

# 17. Validate Only Intended Files Changed

After updating both digests:

```bash
git status --short
```

Expected exactly:

```text
M platform/api/overlays/dev/kustomization.yaml
M platform/operator/overlays/dev/kustomization.yaml
```

Check names:

```bash
git diff --name-only | sort
```

Expected:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

## Add a Workflow Guard

Recommended:

```bash
EXPECTED="$(
  printf '%s\n' \
    platform/api/overlays/dev/kustomization.yaml \
    platform/operator/overlays/dev/kustomization.yaml \
  | sort
)"

ACTUAL="$(
  git diff --name-only \
  | sort
)"

if [[ "${ACTUAL}" != "${EXPECTED}" ]]; then
  echo "ERROR: unexpected files modified" >&2
  echo "Expected:" >&2
  printf '%s\n' "${EXPECTED}" >&2
  echo "Actual:" >&2
  printf '%s\n' "${ACTUAL}" >&2
  exit 1
fi
```

---

# 18. Inspect the Semantic Diff

```bash
git diff -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

The expected semantic result is:

```text
old operator digest -> new operator digest
old API digest      -> new API digest
```

There should be no unrelated field changes.

---

# 19. Render the Operator Overlay

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rendered.yaml
```

Check command status:

```bash
echo $?
```

Expected:

```text
0
```

---

# 20. Render the API Overlay

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rendered.yaml
```

Expected:

```text
successful render
```

---

# 21. Verify Final Rendered Images

Inspect:

```bash
grep -n 'image:' \
  /tmp/operator-rendered.yaml \
  /tmp/api-rendered.yaml
```

Expected images:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<operator-digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<api-digest>
```

No final runtime image should use:

```text
:latest
:dev
:newTag-only
```

---

# 22. Verify the Exact Expected Digests Appeared

Recommended:

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}" \
  /tmp/operator-rendered.yaml
```

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}" \
  /tmp/api-rendered.yaml
```

If either grep fails:

```text
FAIL the workflow
```

This guards against editing the wrong image entry.

---

# 23. Run Whitespace Validation

```bash
git diff --check
```

Expected:

```text
no output
exit code 0
```

A formatting/whitespace error should fail before commit.

---

# 24. Optional Server-Side Dry Run

If the release runner has authenticated access to the development cluster and CI policy explicitly permits read/server validation, a server-side dry-run can be used.

However, the platform design intentionally avoids making CI depend on direct target-cluster deployment credentials.

Therefore the primary GitOps validation happens in the GitOps repository workflow.

Do not add permanent cluster-admin credentials to the source release workflow just to perform:

```bash
kubectl apply --dry-run=server
```

The separation of responsibilities is intentional.

---

# 25. Configure Git Bot Identity

Use the GitHub App identity.

Expected author:

```text
ai-platform-gitops-bot[bot]
```

See:

```text
024-github-app-gitops-automation.md
```

Canonical:

```bash
git config \
  user.name \
  "ai-platform-gitops-bot[bot]"
```

Use the real GitHub App bot user ID to construct the noreply email:

```text
<bot-user-id>+ai-platform-gitops-bot[bot]@users.noreply.github.com
```

---

# 26. Stage Only the Intended Files

```bash
git add \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Verify:

```bash
git diff --cached --name-only
```

Expected exactly those two paths.

---

# 27. Validate Staged Diff

```bash
git diff --cached --check
```

Expected:

```text
no output
```

Inspect:

```bash
git diff --cached
```

Do not commit until the staged diff contains only the intended digest changes.

---

# 28. Commit Convention

Implemented convention:

```text
chore(dev): deploy images from <source-sha>
```

Example:

```bash
git commit \
  -m "chore(dev): deploy images from ${SOURCE_SHA}"
```

Validate:

```bash
git log -1 \
  --format='author=%an <%ae>%nsubject=%s'
```

Expected author:

```text
ai-platform-gitops-bot[bot]
```

Expected subject:

```text
chore(dev): deploy images from <source-sha>
```

---

# 29. Push the Automation Branch

```bash
git push \
  -u origin \
  "${BRANCH}"
```

Expected:

```text
new remote branch created
```

If push fails with:

```text
403
```

review GitHub App:

```text
Contents: Read & write
```

and branch/ruleset restrictions.

---

# 30. Create the Pull Request

Expected:

```text
base: main
head: automation/image-<source-sha>
author: ai-platform-gitops-bot[bot]
```

Example:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head "${BRANCH}" \
  --title "chore(dev): deploy images from ${SOURCE_SHA}" \
  --body "Automated immutable image digest update from source commit ${SOURCE_SHA}."
```

Use:

```text
GH_TOKEN=<GitHub App installation token>
```

for this operation.

---

# 31. Recommended Pull Request Body

A good automated PR body should include traceability.

Example:

```markdown
## Automated image promotion

Source commit:

`<source-sha>`

Operator:

`ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>`

API:

`ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>`

This PR was created automatically by `ai-platform-gitops-bot[bot]`.

The PR is not auto-merged. GitOps validation and human review are required.
```

Do not include sensitive tokens or secrets.

---

# 32. GitOps Pull Request Validation

After PR creation, the GitOps repository workflow runs:

```text
Validate GitOps Manifests
```

Expected workflow file:

```text
.github/workflows/validate.yml
```

The validation includes:

```text
Kustomize rendering
kubeconform
approved GHCR validation
full SHA-256 digest validation
mutable final image rejection
secret checks
git diff --check
```

See:

```text
026-gitops-pr-validation.md
```

---

# 33. Verify the Pull Request from CLI

List:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

Inspect:

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Changed files:

```bash
gh pr diff <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --name-only
```

Expected:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

---

# 34. Verify PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Expected:

```text
Validate GitOps Manifests   pass
```

If validation fails:

```text
do not merge
```

Fix the automation or desired-state change.

---

# 35. Human Merge Is Required

The bot must **not** auto-merge the GitOps PR.

The promotion boundary is:

```text
automation
    |
    v
validated PR
    |
    v
human authorization
    |
    v
merge
```

This means:

```text
successful build
```

does not automatically mean:

```text
authorized deployment
```

---

# 36. Argo CD Reconciliation After Merge

Once merged, the existing child Applications detect the new desired state.

API:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Operator:

```bash
argocd app get \
  ai-platform-operator \
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

```bash
argocd app wait \
  ai-platform-operator \
  --sync \
  --health \
  --timeout 300
```

No root Application sync is needed because these are changes under existing child source paths.

---

# 37. Verify the Live Operator Image

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<new-digest>
```

---

# 38. Verify the Live API Image

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<new-digest>
```

---

# 39. Verify Rollouts

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

Expected:

```text
successfully rolled out
```

---

# 40. Verify Admission Did Not Block the New Artifacts

If rollout fails, inspect:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

```bash
kubectl get events \
  -n ai-platform-operator-system \
  --sort-by=.lastTimestamp
```

Possible causes:

```text
native image policy rejection
Sigstore trust rejection
image pull failure
invalid digest
registry access issue
```

The release must produce attestations for the same digests being promoted.

---

# 41. Failure Scenario: One Build Job Fails

## Symptom

Example:

```text
build-operator = success
build-api = failure
update-gitops = skipped
```

## Expected Behavior

This is correct.

Do not weaken the dependency graph to force a deployment PR.

Fix the failed image build and rerun through the normal release path.

---

# 42. Failure Scenario: Digest Output Is Empty

## Symptom

The update job starts but:

```text
OPERATOR_DIGEST=
```

or:

```text
API_DIGEST=
```

## Diagnosis

Inspect build job output definitions:

```bash
grep -n -A20 \
  'outputs:' \
  .github/workflows/release-images.yml
```

Check the step that writes:

```text
$GITHUB_OUTPUT
```

The digest-producing step must have an `id`.

Example shape:

```yaml
- name: Build and push
  id: build
  ...

outputs:
  digest: ${{ steps.build.outputs.digest }}
```

## Fix

Wire the actual digest output from the build/push step to the job output.

---

# 43. Failure Scenario: Digest Has Wrong Shape

## Symptom

Example:

```text
sha256:
```

or:

```text
<registry>@sha256:...
```

when the update script expects only:

```text
sha256:...
```

## Fix

Normalize the contract.

Recommended job output:

```text
sha256:<64 hex>
```

Then construct the full image identity separately.

Do not mix:

```text
image repository
```

and:

```text
digest
```

in an undocumented output format.

---

# 44. Failure Scenario: Kustomize Render Still Shows Old Digest

## Diagnosis

Inspect the overlay:

```bash
sed -n '1,220p' \
  platform/operator/overlays/dev/kustomization.yaml
```

Check whether the update script modified:

```text
the correct image item
```

Render:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  | grep 'image:'
```

If the old digest remains, the replacement logic targeted the wrong field or `images` entry.

---

# 45. Failure Scenario: Raw Base Contains `latest`

This can be expected.

Known base placeholders include:

```text
controller:latest
ai-platform-api:dev
```

The security invariant applies to:

```text
final rendered dev overlay
```

not necessarily every reusable raw base literal.

Do not weaken final image validation to accommodate raw bases.

Instead, validate rendered manifests.

---

# 46. Failure Scenario: Bot PR Contains Unrelated Changes

## Diagnosis

```bash
git diff --name-only
git status --short
```

## Fix

Fail the automation.

Do not let a release workflow silently modify:

```text
Argo topology
security policies
monitoring
namespaces
RBAC
```

The automated promotion job should have a very narrow mutation surface.

---

# 47. Failure Scenario: GitHub App Cannot Push

Possible error:

```text
403 Resource not accessible by integration
```

Check:

```text
GitHub App installed on ai-platform-gitops
Contents = Read & write
correct owner
correct repository
correct installation token
```

See:

```text
024-github-app-gitops-automation.md
```

---

# 48. Failure Scenario: GitHub App Cannot Open PR

Check:

```text
Pull requests = Read & write
```

Confirm the installation owner accepted updated permissions if permissions were changed after installation.

---

# 49. Failure Scenario: GitOps Validation Rejects the PR

Inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Then open the failed workflow.

Typical reasons:

```text
Kustomize render failure
kubeconform failure
image not approved
image not digest-pinned
unexpected mutable tag
secret pattern match
whitespace error
```

Do not bypass validation.

Fix the desired-state change.

---

# 50. Failure Scenario: PR Merged but Argo Does Not Deploy

Because operator/API are existing child Applications, root sync should not be required.

Check:

```bash
argocd app get ai-platform-api --refresh
argocd app get ai-platform-operator --refresh
```

If `OutOfSync`, inspect:

```bash
argocd app diff ai-platform-api
```

If `Synced` but live image is old, verify:

```text
the merged Git revision
the Application source path
the overlay image digest
the Kubernetes Deployment
```

---

# 51. Failure Scenario: Argo Deploys but Admission Rejects

Check events:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp \
  | tail -n 100
```

If Sigstore denies with a message such as:

```text
no valid bundles exist in registry
```

verify that attestations were generated for **exactly the digest** being promoted.

Do not fix the problem by disabling namespace enforcement.

---

# 52. Rollback

A GitOps deployment rollback is a Git change.

Identify previous deployment commit:

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Create rollback branch:

```bash
git switch main
git pull --ff-only origin main

git switch -c rollback/<description>
```

Revert the bad promotion commit:

```bash
git revert <bad-gitops-commit>
```

Validate:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rollback.yaml

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rollback.yaml

git diff --check
```

Open a normal reviewed PR.

After merge, Argo restores the previous immutable digests.

---

# 53. Why Rollback Uses Git Instead of `kubectl set image`

A command such as:

```bash
kubectl set image ...
```

changes the cluster but not Git.

Because Argo self-heal is enabled, the manual image change may be reverted.

The correct long-lived recovery mechanism is:

```text
Git revert
```

Emergency manual actions must be followed immediately by a Git correction.

---

# 54. Rebuild the Automation from Zero

Use this procedure if the source release workflow is lost or needs to be reconstructed.

```text
[ ] verify source repository
[ ] verify GitOps repository
[ ] verify protected source main
[ ] create/verify build-operator job
[ ] create/verify build-api job
[ ] produce immutable GHCR digest outputs
[ ] add Trivy gate
[ ] add SBOM/provenance
[ ] expose digest outputs
[ ] create update-gitops job
[ ] set needs: build-operator, build-api
[ ] create GitHub App token
[ ] clone GitOps repository
[ ] branch from current main
[ ] validate digest shape
[ ] update operator digest
[ ] update API digest
[ ] verify only two intended files changed
[ ] render operator overlay
[ ] render API overlay
[ ] verify expected images in render
[ ] run git diff --check
[ ] configure bot identity
[ ] commit
[ ] push
[ ] open PR
[ ] confirm bot author
[ ] confirm GitOps validation
[ ] merge manually
[ ] verify Argo reconciliation
[ ] verify Kubernetes image digests
[ ] verify rollout
```

---

# 55. Security Properties of the Workflow

The workflow deliberately preserves these boundaries:

```text
source CI
  cannot silently deploy directly

GitHub App
  can update GitOps branch / PR
  cannot act as repository administrator

bot PR
  cannot become deployment without merge

GitOps validation
  independently validates desired state

Argo
  only reconciles approved Git state

admission
  independently checks runtime artifact trust
```

This is defense in depth.

---

# 56. Recommended Workflow Guards

The following guards should exist in the release workflow.

## Guard 1 — Require Both Build Jobs

```yaml
needs:
  - build-operator
  - build-api
```

## Guard 2 — Validate Digest Format

```bash
^sha256:[0-9a-f]{64}$
```

## Guard 3 — Modify Only Expected Files

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

## Guard 4 — Render Both Overlays

```bash
kubectl kustomize ...
```

## Guard 5 — Verify Final Digests

```bash
grep -F ...
```

## Guard 6 — Validate Git Diff

```bash
git diff --check
```

## Guard 7 — No Auto-Merge

The workflow should stop after opening the PR.

---

# 57. End-to-End Evidence Record

For each release, the platform should be able to trace:

```text
source commit SHA
    |
    v
GitHub Actions run
    |
    v
operator digest
API digest
    |
    v
GHCR packages
    |
    v
artifact attestations
    |
    v
GitOps automation branch
    |
    v
GitOps PR
    |
    v
GitOps merge commit
    |
    v
Argo revision
    |
    v
Kubernetes live image digests
```

This is the deployment audit chain.

---

# 58. Useful Commands

## Source Release Runs

```bash
cd /mnt/data/ai-platform-operator

gh run list \
  --workflow release-images.yml \
  --limit 10
```

## Inspect Run

```bash
gh run view <RUN_ID>
```

## Inspect Failed Logs

```bash
gh run view <RUN_ID> \
  --log-failed
```

## GitOps PR List

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

## GitOps PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

## Argo Revision

```bash
argocd app get ai-platform-api
```

```bash
argocd app get ai-platform-operator
```

## Live Images

```bash
kubectl get deployment ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

---

# 59. What Not to Put in the Automation

Do not add:

```text
kubectl apply to the target cluster
long-lived PATs
GitHub App private key in repository files
automatic GitOps PR merge
force push to GitOps main
floating deployment tags
wildcard repository access
unvalidated arbitrary file mutation
```

These would weaken the design.

---

# 60. Official References

GitHub Actions workflow syntax:

```text
https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
```

GitHub Apps in Actions:

```text
https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow
```

GitHub App token action:

```text
https://github.com/actions/create-github-app-token
```

GitHub CLI PR creation:

```text
https://cli.github.com/manual/gh_pr_create
```

Kustomize images:

```text
https://kubectl.docs.kubernetes.io/references/kustomize/kustomization/images/
```

Kubernetes image names/digests:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

Argo CD automated sync:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
```

---

# 61. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
020-container-build-and-hardening.md
021-container-vulnerability-scanning.md
022-sbom-and-provenance.md
023-github-container-registry.md
024-github-app-gitops-automation.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
029-rollback-strategy.md
030-argocd-sync-selfheal-and-prune.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
