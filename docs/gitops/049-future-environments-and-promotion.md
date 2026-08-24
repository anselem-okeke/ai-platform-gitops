# Future Environments and Promotion

## Purpose

This document defines how staging and production should be added without changing the core GitOps/supply-chain model.

# Principle

```text
Build once
Verify once
Promote the same immutable digest
```

# Recommended Structure

Example:

```text
platform/
  api/
    base/
    overlays/
      dev/
      staging/
      prod/

  operator/
    base/
    overlays/
      dev/
      staging/
      prod/

clusters/
  dev/
  staging/
  prod/
```

# Promotion Path

```text
source commit
    |
    v
build digest X once
    |
    v
dev PR -> digest X
    |
    v
dev validation
    |
    v
staging PR -> same digest X
    |
    v
staging validation
    |
    v
prod PR -> same digest X
```

Do not rebuild per environment.

# What May Differ by Environment

Examples:

```text
replicas
resource requests/limits
hostnames
TLS certificate references
autoscaling
environment configuration
monitoring thresholds
storage classes
network policies
```

# What Should Not Differ

Artifact bytes:

```text
sha256:<digest>
```

# Argo Layout

Each environment should have its own root Application and child topology.

Example:

```text
clusters/staging/root-application.yaml
clusters/staging/apps/
```

```text
clusters/prod/root-application.yaml
clusters/prod/apps/
```

# Promotion PR Requirements

A promotion PR should show:

```text
source SHA
image repository
old digest
new digest
target environment
source environment
CI status
attestation status
change ticket/reference if required
```

# Production Protection

Recommended additions:

- at least one independent reviewer
- CODEOWNERS for security/platform paths
- environment protection rules
- separate production credentials
- restricted Argo RBAC
- production alert routing
- backup/restore validation
- production SLOs
- change windows where appropriate

# Secrets

Production secrets must use production Vault paths/policies.

Do not reuse development credentials.

# Trust Policy

The same artifact trust principles apply:

```text
approved registry
digest pinning
trusted GitHub attestations
Sigstore admission
```

# Rollback

Rollback restores the previous production digest through Git.

# Validation Before Production Adoption

Before first production deployment validate:

1. cluster version compatibility
2. Gateway/TLS
3. Keycloak/OIDC
4. Argo HA/backup requirements
5. Vault backup/restore
6. persistent-volume backup/restore
7. admission behavior
8. trusted/untrusted image tests
9. alert routing
10. Git rollback
11. disaster recovery
12. least-privilege RBAC
13. supply-chain permissions

# Official References

- Argo CD ApplicationSet: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/
- OpenGitOps: https://opengitops.dev/
- Kubernetes production environment: https://kubernetes.io/docs/setup/production-environment/
