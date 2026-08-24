# Branch Protection and GitHub Rulesets

## Purpose

This document is the **reproducible implementation guide** for the GitHub branch protection and repository rulesets used by the AI Platform source and GitOps repositories.

The purpose of these controls is to ensure that CI and security checks are not merely informational.

They must actually **block unauthorized or unsafe changes from reaching protected branches**.

The implemented source protection model enforces:

```text
developer branch
    |
    v
pull request
    |
    +--> Tests
    +--> E2E
    +--> Lint
    +--> CodeQL
    +--> govulncheck
    +--> Gitleaks
    |
    v
required checks pass
    |
    v
merge to main
    |
    v
release workflow
```

The GitOps repository separately protects:

```text
GitOps branch
    |
    v
pull request
    |
    v
Validate GitOps Manifests
    |
    v
human merge
    |
    v
Argo CD reconciliation
```

A new engineer should be able to recreate the source and GitOps branch protection model from this document.

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

## GitOps Repository

```text
anselem-okeke/ai-platform-gitops
```

Local:

```text
/mnt/data/ai-platform-gitops
```

---

# 2. Why Branch Protection Is Required

GitHub Actions workflows are independent.

Without protection, this can happen:

```text
Tests         PASS
E2E           PASS
CodeQL        PASS
Gitleaks      FAIL
Release       PASS
```

GitHub Actions itself is behaving correctly.

The architecture is wrong if a failed security workflow does not block the protected branch.

Branch protection changes the delivery path to:

```text
required checks
      |
      v
merge allowed?
      |
      +--> NO  -> release cannot begin
      |
      v
main
      |
      v
release
```

This is why branch protection is part of the security architecture rather than a cosmetic GitHub setting.

---

# 3. Validated Source Ruleset

The implemented source ruleset was validated as:

```text
Name: Source Main Protection
Ruleset ID: 21120105
Target: default branch
State: active
```

The ruleset protects the source repository default branch.

Do not assume the numeric ruleset ID remains portable across repositories.

If rebuilding, the name and settings matter more than reusing the same numeric ID.

---

# 4. Source Ruleset Required Behavior

Validated behavior includes:

```text
branch deletion blocked
non-fast-forward updates blocked
pull request required
required status checks enabled
strict/up-to-date checks required
stale approvals dismissed when new commits arrive
last-push approval behavior enabled where supported
no bypass actors
current maintainer cannot bypass
```

This means direct pushes to `main` should not be the normal development path.

---

# 5. Required Source Checks

The validated required checks are:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

These names matter.

GitHub rulesets match the check context emitted by Actions.

If a workflow/job is renamed, the required-check configuration may need to be updated.

---

# 6. Solo Maintainer Constraint

The current project uses:

```text
required approving reviews: 0
```

This is intentional because the repository currently has a single maintainer.

That does **not** mean:

```text
zero-review production governance is recommended
```

It means:

```text
do not configure a rule that makes the repository impossible to merge
```

When more maintainers exist, increase independent review requirements.

---

# 7. Source Ruleset Creation — GitHub UI

Navigate:

```text
GitHub
  → anselem-okeke/ai-platform-operator
  → Settings
  → Rules
  → Rulesets
  → New ruleset
  → New branch ruleset
```

If GitHub changes the UI wording, look for:

```text
Repository Settings
Rules
Rulesets
Branch ruleset
```

---

# 8. Ruleset Name

Set:

```text
Source Main Protection
```

This provides a stable human-readable identifier.

---

# 9. Enforcement Status

Set:

```text
Active
```

Do not leave the finished ruleset in:

```text
Evaluate
Disabled
```

unless deliberately testing.

A ruleset in evaluation mode does not provide the same enforcement guarantee.

---

# 10. Target Branch

Prefer targeting the repository's:

```text
Default branch
```

rather than hardcoding a branch name if the project may rename the default branch.

If using include patterns, use:

```text
refs/heads/main
```

or GitHub's branch selector for:

```text
main
```

The validated implementation targeted the default branch.

---

# 11. Bypass List

Validated configuration:

```text
no bypass actors
```

Do not add:

```text
repository administrator
GitHub App
maintainer
organization owner
```

as bypass actors merely to make testing easier.

A bypass is a security exception.

