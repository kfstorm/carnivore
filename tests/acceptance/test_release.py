import hashlib
import json
import subprocess
import tarfile
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
WRAPPER = PROJECT_ROOT / "skills/carnivore-fetch/bin/carnivore-fetch"
CANONICAL_WRAPPER = PROJECT_ROOT / "scripts/carnivore"
STEALTH_EVIDENCE = PROJECT_ROOT / "scripts/verify_stealth_evidence.py"


def run_release_packager(output_dir, validation_path):
    return subprocess.run(
        [
            sys.executable,
            "scripts/release.py",
            "package",
            "--version",
            "v1.0.0-rc.1",
            "--channel",
            "rc",
            "--commit",
            "a" * 40,
            "--image",
            "ghcr.io/kfstorm/carnivore:v1.0.0-rc.1",
            "--digest",
            "sha256:" + "b" * 64,
            "--platform-digests",
            json.dumps(
                {
                    "linux/amd64": "sha256:" + "c" * 64,
                    "linux/arm64": "sha256:" + "d" * 64,
                }
            ),
            "--validation-json",
            str(validation_path),
            "--output",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_runtime_identity_probe_accepts_the_supported_browser_contract():
    document = r"""
    <html><body><pre id="identity">{
      "userAgent": "Mozilla/5.0 Chrome/130.0.0.0 Safari/537.36",
      "platform": "MacIntel",
      "webdriver": false,
      "secChUa": "\"Chromium\";v=\"130\", \"Not_A Brand\";v=\"24\""
    }</pre></body></html>
    """
    result = subprocess.run(
        [sys.executable, str(STEALTH_EVIDENCE), "identity"],
        input=document,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "chrome_major": "130",
        "platform": "MacIntel",
        "status": "passed",
        "webdriver": False,
    }


def test_runtime_identity_probe_rejects_headless_or_contradictory_values():
    document = r"""
    <pre id="identity">{
      "userAgent": "Mozilla/5.0 HeadlessChrome/130.0.0.0",
      "platform": "Linux x86_64",
      "webdriver": true,
      "secChUa": "\"Chromium\";v=\"129\""
    }</pre>
    """
    result = subprocess.run(
        [sys.executable, str(STEALTH_EVIDENCE), "identity"],
        input=document,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert (
        result.stderr
        == "runtime evidence failed: browser platform or webdriver contract failed\n"
    )


def test_runtime_metadata_probe_requires_pinned_version_and_license():
    result = subprocess.run(
        [
            sys.executable,
            str(STEALTH_EVIDENCE),
            "runtime",
            "--version",
            "2.0.3",
            "--wheel-sha256",
            "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb",
            "--source-commit",
            "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8",
            "--license",
            "MIT",
        ],
        input=json.dumps(
            {
                "version": "2.0.3",
                "license": "MIT",
                "wheel_sha256": (
                    "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
                ),
                "source_commit": "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8",
                "requirement": (
                    "playwright-stealth==2.0.3 --hash=sha256:"
                    "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
                ),
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "license": "MIT",
        "status": "passed",
        "source_commit": "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8",
        "requirement": (
            "playwright-stealth==2.0.3 --hash=sha256:"
            "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
        ),
        "version": "2.0.3",
        "wheel_sha256": (
            "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
        ),
    }


def test_carnivore_version_does_not_require_docker():
    result = subprocess.run(
        ["/bin/bash", str(WRAPPER), "--version"],
        capture_output=True,
        cwd=PROJECT_ROOT,
        env={"PATH": "/nonexistent", "HOME": str(PROJECT_ROOT)},
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "carnivore 0.1.0\n"
    assert result.stderr == ""

    canonical = subprocess.run(
        ["/bin/bash", str(CANONICAL_WRAPPER), "--version"],
        capture_output=True,
        cwd=PROJECT_ROOT,
        env={"PATH": "/usr/bin:/bin", "HOME": str(PROJECT_ROOT)},
        text=True,
        check=False,
    )
    assert canonical.returncode == 0
    assert canonical.stdout == "carnivore 0.1.0\n"
    assert canonical.stderr == ""


def test_release_packager_publishes_pinned_assets_and_manifest(tmp_path):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(
        json.dumps(
            {
                "release_gate": "passed",
                "offline_native": {"linux/amd64": "passed", "linux/arm64": "passed"},
                "live_smoke": "passed",
                "benchmark": "passed",
                "cache": "verified",
                "stealth": {
                    "version": "2.0.3",
                    "wheel_sha256": (
                        "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
                    ),
                    "source_commit": "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8",
                    "license": "MIT",
                    "platforms": {
                        "linux/amd64": {
                            "digest": "sha256:" + "c" * 64,
                            "identity": "passed",
                            "runtime": "passed",
                        },
                        "linux/arm64": {
                            "digest": "sha256:" + "d" * 64,
                            "identity": "passed",
                            "runtime": "passed",
                        },
                    },
                },
            }
        )
    )
    output_dir = tmp_path / "release"

    result = run_release_packager(output_dir, validation_path)

    assert result.returncode == 0, result.stderr
    expected_assets = {
        "carnivore",
        "install-carnivore.sh",
        "carnivore-fetch-skill-1.0.0-rc.1.tar.gz",
        "carnivore-sbom.spdx.json",
        "carnivore-provenance.intoto.jsonl",
        "release-manifest.json",
        "SHA256SUMS",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_assets

    wrapper = output_dir / "carnivore"
    assert "ghcr.io/kfstorm/carnivore:v1.0.0-rc.1" in wrapper.read_text()
    assert "--network" in wrapper.read_text()
    assert "--cap-drop" in wrapper.read_text()
    version = subprocess.run(
        ["/bin/bash", str(wrapper), "--version"],
        capture_output=True,
        cwd=PROJECT_ROOT,
        env={"PATH": "/nonexistent", "HOME": str(tmp_path)},
        text=True,
        check=False,
    )
    assert version.returncode == 0
    assert version.stdout == "carnivore 1.0.0-rc.1\n"

    installer_check = subprocess.run(
        ["sh", "-n", str(output_dir / "install-carnivore.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert installer_check.returncode == 0, installer_check.stderr
    installer = (output_dir / "install-carnivore.sh").read_text()
    assert "/releases/download/v1.0.0-rc.1/carnivore" in installer
    assert hashlib.sha256(wrapper.read_bytes()).hexdigest() in installer

    with tarfile.open(
        output_dir / "carnivore-fetch-skill-1.0.0-rc.1.tar.gz"
    ) as archive:
        names = set(archive.getnames())
        assert "carnivore-fetch/SKILL.md" in names
        skill_wrapper = archive.extractfile("carnivore-fetch/bin/carnivore")
        assert skill_wrapper is not None
        assert b"ghcr.io/kfstorm/carnivore:v1.0.0-rc.1" in skill_wrapper.read()

    manifest = json.loads((output_dir / "release-manifest.json").read_text())
    assert manifest["release"]["commit"] == "a" * 40
    assert manifest["image"]["tag"] == "v1.0.0-rc.1"
    assert manifest["image"]["reference"] == ("ghcr.io/kfstorm/carnivore:v1.0.0-rc.1")
    assert manifest["image"]["digest"] == "sha256:" + "b" * 64
    assert manifest["image"]["platforms"] == [
        {"platform": "linux/amd64", "digest": "sha256:" + "c" * 64},
        {"platform": "linux/arm64", "digest": "sha256:" + "d" * 64},
    ]
    assert manifest["validation"]["live_smoke"] == "passed"
    stealth = next(
        item
        for item in manifest["components"]
        if item["component"] == "playwright-stealth"
    )
    assert stealth["version"] == "2.0.3"
    assert stealth["wheel_sha256"] == (
        "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
    )
    assert stealth["source_commit"] == "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8"
    assert stealth["license"] == "MIT"

    verified = subprocess.run(
        [
            sys.executable,
            "scripts/release.py",
            "verify-manifest",
            "--manifest",
            str(output_dir / "release-manifest.json"),
            "--tag",
            "v1.0.0-rc.1",
            "--commit",
            "a" * 40,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert verified.returncode == 0, verified.stderr

    sbom = json.loads((output_dir / "carnivore-sbom.spdx.json").read_text())
    purl = sbom["packages"][0]["externalRefs"][0]["referenceLocator"]
    assert purl == "pkg:docker/ghcr.io/kfstorm/carnivore@sha256:" + "b" * 64
    stealth_package = next(
        package
        for package in sbom["packages"]
        if package["name"] == "playwright-stealth"
    )
    assert stealth_package["versionInfo"] == "2.0.3"
    assert stealth_package["licenseDeclared"] == "MIT"

    checksum_lines = (output_dir / "SHA256SUMS").read_text().splitlines()
    checksums = {
        name: digest
        for digest, name in (line.split("  ", 1) for line in checksum_lines)
    }
    assert checksums["carnivore"] == hashlib.sha256(wrapper.read_bytes()).hexdigest()


def test_release_workflows_publish_and_promote_without_rebuilding():
    acceptance = (PROJECT_ROOT / ".github/workflows/release-acceptance.yml").read_text()
    promotion = (PROJECT_ROOT / ".github/workflows/release-promotion.yml").read_text()
    smoke = (PROJECT_ROOT / "scripts/live-smoke.sh").read_text()

    assert '"v*-rc*"' in acceptance
    assert "docker buildx imagetools create" in acceptance
    assert "release-manifest.json" in acceptance
    assert "actions/attest-build-provenance" in acceptance
    assert "concurrency:" in acceptance
    assert "group: carnivore-release-candidate" in acceptance
    assert "publish_rc:" in acceptance
    assert "Validation-only run for" in acceptance
    assert "image_kind=validation" in acceptance
    assert (
        "if: ${{ needs.release-gate.result == 'success' && "
        "(github.event_name == 'push' || inputs.publish_rc) }}"
    ) in acceptance
    assert "Verify promoted RC tag" in acceptance
    assert "--format '{{json .Manifest}}'" in acceptance
    assert "pandoc/actions/setup" not in acceptance
    assert "PANDOC_SHA256_ARM64" in acceptance
    assert "LIBSSL1_1_SHA256_ARM64" in acceptance
    assert "dpkg --unpack /tmp/libssl1.1.deb" in acceptance
    assert "verify_stealth_evidence.py identity" in acceptance
    assert "verify_stealth_evidence.py runtime" in acceptance
    assert "Require complete native Stealth evidence" in acceptance
    assert "candidate-manifest.json" in acceptance
    assert "https://www.gov.cn/" in smoke
    assert "https://www.gov.cn/zhengce/" in smoke
    assert "content_7077748.htm" in smoke
    assert "rfleury.com" not in smoke
    assert "mp.weixin.qq.com" not in smoke
    assert acceptance.index("Reject an existing GitHub release") < acceptance.index(
        "Promote validated digest to exact RC tag"
    )
    assert acceptance.index(
        "Require complete native Stealth evidence"
    ) < acceptance.index("Promote validated digest to exact RC tag")
    assert "docker buildx imagetools create" in promotion
    assert '--tag "${REGISTRY_IMAGE}:latest"' in promotion
    assert "docker/build-push-action" not in promotion
    assert "git tag -a" in promotion
    assert "concurrency:" in promotion
    assert "group: carnivore-stable-release" in promotion
    assert ".validation + {promoted_from" in promotion
    assert "rc_platform_digests" in promotion
    assert promotion.index(
        "Reject an existing stable GitHub release"
    ) < promotion.index("Promote the verified digest without rebuilding")
    assert "Verify promoted image tags" in promotion


def test_release_tag_validation_rejects_semver_leading_zeroes():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/release.py",
            "validate-tag",
            "--tag",
            "v01.2.3-rc.01",
            "--channel",
            "rc",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "release tag must match" in result.stderr


def test_release_packager_rejects_non_object_platform_digests(tmp_path):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps({"release_gate": "passed"}))
    result = subprocess.run(
        [
            sys.executable,
            "scripts/release.py",
            "package",
            "--version",
            "v1.0.0-rc.1",
            "--channel",
            "rc",
            "--commit",
            "a" * 40,
            "--image",
            "ghcr.io/kfstorm/carnivore:v1.0.0-rc.1",
            "--digest",
            "sha256:" + "b" * 64,
            "--platform-digests",
            "[]",
            "--validation-json",
            str(validation_path),
            "--output",
            str(tmp_path / "release"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "platform digests" in result.stderr


def test_release_packager_rejects_missing_stealth_evidence(tmp_path):
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps({"release_gate": "passed"}))
    result = run_release_packager(tmp_path / "release", validation_path)

    assert result.returncode == 2
    assert "Stealth evidence" in result.stderr
