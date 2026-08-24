# Repository Architecture

## Purpose

This document defines the ownership boundary between the source repository and the GitOps repository and explains how changes move between them.

## Repositories

### Source

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

### GitOps

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

## Ownership Rule

```text
Source repository builds artifacts.
GitOps repository chooses what runs.
Argo CD applies approved desired state.
```

## Source Repository Responsibilities

```text
Go operator
REST API
CRD/controller source
unit tests
E2E tests
lint
go vet
govulncheck
CodeQL
Gitleaks
Dockerfiles
Trivy
SBOM
attestations
GHCR publishing
GitOps update automation
```

## GitOps Repository Responsibilities

```text
Argo bootstrap
AppProject
root Application
child Applications
Kustomize bases/overlays
namespaces
operator/API deployment state
ModelService resources
Gateway
monitoring
admission policies
Policy Controller
trust policies
documentation
```

## GitOps Structure

```text
ai-platform-gitops/
├── argocd/
│   ├── bootstrap/
│   ├── projects/
│   ├── applicationsets/
│   └── exposure/
├── clusters/
│   └── dev/
│       ├── apps/
│       │   ├── kustomization.yaml
│       │   ├── operator.yaml
│       │   ├── api.yaml
│       │   ├── gateway.yaml
│       │   ├── monitoring.yaml
│       │   ├── modelservices.yaml
│       │   ├── policies.yaml
│       │   ├── namespaces.yaml
│       │   ├── policy-controller.yaml
│       │   └── trust-policies.yaml
│       └── root-application.yaml
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

## Source-to-GitOps Automation

```text
source main
   |
   v
build operator + API
   |
   v
publish digests
   |
   v
GitHub App token
   |
   v
clone GitOps
   |
   v
automation/image-<source-sha>
   |
   v
update two digest fields
   |
   v
Kustomize validation
   |
   v
commit + PR
```

Expected branch:

```text
automation/image-<source-sha>
```

Expected commit:

```text
chore(dev): deploy images from <source-sha>
```

Expected files:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

## Why Separate Repositories

Benefits:

- build and deploy privileges separated
- source CI cannot silently mutate cluster state
- deployment changes have their own review history
- environment promotion is explicit
- rollback is easier to reason about
- GitOps repository can evolve independently from source code

## Why GitHub App

Cross-repository automation uses a GitHub App instead of a personal token.

Benefits:

```text
short-lived token
machine identity
repository scope
independent revocation
```

## AppProject Ownership Exception

The AppProject file is stored in Git:

```text
argocd/projects/ai-platform.yaml
```

but is bootstrap-managed, not Argo-tracked.

Therefore:

```text
Git change
    !=
automatic live AppProject change
```

Explicit apply:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml

kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

## Rendered-State Rule

Raw bases may contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

Final overlays replace them with approved immutable digests.

Therefore validation focuses on:

```text
rendered environment state
```

## Secret Boundary

Neither repository should contain:

```text
Vault token
GitHub App private key
JWT
password
registry credential
private key
.env secrets
```

GitOps `.gitignore` includes protections such as:

```text
.local/
.env
*.jwt
*.key
*.pem
secret YAML patterns
```

## Repository Validation

### Source

```bash
cd /mnt/data/ai-platform-operator

git status --short
git diff --check
```

### GitOps

```bash
cd /mnt/data/ai-platform-gitops

git status --short
git diff --check
```

### Secret Scan

```bash
gitleaks git \
  --redact \
  --verbose \
  .
```

Run in both repositories.

## Official References

- GitHub repositories: https://docs.github.com/repositories
- GitHub Apps: https://docs.github.com/apps
- OpenGitOps: https://opengitops.dev/
- Argo CD declarative setup: https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/
