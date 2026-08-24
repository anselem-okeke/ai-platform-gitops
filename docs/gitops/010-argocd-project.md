# Argo CD AppProject

## Purpose

This document records the `ai-platform` AppProject, its allow-lists, bootstrap ownership, update procedure, and validation.

## Resource

```text
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: ai-platform
  namespace: argocd
```

Git path:

```text
argocd/projects/ai-platform.yaml
```

## Why AppProject Matters

The AppProject limits:

```text
source repositories
destination namespaces/clusters
cluster-scoped resource kinds
namespace-scoped resource kinds
project role permissions
```

This is a major Argo CD security boundary.

## Allowed Repositories

Important allowed sources include:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
ghcr.io/sigstore/helm-charts
ghcr.io/github/artifact-attestations-helm-charts
```

## Destination

The project permits the namespaces needed by the AI Platform.

An important addition was:

```text
cosign-system
```

for Policy Controller and trust-policy resources.

## Required Cluster-Scoped Resources

Permissions include the specific kinds required by the implementation, including:

```text
policy.sigstore.dev / TrustRoot
policy.sigstore.dev / ClusterImagePolicy

admissionregistration.k8s.io / ValidatingAdmissionPolicy
admissionregistration.k8s.io / ValidatingAdmissionPolicyBinding
admissionregistration.k8s.io / MutatingWebhookConfiguration
admissionregistration.k8s.io / ValidatingWebhookConfiguration
```

Avoid broad wildcard permissions.

## Bootstrap Ownership

Important:

```text
argocd/projects/ai-platform.yaml
```

is stored in Git but is not currently reconciled by an Argo Application.

Therefore a Git merge alone does not update the live AppProject.

## Update Procedure

Enter GitOps:

```bash
cd /mnt/data/ai-platform-gitops
```

Render/review file:

```bash
sed -n '1,260p' \
  argocd/projects/ai-platform.yaml
```

Server-side validation:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Apply:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Verify:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd \
  -o yaml
```

Argo CLI:

```bash
argocd proj get ai-platform
```

## Why Bootstrap-Managed

The AppProject defines permissions that the Argo application hierarchy depends on.

Keeping it as explicit bootstrap state avoids a child Application casually granting itself new privileges.

## Troubleshooting

### Repository denied

Compare Application `repoURL` against:

```yaml
spec:
  sourceRepos:
```

### Destination denied

Compare target namespace/cluster against:

```yaml
spec:
  destinations:
```

### Resource denied

Compare API group/kind against the project resource allow-lists.

### Git updated but live project unchanged

Expected.

Run the explicit bootstrap apply.

## Security Considerations

AppProject changes are privileged.

Review:

```text
new repositories
new namespaces
new cluster-scoped kinds
wildcards
new project roles
```

Avoid using `*` simply to make a failing Application sync.

## Official References

- Argo CD projects: https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
- Declarative setup: https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/
- Argo security: https://argo-cd.readthedocs.io/en/stable/operator-manual/security/