If one is introduced later, document:

```text
who
why
when
scope
audit requirement
removal date
```

---

# 12. Restrict Deletions

Enable protection against branch deletion.

Expected behavior:

```text
main cannot be deleted
```

This protects the deployment/release source of truth.

---

# 13. Block Non-Fast-Forward Updates

Enable the rule that blocks history rewriting / force pushing.

Expected:

```text
git push --force origin main
```

must fail.

The history of the protected branch should remain auditable.

---

# 14. Require Pull Requests

Enable:

```text
Require a pull request before merging
```

This ensures normal changes reach `main` through PRs.

The rule should apply even to the repository owner unless a deliberate bypass is configured.

---

# 15. Required Approvals

Current project:

```text
Required approvals: 0
```

Reason:

```text
single maintainer
```

For a multi-maintainer environment, recommended progression:

```text
development:
1 approval

sensitive platform/security paths:
CODEOWNERS review

production:
1–2 independent approvals depending on governance
```

Do not change the current project to an impossible approval requirement without adding an independent reviewer.

---

# 16. Dismiss Stale Approvals

Enable:

```text
Dismiss stale pull request approvals when new commits are pushed
```

Why:

```text
reviewed commit A
    |
    v
new commit B pushed
    |
    v
old approval should not automatically approve B
```

Even with zero required approvals today, preserve this rule as the project grows.

---

# 17. Require Approval of Most Recent Push

Where supported and useful, enable the rule that prevents the person who pushed the latest reviewable change from being the only final approver.

This becomes more meaningful once the project has multiple maintainers.

Do not enforce it in a way that deadlocks a solo-maintainer repository.

---

# 18. Require Status Checks

Enable:

```text
Require status checks to pass before merging
```

This is the key security enforcement rule.

Add the exact required checks:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

---

# 19. Require Branch to Be Up to Date

Enable strict required checks / update-before-merge behavior.

Conceptually:

```text
PR checks passed against old main
        |
        v
main changes
        |
        v
PR must be revalidated against current main
```

This reduces the risk that two independently valid branches produce an invalid combined result.

---

# 20. Do Not Require Release Workflow as a PR Check

The release workflow is triggered after changes reach:

```text
main
```

It should not be required as a pull-request check if it does not run in PR context.

Required checks should be the PR security/test gates.

Release happens after merge.

---

# 21. Verify Exact Check Names Before Configuring Rules

GitHub required checks are name-sensitive.

Use:

```bash
cd /mnt/data/ai-platform-operator

gh run list \
  --limit 20
```

Inspect a pull-request run:

```bash
gh run view <RUN_ID>
```

Or inspect PR checks:

```bash
gh pr checks <PR_NUMBER>
```

Record the exact emitted names.

Do not rely only on workflow filenames.

---

# 22. Why Check Name Stability Matters

Suppose the ruleset requires:

```text
Tests / Run on Ubuntu (pull_request)
```

Then you rename the job to:

```text
Unit Tests
```

GitHub may show:

```text
required check expected
```

because the configured context no longer exists.

Treat workflow/job renames as security-control changes.

---

# 23. Validate Source Ruleset from GitHub UI

Navigate:

```text
Repository
  → Settings
  → Rules
  → Rulesets
  → Source Main Protection
```

Verify:

```text
State: Active
Target: Default branch
Bypass: none
PR required
required checks configured
force push blocked
deletion blocked
```

---

# 24. Validate Source Ruleset with GitHub CLI / API

If authenticated GitHub CLI access is available:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets
```

Locate:

```text
Source Main Protection
```

Expected ruleset ID from the implemented environment:

```text
21120105
```

Inspect:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Do not assume this ID exists in a rebuilt repository.

---

# 25. Extract Important Rules Programmatically

Example:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  --jq '{
    name,
    enforcement,
    target,
    bypass_actors,
    conditions,
    rules
  }'
```

Review the actual JSON rather than trusting screenshots alone.

---

# 26. Verify No Bypass Actors

Use:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  --jq '.bypass_actors'
```

Expected:

```json
[]
```

or equivalent empty result.

If non-empty, review every actor.

---

# 27. Verify Required Status Checks via API

Inspect the rules:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  --jq '.rules'
```

Locate the required-status-check rule.

