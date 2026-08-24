# Rollback Strategy

## Purpose

This document is the **reproducible rollback and recovery runbook** for the AI Platform.

It defines how to recover from:

```text
bad image promotion
failed rollout
runtime regression
admission rejection
GitOps misconfiguration
Argo drift/reconciliation problems
bot-created bad promotion pull requests
partial deployment failure
emergency production-style incidents
```

The core principle is:

```text
Git is the source of truth
        |
        v
rollback Git
        |
        v
Argo reconciles
        |
        v
cluster returns to known-good state
```

A new engineer should be able to identify a failed promotion, choose the correct rollback path, restore a known-good digest, validate recovery, and preserve auditability using only this runbook and the repositories.

---

# 1. Scope

This runbook covers rollback for the current development environment.

Implemented:

```text
dev
```

Current first-party workloads:

```text
AI Platform API
AI Platform Operator
```

Current deployment repositories:

```text
source:
anselem-okeke/ai-platform-operator

GitOps:
anselem-okeke/ai-platform-gitops
```

Current GitOps image paths:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

---

# 2. Core Rollback Principle

The preferred rollback mechanism is:

```text
Git revert
```

not:

```text
kubectl set image
manual Deployment editing
Argo live-state patching
rebuilding old source
```

The reason is simple:

```text
Git = desired state
Argo = reconciliation engine
```

If the live cluster is manually changed but Git still contains the bad state:

```text
manual fix
   |
   v
cluster differs from Git
   |
   v
Argo self-heal
   |
   v
bad Git state may return
```

Therefore durable recovery changes Git.

---

# 3. What Counts as a Known-Good Rollback Target

A valid rollback target should ideally satisfy:

```text
previously deployed
previously Synced
previously Healthy
passed GitOps validation
passed admission
used immutable digest
traceable to source release
```

Preferred rollback identity:

```text
ghcr.io/anselem-okeke/<image>@sha256:<known-good-digest>
```

Do not roll back to a mutable tag such as:

```text
latest
main
dev
v1
```

---

# 4. Rollback Decision Tree

Use this decision tree:

```text
Problem discovered
    |
    +--> GitOps PR not merged?
    |       |
    |       +--> YES -> close/fix PR
    |       |
    |       +--> NO
    |
    +--> GitOps merged but Argo has not applied?
    |       |
    |       +--> revert Git before rollout if possible
    |
    +--> Argo applied bad state?
    |       |
    |       +--> Git revert
    |
    +--> Admission rejected bad artifact?
    |       |
    |       +--> Git revert or correct artifact
    |
    +--> Workload is actively breaking service?
            |
            +--> emergency mitigation if required
            |
            +--> immediately restore Git
```

---

# 5. Identify the Failure Stage

Before rolling back, determine where the failure occurred.

Possible stages:

```text
1. source PR
2. source release
3. GHCR publish
4. attestation
5. GitOps bot PR
6. GitOps validation
7. GitOps merge
8. Argo reconciliation
9. admission
10. Kubernetes rollout
11. runtime behavior
```

Rollback action depends on the stage.

---

# 6. Failure Before GitOps Merge

If the promotion pull request has not been merged:

```text
do not perform a cluster rollback
```

Instead:

```text
close PR
or
fix PR
```

The cluster is still running the previous desired state.

---

# 7. Close a Bad Promotion PR

List GitOps PRs:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

Inspect:

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Close:

```bash
gh pr close <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --comment "Closed because this promotion is not approved for deployment."
```

This is not a rollback because no deployment occurred.

---

# 8. Bad Bot Branch Before Merge

If the GitHub App bot created a branch with wrong digests:

```text
automation/image-<source-sha>
```

Do not merge it.

Close the PR and allow the corrected release workflow to create a new PR.

Avoid manually editing an automated branch unless diagnosing the automation.

---

# 9. Failure After GitOps Merge

If the bad promotion is already merged:

```text
create a rollback branch
revert the bad GitOps commit
open a reviewed PR
merge
let Argo reconcile
```

This is the standard rollback flow.

---

# 10. Find Recent Promotion Commits

In the GitOps repository:

```bash
cd /mnt/data/ai-platform-gitops
```

Inspect relevant history:

