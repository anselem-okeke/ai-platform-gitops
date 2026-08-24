# GitOps Promotion Gate

![img](/img/cicd-promotion-gate.png)
## Complete source-to-GitOps implementation and validation runbook

**Source repository:** `anselem-okeke/ai-platform-operator`  
**Source working directory:** `/mnt/data/ai-platform-operator`  
**GitOps repository:** `anselem-okeke/ai-platform-gitops`  
**GitOps working directory:** `/mnt/data/ai-platform-gitops`  
**Implementation window:** 2026-08-22 to 2026-08-23  
**Final positive-path source SHA:** `4cd75ccb351114112257a03b3a43c7d33fcba3c7`  
**Final automated GitOps PR:** `#25`  
**Final GitOps merge commit:** `fcdf138`

> This document is intentionally reconstruction-grade. It records the concept, failure mode, architecture, implementation order, exact commands, exact known IDs, validation evidence, failure handling, rollback, and final state for the centralized platform promotion work.

---

# 1. Why this work existed

The project already had strong individual CI and supply-chain controls:

- lint;
- tests;
- E2E tests;
- security scanning;
- secret scanning;
- container scanning;
- SPDX SBOM generation;
- provenance attestations;
- SBOM attestations;
- immutable image digests;
- GitOps;
- Argo CD;
- admission policy.

The important weakness was not a missing scanner.

The weakness was that the release and GitOps-promotion path was not centrally dependent on every workflow that was intended to be mandatory.

This made the following outcome structurally possible:

```text
Tests          ✅
E2E            ✅
Security       ✅
Secret Scan    ❌
Release Images ✅
GitOps PR      ✅
```

GitHub Actions could behave exactly as configured and still produce that outcome.

The problem was the workflow dependency graph.

The key lesson is:

```text
security visibility != security enforcement
```

A scanner that goes red provides visibility.

A delivery system that refuses to promote when that scanner is red provides enforcement.

The goal of this work was therefore to create one central promotion decision for a source commit and place GitOps write authority behind it.

---

# 2. The original unsafe architecture

Conceptually, the old architecture looked like this:

```text
Source Commit
   |
   +--> Lint
   +--> Tests
   +--> E2E
   +--> Security
   +--> Secret Scan
   +--> Release Images
            |
            +--> Build Operator
            +--> Build API
            +--> Trivy
            +--> SBOM
            +--> Push GHCR
            +--> Attest
            |
            v
       update-gitops
            |
            v
        GitOps PR
```

The critical issue was that `update-gitops` depended on the image build jobs, not on all independent verification workflows.

The old writer had a shape equivalent to:

```yaml
update-gitops:
  name: Create GitOps Update PR
  needs:
    - build-operator
    - build-api
```

That meant:

```text
Security workflow fails
        |
        X  no dependency edge
        |
Release Images succeeds
        |
        v
old update-gitops succeeds
        |
        v
GitOps PR appears
```

This was the architectural flaw to remove.

---

# 3. The incident that exposed the flaw

A dedicated trusted sklearn runtime release path had been created.

The runtime workflow was:

```text
.github/workflows/release-sklearn-runtime.yml
```

The runtime image source was:

```text
Dockerfile.sklearn-runtime
```

The runtime image repository was designed as:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver
```

Its Trivy gate intentionally used:

```yaml
exit-code: '1'
ignore-unfixed: true
vuln-type: os,library
severity: HIGH,CRITICAL
```

The runtime scan found:

```text
20 HIGH
0 CRITICAL
```

The runtime release correctly failed.

The security gate was doing its job.

However, a GitOps PR still appeared.

The important diagnosis was:

```text
failed runtime workflow
     !=
workflow that created the GitOps PR
```

The unrelated `Release Images` workflow was still triggered on `main`, and it still contained the old GitOps writer.

Therefore:

```text
Release sklearn Runtime ❌
Release Images           ✅
old update-gitops        ✅
GitOps PR                ✅
```

This was not a Trivy bypass.

It was independent workflow authority.

---

# 4. Accidental GitOps PR #24

During the first central-gate implementation, the new `Promote to GitOps` workflow was deliberately read-only.

The source commit for that stage was:

```text
6405d43a12f5e7449dceba71af9929ff383fdb12
```

Despite the new gate being read-only, GitOps PR `#24` appeared.

Observed branch:

```text
automation/image-6405d43a12f5e7449dceba71af9929ff383fdb12
```

Observed title pattern:

```text
chore(dev): deploy images from 6405d43...
```

This proved that the old release workflow still had GitOps authority.

It did **not** prove that the new gate wrote GitOps.

PR `#24` was closed during the migration.

---

# 5. Architecture Flow

The final platform promotion architecture is:

```text
Source Commit
   |
   +--> Lint
   +--> Tests
   +--> E2E Tests
   +--> Security
   +--> Secret Scan
   +--> Release Images                  when platform applies
   +--> Release sklearn Runtime         when runtime applies
            |
            v
     Central Promotion Gate
            |
     exact source-SHA correlation
            |
     artifact applicability
            |
      applicable gates pass?
        /       |        \
   BLOCKED   WAITING    READY
      |         |         |
     STOP      STOP       v
                    Resolve exact digests
                             |
                             v
                    Validate promotion inputs
                             |
                             v
                      GitHub App token
                             |
                             v
                      GitOps mutation
                             |
                             v
                    Kustomize validation
                             |
                             v
                         GitOps PR
                             |
                             v
                        GitOps CI
                             |
                             v
                      Human approval
                             |
                             v
                          Argo CD
```

The word **applicable** is essential.

A platform-only change must not require a runtime release.

A runtime-only change must not churn operator/API digests.

A docs-only change must not produce a deployment PR.

---

# 6. Repository map

## Source repository

```text
/mnt/data/ai-platform-operator
```

Important files:

```text
.github/workflows/lint.yml
.github/workflows/test.yml
.github/workflows/test-e2e.yml
.github/workflows/security.yml
.github/workflows/release-images.yml
.github/workflows/release-sklearn-runtime.yml
.github/workflows/promote-gitops.yml
Dockerfile
Dockerfile.platform-api
Dockerfile.sklearn-runtime
.dockerignore
go.mod
go.sum
```

Observed source trees included:

```text
api/v1alpha1/groupversion_info.go
api/v1alpha1/modelservice_types.go
api/v1alpha1/zz_generated.deepcopy.go
cmd/main.go
cmd/platform-api/main.go
internal/api/doc.go
internal/api/routes.go
internal/api/routes_test.go
internal/api/server.go
internal/controller/modelservice_controller.go
internal/controller/modelservice_controller_test.go
internal/controller/suite_test.go
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

The platform promotion writer updates only:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

---

# 7. Exact workflow identities

The exact workflow names verified for the source repository were:

```text
Lint
Release Images
Release sklearn Runtime
Secret Scan
Security
E2E Tests
Tests
```

The new central workflow is:

```text
Promote to GitOps
```

These names matter because the gate matches GitHub Actions runs by workflow name.

A renamed workflow must be updated in the central gate.

---

# 8. Implementation ledger

| Item | ID/value |
|---|---|
| Trusted runtime source PR | `#4` |
| Trusted runtime merge commit | `6aa37e1fdc4f465777a891d632e19b53f80d6b86` |
| Initial centralized gate PR | `#5` |
| Initial gate merge commit | `6405d43a12f5e7449dceba71af9929ff383fdb12` |
| Accidental old-writer GitOps PR | `#24` |
| Artifact applicability PR | `#7` |
| Digest-resolution PR | `#8` |
| Source main after PR #8 | `355cf0c` |
| Digest test PR | `#9` |
| Digest test source SHA | `c5da5f3724a17043c2c2929056f61b3946fccbc7` |
| Central writer PR | `#10` |
| Central writer merge commit | `01ab7c0690753f27f3eaa8a12944695919528bd1` |
| Final positive-path source SHA | `4cd75ccb351114112257a03b3a43c7d33fcba3c7` |
| Final automated GitOps PR | `#25` |
| Final GitOps merge commit | `fcdf138` |

The full merge SHA for PR `#7` was not captured in the evidence used for this runbook.

The observed short source state immediately before PR `#8` was:

```text
e7202ed
```

This document intentionally does not invent a full SHA.

---

# 9. Safe migration order

The migration was deliberately incremental:

1. create a read-only central gate;
2. correlate required workflow results by exact source SHA;
3. implement `READY`, `BLOCKED`, and `WAITING`;
4. replay a known negative runtime case;
5. remove the old `Release Images` GitOps writer;
6. enter a safe state where nobody writes GitOps automatically;
7. inspect real Docker build inputs;
8. define artifact applicability;
9. add `NO-OP`;
10. export gate outputs;
11. validate `NO-OP`;
12. add read-only digest resolution;
13. validate digest resolution with a controlled platform change;
14. add the GitOps writer behind `READY` + platform applicability + digest success;
15. validate writer-enabled `NO-OP`;
16. run a controlled positive platform change;
17. inspect the generated GitOps PR;
18. pass GitOps CI;
19. human-merge the GitOps PR;
20. verify the final immutable digests on GitOps `main`.