Verify all expected contexts appear.

---

# 28. Practical Enforcement Test — Failed Required Check

Create a temporary source branch:

```bash
cd /mnt/data/ai-platform-operator

git switch main
git pull --ff-only

git switch -c test/branch-protection-failure
```

Introduce a safe, intentional validation failure.

For example, modify a test so the test job fails.

Commit and push:

```bash
git add .
git commit -m "test: verify required check enforcement"
git push -u origin test/branch-protection-failure
```

Open PR:

```bash
gh pr create \
  --base main \
  --head test/branch-protection-failure \
  --title "test: verify branch protection" \
  --body "Temporary validation of required-check enforcement."
```

Expected:

```text
one required check FAILS
merge is blocked
```

Do not merge this PR.

Revert the intentional failure and verify the PR becomes mergeable.

---

# 29. Practical Enforcement Test — Direct Push

Do this only if you are comfortable testing rejection.

From a disposable test commit on local `main`, attempting:

```bash
git push origin main
```

should be rejected if the ruleset requires PRs for the current user and no bypass exists.

Do not create valuable unpushed work on `main` before this test.

A safer approach is to use a temporary commit and reset locally after rejection.

---

# 30. Practical Enforcement Test — Force Push

Do **not** test force push against important history unless using a controlled disposable repository/branch scenario.

The intended rule is simply:

```text
force push to protected main = rejected
```

Verify configuration through ruleset inspection instead of risking history damage.

---

# 31. Practical Enforcement Test — Branch Deletion

Do not actually delete the production source branch for testing.

Use GitHub ruleset inspection/API to validate deletion protection.

The expected rule is:

```text
main deletion blocked
```

---

# 32. GitOps Branch Protection

The GitOps repository must protect:

```text
main
```

using an equivalent but GitOps-specific rule.

Required principles:

```text
pull request required
Validate GitOps Manifests required
force push blocked
deletion blocked
human-controlled merge
```

The GitHub App bot should be able to:

```text
create automation branch
push automation branch
open PR
```

but should **not** bypass merge protection on `main`.

---

# 33. GitOps Ruleset Creation — GitHub UI

Navigate:

```text
GitHub
  → anselem-okeke/ai-platform-gitops
  → Settings
  → Rules
  → Rulesets
  → New branch ruleset
```

Recommended name:

```text
GitOps Main Protection
```

If a different validated name already exists, preserve it.

---

# 34. GitOps Target

Target:

```text
Default branch
```

Expected current default:

```text
main
```

---

# 35. GitOps Bypass

Recommended:

```text
no bypass actors
```

Do not add:

```text
ai-platform-gitops-bot
```

as a bypass actor.

The bot should open a PR, not authorize its own deployment.

---

# 36. GitOps Required Check

Require:

```text
Validate GitOps Manifests
```

This check comes from:

```text
.github/workflows/validate.yml
```

See:

```text
026-gitops-pr-validation.md
```

---

# 37. GitOps Pull Request Rule

Enable:

```text
Require a pull request before merging
```

Current solo-maintainer approval count may remain:

```text
0
```

as long as the validation check is mandatory.

---

# 38. GitOps Force Push and Deletion Rules

Enable:

```text
block force pushes
block branch deletion
```

The GitOps `main` branch is deployment desired state and should maintain an auditable history.

---

# 39. GitOps Bot Interaction with Ruleset

Expected automation flow:

```text
ai-platform-gitops-bot[bot]
    |
    +--> create automation/image-<source-sha>
    |
    +--> commit digest updates
    |
    +--> push automation branch
    |
    +--> open PR to main
    |
    X  cannot bypass required merge gate
```

This is the intended separation of duties.

---

# 40. Verify GitOps Bot Cannot Push Main Directly

The App installation should not be granted ruleset bypass.

Even with:

```text
Contents: Read & write
```

repository rules should still protect `main`.

The App needs write access to create its branch, not unrestricted deployment authority.

---

# 41. CODEOWNERS

CODEOWNERS can provide path-specific review requirements.

Useful sensitive paths include:

```text
.github/workflows/
argocd/
platform/policies/
platform/monitoring/
clusters/dev/
```

Possible source sensitive paths:

```text
.github/workflows/
config/
api/
controllers/
Dockerfile*
```