```bash
git log --oneline --decorate --graph -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Promotion commits typically look like:

```text
chore(dev): deploy images from <source-sha>
```

---

# 11. Inspect a Candidate Promotion Commit

```bash
git show \
  --stat \
  <GITOPS_COMMIT>
```

Inspect exact diff:

```bash
git show \
  <GITOPS_COMMIT> \
  -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Confirm that the commit being reverted is actually the promotion that introduced the bad digest.

---

# 12. Identify the Previous Known-Good Digests

Inspect the commit before the bad promotion:

```bash
git show \
  <BAD_COMMIT>^:platform/operator/overlays/dev/kustomization.yaml
```

```bash
git show \
  <BAD_COMMIT>^:platform/api/overlays/dev/kustomization.yaml
```

Look for:

```text
digest: sha256:<known-good>
```

or the equivalent current Kustomize image structure.

---

# 13. Verify the Known-Good State Was Previously Deployed

Before rollback, confirm the previous commit/digest was actually used.

Useful evidence:

```text
GitOps history
Argo history
Kubernetes rollout history
release records
previous successful PR
```

---

# 14. Inspect Argo Application History

API:

```bash
argocd app history \
  ai-platform-api
```

Operator:

```bash
argocd app history \
  ai-platform-operator
```

Identify the revision corresponding to the known-good Git state.

---

# 15. Inspect Current Argo State

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

Record:

```text
Sync Status
Health Status
Revision
```

before rollback.

---

# 16. Inspect Current Live Images

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

Record the bad image digests before rollback for incident evidence.

---

# 17. Create Rollback Branch

Start from current GitOps `main`:

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only origin main
```

Create rollback branch:

```bash
git switch -c rollback/dev-<short-description>
```

Example:

```bash
git switch -c rollback/dev-api-regression
```

---

# 18. Revert the Bad Promotion Commit

Preferred:

```bash
git revert <BAD_GITOPS_COMMIT>
```

This creates a new commit that reverses the bad desired-state change.

Why revert instead of reset:

```text
preserves history
preserves audit trail
works with protected main
does not rewrite shared history
```

---

# 19. If the Bad Commit Contains More Than Image Digests

Inspect carefully.

If the commit contains unrelated changes:

```text
do not blindly revert if that would undo good changes
```

Instead perform a targeted rollback:

```text
restore only affected desired-state files
```

from a known-good revision.

Example:

```bash
git restore \
  --source=<KNOWN_GOOD_COMMIT> \
  -- \
  platform/api/overlays/dev/kustomization.yaml
```

Then review diff.

---

# 20. Targeted Operator Rollback

To restore only operator desired state:

```bash
git restore \
  --source=<KNOWN_GOOD_COMMIT> \
  -- \
  platform/operator/overlays/dev/kustomization.yaml
```

---

# 21. Targeted API Rollback

```bash
git restore \
  --source=<KNOWN_GOOD_COMMIT> \
  -- \
  platform/api/overlays/dev/kustomization.yaml
```

---

# 22. Inspect Rollback Diff

```bash
git diff
```

Expected:

```text
bad digest -> known-good digest
```

No unrelated resources should change.

---

# 23. Verify Changed Files

```bash
git diff --name-only | sort
```

Expected only intended rollback paths.

If rolling back API only:

```text
platform/api/overlays/dev/kustomization.yaml
```

If both:

```text
platform/api/overlays/dev/kustomization.yaml
platform/operator/overlays/dev/kustomization.yaml
```

---

# 24. Render Rollback Operator State

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rollback.yaml
```

---

# 25. Render Rollback API State

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rollback.yaml
```

---

# 26. Verify Rollback Images

```bash
grep -n 'image:' \
  /tmp/operator-rollback.yaml \
  /tmp/api-rollback.yaml
```

Expected:

```text
known-good immutable digests
```

---

# 27. Validate Exact Digest Format

Expected:

```text
@sha256:<64-hex>
```

Reject rollback state containing:

```text
latest
dev
main
short digest
wrong registry
```

---

# 28. Run GitOps Validation Locally

```bash
git diff --check
```

Run kubeconform if installed:

```bash
for file in \
  /tmp/operator-rollback.yaml \
  /tmp/api-rollback.yaml