This order was chosen so that privileged write authority was the last major capability added, not the first.

---

# 10. `workflow_run` fan-in

The promotion gate watches completion of the source workflows.

Conceptually:

```yaml
on:
  workflow_run:
    workflows:
      - Lint
      - Tests
      - E2E Tests
      - Security
      - Secret Scan
      - Release Images
      - Release sklearn Runtime
    types:
      - completed
```

This produces multiple promotion evaluations for one source commit.

Example:

```text
Secret Scan completes
        |
        v
Promote run A -> WAITING

Tests completes
        |
        v
Promote run B -> WAITING

Release Images completes last
        |
        v
Promote run N -> READY
```

Therefore a top-level successful `Promote to GitOps` run can simply mean the gate returned `WAITING` and exited cleanly.

Always inspect the decision and use the newest decisive run after required workflows finish.

---

# 11. Concurrency

The promotion workflow uses source-SHA-based concurrency:

```yaml
concurrency:
  group: promote-${{ github.event.workflow_run.head_sha }}
  cancel-in-progress: true
```

The purpose is to reduce overlapping evaluations for one commit.

It does not eliminate all fan-out events.

Multiple completed-workflow events were observed in practice.

---

# 12. Source SHA as the correlation key

The promotion gate must combine evidence belonging to exactly one commit.

The source SHA is the join key across:

```text
workflow runs
release image tags
promotion decision
registry digest resolution
GitOps branch name
GitOps PR title
GitOps PR body
```

The invariant is:

```text
one source SHA -> one evidence set
```

Never combine:

```text
Lint from commit A
Tests from commit B
Release from commit C
```

---

# 13. Verification-job permissions

The verification job is read-only:

```yaml
permissions:
  actions: read
  contents: read
```

It does not need GitOps write access.

It should be able to decide without possessing the credential needed to act on that decision.

---

# 14. Gate outputs

The finalized output contract is:

```yaml
outputs:
  source_sha: ${{ steps.source.outputs.sha }}
  platform_changed: ${{ steps.changes.outputs.platform_changed }}
  runtime_changed: ${{ steps.changes.outputs.runtime_changed }}
  decision: ${{ steps.gate.outputs.decision }}
```

Downstream jobs consume these outputs instead of recomputing or guessing state.

---

# 15. Build-input investigation before applicability

Before defining platform applicability, the actual build context was inspected.

The `.dockerignore` was:

```dockerignore
# More info: https://docs.docker.com/engine/reference/builder/#dockerignore-file
# Ignore everything by default and re-include only needed files
**

# Re-include Go source files (but not *_test.go)
!**/*.go
**/*_test.go

# Re-include Go module files
!go.mod
!go.sum
```

This means the Dockerfiles' `COPY . .` does not make every repository file an image input.

The effective source context is intentionally narrow.

In particular:

```text
*_test.go
```

is excluded from the image context.

Therefore test-only Go changes should still run CI but should not force a platform deployment promotion.

---

# 16. Commands used to inspect applicability

```bash
cd /mnt/data/ai-platform-operator

echo "===== DOCKERIGNORE ====="
cat .dockerignore
```

```bash
echo
echo "===== SOURCE DIRECTORIES ====="

find cmd api internal controllers pkg \
  -maxdepth 2 \
  -type f \
  2>/dev/null \
  | sort
```

```bash
echo
echo "===== TRACKED TOP-LEVEL FILES ====="

git ls-files \
  | awk 'index($0,"/")==0' \
  | sort
```

```bash
echo
echo "===== TRACKED TOP-LEVEL DIRECTORIES ====="

git ls-files \
  | awk -F/ 'NF>1 {print $1}' \
  | sort -u
```

The design rule was:

```text
do not guess deployment applicability from repository layout
inspect actual build inputs first
```

---

# 17. Final artifact applicability

## Platform domain

`platform_changed=true` when one of the following changes:

```text
non-test *.go
go.mod
go.sum
Dockerfile
Dockerfile.platform-api
.dockerignore
.github/workflows/release-images.yml
```

## Runtime domain

`runtime_changed=true` when one of the following changes:

```text
Dockerfile.sklearn-runtime
.github/workflows/release-sklearn-runtime.yml
```

## Examples

| Changed file | platform_changed | runtime_changed |
|---|---:|---:|
| `cmd/main.go` | true | false |
| `cmd/platform-api/main.go` | true | false |
| `internal/api/server.go` | true | false |
| `internal/api/routes_test.go` | false | false |
| `go.mod` | true | false |
| `go.sum` | true | false |
| `Dockerfile` | true | false |
| `Dockerfile.platform-api` | true | false |
| `.dockerignore` | true | false |
| `.github/workflows/release-images.yml` | true | false |
| `Dockerfile.sklearn-runtime` | false | true |
| `.github/workflows/release-sklearn-runtime.yml` | false | true |
| `docs/example.md` | false | false |
| `.github/workflows/promote-gitops.yml` | false | false |

---

# 18. Applicability implementation

```bash
PLATFORM_CHANGED=false
RUNTIME_CHANGED=false

while IFS= read -r file; do
  case "$file" in
    Dockerfile.sklearn-runtime|\
    .github/workflows/release-sklearn-runtime.yml)
      RUNTIME_CHANGED=true
      ;;

    go.mod|\
    go.sum|\
    Dockerfile|\
    Dockerfile.platform-api|\
    .dockerignore|\
    .github/workflows/release-images.yml)
      PLATFORM_CHANGED=true
      ;;

    *.go)
      case "$file" in
        *_test.go)
          ;;
        *)
          PLATFORM_CHANGED=true
          ;;
      esac
      ;;
  esac
done < /tmp/changed-files.txt

echo "platform_changed=${PLATFORM_CHANGED}" >> "$GITHUB_OUTPUT"
echo "runtime_changed=${RUNTIME_CHANGED}" >> "$GITHUB_OUTPUT"

echo
echo "===== APPLICABILITY ====="
echo "platform_changed=${PLATFORM_CHANGED}"
echo "runtime_changed=${RUNTIME_CHANGED}"
```

---

# 19. Required workflow construction

Common required workflows:

```bash
REQUIRED_WORKFLOWS=(
  "Lint"
  "Tests"
  "E2E Tests"
  "Security"
  "Secret Scan"
)
```

Platform release requirement:

```bash
if [[ "$PLATFORM_CHANGED" == "true" ]]; then
  REQUIRED_WORKFLOWS+=(
    "Release Images"
  )
fi
```

Runtime release requirement:

```bash
if [[ "$RUNTIME_CHANGED" == "true" ]]; then
  REQUIRED_WORKFLOWS+=(
    "Release sklearn Runtime"
  )
fi
```

This is the artifact-aware fan-in.

---

# 20. Promotion state machine

The gate has four meaningful states:

```text
NO-OP
WAITING
BLOCKED
READY
```

## NO-OP

Meaning:

```text
no deployable artifact domain changed
```

Implementation:

```bash
if [[ "$PLATFORM_CHANGED" != "true" && "$RUNTIME_CHANGED" != "true" ]]; then
  echo "decision=no-op" >> "$GITHUB_OUTPUT"

  echo "PROMOTION DECISION: NO-OP"
  echo
  echo "No deployable artifact domain changed."
  echo "No promotion action is required."

  exit 0
fi
```

## WAITING

Meaning:

```text
required evidence is missing or not complete yet
```

It exits successfully because the commit is not known to be bad; the evidence set is simply incomplete.

## BLOCKED

Meaning:

```text
at least one applicable required workflow completed unsuccessfully
```

It exits non-zero.

## READY

Meaning:

```text
all applicable required workflows for the exact source SHA succeeded
```

Only `READY` can continue toward a privileged write.

---

# 21. Workflow-run query

The gate queries runs by exact source SHA:

```bash
RUNS="$(
  gh api \
    --paginate \
    -H "Accept: application/vnd.github+json" \
    "/repos/${GH_REPO}/actions/runs?head_sha=${SOURCE_SHA}&per_page=100"
)"
```

The result selection filters by:

```text
workflow name
event == push
head_branch == main
```

Conceptually:

```jq
[
  .workflow_runs[]
  | select(
      .name == $workflow
      and .event == "push"
      and .head_branch == "main"
    )
]
| sort_by(.created_at)
| reverse
| .[0]
```

A PR run does not substitute for the post-merge `main` run used for deployment promotion.

---

# 22. Initial read-only gate — PR #5

The first central promotion gate was intentionally read-only.

Source PR:

```text
#5
```

Merged source commit:

```text
6405d43a12f5e7449dceba71af9929ff383fdb12
```

At this stage the workflow explicitly did **not**:

```text
mint a GitOps token
clone GitOps
push a branch
create a pull request
```

This made it possible to validate decision logic independently from mutation.

The gate reached `READY` for the source commit after required workflows completed.