---

# 42. CODEOWNERS Example

Example only:

```text
.github/workflows/ @anselem-okeke
argocd/            @anselem-okeke
platform/policies/ @anselem-okeke
clusters/dev/      @anselem-okeke
```

Do not enable required CODEOWNER review if it makes a solo-maintainer repository unmergeable.

---

# 43. CODEOWNERS Is Not a Substitute for Rulesets

CODEOWNERS answers:

```text
who should review?
```

Rulesets answer:

```text
what must be true before merge?
```

Use both where appropriate.

---

# 44. Why Approval Count Is Not the Only Control

Current approval count:

```text
0
```

But merge still requires:

```text
PR
required checks
protected branch
no bypass
```

Therefore the repository is not equivalent to an unprotected direct-push model.

Still, once more maintainers exist, independent review should be added.

---

# 45. Source Ruleset Rebuild Checklist

```text
[ ] open source repository settings
[ ] create branch ruleset
[ ] name = Source Main Protection
[ ] enforcement = Active
[ ] target = default branch
[ ] bypass actors = none
[ ] block deletion
[ ] block force push / non-fast-forward
[ ] require PR
[ ] required approvals = 0 for current solo-maintainer state
[ ] dismiss stale approvals
[ ] enable latest-push approval behavior only if it does not deadlock
[ ] require status checks
[ ] enable strict/up-to-date checks
[ ] add Gitleaks
[ ] add Lint / Run on Ubuntu (pull_request)
[ ] add E2E Tests / Run on Ubuntu (pull_request)
[ ] add Tests / Run on Ubuntu (pull_request)
[ ] add govulncheck
[ ] add CodeQL
[ ] save
[ ] verify Active
[ ] test failed check blocks merge
[ ] verify direct push blocked
```

---

# 46. GitOps Ruleset Rebuild Checklist

```text
[ ] open GitOps repository settings
[ ] create branch ruleset
[ ] name = GitOps Main Protection
[ ] enforcement = Active
[ ] target = default branch
[ ] bypass actors = none
[ ] block deletion
[ ] block force push / non-fast-forward
[ ] require PR
[ ] required approvals = 0 for current solo-maintainer state
[ ] require Validate GitOps Manifests
[ ] require strict/up-to-date checks if supported
[ ] save
[ ] verify bot can create branch
[ ] verify bot can open PR
[ ] verify bot cannot bypass main protection
[ ] verify failed GitOps validation blocks merge
```

---

# 47. Failure Scenario — Required Check Is Always “Expected”

## Symptom

PR shows:

```text
Expected — Waiting for status to be reported
```

for a required check that never appears.

## Common Causes

```text
workflow renamed
job renamed
workflow trigger no longer matches PR
path filters skip the job
ruleset references old context name
job condition prevents execution
```

## Diagnosis

Run:

```bash
gh pr checks <PR_NUMBER>
```

Compare actual emitted check names with the ruleset.

## Fix

Update either:

```text
workflow/job name
```

or:

```text
required-check configuration
```

so they match exactly.

---

# 48. Failure Scenario — Workflow Fails but Merge Is Still Allowed

## Meaning

The check exists but is not actually required by the branch ruleset.

## Fix

Add the exact check to:

```text
Require status checks to pass
```

Then retest with an intentional failure.

---

# 49. Failure Scenario — Repository Owner Can Still Bypass

Inspect:

```text
bypass actors
repository admin bypass settings
organization rulesets
```

The validated project configuration had:

```text
no bypass actors
current user cannot bypass
```

Remove accidental bypass privileges if the intent is strict enforcement.

---

# 50. Failure Scenario — Bot Cannot Push Its Automation Branch

Do not immediately weaken `main` rules.

The bot needs:

```text
Contents: Read & write
```

to the repository and permission to create a non-protected automation branch.

Check:

```text
GitHub App installation
App permissions
branch pattern targeting
ruleset target
```

If a ruleset accidentally targets:

```text
all branches
```

instead of the default branch, it may block the bot's automation branch.

---

# 51. Failure Scenario — Bot Can Push Main Directly

This is too permissive.

Check:

```text
ruleset bypass actors
App bypass configuration
target branch conditions
repository administration permissions
```