do
  kubeconform \
    -strict \
    -summary \
    -ignore-missing-schemas \
    "${file}"
done
```

---

# 29. Commit the Rollback

Example:

```bash
git add \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

Commit:

```bash
git commit \
  -m "revert(dev): restore previous known-good image digests"
```

---

# 30. Push Rollback Branch

```bash
git push \
  -u origin \
  rollback/dev-<short-description>
```

---

# 31. Open Rollback Pull Request

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head rollback/dev-<short-description> \
  --title "revert(dev): restore previous known-good image digests" \
  --body "Rollback of the failed dev image promotion. Restores the last known-good immutable image digests."
```

---

# 32. Recommended Rollback PR Body

Include:

```text
incident summary
bad GitOps commit
bad source SHA
bad image digest(s)
known-good GitOps commit
known-good digest(s)
reason for rollback
validation performed
```

Example:

```markdown
## Rollback

Failed GitOps promotion:

`<bad-gitops-commit>`

Failed source revision:

`<source-sha>`

Rollback target:

`<known-good-gitops-commit>`

Restored API:

`ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>`

Restored operator:

`ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>`

Reason:

`<brief incident description>`

Validation:

- Kustomize render passed
- immutable digest validation passed
- GitOps validation required
```

---

# 33. GitOps Validation Must Still Run

Rollback is not exempt from policy.

The PR must still pass:

```text
Validate GitOps Manifests
```

because a hurried rollback can also contain mistakes.

---

# 34. Human Merge Remains Required

The rollback PR should normally remain:

```text
human-controlled
```

even during recovery.

If a future production incident policy allows emergency bypass, it must be explicitly documented, time-bound, and audited.

---

# 35. Argo Reconciliation After Rollback Merge

Refresh API:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Refresh operator:

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

---

# 36. Wait for API Rollback

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

---

# 37. Wait for Operator Rollback

```bash
argocd app wait \
  ai-platform-operator \
  --sync \
  --health \
  --timeout 300
```

---

# 38. Verify API Rollout

```bash
kubectl rollout status \
  deployment/ai-platform-api \
  -n ai-platform \
  --timeout=300s
```

---

# 39. Verify Operator Rollout

```bash
kubectl rollout status \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  --timeout=300s
```

---

# 40. Confirm Live API Digest

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
known-good API digest
```

---

# 41. Confirm Live Operator Digest

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
known-good operator digest
```

---

# 42. Verify Pods

API:

```bash
kubectl get pods \
  -n ai-platform \
  -o wide
```

Operator:

```bash
kubectl get pods \
  -n ai-platform-operator-system \
  -o wide
```

Expected:

```text
Ready
Running
```

---

# 43. Inspect Events After Rollback

API:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

Operator:

```bash
kubectl get events \
  -n ai-platform-operator-system \
  --sort-by=.lastTimestamp
```

Look for:

```text
admission rejection
image pull errors
readiness failures
crash loops
scheduling failures
```

---

# 44. Verify API Health

Use the platform API health endpoint if implemented.

Example:

```bash
curl -k \
  https://api.ai-platform.local/health