Observed promotion fan-out run IDs included:

```text
32600909329
32601013114
32601015536
32601049415
32601086180
32601154061
```

The final decisive read-only run used in validation was:

```text
32601154061
```

---

# 23. Negative replay

The earlier trusted-runtime commit was:

```text
6aa37e1fdc4f465777a891d632e19b53f80d6b86
```

For that commit:

```text
Lint                     success
Tests                    success
E2E Tests                success
Security                 success
Secret Scan              success
Release Images           success
Release sklearn Runtime  failure
```

The centralized gate replay produced:

```text
PROMOTION DECISION: BLOCKED
```

This proved the gate could represent the exact policy that the old architecture lacked.

No scanner was weakened to make the test pass.

---

# 24. Remove the old GitOps writer from `Release Images`

The old `update-gitops` job was deleted from:

```text
.github/workflows/release-images.yml
```

The following capabilities were removed from that workflow:

```text
GitHub App token creation
GitOps checkout
operator digest update
API digest update
GitOps validation
bot identity
branch creation
push
gh pr create
```

The following release capabilities remained:

```text
build operator
build API
Trivy
SPDX SBOM
GHCR push
provenance attestation
SBOM attestation
```

Verification command:

```bash
grep -nE \
 'update-gitops|Create GitHub App token|GITOPS_APP|ai-platform-gitops|gh pr create|automation/image-' \
 .github/workflows/release-images.yml
```

Expected and observed:

```text
no output
```

This created the safe intermediate state:

```text
release workflows produce artifacts
central gate evaluates
nobody automatically writes GitOps
```

---

# 25. PR #7 — artifact-aware gate and NO-OP

Source PR:

```text
#7
```

This change added:

```text
platform_changed
runtime_changed
source_sha output
decision output
NO-OP
conditional Release Images requirement
conditional Release sklearn Runtime requirement
```

The no-op test changed only:

```text
.github/workflows/promote-gitops.yml
```

Observed:

```text
platform_changed=false
runtime_changed=false
PROMOTION DECISION: NO-OP
No deployable artifact domain changed.
```

GitOps had no open PR.

That established:

```text
READY   validated
BLOCKED validated
NO-OP   validated
```

---

# 26. PR #8 — read-only platform digest resolution

Source PR:

```text
#8
```

Post-merge source `main` observed as:

```text
355cf0c
```

New job:

```yaml
resolve-platform-digests:
  name: Resolve Platform Image Digests

  needs:
    - verify-promotion-gates

  if: >
    needs.verify-promotion-gates.outputs.decision == 'ready' &&
    needs.verify-promotion-gates.outputs.platform_changed == 'true'

  permissions:
    contents: read
    packages: read
```

The job still had no GitOps write authority.

---

# 27. Source-SHA image lookup

`Release Images` publishes source-SHA tags.

The promotion job constructs:

```bash
OPERATOR_IMAGE="ghcr.io/anselem-okeke/ai-platform-operator:sha-${SOURCE_SHA}"
API_IMAGE="ghcr.io/anselem-okeke/ai-platform-api:sha-${SOURCE_SHA}"
```

The source-SHA tag is used to find the artifact belonging to the source commit.

The deployment reference is the registry digest, not the tag.

---

# 28. Digest resolution

```bash
OPERATOR_DIGEST="$(
  docker buildx imagetools inspect \
    "$OPERATOR_IMAGE" \
    --format '{{json .Manifest.Digest}}' \
  | tr -d '"'
)"

API_DIGEST="$(
  docker buildx imagetools inspect \
    "$API_IMAGE" \
    --format '{{json .Manifest.Digest}}' \
  | tr -d '"'
)"
```

The result is expected to be:

```text
sha256:<64 lowercase hexadecimal characters>
```

---

# 29. Digest validation hardening

The first draft only checked a fixed length with shell wildcard matching.

That was strengthened to a true hexadecimal format check:

```bash
if [[ ! "$OPERATOR_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid operator digest: ${OPERATOR_DIGEST}" >&2
  exit 1
fi

if [[ ! "$API_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid API digest: ${API_DIGEST}" >&2
  exit 1
fi
```

This is a fail-closed input check.

---

# 30. PR #9 — controlled digest-resolution test

A harmless comment was added to:

```text
.github/workflows/release-images.yml
```

This was intentionally platform-applicable but behavior-neutral.

Source PR:

```text
#9
```

Merge source SHA:

```text
c5da5f3724a17043c2c2929056f61b3946fccbc7
```

An early promotion run was:

```text
32609463373
```

At that time several required workflows were still running.

Observed job state:

```text
✓ Verify Promotion Gates
- Resolve Platform Image Digests
```

That was expected WAITING behavior.

A later promotion run was:

```text
32609680687
```

Observed:

```text
✓ Verify Promotion Gates
✓ Resolve Platform Image Digests

platform_changed=true
runtime_changed=false
PROMOTION DECISION: READY
```

Resolved digests:

```text
operator=sha256:d8bae792cfb00baac2081e9f2f4375f385b78c6f157684486225d600ddea3e1c
api=sha256:fb2c6df0d66d941fa0cae54f92f03b7b882f3643d377fad0d572ad749164cc12
```

At this point there was still no centralized writer.

Observed GitOps state:

```text
no open pull requests
```

This proved immutable digest resolution independently from GitOps mutation.

---

# 31. PR #10 — put GitOps write authority behind the gate

Source PR:

```text
#10
```

Merged source commit:

```text
01ab7c0690753f27f3eaa8a12944695919528bd1
```

The new centralized writer is:

```yaml
update-gitops:
  name: Create GitOps Update PR

  needs:
    - verify-promotion-gates
    - resolve-platform-digests

  if: >
    needs.verify-promotion-gates.outputs.decision == 'ready' &&
    needs.verify-promotion-gates.outputs.platform_changed == 'true' &&
    needs.resolve-platform-digests.result == 'success'

  permissions:
    contents: read
```

All three conditions are security-relevant.

---

# 32. Meaning of the writer condition

```text
decision == ready
```

means all applicable required workflows for the exact source SHA passed.

```text
platform_changed == true
```

means the operator/API GitOps writer is relevant to this source commit.

```text
resolve-platform-digests.result == success
```

means the exact release artifacts were found and validated.

If any clause is false, the writer does not run.

---

# 33. Runtime-only protection

For a runtime-only commit:

```text
platform_changed=false
runtime_changed=true
```

Even if the runtime release eventually succeeds and the gate reaches `READY`:

```text
Resolve Platform Image Digests = skipped
Create GitOps Update PR        = skipped
```

This prevents operator/API digest churn from a runtime-only source change.

A later runtime promotion target must be implemented explicitly.

---

# 34. Promotion checkpoint rename

Before the writer existed, the workflow step was called:

```text
Read-only promotion checkpoint
```

After write authority was added, that name was changed to:

```text
Promotion gate passed
```

The log header became:

```text
===== PROMOTION CHECKPOINT =====
```

Operational logs should describe the real trust boundary accurately.

---

# 35. Verify promotion inputs before creating a credential

Before the GitHub App token is minted, the writer validates:

```text
SOURCE_SHA
OPERATOR_DIGEST
API_DIGEST
```

Implementation:

```bash
if [[ ! "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid source SHA: ${SOURCE_SHA}" >&2
  exit 1
fi

if [[ ! "$OPERATOR_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid operator digest: ${OPERATOR_DIGEST}" >&2
  exit 1
fi

if [[ ! "$API_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid API digest: ${API_DIGEST}" >&2
  exit 1
fi

echo "PASS: promotion inputs are valid"
```

The order is deliberately:

```text
evaluate
resolve
validate
validate again at writer boundary
then mint privileged token
```

---

# 36. GitHub App token

```yaml
- name: Create GitHub App token
  id: app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
  with:
    client-id: ${{ vars.GITOPS_APP_CLIENT_ID }}
    private-key: ${{ secrets.GITOPS_APP_PRIVATE_KEY }}
    owner: anselem-okeke
    repositories: |
      ai-platform-gitops
    permission-contents: write
    permission-pull-requests: write
```

The token is scoped to:

```text
ai-platform-gitops
```

The requested write capabilities are:

```text
contents: write
pull-requests: write
```

The normal job token remains read-only.

---

# 37. Why use a GitHub App

The GitHub App provides:

- a machine identity distinct from a human;
- short-lived installation tokens;
- repository scoping;
- explicit permission scoping;
- easy revocation;
- audit-friendly commits and PR authorship.

The final PR author was observed as:

```text
app/ai-platform-gitops-bot
```

---

# 38. Clone GitOps

```yaml
- name: Clone GitOps repository
  uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    repository: anselem-okeke/ai-platform-gitops
    token: ${{ steps.app-token.outputs.token }}
    path: ai-platform-gitops
    ref: main
    persist-credentials: false
```

`persist-credentials: false` avoids leaving checkout credentials persisted automatically.

The push step later configures the authenticated remote explicitly.

---