The GitHub App should not be a bypass actor.

---

# 52. Failure Scenario — Solo Maintainer Cannot Merge Anything

Common causes:

```text
required approvals = 1
CODEOWNERS review required
last-push approval prevents self-approval
no second maintainer exists
```

Do not solve by disabling all protection.

Instead use a solo-maintainer-compatible configuration:

```text
required approvals = 0
required CI checks = enabled
no direct push
no force push
```

Then raise review requirements once another maintainer is available.

---

# 53. Failure Scenario — Security Check Renamed

If:

```text
govulncheck
```

becomes:

```text
Security / govulncheck
```

the ruleset may continue requiring the old context.

Before merging workflow-name changes:

```text
1. identify new emitted check
2. update required-check configuration
3. verify test PR
4. remove obsolete context
```

Treat this as a controlled migration.

---

# 54. Failure Scenario — Check Runs Only on `push`

A required PR check must run for:

```text
pull_request
```

if it is required before merge.

If it only runs:

```yaml
on:
  push:
```

the PR may wait forever for a check that cannot occur before merge.

Fix the workflow trigger.

---

# 55. Failure Scenario — Required Check Has a Matrix Name

For matrix workflows, GitHub emits job contexts such as:

```text
Tests / Run on Ubuntu (pull_request)
```

The ruleset must require the actual matrix job context.

Do not shorten it to:

```text
Tests
```

unless that is the real emitted status context.

---

# 56. Failure Scenario — Ruleset Appears Active but Does Not Affect `main`

Inspect the target condition.

Common mistakes:

```text
wrong include pattern
wrong branch
tag ruleset instead of branch ruleset
default branch selector not enabled
exclude rule accidentally matches main
```

Use the GitHub API to inspect conditions.

---

# 57. Failure Scenario — Organization Rules Conflict with Repository Rules

If the repository is under an organization, organization-level rulesets may also apply.

Inspect effective rules.

Do not assume repository settings are the only enforcement layer.

Document organization-level governance separately if introduced.

---

# 58. Safe Ruleset Change Procedure

Treat branch protection as production configuration.

Before changing:

```text
1. capture current ruleset JSON/screenshots
2. identify exact reason for change
3. confirm workflow/check names
4. change one logical control at a time
5. use a test PR
6. verify enforcement
7. document final state
```

Do not make many protection changes at once without validation.

---

# 59. Export Source Ruleset Configuration

Example:

```bash
mkdir -p /tmp/ai-platform-rulesets

gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105 \
  > /tmp/ai-platform-rulesets/source-main-protection.json
```

Review:

```bash
jq . \
  /tmp/ai-platform-rulesets/source-main-protection.json
```

Do not blindly replay response JSON as a create request; GitHub API read/write schemas may differ.

Use it as an audit/reference artifact.

---

# 60. Discover Ruleset ID if Rebuilt

Do not hardcode:

```text
21120105
```

in automation that must survive recreation.

Discover by name:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets \
  --jq '.[] | select(.name=="Source Main Protection") | .id'
```

---

# 61. Verify Enforcement State

```bash
RULESET_ID="$(
  gh api \
    repos/anselem-okeke/ai-platform-operator/rulesets \
    --jq '.[] | select(.name=="Source Main Protection") | .id'
)"

gh api \
  "repos/anselem-okeke/ai-platform-operator/rulesets/${RULESET_ID}" \
  --jq '{name,enforcement,target}'
```

Expected:

```text
name: Source Main Protection
enforcement: active
target: branch
```

Exact API rendering may vary.

---

# 62. Inspect Bypass Actors

```bash
gh api \
  "repos/anselem-okeke/ai-platform-operator/rulesets/${RULESET_ID}" \
  --jq '.bypass_actors'
```

Expected:

```text
empty
```

---

# 63. Inspect Rule Types

```bash
gh api \
  "repos/anselem-okeke/ai-platform-operator/rulesets/${RULESET_ID}" \
  --jq '.rules[].type'
```

Look for rules representing:

```text
deletion protection
non-fast-forward protection
pull request requirement
required status checks
```

GitHub's exact API type strings should be taken from the live response.

---

# 64. Validate PR Enforcement from CLI

For a real PR:

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

The PR should not be mergeable while a required check is:

```text
pending
failed
cancelled
```

---

# 65. Why Release Is Not on the Required-Check List

Release executes after:

```text
merge to main
```

The protected-branch architecture is:

```text
security/test checks
      |
      v