```

Use the actual endpoint from the API implementation.

Do not invent a health route if the repository uses another path.

---

# 45. Verify Functional Behavior

A rollback is not complete merely because the pod is:

```text
Running
```

Repeat the business/platform operation that failed.

Examples:

```text
GET model status
create ModelService
read API resource
operator reconciliation
```

Use the specific failing use case from the incident.

---

# 46. Rollback When Only API Is Bad

If operator is healthy and only API regressed:

```text
rollback API digest only
```

Avoid unnecessarily changing operator state.

This reduces blast radius.

---

# 47. Rollback When Only Operator Is Bad

Similarly:

```text
rollback operator only
```

if API remains compatible and healthy.

---

# 48. Coordinated Rollback

If API and operator changes are coupled and compatibility requires both:

```text
rollback both together
```

The decision should be based on release compatibility, not convenience.

---

# 49. Failure Scenario — Git Revert Conflicts

Symptom:

```text
CONFLICT
```

when running:

```bash
git revert <commit>
```

Diagnosis:

```bash
git status
```

Review conflict files carefully.

If the affected Kustomize files changed since the bad commit, resolve them to the intended known-good digest state.

Then:

```bash
git add <resolved-files>
git revert --continue
```

Do not use:

```bash
git checkout --theirs .
```

blindly.

---

# 50. Abort a Bad Revert

If you realize the wrong commit was selected:

```bash
git revert --abort
```

Then re-identify the target.

---

# 51. Failure Scenario — Rollback PR Fails GitOps Validation

Do not bypass.

Inspect:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Typical causes:

```text
wrong digest
invalid Kustomize
wrong registry
secret-pattern issue
whitespace
```

Correct the rollback branch.

---

# 52. Failure Scenario — Known-Good Digest No Longer Pulls

Possible reasons:

```text
registry package deleted
retention cleanup
private package permission changed
registry outage
```

This is a serious artifact-retention failure.

A rollback target is only useful if the artifact still exists.

For production, define retention policy so known-good releases remain retrievable.

---

# 53. Failure Scenario — Known-Good Digest Lacks Valid Attestation

Admission may reject an old image if:

```text
attestation missing
trust policy changed
artifact evidence removed
```

Check admission events.

Do not disable policy immediately.

Confirm the rollback artifact still satisfies the current trust policy.

---

# 54. Admission-Rejection Rollback

If the newly promoted image is denied before a pod runs:

```text
service may still be running old replicas
```

depending on rollout behavior.

Inspect:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform
```

Then:

```bash
kubectl describe deployment \
  ai-platform-api \
  -n ai-platform
```

If the desired state references a denied image, revert Git to known-good trusted digest.

---

# 55. Fake Digest Failure

A syntactically valid fake digest can be rejected by Sigstore trust validation.

Known observed error:

```text
no valid bundles exist in registry
```

Correct response:

```text
use a real trusted digest
or
rollback to known-good digest
```

Incorrect response:

```text
disable policy-controller
remove namespace enforcement
```

---

# 56. Failed Rollout with Existing Healthy Replica

If Kubernetes cannot create the new ReplicaSet but old replicas remain healthy:

```text
impact may be limited
```

Still revert bad Git promptly so desired state returns to known-good.

---

# 57. Failed Rollout with Service Impact

If the rollout degrades availability:

```text
prioritize service restoration
```

Preferred:

```text
fast Git revert
```

If Git review latency is too slow for a future production SLA, establish an explicit emergency procedure before production.

---

# 58. Emergency Manual Rollback

Manual rollback is a **break-glass mitigation**, not normal operation.

Potential emergency action:

```bash
kubectl set image ...
```

or:

```bash
kubectl rollout undo ...
```

should only be used when:

```text
service impact is severe
Git path cannot restore fast enough
authorized responder chooses emergency action
```

---

# 59. Important Warning About `kubectl rollout undo`

Kubernetes rollback history may restore:

```text
a previous ReplicaSet template
```

but Git remains unchanged.

Argo may then re-apply the bad Git desired state.

Therefore:

```text
kubectl rollout undo
```

is temporary mitigation only.

Immediately follow with:

```text
Git rollback
```

---

# 60. Emergency Manual API Rollback Example

First inspect history:

```bash
kubectl rollout history \
  deployment/ai-platform-api \
  -n ai-platform
```

If authorized:

```bash
kubectl rollout undo \
  deployment/ai-platform-api \
  -n ai-platform
```

Then immediately correct Git.

---

# 61. Emergency Operator Rollback Example

```bash
kubectl rollout history \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system
```

Emergency:

```bash
kubectl rollout undo \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system
```

Then immediately restore Git.

---

# 62. Argo Self-Heal and Emergency Changes

Because self-heal is enabled:

```text
manual live change
    |
    v
Argo detects drift
    |
    v
Argo restores Git state
```

This is normally desirable.

During an emergency, it means out-of-band mitigation may not persist.

Do not disable self-heal casually.

If a future incident procedure temporarily pauses reconciliation, document:

```text
who paused it
why
when
what app
how it was restored
```

---

# 63. Do Not Delete Argo Application to Roll Back

Deleting the Application is not a rollback strategy.

It can create:

```text
resource orphaning
unexpected pruning
loss of reconciliation
operational confusion
```

Rollback desired state instead.

---

