# Repository Architecture

## Purpose

The platform intentionally separates software production from deployment state.

| Repository | Responsibility |
|---|---|
| `ai-platform-operator` | Source, CI, build, scan, attest, publish |
| `ai-platform-gitops` | Desired state, Argo CD, security, monitoring, promotion |

Local paths:

```text
/mnt/data/ai-platform-operator
/mnt/data/ai-platform-gitops
```

## Source Repository

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

Owns:

- Go operator
- AI Platform API
- tests
- lint
- govulncheck
- CodeQL
- Gitleaks
- Dockerfiles
- Trivy
- SBOM
- provenance
- GHCR publishing
- GitOps update automation

It does **not** own the cluster's final desired state.

## Source CI

```text
Pull Request
   |
   +-- Lint
   +-- Tests
   +-- E2E
   +-- govulncheck
   +-- CodeQL
   +-- Gitleaks
   |
   v
Protected main
```

Release runs from `main`.

The `update-gitops` job depends on both operator and API build jobs, preventing a GitOps update if one required image build fails.

## Artifact Identity

Images are deployed as:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

## GitOps Repository

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Owns:

- Argo bootstrap
- AppProject
- root/child Applications
- Kustomize bases/overlays
- namespaces
- operator/API desired state
- ModelService resources
- gateway resources
- monitoring
- admission policies
- Policy Controller/trust-policy Applications
- image digests
- documentation

## Current Structure

```text
ai-platform-gitops/
├── argocd/
│   ├── bootstrap/
│   ├── projects/
│   ├── applicationsets/
│   └── exposure/
├── clusters/dev/
│   ├── apps/
│   └── root-application.yaml
├── platform/
│   ├── operator/{base,overlays/dev}
│   ├── api/{base,overlays/dev}
│   ├── gateway/{base,overlays/dev}
│   ├── monitoring/{base,overlays/dev}
│   ├── namespaces/{base,overlays/dev}
│   └── policies/{base,overlays/dev}
├── modelservices/{base,overlays/dev}
├── docs/
├── .github/workflows/
├── .gitignore
└── README.md
```

## Ownership Boundary

```text
Source repo builds artifacts.
GitOps repo decides what is deployed.
Argo CD reconciles GitOps state into Kubernetes.
```

## Cross-Repository Automation

```text
Source main commit
    |
    v
Build operator/API
    |
    v
Publish GHCR
    |
    v
Capture digests
    |
    v
GitHub App token
    |
    v
Clone GitOps repo
    |
    v
automation/image-<source-sha>
    |
    v
Update two digests
    |
    v
Kustomize validation
    |
    v
GitOps PR
```

Expected commit/PR title:

```text
chore(dev): deploy images from <source-sha>
```

## Why GitHub App

- short-lived token
- installation scope
- repository-specific permissions
- automation identity separate from a person
- easier governance/revocation

## Why No Auto-Merge

Human merge preserves review, auditable promotion, separation of build from deployment, and controlled release approval.

## AppProject Bootstrap Boundary

Stored at:

```text
argocd/projects/ai-platform.yaml
```

It is bootstrap-managed rather than Argo-tracked.

Changes require explicit application:

```bash
kubectl apply --dry-run=server -f argocd/projects/ai-platform.yaml
kubectl apply -f argocd/projects/ai-platform.yaml
```

## Rendered-Output Validation

Raw bases may contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

The dev overlay replaces them with immutable approved images. Therefore CI validates rendered Kustomize output rather than treating raw base placeholders as final deployment values.

## Security/Monitoring Ownership

Native admission policy:

```text
platform/policies/
```

Policy Controller and trust policies:

```text
clusters/dev/apps/policy-controller.yaml
clusters/dev/apps/trust-policies.yaml
```

Monitoring integration:

```text
platform/monitoring/base/
```

## Secret Boundary

Repositories must not contain live credentials.

Protected patterns include:

```text
.local/
.env
*.jwt
*.key
*.pem
secret YAML patterns
```

Gitleaks scans both CI changes and full Git history.

## Design Principles

1. Build and deploy responsibilities are separate.
2. GitOps is the normal deployment path.
3. CI does not directly mutate the cluster.
4. GitOps does not rebuild artifacts.
5. Images are promoted by digest.
6. Cross-repo automation uses machine identity.
7. Promotion is PR-controlled.
8. Argo reconciles declared state.
9. Security and monitoring resources are version controlled.
10. Operational documentation lives with the GitOps knowledge base.

## Related Documentation

- [000-documentation-index.md](000-documentation-index.md)
- [001-platform-overview.md](001-platform-overview.md)
- [002-architecture.md](002-architecture.md)
- [004-cluster-and-environment.md](004-cluster-and-environment.md)