# 39. Exact GitOps targets

The writer uses:

```bash
OPERATOR_FILE="platform/operator/overlays/dev/kustomization.yaml"
API_FILE="platform/api/overlays/dev/kustomization.yaml"
```

No other platform files are intended to be mutated by this writer.

---

# 40. Pre-mutation guards

```bash
grep -q \
  'newName: ghcr.io/anselem-okeke/ai-platform-operator' \
  "$OPERATOR_FILE"

grep -q \
  '^[[:space:]]*digest: sha256:' \
  "$OPERATOR_FILE"

grep -q \
  'newName: ghcr.io/anselem-okeke/ai-platform-api' \
  "$API_FILE"

grep -q \
  '^[[:space:]]*digest: sha256:' \
  "$API_FILE"
```

If the file structure changes unexpectedly, the workflow should fail rather than blindly editing unrelated text.

---

# 41. Exact digest mutation

```bash
sed -i \
  "s|^[[:space:]]*digest: sha256:.*|    digest: ${OPERATOR_DIGEST}|" \
  "$OPERATOR_FILE"

sed -i \
  "s|^[[:space:]]*digest: sha256:.*|    digest: ${API_DIGEST}|" \
  "$API_FILE"
```

The target is a digest-only GitOps mutation.

---

# 42. Kustomize render validation

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator.yaml

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api.yaml
```

A syntactically edited file is not enough.

The desired state must render.

---

# 43. Verify exact rendered images

```bash
grep -F \
  "ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}" \
  /tmp/operator.yaml

grep -F \
  "ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}" \
  /tmp/api.yaml

echo "PASS: expected immutable digests rendered"
```

This proves the Kustomize transform produced the intended final immutable image references.

---

# 44. No-change behavior

```bash
if git diff --quiet; then
  echo "changed=false" >> "$GITHUB_OUTPUT"
  echo "GitOps already references these digests."
else
  echo "changed=true" >> "$GITHUB_OUTPUT"
  echo "GitOps image update required."
fi
```

If GitOps already contains the desired digests, branch and PR creation are skipped.

---

# 45. Resolve GitHub App bot identity

```bash
BOT_ID="$(
  gh api \
    "/users/${APP_SLUG}[bot]" \
    --jq '.id'
)"
```

Then:

```bash
git config user.name "${APP_SLUG}[bot]"
git config user.email "${BOT_ID}+${APP_SLUG}[bot]@users.noreply.github.com"
```

This keeps automated Git history attributable.

---

# 46. Deterministic GitOps branch

The branch name is:

```bash
BRANCH="automation/image-${SOURCE_SHA}"
```

Final positive example:

```text
automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

This directly ties the GitOps proposal to the source commit.

---

# 47. Explicit staging

Only the intended two files are staged:

```bash
git add \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

The privileged automation does not use:

```text
git add .
git add -A
```

This is important because unrelated local/untracked files had existed during development.

---

# 48. Staged diff checks

```bash
git diff --cached --check
```

Then:

```bash
echo "=== STAGED CHANGE ==="
git diff --cached
```

The commit message is:

```bash
git commit \
  -m "chore(dev): deploy images from ${SOURCE_SHA}"
```

---

# 49. Push the automation branch

```bash
git remote set-url \
  origin \
  "https://x-access-token:${GH_TOKEN}@github.com/anselem-okeke/ai-platform-gitops.git"

git push \
  --set-upstream \
  origin \
  "$BRANCH"
```

The App token must not be echoed manually.

GitHub Actions masks secrets in normal secret contexts, but good pipeline design avoids unnecessary token exposure entirely.

---

# 50. GitOps PR body

The automated PR records:

- the source SHA;
- the operator digest;
- the API digest;
- the major gates;
- the fact that promotion was created only after `READY`;
- the fact that human approval remains before Argo CD reconciliation.

Reference body:

```markdown
Automated deployment update from:

`anselem-okeke/ai-platform-operator@${SOURCE_SHA}`

## Immutable images

- Operator:
  `ghcr.io/anselem-okeke/ai-platform-operator@${OPERATOR_DIGEST}`

- API:
  `ghcr.io/anselem-okeke/ai-platform-api@${API_DIGEST}`

## Promotion gates

- Lint
- Tests
- E2E Tests
- Security
- Secret Scan
- Release Images
- Container vulnerability gates
- SPDX SBOM generation
- Provenance attestation
- SBOM attestation
- Kustomize rendering validation

Promotion is created only after the centralized promotion gate reaches READY.

After approval and merge, Argo CD will reconcile these immutable digests into the dev cluster.
```

---

# 51. PR creation command inside the workflow

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head "$BRANCH" \
  --title "chore(dev): deploy images from ${SOURCE_SHA}" \
  --body-file /tmp/gitops-pr-body.md
```

The bot creates the PR.

The bot does not merge it.

---

# 52. Writer-enabled NO-OP safety validation

After PR `#10` merged, source `main` was:

```text
01ab7c0690753f27f3eaa8a12944695919528bd1
```

That merge only changed:

```text
.github/workflows/promote-gitops.yml
```

Promotion run:

```text
32611832878
```

Observed jobs:

```text
✓ Verify Promotion Gates
- Resolve Platform Image Digests
- Create GitOps Update PR
```

Observed decision:

```text
platform_changed=false
runtime_changed=false
PROMOTION DECISION: NO-OP
```

Observed GitOps state:

```text
no open pull requests
```

This is a critical proof:

```text
adding write authority did not make the workflow write eagerly
```

---

# 53. Final positive-path test

A harmless platform-applicable change was made again in:

```text
.github/workflows/release-images.yml
```

This exercised the complete pipeline without changing application logic.

Final source SHA:

```text
4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

The centralized writer created GitOps branch:

```text
automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

and GitOps PR:

```text
#25
```

---

# 54. Final GitOps PR diff

The PR changed exactly two files.

API:

```diff
diff --git a/platform/api/overlays/dev/kustomization.yaml b/platform/api/overlays/dev/kustomization.yaml
@@
 images:
   - name: ai-platform-api
     newName: ghcr.io/anselem-okeke/ai-platform-api
-    digest: sha256:4f736e67a60a1d80f8d918e26ff2c530ce71f28dda875ab5d926415ec658d386
+    digest: sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
```

Operator:

```diff
diff --git a/platform/operator/overlays/dev/kustomization.yaml b/platform/operator/overlays/dev/kustomization.yaml
@@
 images:
   - name: ai-platform-operator
     newName: ghcr.io/anselem-okeke/ai-platform-operator
-    digest: sha256:e8e0c4b2db8aeaa1d7f53cc42c5ecf477e0e64f94714bb82dec0f99ece4dedf8
+    digest: sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
```

No unrelated GitOps file changed.

---

# 55. GitOps PR checks

Command:

```bash
gh pr checks 25 \
  --repo anselem-okeke/ai-platform-gitops
```

Observed summary:

```text
All checks were successful
0 cancelled, 0 failing, 4 successful, 0 skipped, and 0 pending checks
```

Successful checks:

```text
GitGuardian Security Checks
Secret Scan/Gitleaks (push)
Secret Scan/Gitleaks (pull_request)
Validate GitOps/Validate GitOps Manifests (pull_request)
```

The source promotion gate does not replace GitOps-repository controls.

The destination repository validates the proposal again.

---

# 56. GitOps PR identity and mergeability

Command:

```bash
gh pr view 25 \
  --repo anselem-okeke/ai-platform-gitops \
  --json title,headRefName,baseRefName,author,mergeable,reviewDecision,statusCheckRollup
```

Observed key values:

```text
author.is_bot = true
author.login = app/ai-platform-gitops-bot
baseRefName = main
headRefName = automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
mergeable = MERGEABLE
```

This confirms the expected automation identity and branch traceability.

---

# 57. Human merge

The PR was merged manually:

```bash
gh pr merge 25 \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

Observed:

```text
✓ Merged pull request #25
```

The control sequence is therefore:

```text
automation verifies
automation proposes
GitOps CI verifies
human approves
Git main changes
Argo CD reconciles
```

---

# 58. Final GitOps merge state

Commands:

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main

git log -1 --oneline
```

Observed:

```text
fcdf138 (HEAD -> main, origin/main, origin/HEAD) Merge pull request #25 from anselem-okeke/automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

Final digest check:

```bash
grep -n 'digest:' \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Observed:

```text
platform/operator/overlays/dev/kustomization.yaml:10:    digest: sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
platform/api/overlays/dev/kustomization.yaml:10:    digest: sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
```

---

# 59. Final proof matrix

```text
READY gate                          [x]
BLOCKED gate                        [x]
WAITING behavior                    [x]
NO-OP behavior                      [x]

Platform applicability              [x]
Runtime applicability               [x]

Old Release Images GitOps writer    [x] removed
Centralized digest resolution       [x]
Exact sha256 validation             [x]
Promotion input validation          [x]
GitHub App authority isolated       [x]

NO-OP creates no PR                 [x]
Platform READY creates PR           [x]

Only operator digest changed        [x]
Only API digest changed             [x]
No unrelated GitOps mutation        [x]

GitOps security checks pass         [x]
GitOps manifest validation passes   [x]
Bot identity validated              [x]
Human merge succeeds                [x]
Immutable digests land on main      [x]
```