# 64. Do Not Edit Live Deployment YAML Manually

Avoid:

```bash
kubectl edit deployment ...
```

for durable recovery.

This produces undocumented drift.

---

# 65. Do Not Rebuild Old Source as Rollback

If a known-good digest already exists:

```text
reuse it
```

Do not rebuild the old commit and assume the new output is equivalent.

Rebuild may produce a different digest.

---

# 66. Do Not Roll Back by Tag

Bad:

```text
image: ...:previous
```

Good:

```text
image: ...@sha256:<known-good>
```

---

# 67. Argo Rollback Command

Argo CD has application history/rollback capabilities.

However, in a GitOps workflow where Git is authoritative, prefer:

```text
Git revert
```

because Argo-only rollback can cause live state to disagree with Git and be re-reconciled.

Use Argo rollback only as a temporary emergency measure if explicitly required.

---

# 68. Argo History Is Still Useful

Use:

```bash
argocd app history \
  ai-platform-api
```

to identify previously deployed revisions.

Do not confuse:

```text
finding rollback target
```

with:

```text
authorizing out-of-Git rollback
```

---

# 69. Rollback After Bad Configuration Change

Rollback is not limited to images.

If a GitOps config change causes failure:

```text
Gateway
monitoring
policies
namespace labels
Argo Application config
```

the same principle applies:

```text
revert the bad Git commit
```

But assess pruning/side effects carefully.

---

# 70. Rollback of Security Policy Changes

Security-policy rollback requires extra caution.

Never restore service by broadly disabling:

```text
admission
signature verification
namespace enforcement
```

unless an approved emergency procedure specifically allows it.

Prefer fixing the offending workload or reverting only the broken policy change.

---

# 71. Rollback of AppProject Changes

If a restrictive AppProject change blocks Argo:

```text
revert the AppProject configuration
```

Remember that the AppProject itself may be bootstrap-managed manually rather than Argo-managed.

Use the documented bootstrap procedure for that resource.

---

# 72. Rollback of Root App-of-Apps Changes

Root topology changes are privileged.

If a child Application definition is removed or broken:

```text
revert Git
```

Then manually sync/apply root changes only according to the documented root manual-sync process.

Do not assume root is automatically reconciled.

---

# 73. Whole-Resource Prune Caution

Destructive whole-resource prune has not been fully empirically tested for every resource type.

Therefore during rollback:

```text
do not claim full destructive recovery behavior is validated
```

Inspect the specific resource and Argo prune semantics.

---

# 74. Rollback Validation Matrix

| Condition | Validation |
|---|---|
| Git rollback merged | Confirm merge commit |
| Argo revision updated | `argocd app get` |
| App Synced | Argo Sync Status |
| App Healthy | Argo Health Status |
| Workload rollout complete | `kubectl rollout status` |
| Known-good digest live | `kubectl get deployment ... image` |
| Admission accepts artifact | events / successful pod creation |
| Pods ready | `kubectl get pods` |
| Functional behavior restored | repeat failing operation |
| No unexpected drift | `argocd app diff` |

---

# 75. Verify No Argo Drift After Rollback

API:

```bash
argocd app diff \
  ai-platform-api
```

Operator:

```bash
argocd app diff \
  ai-platform-operator
```

Expected:

```text
no unintended diff
```

---

# 76. Confirm Git and Cluster Match

Compare:

```text
GitOps rendered image
```

with:

```text
live Kubernetes image
```

