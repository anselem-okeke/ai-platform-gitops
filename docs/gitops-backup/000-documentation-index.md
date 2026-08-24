# AI Platform Documentation Index

## Purpose

This documentation set is the engineering knowledge base for the AI Platform GitOps implementation. It explains what is deployed, why the architecture was chosen, how each component is configured, how delivery and security controls work, how the platform is validated, and how engineers should operate and recover it.

## Audience

- Platform Engineers
- DevOps Engineers
- SREs
- Kubernetes Administrators
- Security Engineers
- Software and ML Engineers contributing to the platform

## Repository Scope

### Source repository

`/mnt/data/ai-platform-operator`

Owns:
- Go operator and REST API source
- unit/E2E tests
- linting, govulncheck, CodeQL, Gitleaks
- container builds and Trivy
- SBOM and provenance
- GHCR publishing
- GitHub App-driven GitOps update PRs

### GitOps repository

`/mnt/data/ai-platform-gitops`

Owns:
- Kubernetes desired state
- Argo CD topology
- Kustomize bases/overlays
- namespaces, routing, monitoring
- admission policies and Sigstore integration
- environment promotion and rollback
- operational documentation

## Recommended Reading Order

1. [001-platform-overview.md](001-platform-overview.md)
2. [002-architecture.md](002-architecture.md)
3. [003-repository-architecture.md](003-repository-architecture.md)
4. [004-cluster-and-environment.md](004-cluster-and-environment.md)
5. GitOps and Argo CD implementation
6. CI and software supply-chain security
7. Admission control
8. Monitoring and observability
9. Operations, troubleshooting, recovery, and command reference

## Documentation Catalogue

| Document | Purpose |
|---|---|
| `000-documentation-index.md` | Master documentation index and reading order |
| `001-platform-overview.md` | Platform purpose, capabilities, goals, and operating model |
| `002-architecture.md` | Architecture, control flows, trust flows, and delivery flows |
| `003-repository-architecture.md` | Source and GitOps repository ownership boundaries |
| `004-cluster-and-environment.md` | Kubernetes environment, namespaces, domains, and endpoints |
| `005-gitops-architecture.md` | Desired-state and reconciliation architecture |
| `006-argocd-installation.md` | Argo CD installation and validation |
| `007-argocd-secure-access.md` | Secure Argo CD exposure and TLS |
| `008-keycloak-oidc-integration.md` | Keycloak OIDC/PKCE integration |
| `009-argocd-rbac.md` | Group-to-role authorization |
| `010-argocd-project.md` | AppProject design and permissions |
| `011-app-of-apps.md` | Root/child Application topology |
| `012-kustomize-architecture.md` | Base/overlay strategy |
| `013-namespace-management.md` | Namespace ownership and policy labels |
| `014-operator-gitops-deployment.md` | Operator GitOps deployment |
| `015-api-gitops-deployment.md` | API GitOps deployment |
| `016-modelservice-gitops-deployment.md` | ModelService deployment |
| `017-gateway-and-routing.md` | Envoy Gateway and routes |
| `018-monitoring-gitops.md` | Prometheus/Grafana GitOps integration |
| `019-source-ci-pipeline.md` | Source CI pipeline |
| `020-container-build-and-hardening.md` | Container hardening |
| `021-container-vulnerability-scanning.md` | Trivy policy |
| `022-sbom-and-provenance.md` | SBOM/provenance |
| `023-github-container-registry.md` | GHCR publishing |
| `024-github-app-gitops-automation.md` | GitHub App automation |
| `025-image-digest-update-workflow.md` | Digest update PR workflow |
| `026-gitops-pr-validation.md` | GitOps validation |
| `027-branch-protection-and-rulesets.md` | Rulesets and required checks |
| `028-promotion-workflow.md` | Promotion model |
| `029-rollback-strategy.md` | Git rollback |
| `030-argocd-sync-selfheal-and-prune.md` | Sync/self-heal/prune |
| `031-sigstore-policy-controller.md` | Sigstore Policy Controller |
| `032-github-artifact-attestation-policy.md` | GitHub artifact trust |
| `033-image-admission-policies.md` | Registry/digest admission |
| `034-pod-init-and-ephemeral-container-policy.md` | Pod/init/ephemeral enforcement |
| `035-policy-controller-observability.md` | Policy Controller metrics |
| `036-prometheus-alerting.md` | Prometheus rules and alerts |
| `037-secret-management-strategy.md` | Secret-management model |
| `038-secret-scanning.md` | Gitleaks/history scanning |
| `039-software-supply-chain-security.md` | Full supply-chain security model |
| `040-end-to-end-delivery-workflow.md` | Developer-to-cluster flow |
| `041-validation-and-security-tests.md` | Positive/negative tests |
| `042-disaster-recovery-and-rebuild.md` | Rebuild/recovery |
| `043-troubleshooting-guide.md` | Failures, diagnosis, fixes |
| `044-operations-runbook.md` | Routine operations |
| `045-command-reference.md` | Command reference |
| `046-security-model.md` | Trust boundaries |
| `047-design-decisions.md` | Architecture decisions |
| `048-known-limitations.md` | Known limitations |
| `049-future-environments-and-promotion.md` | Future staging/prod |
| `050-phase-7-completion-checklist.md` | Evidence-backed completion checklist |

## Documentation Standard

Implementation documents should include, where applicable:

- Purpose
- Scope
- Architecture
- Prerequisites
- Repository locations
- Configuration
- Step-by-step implementation
- How it works
- Security considerations
- Validation commands and expected results
- Failure scenarios
- Troubleshooting
- Recovery/rollback
- Operational notes
- Official references
- Related documentation

## Core Platform Facts

- Argo CD runs in `argocd`.
- The source and GitOps repositories have separate responsibilities.
- The root Argo CD Application is intentionally manual.
- Child Applications use automated sync/self-heal/prune where appropriate.
- Workloads deploy by immutable SHA-256 digest.
- CI builds artifacts but does not directly deploy them to Kubernetes.
- GitHub App authentication is used for source-to-GitOps automation.
- GitOps promotion occurs through pull requests.
- Native admission policy enforces approved registry/digest requirements.
- Sigstore Policy Controller verifies trusted artifact attestations.
- Enforcement includes regular, init, and ephemeral containers.
- Prometheus monitors Policy Controller health and reconciliation.
- Secrets are excluded from Git and scanned with Gitleaks.

## Maintenance Rule

When platform behavior changes, update the relevant documentation in the same pull request where practical. Commands, versions, resource names, and expected results should remain grounded in tested platform behavior.