---

# 60. Day-2 operator command sequence

## Source repository

```bash
cd /mnt/data/ai-platform-operator

git switch main
git pull --ff-only origin main

SOURCE_SHA="$(git rev-parse HEAD)"
echo "$SOURCE_SHA"
```

List workflows for the exact commit:

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --commit "$SOURCE_SHA" \
  --limit 30
```

Get newest promotion run:

```bash
PROMOTION_RUN_ID="$(
  gh run list \
    --repo anselem-okeke/ai-platform-operator \
    --workflow promote-gitops.yml \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId'
)"

echo "$PROMOTION_RUN_ID"
```

Inspect jobs:

```bash
gh run view "$PROMOTION_RUN_ID" \
  --repo anselem-okeke/ai-platform-operator
```

Inspect decisive logs:

```bash
gh run view "$PROMOTION_RUN_ID" \
  --repo anselem-okeke/ai-platform-operator \
  --log \
  | grep -E \
    'platform_changed=|runtime_changed=|PROMOTION DECISION|IMMUTABLE DIGESTS|PASS: promotion inputs are valid|GitOps image update required|PASS: expected immutable digests rendered'
```

## GitOps repository

List proposals:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --state open
```

Review a proposal:

```bash
GITOPS_PR=<NUMBER>

gh pr diff "$GITOPS_PR" \
  --repo anselem-okeke/ai-platform-gitops
```

Check GitOps CI:

```bash
gh pr checks "$GITOPS_PR" \
  --repo anselem-okeke/ai-platform-gitops
```

Review metadata:

```bash
gh pr view "$GITOPS_PR" \
  --repo anselem-okeke/ai-platform-gitops \
  --json title,headRefName,baseRefName,author,mergeable,reviewDecision,statusCheckRollup
```

Human merge:

```bash
gh pr merge "$GITOPS_PR" \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

Post-merge:

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main

git log -1 --oneline

grep -n 'digest:' \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

---

# 61. Failure modes

## 61.1 Promotion run completes but digest job is skipped

**Symptom**

```text
✓ Verify Promotion Gates
- Resolve Platform Image Digests
```

**Likely cause**

An early `workflow_run` event fired while one or more required workflows were still running.

**Diagnosis**

```bash
gh run list \
  --repo anselem-okeke/ai-platform-operator \
  --commit "$SOURCE_SHA" \
  --limit 30
```

**Fix**

Wait for required workflows, then fetch the newest promotion run again.

Do not edit the gate to make an early run promote.

## 61.2 Gate returns BLOCKED

**Meaning**

At least one applicable required workflow failed, was cancelled, timed out, required action, or otherwise completed unsuccessfully.

**Correct response**

Fix the failing workflow.

Do not remove the workflow from the gate merely to unblock release.

Do not weaken Trivy from exit code `1` to `0`.

## 61.3 Gate returns NO-OP unexpectedly

Inspect the exact changed files for the source SHA.

Confirm whether the changed file is a real platform or runtime build input.

Do not broaden applicability merely to force a deployment.

## 61.4 Release Images still runs on docs-only commits

At this stage, `Release Images` still has a broad `main` trigger.

That can cause unnecessary builds.

The centralized gate prevents irrelevant deployment because `platform_changed=false`.

This is currently an efficiency issue, not a promotion-authority bypass.

## 61.5 Registry tag cannot be resolved

Possible causes:

- release still running;
- release failed;
- wrong source SHA;
- tag scheme changed;
- package permission issue;
- image push failed.

Do not substitute `latest`.

The source-SHA tag is the commit correlation mechanism.

## 61.6 Invalid digest

If a digest does not match:

```text
^sha256:[0-9a-f]{64}$
```

stop.

Do not write GitOps.

## 61.7 Promotion input validation fails

The GitOps writer has rejected its upstream inputs before credential creation.

This is intentional fail-closed behavior.

Investigate job-output wiring.

## 61.8 GitHub App token creation fails

Check:

```text
GITOPS_APP_CLIENT_ID
GITOPS_APP_PRIVATE_KEY
GitHub App installation on ai-platform-gitops
Contents permission
Pull requests permission
```

Do not replace the App with a broad long-lived human PAT as a shortcut.

## 61.9 GitOps checkout fails

Verify:

```text
owner = anselem-okeke
repository = ai-platform-gitops
App token creation succeeded
App installation includes repository
```

## 61.10 Pre-mutation grep fails

The GitOps file structure has changed.

Inspect the current overlay manually.

Do not delete the guard without understanding the new structure.

## 61.11 Kustomize render fails

Reproduce locally:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize platform/operator/overlays/dev >/tmp/operator.yaml
kubectl kustomize platform/api/overlays/dev >/tmp/api.yaml
```

Fix renderability before promotion.

## 61.12 Exact image absent from rendered YAML

The Kustomize image transform did not produce the expected immutable reference.

Stop the proposal.

Inspect `name`, `newName`, and `digest` semantics.

## 61.13 GitOps already has the digest

Message:

```text
GitOps already references these digests.
```

This is a content-level no-op.

Branch/commit/PR creation should skip.

## 61.14 Automation branch already exists

The deterministic branch name is excellent for traceability but retries can encounter an existing branch.

Future hardening can explicitly detect:

```text
existing branch
existing open PR
already merged proposal
```

Do not abandon source-SHA traceability.

## 61.15 GitOps PR contains unexpected files

Do not merge.

Run:

```bash
gh pr diff "$GITOPS_PR" \
  --repo anselem-okeke/ai-platform-gitops
```

Expected platform files are only:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

## 61.16 GitOps CI fails

Do not merge.

Investigate:

```text
GitGuardian
Gitleaks
Validate GitOps
```

The destination repository is allowed to reject the proposal.

## 61.17 Old writer reappears

Audit:

```bash
cd /mnt/data/ai-platform-operator

grep -nE \
 'update-gitops|Create GitHub App token|GITOPS_APP|ai-platform-gitops|gh pr create|automation/image-' \
 .github/workflows/release-images.yml
```

Expected:

```text
no output
```

There should be one clear platform promotion authority.

---

# 62. Recovery and rollback

## Close an unwanted GitOps PR

```bash
gh pr close <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --comment "Closing automated promotion because the source/promotion state is not approved."
```

## Delete an unwanted automation branch

```bash
git push origin \
  --delete \
  automation/image-<SOURCE_SHA>
```

## Inspect GitOps history

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main

git log --oneline --decorate -20
```

## Revert a bad merged GitOps promotion

Create a branch:

```bash
git switch -c revert/bad-image-promotion
```

Revert the merge commit:

```bash
git revert -m 1 <MERGE_COMMIT>
```

Push and open a reviewed PR.

Prefer Git history over imperative cluster mutation.

## Revert the promotion workflow itself

```bash
cd /mnt/data/ai-platform-operator

git switch main
git pull --ff-only origin main

