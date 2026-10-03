import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def fail(message):
    raise SystemExit(f"ERROR: {message}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def required_env(name):
    value = os.environ.get(name, "")
    if not value or value != value.strip():
        fail(f"{name} must be present without surrounding whitespace")
    return value


def require_pattern(name, value, pattern):
    if re.fullmatch(pattern, value) is None:
        fail(f"invalid {name}")
    return value


artifact_dir = Path("/model")
model_name = require_pattern(
    "MODEL_NAME", required_env("MODEL_NAME"),
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
)
model_version = require_pattern(
    "MODEL_VERSION", required_env("MODEL_VERSION"),
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}",
)
expected_revision = require_pattern(
    "EXPECTED_SOURCE_REVISION", required_env("EXPECTED_SOURCE_REVISION"),
    r"[0-9a-f]{40}",
)
expected_sha256 = require_pattern(
    "EXPECTED_MODEL_SHA256", required_env("EXPECTED_MODEL_SHA256"),
    r"[0-9a-f]{64}",
)
expected_manifest_sha256 = require_pattern(
    "EXPECTED_MANIFEST_SHA256", required_env("EXPECTED_MANIFEST_SHA256"),
    r"[0-9a-f]{64}",
)
bucket = required_env("MODEL_BUCKET")
prefix = required_env("MODEL_PREFIX")
verifier = Path(required_env("MODEL_VERIFIER_PATH"))
validate_only = os.environ.get("VALIDATE_ONLY", "true")

if validate_only not in ("true", "false"):
    fail("VALIDATE_ONLY must be true or false")

if bucket != "models":
    fail("unexpected model bucket")

if prefix != f"sklearn/{model_name}/{model_version}/{expected_revision}":
    fail("destination does not match the approved model release path")

if not verifier.is_absolute() or not verifier.is_file():
    fail("model verifier must be an existing absolute file path")

if not artifact_dir.is_dir():
    fail("artifact directory does not exist")

files = ("model.joblib", "checksums.sha256", "manifest.json")
entries = list(artifact_dir.iterdir())

if {p.name for p in entries} != set(files) or any(
    p.is_symlink() or not p.is_file() for p in entries
):
    fail("artifact directory must contain exactly three regular bundle files")

payloads = {
    name: (artifact_dir / name).read_bytes()
    for name in files
}

if digest(payloads["model.joblib"]) != expected_sha256:
    fail("model does not match the approved release checksum")

if digest(payloads["manifest.json"]) != expected_manifest_sha256:
    fail("manifest does not match the approved release checksum")

try:
    manifest = json.loads(payloads["manifest.json"])
except (ValueError, UnicodeDecodeError):
    fail("manifest is not valid JSON")

if (
    not isinstance(manifest, dict)
    or type(manifest.get("schemaVersion")) is not int
):
    fail("manifest schema version is missing or invalid")

if manifest["schemaVersion"] != 1:
    fail("unsupported manifest schema version")

model = manifest.get("model")
source_info = manifest.get("source")

if not isinstance(model, dict) or not isinstance(source_info, dict):
    fail("manifest model/source sections must be objects")

for field, expected in {
    "name": model_name,
    "version": model_version,
    "format": "sklearn",
    "runtime": "kserve-sklearnserver",
    "artifact": "model.joblib",
    "sha256": expected_sha256,
}.items():
    if model.get(field) != expected:
        fail(f"manifest model.{field} does not match the approved release")

if source_info.get("revision") != expected_revision:
    fail("manifest source revision does not match the approved release")

checksums = {}

for line in payloads["checksums.sha256"].decode("utf-8").splitlines():
    if not line.strip():
        continue

    parts = line.split()

    if len(parts) != 2:
        fail("invalid checksum entry")

    checksum, filename = parts
    filename = filename.removeprefix("*")

    if (
        filename not in ("model.joblib", "manifest.json")
        or filename in checksums
    ):
        fail("unexpected or duplicate checksum entry")

    require_pattern("bundle checksum", checksum, r"[0-9a-f]{64}")

    if checksum != digest(payloads[filename]):
        fail(f"checksum mismatch for {filename}")

    checksums[filename] = checksum

if set(checksums) != {"model.joblib", "manifest.json"}:
    fail("bundle checksum entries are incomplete")

subprocess.run(
    [
        sys.executable,
        str(verifier),
        "--artifact-dir",
        str(artifact_dir),
        "--expected-model-version",
        model_version,
    ],
    check=True,
)

# The image-provided verifier checks model loading and predictions.
# Require it to preserve the verified input bytes.
if any(
    (artifact_dir / name).read_bytes() != data
    for name, data in payloads.items()
):
    fail("model verifier changed the approved bundle")

print(
    "PASS: approved release identity, checksums and model verifier passed",
    flush=True,
)

if validate_only == "true":
    print(
        "PASS: validation-only run completed; no S3 client or writes",
        flush=True,
    )
    raise SystemExit(0)

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    region_name="us-east-1",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"mode": "standard", "max_attempts": 5},
        connect_timeout=10,
        read_timeout=30,
    ),
)


def read_object(key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise

    body = response["Body"]
    try:
        return body.read()
    finally:
        body.close()


# Publish the manifest last. A failed run can safely resume by
# comparing objects already written with this exact release bundle.

# Check all existing objects before making any writes.
for name, local_bytes in payloads.items():
    key = f"{prefix}/{name}"
    existing = read_object(key)
    if existing is not None and existing != local_bytes:
        fail(f"existing release object has different content: {key}")

print("PASS: existing release objects contain no conflicts", flush=True)

for name, local_bytes in payloads.items():
    key = f"{prefix}/{name}"
    existing = read_object(key)

    if existing is None:
        try:
            response = s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=local_bytes,
                IfNoneMatch="*",
                Metadata={
                    "sha256": digest(local_bytes),
                    "source-revision": expected_revision,
                    "model-version": model_version,
                    "model-name": model_name,
                },
            )
            print(
                f"Uploaded {key}; versionId={response.get('VersionId', 'none')}",
                flush=True,
            )
        except ClientError as error:
            # Another run may have created the same object.
            # Only an identical object is acceptable.
            if error.response["Error"]["Code"] not in (
                "PreconditionFailed",
                "412",
            ):
                raise
    elif existing != local_bytes:
        fail(f"release object changed during upload: {key}")

    downloaded = read_object(key)
    if downloaded != local_bytes:
        fail(f"downloaded object differs from the approved bundle: {key}")

    print(
        f"PASS: downloaded object verified: {key}; sha256={digest(downloaded)}",
        flush=True,
    )

print(f"ARTIFACT_URI=s3://{bucket}/{prefix}", flush=True)
print(f"MODEL_SHA256={expected_sha256}", flush=True)
print(f"SOURCE_REVISION={expected_revision}", flush=True)
print(f"MODEL_NAME={model_name}", flush=True)
print(f"MODEL_VERSION={model_version}", flush=True)
print("PASS: model artifact onboarding completed", flush=True)
