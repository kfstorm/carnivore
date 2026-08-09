#!/usr/bin/env python3

"""Build reproducible, self-contained release assets for Carnivore."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_SOURCE = PROJECT_ROOT / "skills/carnivore-fetch/bin/carnivore-fetch"
SKILL_SOURCE = PROJECT_ROOT / "skills/carnivore-fetch/SKILL.md"
LOCK_SOURCE = PROJECT_ROOT / "docker/core.lock"
REPOSITORY = "ghcr.io/kfstorm/carnivore"
GITHUB_RELEASE_BASE = "https://github.com/kfstorm/carnivore/releases/download"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SEMVER_NUMBER = r"(?:0|[1-9][0-9]*)"
STABLE_TAG_PATTERN = re.compile(
    rf"^v{SEMVER_NUMBER}\.{SEMVER_NUMBER}\.{SEMVER_NUMBER}$"
)
RC_TAG_PATTERN = re.compile(
    rf"^v{SEMVER_NUMBER}\.{SEMVER_NUMBER}\.{SEMVER_NUMBER}" rf"-rc\.{SEMVER_NUMBER}$"
)


@dataclass(frozen=True)
class ReleaseTag:
    tag: str
    version: str
    channel: str


def parse_release_tag(tag: str, channel: str | None = None) -> ReleaseTag:
    """Validate a release tag and return its normalized release metadata."""
    if RC_TAG_PATTERN.fullmatch(tag):
        parsed = ReleaseTag(tag=tag, version=tag[1:], channel="rc")
    elif STABLE_TAG_PATTERN.fullmatch(tag):
        parsed = ReleaseTag(tag=tag, version=tag[1:], channel="stable")
    else:
        raise ValueError(
            "release tag must match vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-rc.N"
        )
    if channel is not None and parsed.channel != channel:
        raise ValueError(f"release tag {tag} is not a {channel} release")
    return parsed


def _require_digest(value: str, name: str) -> str:
    if not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a sha256 digest")
    return value


def _require_commit(value: str) -> str:
    if not COMMIT_PATTERN.fullmatch(value):
        raise ValueError("commit must be a 40-character lowercase Git SHA")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, content: str | bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    path.chmod(mode)


def _render_wrapper(release: ReleaseTag, image: str) -> str:
    wrapper = WRAPPER_SOURCE.read_text(encoding="utf-8")
    version_pattern = r'(?m)^wrapper_version="[^"]+"$'
    image_pattern = r'(?m)^default_image="[^"]+"$'
    wrapper, version_count = re.subn(
        version_pattern,
        f'wrapper_version="{release.version}"',
        wrapper,
    )
    wrapper, image_count = re.subn(
        image_pattern,
        f'default_image="{image}"',
        wrapper,
    )
    if version_count != 1 or image_count != 1:
        raise ValueError("wrapper version or image marker is missing")
    return wrapper


def _render_installer(release: ReleaseTag, wrapper_sha256: str) -> str:
    wrapper_url = f"{GITHUB_RELEASE_BASE}/{release.tag}/carnivore"
    return f"""#!/bin/sh

set -eu

release_tag="{release.tag}"
wrapper_url="{wrapper_url}"
wrapper_sha256="{wrapper_sha256}"
target_path="${{HOME}}/.local/bin/carnivore"
force=false

while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      force=true
      shift
      ;;
    --prefix)
      if [ $# -lt 2 ]; then
        echo "Missing value for --prefix" >&2
        exit 1
      fi
      target_path="$2/carnivore"
      shift 2
      ;;
    --target)
      if [ $# -lt 2 ]; then
        echo "Missing value for --target" >&2
        exit 1
      fi
      target_path="$2"
      shift 2
      ;;
    --version)
      printf '%s\\n' "$release_tag"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ -e "${{target_path}}" ] && [ "${{force}}" != "true" ]; then
  echo "Refusing to overwrite existing file: ${{target_path}}" >&2
  echo "Pass --force to overwrite it." >&2
  exit 1
fi

