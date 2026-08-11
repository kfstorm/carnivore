#!/usr/bin/env python3

"""Validate desensitized runtime evidence for the pinned Stealth layer."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from typing import Any


EXPECTED_CHROME_MAJOR = "130"
EXPECTED_PLATFORM = "MacIntel"
UA_CHROME_PATTERN = re.compile(r"(?:Headless)?Chrome/(\d+)")
SEC_CH_UA_PATTERN = re.compile(r"Chrom(?:e|ium)\";v=\"(\d+)\"")


class _IdentityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre" and dict(attrs).get("id") == "identity":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre" and self._capture:
            self._capture = False

    def value(self) -> str:
        return html.unescape("".join(self._parts)).strip()


def _fail(message: str) -> ValueError:
    return ValueError(message)


def parse_identity(document: str) -> dict[str, Any]:
    parser = _IdentityParser()
    parser.feed(document)
    raw_identity = parser.value()
    if not raw_identity:
        raise _fail("identity marker is missing")
    try:
        identity = json.loads(raw_identity)
    except json.JSONDecodeError as error:
        raise _fail("identity marker is not valid JSON") from error
    if not isinstance(identity, dict):
        raise _fail("identity marker is not an object")

    user_agent = identity.get("userAgent")
    platform = identity.get("platform")
    webdriver = identity.get("webdriver")
    sec_ch_ua = identity.get("secChUa")
    if not all(isinstance(value, str) for value in (user_agent, platform, sec_ch_ua)):
        raise _fail("identity fields are incomplete")
    if platform != EXPECTED_PLATFORM or webdriver is not False:
        raise _fail("browser platform or webdriver contract failed")
    if "HeadlessChrome" in user_agent or "HeadlessChrome" in sec_ch_ua:
        raise _fail("headless browser identity detected")

    user_agent_majors = UA_CHROME_PATTERN.findall(user_agent)
    sec_ch_ua_majors = SEC_CH_UA_PATTERN.findall(sec_ch_ua)
    if user_agent_majors != [EXPECTED_CHROME_MAJOR]:
        raise _fail("user-agent Chrome major contract failed")
    if EXPECTED_CHROME_MAJOR not in sec_ch_ua_majors:
        raise _fail("client-hint Chrome major contract failed")
    if set(user_agent_majors + sec_ch_ua_majors) != {EXPECTED_CHROME_MAJOR}:
        raise _fail("browser identity reports multiple Chrome majors")

    return {
        "status": "passed",
        "chrome_major": EXPECTED_CHROME_MAJOR,
        "platform": EXPECTED_PLATFORM,
        "webdriver": False,
    }


def parse_runtime_metadata(
    document: str,
    expected_version: str,
    expected_wheel_sha256: str,
    expected_source_commit: str,
    expected_license: str,
) -> dict[str, str]:
    try:
        metadata = json.loads(document)
    except json.JSONDecodeError as error:
        raise _fail("runtime metadata is not valid JSON") from error
    if not isinstance(metadata, dict):
        raise _fail("runtime metadata is not an object")
    version = metadata.get("version")
    license_name = metadata.get("license")
    wheel_sha256 = metadata.get("wheel_sha256")
    source_commit = metadata.get("source_commit")
    requirement = metadata.get("requirement")
    expected_requirement = (
        f"playwright-stealth=={expected_version} --hash=sha256:{expected_wheel_sha256}"
    )
    if (
        version != expected_version
        or license_name != expected_license
        or wheel_sha256 != expected_wheel_sha256
        or source_commit != expected_source_commit
        or requirement != expected_requirement
    ):
        raise _fail("runtime Stealth metadata does not match the lock")
    return {
        "status": "passed",
        "version": version,
        "wheel_sha256": wheel_sha256,
        "source_commit": source_commit,
        "license": license_name,
        "requirement": requirement,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    identity = subparsers.add_parser("identity")
    identity.add_argument("--input", default="-", help="HTML file, or - for stdin")
    identity.set_defaults(handler=parse_identity)
    runtime = subparsers.add_parser("runtime")
    runtime.add_argument("--input", default="-", help="JSON file, or - for stdin")
    runtime.add_argument("--version", required=True)
    runtime.add_argument("--wheel-sha256", required=True)
    runtime.add_argument("--source-commit", required=True)
    runtime.add_argument("--license", required=True)
    runtime.set_defaults(handler=parse_runtime_metadata)
    return parser


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as source:
        return source.read()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "runtime":
            result = args.handler(
                _read_input(args.input),
                args.version,
                args.wheel_sha256,
                args.source_commit,
                args.license,
            )
        else:
            result = args.handler(_read_input(args.input))
    except (OSError, ValueError) as error:
        print(f"runtime evidence failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
