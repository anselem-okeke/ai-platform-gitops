# Argo CD AppProject

## Purpose

This document records the `ai-platform` AppProject, its security boundary, and the important distinction that the AppProject is bootstrap-managed rather than currently reconciled by Argo CD itself.

## Resource

```text
Kind: AppProject
Name: ai-platform
Namespace: argocd
```

Git location:

```text
argocd/projects/ai-platform.yaml
```

## Why AppProject Exists

Argo CD Projects restrict:

- source repositories Applications may use
- destination clusters/namespaces
- cluster-scoped resource kinds
- namespace-scoped resource kinds
- project-scoped roles

This prevents every Application from implicitly having unrestricted deployment capabilities.

## Allowed Sources

Important allowed repositories include:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
ghcr.io/sigstore/helm-charts
ghcr.io/github/artifact-attestations-helm-charts
```

The OCI Helm sources are required by:

- Sigstore Policy Controller
- GitHub artifact trust policies

## Destinations

The project permits the namespaces required by the AI Platform.

An important later addition was:

```text
cosign-system
```

which is necessary for supply-chain policy components.

## Important Cluster-Scoped Kinds

The project permits required policy-related cluster resources, including:

```text
policy.sigstore.dev / TrustRoot
policy.sigstore.dev / ClusterImagePolicy
admissionregistration.k8s.io / ValidatingAdmissionPolicy
admissionregistration.k8s.io / ValidatingAdmissionPolicyBinding
admissionregistration.k8s.io / MutatingWebhookConfiguration
admissionregistration.k8s.io / ValidatingWebhookConfiguration
```

Permissions should remain explicit rather than using unrestricted wildcard access.

## Namespace-Scoped Kinds

The project allows required namespace resources, including Secrets where needed by approved platform components.

Secret permission does not mean plaintext secrets should be stored in Git.

## Bootstrap Ownership

A critical architectural fact:

```text
argocd/projects/ai-platform.yaml
```

is stored in Git but is **not currently tracked by an Argo Application**.

It has no Argo tracking annotation.

Therefore:

```text
git commit changes AppProject
    !=
live AppProject automatically changes
```

An explicit bootstrap apply is required.

## Update Procedure

From the GitOps repository:

```bash
cd /mnt/data/ai-platform-gitops
```

Validate server-side:

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

or:

```bash
argocd proj get ai-platform
```

## Why Bootstrap-Manage It

The AppProject defines permissions that Argo Applications themselves depend on.

Keeping it in the bootstrap boundary prevents a child Application from casually changing the permissions that authorize the same application hierarchy.

This is a deliberate trust-boundary decision and must be documented because it changes the expected sync behavior.

## Troubleshooting

### Application blocked with source repo denied

Compare the Application `repoURL` against AppProject `sourceRepos`.

### Destination denied

Check the namespace/cluster destination list.

### Resource kind denied

Inspect the resource group/kind and compare it with:

- `clusterResourceWhitelist`
- `namespaceResourceWhitelist`
- blacklist fields, if present

### Git file changed but live AppProject did not

Expected if the change was only committed.

Run the explicit bootstrap apply procedure.

## Security Considerations

- Do not replace explicit allow-lists with `*` merely to fix a sync error.
- Add the smallest required repository, namespace, group, or kind.
- Review AppProject changes as privileged platform changes.
- Keep the bootstrap procedure documented.

## Official References

- Argo CD Projects: https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
- Argo CD declarative setup: https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/
- Argo CD security: https://argo-cd.readthedocs.io/en/stable/operator-manual/security/

## Related Documentation

- [005-gitops-architecture.md](005-gitops-architecture.md)
- [011-app-of-apps.md](011-app-of-apps.md)
- [031-sigstore-policy-controller.md](031-sigstore-policy-controller.md)