target_dir=$(dirname "${{target_path}}")
mkdir -p "${{target_dir}}"
temporary_path=$(mktemp "${{TMPDIR:-/tmp}}/carnivore.XXXXXX")
cleanup() {{
  rm -f "${{temporary_path}}"
}}
trap cleanup EXIT HUP INT TERM

curl -fsSL "${{wrapper_url}}" -o "${{temporary_path}}"
if command -v sha256sum >/dev/null 2>&1; then
  actual_sha256=$(sha256sum "${{temporary_path}}" | cut -d' ' -f1)
else
  actual_sha256=$(shasum -a 256 "${{temporary_path}}" | cut -d' ' -f1)
fi
if [ "${{actual_sha256}}" != "${{wrapper_sha256}}" ]; then
  echo "Downloaded wrapper checksum does not match release ${{release_tag}}" >&2
  exit 1
fi

chmod 0755 "${{temporary_path}}"
mv -f "${{temporary_path}}" "${{target_path}}"
trap - EXIT HUP INT TERM
echo "Installed carnivore ${{release_tag}} to ${{target_path}}"
"""


def _parse_lock() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in LOCK_SOURCE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _component_facts(platforms: list[dict[str, str]]) -> list[dict[str, Any]]:
    lock = _parse_lock()
    components = [
        ("base-image", lock.get("BASE_IMAGE_REF", "")),
        ("node", lock.get("NODE_VERSION", "")),
        ("playwright", lock.get("PLAYWRIGHT_VERSION", "")),
        ("chromium", lock.get("CHROMIUM_REVISION", "")),
        ("pandoc", lock.get("PANDOC_VERSION", "")),
        ("monolith", lock.get("MONOLITH_VERSION", "")),
        ("readability-lock", lock.get("NPM_LOCK_SHA256", "")),
    ]
    platform_names = [item["platform"] for item in platforms]
    facts = []
    for name, version in components:
        fact: dict[str, Any] = {
            "component": name,
            "version": version,
            "platforms": platform_names,
        }
        if name == "node":
            fact["digests"] = {
                "linux/amd64": lock.get("NODE_SHA256_AMD64", ""),
                "linux/arm64": lock.get("NODE_SHA256_ARM64", ""),
            }
        elif name == "chromium":
            fact["digests"] = {
                "linux/amd64": lock.get("CHROMIUM_SHA256_AMD64", ""),
                "linux/arm64": lock.get("CHROMIUM_SHA256_ARM64", ""),
            }
        elif name == "pandoc":
            fact["digests"] = {
                "linux/amd64": lock.get("PANDOC_SHA256_AMD64", ""),
                "linux/arm64": lock.get("PANDOC_SHA256_ARM64", ""),
            }
        elif name == "monolith":
            fact["digests"] = {
                "linux/amd64": lock.get("MONOLITH_SHA256_AMD64", ""),
                "linux/arm64": lock.get("MONOLITH_SHA256_ARM64", ""),
            }
        facts.append(fact)
    return facts


def _spdx_document(
    release: ReleaseTag,
    commit: str,
    image: str,
    digest: str,
    platforms: list[dict[str, str]],
) -> str:
    image_package = {
        "SPDXID": "SPDXRef-Image",
        "name": image,
        "versionInfo": release.version,
        "downloadLocation": f"{image}@{digest}",
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "filesAnalyzed": False,
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:docker/{image}@{digest}",
            }
        ],
    }
    packages = [image_package]
    for index, fact in enumerate(_component_facts(platforms), start=1):
        packages.append(
            {
                "SPDXID": f"SPDXRef-Component{index}",
                "name": fact["component"],
                "versionInfo": fact["version"],
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "filesAnalyzed": False,
                "annotations": [
                    {
                        "annotationType": "OTHER",
                        "annotator": "Tool: carnivore-release",
                        "comment": json.dumps(fact, sort_keys=True),
                    }
                ],
            }
        )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"carnivore-{release.version}",
        "documentNamespace": (
            f"https://github.com/kfstorm/carnivore/spdx/{release.tag}/{commit}"
        ),
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: carnivore-release"],
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Image",
            }
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _provenance(
    release: ReleaseTag,
    commit: str,
    image: str,
    digest: str,
    workflow_run: str,
) -> str:
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": image,
                "digest": {"sha256": digest.removeprefix("sha256:")},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/kfstorm/carnivore/release",
                "externalParameters": {
                    "release_tag": release.tag,
                    "channel": release.channel,
                },
                "internalParameters": {},
                "resolvedDependencies": [
                    {
                        "uri": "git+https://github.com/kfstorm/carnivore.git",
                        "digest": {"sha1": commit},
                    }
                ],
            },
            "runDetails": {
                "builder": {
                    "id": "https://github.com/actions/runner",
                },
                "metadata": {"invocationId": workflow_run},
            },
        },
    }
    return json.dumps(statement, separators=(",", ":"), sort_keys=True) + "\n"


def _skill_archive(wrapper: str, skill: str) -> bytes:
    files = {
        "carnivore-fetch/SKILL.md": skill.encode("utf-8"),
        "carnivore-fetch/bin/carnivore": wrapper.encode("utf-8"),
    }
    tar_buffer = io.BytesIO()
    with tarfile.open(
        fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT
    ) as archive:
        for name in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(files[name])
            info.mode = 0o755 if name.endswith("/carnivore") else 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(files[name]))
    return gzip.compress(tar_buffer.getvalue(), mtime=0)


def package_release(
    *,
    tag: str,
    channel: str,
    commit: str,
    image: str,
    digest: str,
    platform_digests: dict[str, str],
    validation: dict[str, Any],
    output: Path,
    workflow_run: str = "local",
) -> dict[str, Any]:
    release = parse_release_tag(tag, channel)
    _require_commit(commit)
    _require_digest(digest, "digest")
    if not image.startswith(f"{REPOSITORY}:") or not image.endswith(f":{tag}"):
        raise ValueError("image must use the exact release tag")
    if not isinstance(platform_digests, dict):
        raise ValueError("platform digests must be a JSON object of strings")
    if any(
        not isinstance(platform, str) or not isinstance(platform_digest, str)
        for platform, platform_digest in platform_digests.items()
    ):
        raise ValueError("platform digests must be a JSON object of strings")
    platforms = []
    for platform, platform_digest in sorted(platform_digests.items()):
        if platform not in ("linux/amd64", "linux/arm64"):
            raise ValueError(f"unsupported platform: {platform}")
        platforms.append(
            {"platform": platform, "digest": _require_digest(platform_digest, platform)}
        )
    if {item["platform"] for item in platforms} != {"linux/amd64", "linux/arm64"}:
        raise ValueError("linux/amd64 and linux/arm64 platform digests are required")
    if not isinstance(validation, dict):
        raise ValueError("validation facts must be a JSON object")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"release output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    wrapper = _render_wrapper(release, image)
    wrapper_path = output / "carnivore"
    _write(wrapper_path, wrapper, 0o755)
    wrapper_sha256 = _sha256(wrapper_path)

    installer = _render_installer(release, wrapper_sha256)
    _write(output / "install-carnivore.sh", installer, 0o755)

    skill = SKILL_SOURCE.read_text(encoding="utf-8")
    skill = skill.replace("bin/carnivore-fetch", "bin/carnivore")
    skill += (
        f"\nThis release pins `{image}` by default. Set `CARNIVORE_IMAGE` to "
        "`latest` or an image digest only when an explicit override is needed.\n"
    )
    archive_name = f"carnivore-fetch-skill-{release.version}.tar.gz"
    _write(output / archive_name, _skill_archive(wrapper, skill))

    sbom_name = "carnivore-sbom.spdx.json"
    _write(
        output / sbom_name,
        _spdx_document(release, commit, image, digest, platforms),
    )
    provenance_name = "carnivore-provenance.intoto.jsonl"
    _write(
        output / provenance_name,
        _provenance(release, commit, image, digest, workflow_run),
    )

    artifact_names = [
        "carnivore",
        "install-carnivore.sh",
        archive_name,
        sbom_name,
        provenance_name,
    ]
    artifacts = [
        {
            "name": name,
            "component": (
                "wrapper"
                if name == "carnivore"
                else "installer"
                if name == "install-carnivore.sh"
                else "skill"
                if name == archive_name
                else "sbom"
                if name == sbom_name
                else "provenance"
            ),
            "platform": "any",
            "sha256": _sha256(output / name),
        }
        for name in artifact_names
    ]
    manifest = {
        "schema_version": 1,
        "release": {
            "tag": release.tag,
            "version": release.version,
            "channel": release.channel,
            "commit": commit,
            "workflow_run": workflow_run,
        },
        "image": {
            "repository": REPOSITORY,
            "tag": release.tag,
            "reference": image,
            "digest_reference": f"{image}@{digest}",
            "digest": digest,
            "platforms": platforms,
        },
        "components": _component_facts(platforms),
        "validation": validation,
        "artifacts": artifacts,
    }
    _write(
        output / "release-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )

    checksum_names = artifact_names + ["release-manifest.json"]
    checksums = "".join(
        f"{_sha256(output / name)}  {name}\n" for name in checksum_names
    )
    _write(output / "SHA256SUMS", checksums)
    return manifest


def verify_manifest(
    manifest_path: Path,
    *,
    expected_tag: str | None = None,
    expected_commit: str | None = None,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release = manifest.get("release", {})
    tag = release.get("tag")
    if not isinstance(tag, str):
        raise ValueError("manifest does not contain a release tag")
    parse_release_tag(tag)
    if expected_tag is not None and tag != expected_tag:
        raise ValueError("manifest release tag does not match the requested tag")
    commit = release.get("commit")
    if not isinstance(commit, str):
        raise ValueError("manifest does not contain a source commit")
    _require_commit(commit)
    if expected_commit is not None and commit != expected_commit:
        raise ValueError("manifest source commit does not match the Git ref")
    image = manifest.get("image", {})
    digest = image.get("digest")
    if not isinstance(digest, str):
        raise ValueError("manifest does not contain an image digest")
    _require_digest(digest, "manifest image digest")
    if image.get("repository") != REPOSITORY or image.get("tag") != tag:
        raise ValueError("manifest image does not use the release tag")
    if image.get("reference") != f"{REPOSITORY}:{tag}":
        raise ValueError("manifest image does not use the release tag")
    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("manifest does not contain validation facts")
    if validation.get("release_gate") not in ("passed", True):
        raise ValueError("release validation did not pass")
    return manifest


def _package_command(args: argparse.Namespace) -> None:
    validation = json.loads(Path(args.validation_json).read_text(encoding="utf-8"))
    platform_digests = json.loads(args.platform_digests)
    package_release(
        tag=args.version,
        channel=args.channel,
        commit=args.commit,
        image=args.image,
        digest=args.digest,
        platform_digests=platform_digests,
        validation=validation,
        output=Path(args.output),
        workflow_run=args.workflow_run,
    )


def _verify_command(args: argparse.Namespace) -> None:
    verify_manifest(
        Path(args.manifest),
        expected_tag=args.tag,
        expected_commit=args.commit,
    )


def _validate_tag_command(args: argparse.Namespace) -> None:
    parse_release_tag(args.tag, args.channel)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    package = commands.add_parser("package", help="build release assets")
    package.add_argument("--version", required=True, help="full Git release tag")
    package.add_argument("--channel", choices=("rc", "stable"), required=True)
    package.add_argument("--commit", required=True)
    package.add_argument("--image", required=True)
    package.add_argument("--digest", required=True)
    package.add_argument("--platform-digests", required=True)
    package.add_argument("--validation-json", required=True)
    package.add_argument("--output", required=True)
    package.add_argument("--workflow-run", default="local")
    package.set_defaults(handler=_package_command)

    verify = commands.add_parser("verify-manifest", help="verify release metadata")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--tag")
    verify.add_argument("--commit")
    verify.set_defaults(handler=_verify_command)

    validate = commands.add_parser("validate-tag", help="validate a release tag")
    validate.add_argument("--tag", required=True)
    validate.add_argument("--channel", choices=("rc", "stable"))
    validate.set_defaults(handler=_validate_tag_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"release error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