git log --oneline -- .github/workflows/promote-gitops.yml
```

Create a normal revert branch and use the source repository's standard PR checks.

---

# 63. Security rationale

## 63.1 Visibility versus enforcement

A scanner must be part of the release authorization decision to become an enforcement control.

## 63.2 Exact source SHA

Every required workflow result must belong to the same source commit.

## 63.3 Artifact applicability

A release gate should require only artifacts relevant to the commit, while still enforcing common source-quality/security checks.

## 63.4 Tags locate; digests deploy

The source-SHA tag is a lookup key.

The digest is the immutable deployment identity.

## 63.5 Late credential creation

The GitOps write token is created only after:

```text
READY
platform_changed=true
digest resolution success
source SHA validation
digest validation
```

## 63.6 Repository-scoped App token

The writer requests access only to:

```text
ai-platform-gitops
```

## 63.7 Narrow mutation

Only the two platform overlay Kustomizations are staged.

## 63.8 Rendered-intent validation

The writer verifies the exact final image references, not just file syntax.

## 63.9 Automation proposes; humans approve

PR creation is automated.

PR merge remains a human action.

## 63.10 Source CI and GitOps CI are both required

The source gate authorizes a proposal.

The GitOps repository validates the proposal in its own context.

---

# 64. State examples

## Docs-only

```text
platform_changed=false
runtime_changed=false
NO-OP
digest job skipped
writer skipped
```

## Promotion-workflow-only

```text
changed: .github/workflows/promote-gitops.yml
platform_changed=false
runtime_changed=false
NO-OP
```

## Platform code

```text
changed: internal/controller/modelservice_controller.go
platform_changed=true
runtime_changed=false
Release Images required
READY only after all applicable gates pass
platform writer eligible
```

## Test-only Go

```text
changed: internal/controller/modelservice_controller_test.go
platform_changed=false
runtime_changed=false
common CI still runs
NO-OP for deployment
```

## Runtime-only

```text
changed: Dockerfile.sklearn-runtime
platform_changed=false
runtime_changed=true
Release sklearn Runtime required
platform digest job skipped
operator/API writer skipped
```

## Platform + runtime

```text
platform_changed=true
runtime_changed=true
Release Images required
Release sklearn Runtime required
failure of either applicable release prevents READY
```

## Incomplete evidence

```text
one required workflow still running
WAITING
no promotion
```

## Applicable failure

```text
required workflow failure
BLOCKED
no promotion
```

---

# 65. Operator checklists

## Before editing source workflows

- [ ] correct repository path confirmed;
- [ ] current branch confirmed;
- [ ] `main` updated with `--ff-only`;
- [ ] untracked files reviewed;
- [ ] no `git add .`;
- [ ] no `git add -A`;
- [ ] exact workflow names verified;
- [ ] GitOps target files understood;
- [ ] rollback path understood.

## After source merge

- [ ] capture full `SOURCE_SHA`;
- [ ] list all runs for `SOURCE_SHA`;
- [ ] wait for applicable required workflows;
- [ ] fetch newest promotion run;
- [ ] inspect applicability;
- [ ] inspect decision;
- [ ] inspect downstream jobs.

## Before GitOps merge

- [ ] PR author is expected bot;
- [ ] base is `main`;
- [ ] head branch contains expected source SHA;
- [ ] only expected files changed;
- [ ] both image references are digest-pinned;
- [ ] GitOps checks all pass;
- [ ] PR is mergeable;
- [ ] human reviewer accepts the desired-state change.

---

# 66. What is proven versus not proven

## Proven

- central gate can return `READY`;
- central gate can return `BLOCKED`;
- early fan-out can produce `WAITING` without writing;
- non-deployable changes produce `NO-OP`;
- platform and runtime applicability are separate;
- old `Release Images` GitOps writer was removed;
- exact platform digests can be resolved by source SHA;
- malformed digests are rejected;
- writer validates inputs before credential minting;
- GitHub App creates the GitOps proposal;
- only two intended GitOps files changed in the positive test;
- GitOps CI passed;
- human merge succeeded;
- expected immutable digests landed on GitOps `main`.

## Not proven by this work

- sklearn runtime release success;
- runtime GitOps promotion;
- runtime Sigstore trust extension;
- `ClusterServingRuntime` deployment;
- model artifact integrity;
- S3/object-store model loading;
- first real KServe inference;
- destructive whole-resource Argo prune behavior.

---

# 67. Current limitations

1. `Release Images` still has a broad `main` trigger, so irrelevant commits can still cause unnecessary builds. The promotion gate prevents irrelevant deployment.
2. Deterministic branch retry/idempotency can be hardened further.
3. Runtime GitOps promotion is not yet implemented.
4. The sklearn runtime remains blocked by Trivy findings.
5. Runtime Sigstore scope has not yet been extended.
6. `ClusterServingRuntime` is not yet GitOps-managed.
7. Object storage and first-model serving remain later Phase 8 work.

---

# 68. Next technical step after this runbook

The next chain is:

```text
Trusted sklearn wrapper
      |
      v
Trivy HIGH/CRITICAL gate   <-- current blocker
      |
      v
SBOM + provenance
      |
      v
immutable runtime digest
      |
      v
Sigstore trust extension
      |
      v
ClusterServingRuntime
      |
      v
KServe workload
```

The central platform promotion work documented here is complete before returning to that runtime problem.

---

# 69. Official references

- GitHub Actions workflow syntax: https://docs.github.com/actions/writing-workflows/workflow-syntax-for-github-actions
- `workflow_run`: https://docs.github.com/actions/using-workflows/events-that-trigger-workflows#workflow_run
- Job outputs: https://docs.github.com/actions/using-jobs/defining-outputs-for-jobs
- `GITHUB_TOKEN` permissions: https://docs.github.com/actions/security-guides/automatic-token-authentication
- GitHub App token action: https://github.com/actions/create-github-app-token
- GitHub CLI PR manual: https://cli.github.com/manual/gh_pr
- Docker Buildx `imagetools inspect`: https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/
- GitHub Artifact Attestations: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- Kustomize: https://kubectl.docs.kubernetes.io/references/kustomize/
- Argo CD: https://argo-cd.readthedocs.io/
- SPDX: https://spdx.dev/
- Trivy: https://trivy.dev/

---

# 70. Final state statement

The operator/API delivery path now has centralized artifact-aware promotion enforcement.

The final proven chain is:

```text
Source commit
  -> common quality/security workflows
  -> applicable platform release
  -> central source-SHA gate
  -> READY
  -> exact registry digest resolution
  -> source/digest validation
  -> scoped GitHub App credential
  -> exact GitOps digest mutation
  -> Kustomize render validation
  -> automated GitOps PR
  -> GitOps security/validation checks
  -> human merge
  -> GitOps main
  -> Argo CD reconciliation
```

Final source SHA exercised through the complete positive path:

```text
4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

Final GitOps PR:

```text
#25
```

Final GitOps merge:

```text
fcdf138
```

Final operator image:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
```

Final API image:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
```

The structural flaw that allowed an independent failed security workflow to coexist with an automated platform GitOps proposal is closed for the operator/API promotion path.

---

# Appendix A — PR and commit ledger

```text
Runtime trusted-image source PR:
#4

Runtime trusted-image merge commit:
6aa37e1fdc4f465777a891d632e19b53f80d6b86

Initial central gate PR:
#5

Initial central gate merge commit:
6405d43a12f5e7449dceba71af9929ff383fdb12

Accidental old-path GitOps PR:
#24

Artifact applicability PR:
#7

Digest resolution PR:
#8

Observed source main after PR #8:
355cf0c

Controlled digest test PR:
#9

Controlled digest test source SHA:
c5da5f3724a17043c2c2929056f61b3946fccbc7

Centralized writer PR:
#10

Centralized writer merge source SHA:
01ab7c0690753f27f3eaa8a12944695919528bd1

Final positive source SHA:
4cd75ccb351114112257a03b3a43c7d33fcba3c7

Final GitOps branch:
automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7

Final GitOps PR:
#25

Final GitOps merge:
fcdf138
```

# Appendix B — workflow-run ledger

```text
Initial read-only final READY run:
32601154061

Early digest-test run:
32609463373

Final digest READY run:
32609680687

Writer-enabled NO-OP run:
32611832878
```

Additional observed promotion fan-out runs during initial validation:

```text
32600909329
32601013114
32601015536
32601049415
32601086180
32601154061
```

# Appendix C — digest ledger

## Digest-resolution controlled test

Source SHA:

```text
c5da5f3724a17043c2c2929056f61b3946fccbc7
```

Resolved operator:

```text
sha256:d8bae792cfb00baac2081e9f2f4375f385b78c6f157684486225d600ddea3e1c
```

Resolved API:

```text
sha256:fb2c6df0d66d941fa0cae54f92f03b7b882f3643d377fad0d572ad749164cc12
```

## Final positive GitOps promotion

Source SHA:

