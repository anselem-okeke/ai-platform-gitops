# AI Platform Documentation Index

## Purpose

This document is the master index for the AI Platform engineering knowledge base.

The documentation set is designed so that another engineer can:

- understand the platform architecture
- reproduce the development environment
- rebuild the platform after loss
- operate the platform safely
- validate GitOps and software supply-chain controls
- troubleshoot known failure modes
- understand why important architectural decisions were made
- identify current limitations before extending the platform

The documentation is intended to be implementation-grade, not merely descriptive.

## Audience

Primary audiences:

- Platform Engineers
- DevOps Engineers
- Site Reliability Engineers
- Kubernetes Administrators
- Security Engineers
- Software Engineers contributing to the operator/API
- Engineers extending the platform into staging/production

## Repository Boundaries

### Source Repository

Local path:

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

Responsibilities:

- Go operator source
- REST API source
- unit and E2E testing
- linting
- go vet
- govulncheck
- CodeQL
- Gitleaks
- container builds
- Trivy scanning
- SBOM generation
- provenance/SBOM attestations
- GHCR publishing
- GitHub App-driven GitOps update pull requests

### GitOps Repository

Local path:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Responsibilities:

- Kubernetes desired state
- Argo CD bootstrap/topology
- AppProject
- Kustomize bases and overlays
- namespaces
- operator/API desired state
- ModelService resources
- Gateway/routing
- monitoring
- admission policies
- Policy Controller
- GitHub artifact trust policy
- environment promotion
- rollback
- operational documentation

## Documentation Principles

Every implementation document should include, where applicable:

1. Purpose
2. Scope
3. Prerequisites
4. Repository/file locations
5. Architecture
6. Step-by-step implementation
7. Actual configuration examples
8. Commands
9. Validation commands
10. Expected results
11. Positive tests
12. Negative/security tests
13. Failure scenarios
14. Root causes
15. Troubleshooting
16. Recovery/rollback
17. Operational notes
18. Security considerations
19. Official references
20. Related documentation

## Reading Order

Recommended order for a new engineer:

```text
000 Documentation Index
001 Platform Overview
002 Architecture
003 Repository Architecture
004 Cluster and Environment

005-018 GitOps / Argo / workload implementation
019-030 CI / build / promotion / rollback
031-039 admission / Sigstore / observability / secrets
040-050 operations / validation / DR / security / completion
README.md final entry point
```

## Full Documentation Catalogue