merge authorization
      |
      v
release
```

Making a post-merge release workflow a required pre-merge check creates a circular/unreachable condition.

---

# 66. Required Checks Should Represent Independent Failure Domains

The current source checks cover:

```text
secret leakage
lint/static correctness
unit tests
E2E behavior
reachable Go vulnerabilities
code scanning
```

This is stronger than requiring one umbrella job that could hide which control failed.

If you later consolidate jobs, preserve independent enforcement semantics.

---

# 67. No Artificial Waiting for Post-Merge Jobs

Do not delay source merge waiting for workflows that only run after merge.

The correct sequence is:

```text
required PR checks pass
        |
        v
merge
        |
        v
release starts
```

Not:

```text
PR checks pass
        |
        v
wait for release that cannot start
```

---

# 68. Relationship to GitHub App Bot

Source ruleset:

```text
protects source main
```

GitHub App bot:

```text
acts after source main release
```

GitOps ruleset:

```text
protects deployment main
```

Together:

```text
Source PR
   |
   v
Source ruleset
   |
   v
main
   |
   v
release
   |
   v
GitHub App bot
   |
   v
GitOps PR
   |
   v
GitOps ruleset
   |
   v
GitOps main
   |
   v
Argo
```

---

# 69. Relationship to Argo CD

Branch protection determines:

```text
what may become Git desired state
```

Argo determines:

```text
how approved Git state becomes cluster state
```

Argo self-heal does not replace GitHub merge protection.

---

# 70. Relationship to Admission Policy

Even after GitOps merge:

```text
Kubernetes admission
```

can still reject an untrusted image.

The defense layers are:

```text
source required checks
GitOps required checks
Argo reconciliation
admission verification
```

No single layer should be treated as sufficient.

---

# 71. Emergency Access / Break-Glass

Do not create a permanent bypass just because emergencies may occur.

A mature break-glass process should be:

```text
time-bound
audited
explicitly authorized
removed after use
followed by normal Git reconciliation
```

For the current project, no bypass actors are configured.

---

# 72. Protection Change Audit Checklist

Whenever rules change:

```text
[ ] ruleset name
[ ] target
[ ] enforcement status
[ ] bypass actors
[ ] PR requirement
[ ] approval count
[ ] stale approval behavior
[ ] strict checks
[ ] required status contexts
[ ] force-push protection
[ ] deletion protection
[ ] test PR result
```

Record the final effective state.

---

# 73. Source Security Validation Test Matrix

| Test | Expected |
|---|---|
| Required check fails | Merge blocked |
| Required check pending | Merge blocked |
| All required checks pass | Merge may proceed |
| Direct push to main | Rejected |
| Force push to main | Rejected |
| Delete main | Rejected |
| Stale approval after new commit | Dismissed where applicable |
| Non-required informational check fails | Depends on ruleset; should not be mistaken for required gate |
| App/user on bypass list | None expected |

---

# 74. GitOps Security Validation Test Matrix

| Test | Expected |
|---|---|
| `Validate GitOps Manifests` fails | Merge blocked |
| Bot opens PR | Allowed |
| Bot pushes automation branch | Allowed |
| Bot pushes main directly | Rejected |
| Human merges valid PR | Allowed |
| Force push GitOps main | Rejected |
| Delete GitOps main | Rejected |

---

# 75. Production Hardening When Team Grows

When the project has multiple maintainers, consider:

```text
required approvals >= 1
CODEOWNERS for security-sensitive paths
different reviewer from latest pusher
environment-specific approval
organization-level rulesets
security-team ownership of workflow changes
```

Do not retrofit these blindly into a one-person repository.

---

# 76. Recommended Sensitive CODEOWNERS Paths Later

Source:

```text
.github/workflows/
Dockerfile*
api/
controllers/
config/
```

GitOps:

```text
.github/workflows/
argocd/
clusters/
platform/policies/
platform/monitoring/
```

Especially protect:

```text
workflow security controls
AppProject permissions
admission policies
production overlays
```

---

# 77. Ruleset Recovery if Repository Becomes Unmergeable

If a configuration mistake blocks all legitimate merges:

```text
1. inspect exact rule causing deadlock
2. do not disable all protection
3. adjust only the blocking rule
4. preserve PR and required-check enforcement
5. test with an existing PR
6. document the temporary correction
```

Typical solo-maintainer deadlocks:

```text
required approval = 1
CODEOWNER approval required
most-recent-push approval required
no second reviewer exists
```

---

# 78. Ruleset Recovery if Required Checks Were Deleted

If a required workflow/job was removed:

```text
1. inspect PR expected checks
2. identify obsolete required context
3. create replacement workflow/check if required
4. update ruleset to exact new context
5. test PR
6. remove stale context
```

Avoid leaving the branch permanently waiting for a check that can never run.

---

# 79. Ruleset Recovery if GitHub App Automation Breaks

If bot PR creation/push fails after a ruleset change:

```text
1. confirm ruleset targets only protected branch
2. confirm automation branch is allowed
3. confirm bot is not required to bypass
4. confirm App Contents permission
5. confirm App Pull requests permission
6. test creation of automation branch
7. test PR creation
```

Do not weaken `main` protection to fix an automation-branch problem.

---

# 80. Operational Commands

## List Source Rulesets

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets
```

