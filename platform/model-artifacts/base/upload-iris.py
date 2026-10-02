import hashlib
import json
import os
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


artifact_dir = Path("/model")
expected_revision = os.environ["EXPECTED_SOURCE_REVISION"]
expected_sha256 = os.environ["EXPECTED_MODEL_SHA256"]
bucket = os.environ["MODEL_BUCKET"]
prefix = os.environ["MODEL_PREFIX"].rstrip("/")

if bucket != "models":
    fail("unexpected model bucket")

if prefix != f"sklearn/iris/v2/{expected_revision}":
    fail("destination does not match the approved Iris release path")

model_bytes = (artifact_dir / "model.joblib").read_bytes()

if digest(model_bytes) != expected_sha256:
    fail("model does not match the approved release checksum")

manifest = json.loads((artifact_dir / "manifest.json").read_text())

if manifest["source"]["revision"] != expected_revision:
    fail("manifest source revision does not match the approved release")

subprocess.run(
    [
        sys.executable,
        "/opt/iris/verify.py",
        "--artifact-dir",
        str(artifact_dir),
        "--expected-model-version",
        "v2",
    ],
    check=True,
)

print("PASS: approved source, model checksum and bundle verified", flush=True)

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
files = ("model.joblib", "checksums.sha256", "manifest.json")
payloads = {
    name: (artifact_dir / name).read_bytes()
    for name in files
}

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
                    "model-version": "v2",
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
print("PASS: Iris artifact onboarding completed", flush=True)