```text
4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

Operator:

```text
sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
```

API:

```text
sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
```

# Appendix D — evidence discipline

When extending this runbook later:

1. prefer exact repository output over memory;
2. record full SHA when captured;
3. if only a short SHA was captured, label it short;
4. do not invent missing PR numbers or commits;
5. distinguish designed from validated;
6. distinguish observed from assumed;
7. distinguish source CI success from GitOps CI success;
8. distinguish PR creation from PR merge;
9. distinguish GitOps merge from Argo reconciliation;
10. distinguish container-image trust from model-artifact trust.

---

End of core runbook.

# Appendix E — Deep reconstruction notes

## E.1 Workflow identity

The gate depends on exact workflow names. Renaming a watched workflow without updating the gate can turn a valid run into a logical missing result.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.2 Main-branch evidence

Deployment promotion consumes post-merge push evidence from `main`, not an arbitrary pull-request run.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.3 Source SHA

The 40-character commit SHA is the immutable identity of the source state and the correlation key for every later step.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.4 Changed-file detection

Applicability must be computed from the exact commit change set, not from a PR title or an operator guess.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.5 Dockerignore

The effective container build context determines whether a file can influence the produced artifact.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.6 Test-only Go files

Because `*_test.go` is excluded from the image context, a test-only source change should not force an image deployment.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.7 Release Images

This workflow remains responsible for producing and attesting platform images but no longer owns GitOps mutation.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.8 Runtime release

The sklearn release is a separate artifact domain and is required only for runtime-applicable commits.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.9 NO-OP

A commit can be fully valid while having nothing deployable to promote.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.10 WAITING

The evidence set can be incomplete without being negative; this is why WAITING is distinct from BLOCKED.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.11 BLOCKED

A completed unsuccessful applicable workflow must fail closed and prevent downstream write jobs.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.12 READY

READY means the policy evidence is sufficient to continue. It does not itself mean the cluster has been changed.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.13 Source-SHA tag

`sha-${SOURCE_SHA}` is a registry lookup handle that connects a source commit to the release produced for that commit.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.14 Immutable digest

The `sha256:` registry digest is the content-addressed image identity that belongs in GitOps.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.15 Digest regex

The regular expression protects the mutation boundary from malformed or unexpected registry output.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.16 Job outputs

Explicit outputs define the data contract from the verification job to digest resolution and from digest resolution to the writer.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.17 packages read

Digest resolution needs registry read access but should not receive repository write privileges.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.18 GitHub App

The App provides a short-lived automation identity rather than a long-lived human token.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.19 App scope

The App token is constrained to `ai-platform-gitops` and the specific write permissions needed for branch/PR operations.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.20 persist-credentials false

The checkout action does not leave a credential automatically persisted for later Git commands.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.21 Pre-mutation grep

The writer verifies that the target files still have the expected image structure before changing them.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.22 Kustomize render

A syntactically edited Kustomization must still render into valid desired state.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.23 Rendered-image verification

The exact digest-pinned image is grepped from rendered YAML, proving that the transform created the intended deployment reference.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.24 git diff quiet

If desired state already equals the resolved release, the writer avoids creating a redundant proposal.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.25 Bot identity

Git history and PR metadata clearly distinguish automation from human authors.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.26 Deterministic branch

Embedding the source SHA in the branch name makes later audit and troubleshooting direct.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.27 Explicit staging

Only the two platform overlay files are eligible for commit in the writer.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.28 Cached diff check

Whitespace and staged-diff issues are detected before a privileged automation commit is pushed.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.29 GitOps PR

The deployment transition is represented as a reviewable desired-state diff rather than an imperative cluster command.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.30 GitOps CI

The destination repository applies its own secret and manifest validation controls to the automated proposal.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.31 Human approval

Automation proposes a deployment state, while a human remains responsible for accepting it into GitOps main.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.32 Argo CD

After merge, the cluster reconciles the Git state, preserving GitOps as the deployment mechanism.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.33 PR #24

The accidental old-path proposal demonstrated why two independent writers must not coexist during migration.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.34 PR #25

The final proposal is the positive evidence that the centralized writer can create the exact intended GitOps diff.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

## E.35 fcdf138

This merge commit is the observed final GitOps main state after human acceptance of PR #25.

**Why it matters**

This item closes ambiguity at a specific trust boundary in the source-to-deployment chain. The architecture is intentionally explicit so one successful workflow cannot silently stand in for unrelated evidence.

**How to validate it**

Use exact source SHAs, workflow-run metadata, immutable registry digests, explicit Git diffs, and PR metadata. Do not infer the result from a green top-level status alone.

**Failure policy**

Stop before the next privilege boundary. Preserve audit history and fix the failed assumption instead of bypassing the control.

**Recovery principle**

Prefer a reviewed Git change or revert over an imperative deployment shortcut. Keep source, artifact, GitOps, and cluster state traceable.

# Appendix F — Definition of Done

- [x] All required workflow identities are explicit.
- [x] Every decision is correlated to one exact source SHA.
- [x] Platform and runtime applicability are independent.
- [x] NO-OP is emitted for non-deployable changes.
- [x] WAITING prevents premature downstream work.
- [x] BLOCKED prevents promotion after applicable failure.
- [x] READY is observed only after all applicable success.
- [x] The old release-images GitOps writer is absent.
- [x] Release Images retains build, scan, SBOM, push, and attest responsibilities.
- [x] Platform digests are resolved from source-SHA tags.
- [x] Digests are validated as lowercase SHA-256.
- [x] Writer inputs are revalidated before privileged token minting.
- [x] The GitHub App token is scoped to the GitOps repository.
- [x] The writer changes only the two dev overlay digest fields.
- [x] Both overlays render through Kustomize.
- [x] Rendered manifests contain the exact expected digests.
- [x] The automation stages only intended files.
- [x] The automation branch contains the source SHA.
- [x] The automated PR is authored by the GitHub App bot.
- [x] GitOps CI succeeds before merge.
- [x] Human approval remains before desired state changes.
- [x] Final GitOps main contains the expected immutable digests.

# Appendix G — Handoff summary

A new engineer taking over from this point should treat the centralized platform promotion path as complete and validated. The next technical blocker is the sklearn runtime image vulnerability gate. Do not reopen or weaken the central promotion controls merely to make the runtime release succeed. Runtime image trust, runtime GitOps state, and model artifact integrity remain separate future trust boundaries.

# 72. The complete connection: source SHA → release artifact → digest → GitOps PR

This section is the conceptual center of the runbook.

The most important idea is that the **same source commit SHA is carried through every major stage**. It is the correlation key that lets us prove that the GitOps change came from the exact source commit whose workflows passed.

The chain is:

```text
Git source commit
      |
      | SOURCE_SHA
      v
GitHub Actions workflows
      |
      | all required runs queried by the same SHA
      v
Central promotion decision
      |
      | READY only if all applicable workflows for that SHA succeeded
      v
Release Images produced tags:
  ghcr.io/.../ai-platform-operator:sha-<SOURCE_SHA>
  ghcr.io/.../ai-platform-api:sha-<SOURCE_SHA>
      |
      | registry lookup
      v
Resolve immutable digests:
  operator -> sha256:<digest>
  api      -> sha256:<digest>
      |
      | validated job outputs
      v
GitOps writer
      |
      | branch contains SOURCE_SHA
      v
automation/image-<SOURCE_SHA>
      |
      | exactly two digest substitutions
      v
GitOps PR
      |
      | title/body also contain SOURCE_SHA
      v
Human merge
      |
      v
GitOps main
      |
      v
Argo CD deploys exact immutable digests
```

## 72.1 Why the source SHA is the anchor

A Git commit SHA such as:

```text
4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

identifies one exact source-tree state.

The promotion workflow uses that SHA for several different jobs:

1. it determines which workflow runs belong to the same source state;
2. it identifies the release tag created from that source state;
3. it appears in the GitOps automation branch;
4. it appears in the GitOps PR title/body;
5. it gives the operator a direct way to trace GitOps back to source.

The important rule is:

```text
never promote based on "latest successful workflow"
promote based on "all required successful workflows for this exact SHA"
```

This avoids mixing evidence from different commits.

## 72.2 How `workflow_run.head_sha` connects the workflows

Each watched GitHub Actions workflow completion contains:

```text
github.event.workflow_run.head_sha
```

For the final positive-path source commit that value was:

```text
4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

The gate does not ask:

```text
"Did Tests pass recently?"
```

It asks:

```text
"Did Tests pass for 4cd75ccb351114112257a03b3a43c7d33fcba3c7?"
```

It asks the same question for:

```text
Lint
Tests
E2E Tests
Security
Secret Scan
Release Images
```

and, when applicable:

```text
Release sklearn Runtime
```

This is why the source SHA is the correlation boundary.

## 72.3 Why the release workflow uses `sha-${GITHUB_SHA}`

The release workflow publishes source-correlated tags.

Conceptually:

```bash
echo "tag=sha-${GITHUB_SHA}" >> "$GITHUB_OUTPUT"
```

For the final positive source SHA, the expected lookup tag is:

```text
sha-4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

So the promotion workflow knows exactly which registry artifact corresponds to the source commit it just authorized.

The operator image lookup becomes:

```text
ghcr.io/anselem-okeke/ai-platform-operator:sha-<EXAMPLE_COMMIT_SHA>
```

The API image lookup becomes:

```text
ghcr.io/anselem-okeke/ai-platform-api:sha-<EXAMPLE_COMMIT_SHA>
```

This tag is the bridge between:

```text
source identity
```

and:

```text
registry artifact
```

## 72.4 Why the source-SHA tag is not enough for GitOps

A tag is useful for lookup, but GitOps should not deploy a tag.

The workflow therefore resolves:

```text
repository:sha-<SOURCE_SHA>
```

into:

```text
repository@sha256:<digest>
```

The final GitOps state used:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
```

and:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
```

The distinction is:

```text
source-SHA tag = correlation handle
registry digest = immutable deployment identity
```

That is one of the most important concepts in the design.

## 72.5 Exact digest resolution

The job builds the source-correlated registry references:

```bash
OPERATOR_IMAGE="ghcr.io/anselem-okeke/ai-platform-operator:sha-${SOURCE_SHA}"
API_IMAGE="ghcr.io/anselem-okeke/ai-platform-api:sha-${SOURCE_SHA}"
```

Then:

```bash
OPERATOR_DIGEST="$(
  docker buildx imagetools inspect \
    "$OPERATOR_IMAGE" \
    --format '{{json .Manifest.Digest}}' \
  | tr -d '"'
)"
```

and:

```bash
API_DIGEST="$(
  docker buildx imagetools inspect \
    "$API_IMAGE" \
    --format '{{json .Manifest.Digest}}' \
  | tr -d '"'
)"
```

At this point the workflow has converted:

