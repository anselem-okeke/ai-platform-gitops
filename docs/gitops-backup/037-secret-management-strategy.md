# Secret Management Strategy

## Purpose

Defines what secret material may exist in Git and how Vault fits the design.

## Principle
```text
Git contains desired configuration. Git does not contain live credentials.
```

Vault endpoint: `https://vault.platform.local:8200`. Vault is the foundation for secrets and PKI.

Never commit private keys, GitHub App keys, Vault tokens, passwords, JWTs, registry credentials, or credential-bearing `.env` files. Public certificates and public keys are not inherently secrets; therefore the repository intentionally does not broadly ignore every `*.crt`.

Kubernetes Secret YAML is only base64 encoded and should not be treated as secure repository storage.

## Leak Response
Revoke/rotate first, then inspect Git history, remove sensitive history if required, verify consumers, rescan, and document the incident.

## Official References
- https://developer.hashicorp.com/vault/docs
- https://developer.hashicorp.com/vault/docs/secrets/pki
- https://kubernetes.io/docs/concepts/configuration/secret/
- https://docs.github.com/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
