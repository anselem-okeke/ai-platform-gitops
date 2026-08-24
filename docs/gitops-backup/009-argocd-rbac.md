# Argo CD RBAC

## Purpose

This document describes how Keycloak groups are mapped to Argo CD authorization roles and how the platform avoids using the built-in admin account for routine operation.

## Authentication vs Authorization

```text
Keycloak
   |
   | authenticates user and emits groups
   v
Argo CD
   |
   | evaluates RBAC policy
   v
allowed / denied action
```

Keycloak proves identity. Argo CD determines permission.

## Identity Groups

```text
platform-viewer
platform-deployer
platform-admin
```

These groups are delivered to Argo CD through the OIDC `groups` claim.

## Role Intent

### Viewer

Intended for:

- reading Application state
- observing sync/health
- reviewing platform configuration
- non-mutating operational visibility

### Deployer

Intended for controlled deployment-oriented operations where explicitly granted.

### Admin

Intended for platform administration.

Admin membership should remain tightly controlled.

## Built-In Admin

Argo CD's built-in `admin` account is highly privileged.

The implemented operating model is:

```text
bootstrap:
  initial admin available temporarily

steady state:
  Keycloak OIDC + RBAC

recovery:
  documented break-glass process
```

Routine platform work should not depend on the shared local admin identity.

## RBAC Configuration

Argo CD RBAC is represented through Argo CD configuration and/or project-scoped roles, depending on the permission boundary.

Key ideas:

- keep default permissions minimal
- map OIDC groups explicitly
- prefer least privilege
- scope application permissions to the `ai-platform` project
- avoid wildcard admin access except where genuinely required

## Verification

### Check current login

```bash
argocd account get-user-info
```

Verify:

- authenticated username
- groups claim
- expected group membership

### Test viewer behavior

Authenticate as a viewer and confirm read-only operations such as:

```bash
argocd app list
argocd app get ai-platform-api
```

Mutation attempts should be denied unless deliberately granted.

### Test deployer/admin behavior

Use accounts with the corresponding Keycloak group and verify only the intended actions succeed.

## Security Considerations

Argo CD documentation warns that the default policy applies to every authenticated user and cannot be reduced later by a deny rule.

Therefore the platform should keep the default role minimal and grant elevated permissions explicitly.

## Troubleshooting

### User logs in but has no role

Check:

1. Keycloak user group membership
2. `groups` client scope
3. token groups claim
4. Argo CD RBAC group mapping
5. spelling of group names

### User has too many permissions

Check:

- `policy.default`
- global role mappings
- AppProject role policies
- unexpected nested/group claims

## Official References

- Argo CD RBAC: https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/
- Argo CD projects and project roles: https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
- Argo CD Keycloak integration: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/

## Related Documentation

- [008-keycloak-oidc-integration.md](008-keycloak-oidc-integration.md)
- [010-argocd-project.md](010-argocd-project.md)
