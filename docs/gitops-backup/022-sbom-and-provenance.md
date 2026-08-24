# SBOM and Provenance

## Purpose

Documents SBOM generation and artifact provenance.

## SBOM
The release pipeline produces an **SPDX JSON** SBOM using Anchore tooling.

## Provenance and Attestations
GitHub artifact attestations bind provenance and SBOM evidence to the immutable image digest. The attestation action is pinned to:
```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

```text
source -> build -> SBOM -> push -> digest -> provenance + SBOM attestations
```

The digest, not a tag, is the artifact identity. A standalone SBOM file does not by itself prove association with the exact runtime artifact; the attestation provides that binding.

Sigstore admission later validates trusted evidence. A fake digest was denied with `no valid bundles exist in registry`.

## Official References
- https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- https://spdx.dev/
- https://github.com/anchore/syft
- https://slsa.dev/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