| File | Purpose |
|---|---|
| `000-documentation-index.md` | Master index, reading order, documentation rules |
| `001-platform-overview.md` | Platform purpose, capabilities, goals, user model |
| `002-architecture.md` | Full platform architecture and control/trust/data flows |
| `003-repository-architecture.md` | Source vs GitOps ownership and repository layout |
| `004-cluster-and-environment.md` | Current development cluster/environment facts |
| `005-gitops-architecture.md` | Desired-state model and reconciliation architecture |
| `006-argocd-installation.md` | Argo CD installation and bootstrap |
| `007-argocd-secure-access.md` | Argo secure exposure, TLS, Gateway |
| `008-keycloak-oidc-integration.md` | Keycloak OIDC/PKCE setup |
| `009-argocd-rbac.md` | OIDC group-to-role authorization |
| `010-argocd-project.md` | AppProject permissions and bootstrap ownership |
| `011-app-of-apps.md` | Root/child Application topology |
| `012-kustomize-architecture.md` | Base/overlay and rendered-state validation |
| `013-namespace-management.md` | Namespace and security-label ownership |
| `014-operator-gitops-deployment.md` | Operator GitOps deployment |
| `015-api-gitops-deployment.md` | REST API GitOps deployment |
| `016-modelservice-gitops-deployment.md` | ModelService GitOps/reconciliation |
| `017-gateway-and-routing.md` | Envoy Gateway / HTTPRoute implementation |
| `018-monitoring-gitops.md` | Monitoring resources and validation |
| `019-source-ci-pipeline.md` | Source CI gates |
| `020-container-build-and-hardening.md` | Hardened container build |
| `021-container-vulnerability-scanning.md` | Trivy release gate |
| `022-sbom-and-provenance.md` | SBOM/provenance/attestation |
| `023-github-container-registry.md` | GHCR and immutable digests |
| `024-github-app-gitops-automation.md` | GitHub App machine identity |
| `025-image-digest-update-workflow.md` | Source-to-GitOps digest update PR |
| `026-gitops-pr-validation.md` | Kustomize/kubeconform/digest validation |
| `027-branch-protection-and-rulesets.md` | Required checks and branch rules |
| `028-promotion-workflow.md` | Build-once/promote-same-digest model |
| `029-rollback-strategy.md` | Git-based rollback |
| `030-argocd-sync-selfheal-and-prune.md` | Argo sync/self-heal/prune |
| `031-sigstore-policy-controller.md` | Policy Controller implementation |
| `032-github-artifact-attestation-policy.md` | GitHub trust policy |
| `033-image-admission-policies.md` | Native image registry/digest admission |
| `034-pod-init-and-ephemeral-container-policy.md` | Pod/init/ephemeral enforcement |
| `035-policy-controller-observability.md` | Policy Controller metrics |
| `036-prometheus-alerting.md` | Policy Controller alerts |
| `037-secret-management-strategy.md` | Vault/Git secret boundary |
| `038-secret-scanning.md` | Gitleaks and history scanning |
| `039-software-supply-chain-security.md` | End-to-end supply-chain threat/control model |
| `040-end-to-end-delivery-workflow.md` | Full developer-to-runtime workflow |
| `041-validation-and-security-tests.md` | Positive/negative validation matrix |
| `042-disaster-recovery-and-rebuild.md` | Rebuild order after cluster/platform loss |
| `043-troubleshooting-guide.md` | Known failures, diagnosis, fixes |
| `044-operations-runbook.md` | Day-to-day operational procedures |
| `045-command-reference.md` | Copy/paste command library |
| `046-security-model.md` | Security boundaries and trust model |
| `047-design-decisions.md` | Architecture decision rationale |
| `048-known-limitations.md` | Explicit non-goals and unvalidated areas |
| `049-future-environments-and-promotion.md` | Staging/prod extension model |
| `050-phase-7-completion-checklist.md` | Evidence-backed Phase 7 completion |
| `README.md` | Final project entry point |

## Current Documentation Status

```text
000-004 foundation                  hardened
005-018 GitOps/Argo/workloads       hardened
019-030 CI/build/promotion          hardened
031-039 security/admission          hardened
040-050 operations/final            created
README.md                            pending final generation
cross-document consistency review   pending
```

## Documentation Maintenance Rules

When implementation changes:

1. update the relevant manifest/code
2. update the corresponding documentation in the same PR where practical
3. update version-specific commands
4. keep expected output realistic
5. preserve troubleshooting lessons
6. distinguish validated facts from future recommendations
7. never document secrets or sensitive values
8. prefer official upstream references
9. re-check links when versions change
10. update `050-phase-7-completion-checklist.md`

## Validation of the Documentation Set

From the GitOps repository after copying the final documents into `docs/`:

```bash
cd /mnt/data/ai-platform-gitops

find docs -maxdepth 1 -type f -name '*.md' \
  -printf '%f\n' \
  | sort
```

Expected numbered sequence:

```text
000-documentation-index.md
001-platform-overview.md
...
050-phase-7-completion-checklist.md
```

Check for duplicate numbers:

```bash
find docs -maxdepth 1 -type f -name '[0-9][0-9][0-9]-*.md' \
  -printf '%f\n' \
  | cut -c1-3 \
  | sort \
  | uniq -d
```

Expected:

```text
no output
```

Check Markdown files are tracked:

```bash
git status --short docs
```

## Official References

- Kubernetes documentation: https://kubernetes.io/docs/
- Argo CD documentation: https://argo-cd.readthedocs.io/en/stable/
- GitHub Actions documentation: https://docs.github.com/actions
- Sigstore documentation: https://docs.sigstore.dev/
- Prometheus documentation: https://prometheus.io/docs/
- Keycloak documentation: https://www.keycloak.org/documentation
- HashiCorp Vault documentation: https://developer.hashicorp.com/vault/docs
