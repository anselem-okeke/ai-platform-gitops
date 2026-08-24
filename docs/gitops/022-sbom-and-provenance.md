# SBOM and Provenance

## Purpose

This document explains how the release pipeline creates software inventory and provenance evidence for the exact image digest that is later promoted through GitOps.

## Artifacts

For each release image, the pipeline produces:

```text
SPDX JSON SBOM
provenance attestation
SBOM attestation
```

## Why This Matters

The platform must be able to answer:

```text
What is in the image?
Which build created it?
Which source revision produced it?
Can runtime policy verify trusted evidence for it?
```

## SBOM Generation

The release uses Anchore tooling to generate an SPDX JSON SBOM.

Validated output format:

```text
SPDX JSON
```

## Artifact Attestations

GitHub artifact attestations bind evidence to the immutable digest.

Pinned attestation action:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

## Flow

```text
source SHA
   |
   v
build
   |
   +--> SBOM
   |
   v
push GHCR
   |
   v
digest
   |
   +--> provenance attestation
   |
   +--> SBOM attestation
```

## Why Digest Binding Is Important

A standalone SBOM file could be copied, renamed, or associated with the wrong image.

Attestation binds evidence to:

```text
sha256:<digest>
```

which is the same identity used by GitOps and admission.

## Verification

Inspect workflow:

```bash
cd /mnt/data/ai-platform-operator

grep -RIn \
  -E 'attest|sbom|syft|spdx' \
  .github/workflows
```

Verify digest outputs are passed into attestation steps.

## Runtime Relationship

Sigstore/GitHub trust policy verifies trusted evidence for the exact digest during Kubernetes admission.

A syntactically valid but fake digest was denied with:

```text
no valid bundles exist in registry
```

That demonstrates that digest shape alone is not considered sufficient trust.

## Security Considerations

The SBOM should be generated from the same artifact that is pushed and attested.

Avoid:

```text
build A
generate SBOM A
rebuild B
push B
```

because evidence would no longer describe the runtime artifact.

## Official References

- GitHub artifact attestations: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- SPDX: https://spdx.dev/
- SPDX specification: https://spdx.github.io/spdx-spec/
- Syft: https://github.com/anchore/syft
- SLSA: https://slsa.dev/
