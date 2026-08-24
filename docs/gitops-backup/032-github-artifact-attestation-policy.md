# GitHub Artifact Attestation Policy

## Purpose

Documents the GitHub trust-policy Helm deployment consumed by Policy Controller.

## Chart
```text
oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies
version: v0.7.0
```

Validated values:
```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

Resources:
```text
TrustRoot/github
ClusterImagePolicy/github-policy
```

A fake 64-character digest was rejected with `no valid bundles exist in registry`, proving that structural digest validity alone is insufficient; trusted evidence must exist.

## Official References
- https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- https://github.com/github/artifact-attestations-helm-charts
- https://docs.sigstore.dev/policy-controller/overview/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