```text
source commit
```

into:

```text
exact immutable artifact identity
```

## 72.6 Why the digest is validated before GitOps

The writer refuses to consume malformed outputs.

Expected format:

```text
sha256:<64 lowercase hex characters>
```

Validation:

```bash
if [[ ! "$OPERATOR_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  exit 1
fi
```

and the same for API.

This means malformed registry output cannot flow silently into GitOps.

## 72.7 Why digest resolution is its own job

Separating digest resolution from the GitOps writer gives a clean privilege model:

```text
Verify Promotion Gates
  permissions:
    actions: read
    contents: read

Resolve Platform Image Digests
  permissions:
    contents: read
    packages: read

Create GitOps Update PR
  normal token:
    contents: read

GitHub App token:
    GitOps contents: write
    GitOps pull requests: write
```

The writer only receives privileged credentials after the earlier read-only stages succeed.

## 72.8 How the outputs pass between jobs

The gate exports:

```yaml
source_sha: ...
platform_changed: ...
runtime_changed: ...
decision: ...
```

The digest job exports:

```yaml
operator_digest: ...
api_digest: ...
```

The writer consumes them with:

```yaml
needs.verify-promotion-gates.outputs.source_sha
needs.resolve-platform-digests.outputs.operator_digest
needs.resolve-platform-digests.outputs.api_digest
```

This is how data moves from one job to another without recomputing or guessing.

## 72.9 Why the writer validates the same values again

Immediately before privileged token creation, the writer checks:

```text
SOURCE_SHA
OPERATOR_DIGEST
API_DIGEST
```

again.

The writer treats its inputs as untrusted until validated at the mutation boundary.

The sequence is:

```text
Gate
  |
  v
Resolve
  |
  v
Validate
  |
  v
Export outputs
  |
  v
Writer receives outputs
  |
  v
Validate again
  |
  v
Mint write token
```

This is defense in depth.

## 72.10 How the GitHub App connects source automation to GitOps

The source repo does not directly own GitOps credentials permanently.

Instead, the writer creates a short-lived GitHub App token scoped to:

```text
anselem-okeke/ai-platform-gitops
```

with:

```text
contents: write
pull-requests: write
```

That token is then used to:

```text
clone GitOps
push the automation branch
open the GitOps PR
```

The final PR confirmed the machine identity:

```text
app/ai-platform-gitops-bot
```

## 72.11 Why the GitOps branch includes the source SHA

The branch format is:

```text
automation/image-${SOURCE_SHA}
```

For the final test:

```text
automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
```

This means someone investigating GitOps months later can read the branch/PR and immediately know:

```text
which source commit caused this deployment proposal?
```

## 72.12 How the source SHA appears in the GitOps PR

The automated commit message is:

```text
chore(dev): deploy images from <SOURCE_SHA>
```

The PR title is the same pattern.

The PR body records:

```text
source SHA
operator digest
API digest
promotion gates
```

This creates a human-readable audit chain:

```text
GitOps PR
  -> source commit
  -> source workflows
  -> released images
```

## 72.13 Why only two GitOps files are changed

The platform writer only targets:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

It stages those two files explicitly.

It does not use:

```bash
git add .
```

The final PR proved that only those two digest fields changed.

## 72.14 How Kustomize connects the changed digest to the deployed manifest

The GitOps overlays contain image transforms.

Example:

```yaml
images:
  - name: ai-platform-operator
    newName: ghcr.io/anselem-okeke/ai-platform-operator
    digest: sha256:...
```

After updating the digest, the workflow renders:

```bash
kubectl kustomize platform/operator/overlays/dev
```

and then checks that the final rendered YAML contains:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<expected digest>
```

So the connection is not merely:

```text
changed YAML file
```

It is proven as:

```text
changed Kustomization
  -> rendered Kubernetes manifest
  -> exact expected immutable image
```

## 72.15 Why the GitOps PR is the deployment handoff

The source workflow does not deploy directly.

It stops at:

```text
GitOps PR
```

The PR is the handoff between:

```text
software supply chain
```

and:

```text
deployment desired state
```

Once the PR is human-approved and merged:

```text
GitOps main contains the new digests
```

Then Argo CD sees Git as desired state and reconciles the cluster.

## 72.16 Final trace of the real positive test

The actual final chain was:

```text
Source commit
4cd75ccb351114112257a03b3a43c7d33fcba3c7
        |
        v
all applicable source workflows pass
        |
        v
Promote to GitOps = READY
        |
        v
operator tag
ghcr.io/anselem-okeke/ai-platform-operator:sha-4cd75ccb...
        |
        v
operator digest
sha256:5a1532aeb3a413d4af3ab204405ad7ee51185c6545f3acaf10144402d6e80fe4
        |
        v
API tag
ghcr.io/anselem-okeke/ai-platform-api:sha-4cd75ccb...
        |
        v
API digest
sha256:77baf2d622c12304f40e38f5fe9c7227d6ca5e013807e8ca8ae1d9ea3e1189dd
        |
        v
GitOps branch
automation/image-4cd75ccb351114112257a03b3a43c7d33fcba3c7
        |
        v
GitOps PR #25
        |
        v
exactly two overlay digest changes
        |
        v
GitOps CI passes
        |
        v
human merge
        |
        v
GitOps main
fcdf138
```

That is the connection from source code to GitOps desired state.

# 73. The implementation sequence we actually followed

This section describes the work in chronological order rather than as a final architecture.

## 73.1 We first discovered the enforcement gap

We saw that security workflows and release workflows were independent.

The core question was:

```text
If one required security workflow fails, what actually prevents release promotion?
```

The answer was:

```text
nothing in the old GitOps writer dependency graph
```

## 73.2 We introduced a central gate without write access

The first gate could only:

```text
read workflow state
detect source SHA
evaluate results
print a decision
```

This let us prove the logic before moving credentials.

## 73.3 We tested READY

A commit where common workflows succeeded reached:

```text
READY
```

while the workflow was still read-only.

## 73.4 We replayed a known failed runtime commit

The runtime release failure caused:

```text
BLOCKED
```

This proved the centralized design understood applicable failure.

## 73.5 We discovered old GitOps PR #24

Even though the new gate was read-only, GitOps PR `#24` appeared.

That told us:

```text
the old Release Images writer still existed
```

We closed the PR and removed that writer.

## 73.6 We created a safe intermediate state

For a short period:

```text
release workflows produced artifacts
central gate evaluated
nobody automatically wrote GitOps
```

That was deliberate.

## 73.7 We investigated Docker build inputs

Before deciding which changes should trigger platform promotion, we inspected:

```text
.dockerignore
Dockerfiles
source directories
tracked top-level files
```

This showed that test-only Go files were not image inputs.

## 73.8 We added platform/runtime applicability

We introduced:

```text
platform_changed
runtime_changed
```

This prevented unrelated artifact promotion.

## 73.9 We added NO-OP

A change only to the promotion workflow produced:

```text
platform_changed=false
runtime_changed=false
NO-OP
```

No deployment work occurred.

## 73.10 We added read-only digest resolution

We did not immediately write GitOps.

First we proved that a READY platform commit could resolve:

```text
operator digest
API digest
```

from the exact source-SHA tags.

## 73.11 We saw an early WAITING run

The first promotion run for the digest test fired while other workflows were still running.

Digest resolution was skipped.

Later, after all required workflows completed, a newer promotion run reached READY.

This demonstrated how `workflow_run` fan-out behaves in practice.

## 73.12 We added the GitOps writer

Only after gate states and digest resolution were proven did we add:

```text
GitHub App token
GitOps clone
digest mutation
render validation
branch push
PR creation
```

## 73.13 We tested writer-enabled NO-OP

The writer itself was now present, but a workflow-only commit still resulted in:

```text
NO-OP
writer skipped
no GitOps PR
```

This proved the new privilege did not make the system eager.

## 73.14 We executed the final positive test

A harmless platform-applicable change caused:

```text
platform_changed=true
READY
digest resolution
input validation
GitHub App token
GitOps branch
GitOps PR #25
```

## 73.15 We reviewed the exact GitOps diff

The diff contained only:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Each changed only the digest.

## 73.16 GitOps CI then ran independently

The destination repository still enforced:

```text
GitGuardian
Gitleaks
Validate GitOps
```

All passed.

## 73.17 We manually merged the GitOps PR

The automation stopped at proposal.

Human approval merged PR `#25`.

## 73.18 We verified final GitOps main

GitOps main became:

```text
fcdf138
```

and contained the exact operator/API digests produced by the source promotion.

# 74. What to focus on when reading this runbook

The key concepts are not the checklists.

They are the connections:

```text
source SHA
  -> exact workflow evidence
  -> artifact applicability
  -> source-SHA registry tag
  -> immutable digest
  -> validated job output
  -> scoped GitHub App
  -> exact GitOps mutation
  -> rendered manifest
  -> GitOps PR
  -> human merge
  -> Argo CD
```

If you understand that chain, you understand the design.