Git:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  | grep 'image:'
```

Live:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

They should match.

---

# 77. Incident Evidence to Preserve

For each rollback, capture:

```text
incident start time
source commit
release run ID
bad image digest
bad GitOps PR
bad GitOps merge commit
Argo revision
symptom
rollback target
rollback PR
rollback merge commit
restored image digest
recovery validation
```

Never store secret tokens in incident notes.

---

# 78. Rollback Timing

For development, manual review is acceptable.

For future production, define:

```text
RTO
RPO
approval latency
emergency rollback authority
```

before production launch.

The current documentation does not claim production-grade incident SLAs.

---

# 79. Partial Failure: API Bad, Operator Good

Recommended:

```text
rollback only API
```

unless version compatibility requires a coordinated rollback.

---

# 80. Partial Failure: Operator Bad, API Good

Recommended:

```text
rollback only operator
```

again considering compatibility.

---

# 81. Partial Failure: Both Bad

Rollback both to the last known compatible pair.

Do not mix arbitrary versions unless compatibility is known.

---

# 82. Compatibility Record

For future releases, consider recording:

```text
API digest
operator digest
source SHA
compatibility set
```

in the promotion PR.

This helps coordinated rollback.

---

# 83. Rollback After Security Vulnerability Discovery

If a deployed digest is later found vulnerable:

```text
rollback only if previous digest is safer and still acceptable
```

Otherwise:

```text
build fixed artifact
validate
promote fixed digest
```

A rollback is not automatically the right answer for security incidents.

---

# 84. Roll Forward vs Roll Back

Choose rollback when:

```text
known-good previous state exists
recovery must be fast
regression is caused by new release
```

Choose roll-forward when:

```text
previous version is also unsafe
data/schema changes make rollback dangerous
forward fix is faster/safer
```

Document the decision.

---

# 85. Data Migration Warning

The current API/operator deployment has no documented complex database schema migration workflow in this Phase 7 runbook.

If future releases add persistent schema migrations:

```text
application rollback
```

may not imply:

```text
data rollback
```

Add migration-specific rollback procedures before introducing irreversible schema changes.

---

# 86. Secret Rotation Rollback Warning

Secret rotations are not image rollbacks.

If a deployment fails after credential rotation:

```text
restore credential compatibility carefully
```

Do not expose old secrets in Git.

Use Vault/Kubernetes secret-management procedures.

---

# 87. Certificate Rollback Warning

TLS/certificate changes may require:

```text
certificate restore
Secret restore
Gateway reconciliation
```

not simply image rollback.

Use component-specific recovery runbooks.

---

# 88. Monitoring During Rollback

Observe:

```text
pod readiness
restart count
events
Prometheus targets
API health
operator reconciliation errors
```

Do not stop at:

```text
Argo = Synced
```

---

# 89. Prometheus Validation

If relevant:

```bash
kubectl get pods \
  -n monitoring