## Find Source Ruleset ID

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets \
  --jq '.[] | select(.name=="Source Main Protection") | .id'
```

## Inspect Source Ruleset

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/<RULESET_ID>
```

## List Source PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

## List GitOps PR Checks

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

---

# 81. Full Rebuild Procedure

From an unprotected repository:

```text
SOURCE

[ ] verify all PR workflows run correctly
[ ] identify exact emitted check names
[ ] create Source Main Protection
[ ] set Active
[ ] target default branch
[ ] configure no bypass
[ ] block deletion
[ ] block non-fast-forward/force push
[ ] require PR
[ ] required approvals = 0 for solo maintainer
[ ] dismiss stale approvals
[ ] require strict/up-to-date checks
[ ] require Gitleaks
[ ] require Lint / Run on Ubuntu (pull_request)
[ ] require E2E Tests / Run on Ubuntu (pull_request)
[ ] require Tests / Run on Ubuntu (pull_request)
[ ] require govulncheck
[ ] require CodeQL
[ ] test intentional failure
[ ] verify merge blocked
[ ] fix failure
[ ] verify merge allowed

GITOPS

[ ] verify Validate GitOps Manifests exists
[ ] create GitOps Main Protection
[ ] set Active
[ ] target default branch
[ ] configure no bypass
[ ] block deletion
[ ] block force push
[ ] require PR
[ ] require Validate GitOps Manifests
[ ] approvals compatible with current team size
[ ] test invalid digest PR
[ ] verify merge blocked
[ ] verify GitHub App bot can open PR
[ ] verify bot cannot bypass main protection
```

---

# 82. Implementation Evidence

Validated source facts:

```text
Ruleset:
Source Main Protection

Ruleset ID:
21120105

State:
active

Target:
default branch

Bypass:
none

Required checks:
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL

Approvals:
0

Reason:
solo maintainer
```

Validated GitOps design:

```text
main protected
PR required
Validate GitOps Manifests required
force push blocked
deletion blocked
human-controlled merge
```

---

# 83. What Must Be Verified from Live GitHub

Do not invent:

```text
current GitOps ruleset numeric ID
current GitOps ruleset exact name if changed
exact current UI wording
exact effective organization-level rules
exact emitted status-check names after workflow renames
```

Verify through:

```text
GitHub UI
gh pr checks
gh api .../rulesets
```

before rebuilding.

---

# 84. Official References

GitHub rulesets:

```text
https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
```

Available rules:

```text
https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
```

Create repository rulesets:

```text
https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
```

Required status checks:

```text
https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
```

CODEOWNERS:

```text
https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
```

GitHub REST rules API:

```text
https://docs.github.com/rest/repos/rules
```

GitHub CLI:

```text
https://cli.github.com/manual/
```

---

# 85. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
024-github-app-gitops-automation.md
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
028-promotion-workflow.md
029-rollback-strategy.md
030-argocd-sync-selfheal-and-prune.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
```