```

Confirm monitoring remains healthy while validating rollback.

For service-specific metrics, query the actual metric names defined by the platform.

---

# 90. Post-Rollback Review

After service is restored:

```text
identify root cause
fix source/release automation
verify guardrail should catch recurrence
update documentation
add regression test
```

Rollback restores service; it does not complete the engineering response.

---

# 91. If Bot Created a Bad PR Because Automation Is Wrong

Do not only fix the GitOps PR.

Also fix:

```text
release-images.yml
digest update logic
validation guard
```

otherwise the next release may recreate the same bad PR.

---

# 92. If GitOps Validation Allowed a Bad Promotion

Treat this as a control gap.

Update:

```text
026-gitops-pr-validation.md
.github/workflows/validate.yml
```

and add a negative test reproducing the failure.

---

# 93. If Admission Allowed an Untrusted Artifact

This is a higher-severity control failure.

Inspect:

```text
native policies
Sigstore Policy Controller
TrustRoot
ClusterImagePolicy
namespace labels
webhook health
```

Do not assume rollback alone fixes the security gap.

---

# 94. If Argo Did Not Self-Heal

Inspect:

```bash
argocd app get <APP>
```

Check:

```text
automated sync enabled
selfHeal enabled
sync policy
ignoreDifferences
resource health
```

Only narrow, intentional ignore rules should exist.

---

# 95. Rollback Drill

A controlled rollback drill should be performed periodically.

Suggested drill:

```text
1. deploy known-good version A
2. promote test version B
3. verify B
4. revert B GitOps commit
5. confirm Argo restores A
6. verify live digest is A
7. verify application health
8. record elapsed recovery time
```

Do not use destructive production data during drills.

---

# 96. Known Empirical Validation

The platform has empirically validated:

```text
Git reconciliation
drift self-heal
rollback through Git revert
```

Do not overstate:

```text
full destructive whole-resource prune recovery
production DR
persistent-volume disaster recovery
```

as fully validated.

---

# 97. Rollback Checklist — Standard

```text
[ ] identify failed promotion
[ ] record bad source SHA
[ ] record bad image digest
[ ] record bad GitOps commit
[ ] identify known-good GitOps revision
[ ] identify known-good digest
[ ] create rollback branch
[ ] revert or restore targeted files
[ ] inspect diff
[ ] render Kustomize
[ ] validate immutable digest
[ ] run git diff --check
[ ] run kubeconform if available
[ ] commit rollback
[ ] push branch
[ ] open PR
[ ] pass Validate GitOps Manifests
[ ] human merge
[ ] refresh Argo
[ ] wait for Synced/Healthy
[ ] wait for Kubernetes rollout
[ ] verify live digest
[ ] verify pods ready
[ ] repeat functional test
[ ] confirm no Argo drift
[ ] document incident
```

---

# 98. Rollback Checklist — Emergency

```text
[ ] declare incident
[ ] identify affected workload
[ ] identify last known-good version
[ ] choose fastest safe mitigation
[ ] if manual rollback is required, record exact command
[ ] restore Git immediately
[ ] verify Argo/Git consistency
[ ] validate service
[ ] remove temporary emergency changes
[ ] preserve evidence
[ ] perform post-incident review
```

---

# 99. Full Rebuild of Rollback Capability

An engineer rebuilding the platform should verify:

```text
[ ] GitOps history preserved
[ ] protected main prevents force rewrite
[ ] immutable image digests used
[ ] prior known-good digests retained in registry
[ ] GitOps PR validation works
[ ] Argo automated child sync enabled
[ ] Argo self-heal enabled
[ ] live image can be inspected
[ ] Git revert workflow tested
[ ] admission accepts known-good artifact
[ ] rollback drill succeeds
[ ] emergency procedure documented
```

---

# 100. Useful Commands

## GitOps History

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

## Inspect Commit

```bash
git show <COMMIT>
```

## Revert Commit

```bash
git revert <COMMIT>
```

## Argo History

```bash
argocd app history ai-platform-api
argocd app history ai-platform-operator
```

## Argo State

```bash
argocd app get ai-platform-api --refresh
argocd app get ai-platform-operator --refresh
```

## Live Images

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

## Rollout Status

```bash
kubectl rollout status \
  deployment/ai-platform-api \
  -n ai-platform \
  --timeout=300s
```

```bash
kubectl rollout status \
  deployment/ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  --timeout=300s
```

## Events

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp \
  | tail -n 100
```

---

# 101. What Must Never Be Done

Do not:

```text
force-push GitOps main to erase a bad promotion
roll back using mutable tags
rebuild old source and call it the same release
disable admission to make an image deploy
delete Argo Applications as a rollback shortcut
leave emergency kubectl drift without Git correction
assume Running pod means functional recovery
assume old digest is safe without validation
```

---

# 102. Known Implementation Facts

Current validated project facts:

```text
environment:
dev

rollback source of truth:
Git

primary rollback:
Git revert

Argo:
automated child reconciliation
self-heal enabled

first-party images:
ghcr.io/anselem-okeke/ai-platform-api
ghcr.io/anselem-okeke/ai-platform-operator

deployment identity:
sha256 digest

GitOps validation:
Validate GitOps Manifests

admission:
native policies + Sigstore trust

empirically validated:
Git rollback and self-heal
```

---

# 103. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact bad commit
exact known-good digest
exact Argo revision
exact deployment revision history
exact health endpoint
exact incident-specific rollback target
```

Retrieve them from:

```text
Git
GitHub
Argo CD
Kubernetes
release workflow history
```

at incident time.

---

# 104. Official References

Git revert:

```text
https://git-scm.com/docs/git-revert
```

Kubernetes Deployment rollback:

```text
https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment
```

Argo CD application rollback/history:

```text
https://argo-cd.readthedocs.io/
```

Argo automated sync/self-heal:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
```

OpenGitOps principles:

```text
https://opengitops.dev/
```

Kubernetes images/digests:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

GitHub pull requests:

```text
https://docs.github.com/pull-requests
```

---

# 105. Related AI Platform Documentation

```text
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
028-promotion-workflow.md
030-argocd-sync-selfheal-and-prune.md
031-sigstore-policy-controller.md
032-github-attestation-trust.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-rebuild-and-disaster-recovery.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
