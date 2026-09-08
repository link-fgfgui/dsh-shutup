#!/usr/bin/env python3
"""Upstream compat watchdog for the dsh-shutup bundle.

dsh-shutup integrates with three upstream surfaces of deepseek-harness by
name/shape (it cannot use semver: loader patches and service monkey-patches
bind to exact row ids, service names, method names and provider shapes):

  1. web-startup CLI provider  (packages/bundle/web-app/src/startup.ts)
  2. web-runtime row config    (packages/bundle/web-app/{cordis.patch.yml,src/index.ts})
  3. connection token gate     (packages/client/connection/src/{rpc-host,browser-auth}.ts,
                                packages/host/frontend-static/src/index.ts,
                                packages/boot/cmdline/src/index.ts)

This script fetches those files from the upstream repo at a ref (default HEAD)
and asserts every anchor our bundle relies on is still there, in the same
shape. Any drift -- or any fetch failure after retries -- prints what broke
and exits 1 so the scheduled GitHub Action fails loudly.

Usage:
    python scripts/check_upstream.py                  # check upstream HEAD
    python scripts/check_upstream.py --ref v0.2.0     # check a tag/branch/SHA
    python scripts/check_upstream.py --local C:\\path\\to\\deepseek-harness
                                                      # check a local checkout (no network)

Exit codes: 0 = compatible, 1 = drift/fetch failure, 2 = usage error.
Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_REPO = "deepseek-ai/deepseek-harness"
DEFAULT_REF = "HEAD"
RAW_BASE = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"


@dataclass
class FileChecks:
    path: str
    patterns: list[tuple[str, str]] = field(default_factory=list)  # (label, regex)


# Every (label, pattern) below is an anchor dsh-shutup depends on.
# startup.js mirrors startup.ts minus the 0.0.0.0 guard; cordis.patch.yml
# disables the `web-startup` row and restates the `web-runtime` config whole;
# index.js monkey-patches the `connection` service methods.
CHECKS: list[FileChecks] = [
    FileChecks(
        "packages/bundle/web-app/src/startup.ts",
        [
            ("plugin name", r"export const name = 'web-startup'"),
            ("injects cmdlineArgs", r"export const inject = \['cmdlineArgs'\]"),
            ("service name", r"WEB_STARTUP_SERVICE = 'webStartup'"),
            ("--host flag", r"\.option\('--host <host>'"),
            ("--no-open flag", r"\.option\('--no-open'"),
            ("--port flag", r"\.option\('--port <port>'"),
            ("--trusted-host flag", r"--trusted-host <authority\.\.\.>"),
            ("0.0.0.0 guard present", r"options\.host === '0\.0\.0\.0'"),
            ("provides openBrowser", r"openBrowser: options\.open"),
            ("provides trustedHosts", r"trustedHosts: options\.trustedHost"),
            ("parseCmdline 2-arg call", r"parseCmdline\(ctx, program\)"),
        ],
    ),
    FileChecks(
        "packages/bundle/web-app/cordis.patch.yml",
        [
            ("web-startup row", r"(?m)^\s*- id: web-startup\s*$"),
            ("webserver row", r"(?m)^\s*- id: webserver\s*$"),
            ("web-runtime row", r"(?m)^\s*- id: web-runtime\s*$"),
            ("connection row", r"(?m)^\s*- id: connection\s*$"),
        ],
    ),
    FileChecks(
        "packages/bundle/web-app/src/index.ts",
        [
            ("openBrowser config key", r"openBrowser: z\.boolean\(\)"),
            ("printUrl config key", r"printUrl: z\.boolean\(\)"),
            ("surfaceContext config key", r"surfaceContext: z\.boolean\(\)"),
            ("trustedHosts config key", r"trustedHosts: z\.array\(String\)"),
            ("prints authenticatedUrl", r"connection\.authenticatedUrl\("),
            ("0.0.0.0 LAN-trust path", r"ALL_INTERFACES_HOST = '0\.0\.0\.0'"),
        ],
    ),
    FileChecks(
        "packages/client/connection/src/rpc-host.ts",
        [
            ("HostConnectionService class", r"class HostConnectionService"),
            ("service name", r"super\(ctx, 'connection'\)"),
            ("requestRejection method", r"requestRejection\(request"),
            ("trust fence 403", r"return 403"),
            ("auth gate 401", r"\? undefined : 401"),
            ("authorizeIndex method", r"authorizeIndex\(request"),
            ("authenticatedUrl method", r"authenticatedUrl\(baseUrl"),
        ],
    ),
    FileChecks(
        "packages/client/connection/src/browser-auth.ts",
        [
            ("BrowserAuth class", r"class BrowserAuth"),
            ("authenticatedUrl method", r"authenticatedUrl\("),
            ("authorizeIndex method", r"authorizeIndex\("),
            ("isAuthenticated method", r"isAuthenticated\("),
        ],
    ),
    FileChecks(
        "packages/host/frontend-static/src/index.ts",
        [
            ("index gated on connection", r"connection\.authorizeIndex"),
        ],
    ),
    FileChecks(
        "packages/boot/cmdline/src/index.ts",
        [
            ("parseCmdline signature", r"export function parseCmdline\(ctx: Context, program: Command\)"),
        ],
    ),
]


def fetch_remote(url: str, timeout: int, retries: int) -> str:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dsh-shutup-compat-watchdog"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"fetch failed after {retries} tries: {last}")


def load_file(path: str, args: argparse.Namespace) -> str:
    if args.local:
        import os

        full = os.path.join(args.local, *path.split("/"))
        with open(full, encoding="utf-8") as fh:
            return fh.read()
    url = RAW_BASE.format(repo=args.repo, ref=args.ref, path=path)
    return fetch_remote(url, args.timeout, args.retries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO, help="upstream repo (default: %(default)s)")
    parser.add_argument("--ref", default=DEFAULT_REF, help="upstream ref: HEAD/tag/branch/SHA (default: %(default)s)")
    parser.add_argument("--local", default=None, help="check a local checkout instead of fetching")
    parser.add_argument("--timeout", type=int, default=20, help="per-request seconds (default: %(default)s)")
    parser.add_argument("--retries", type=int, default=3, help="fetch retries (default: %(default)s)")
    args = parser.parse_args(argv)

    source = args.local if args.local else f"{args.repo}@{args.ref}"
    print(f"dsh-shutup compat check vs {source}")

    failures: list[str] = []
    passed = 0
    total = 0
    for fc in CHECKS:
        try:
            text = load_file(fc.path, args)
        except (RuntimeError, OSError, UnicodeDecodeError) as exc:
            print(f"[FETCH-FAIL] {fc.path}: {exc}")
            failures.append(f"{fc.path} :: <fetch> :: {exc}")
            total += len(fc.patterns)
            continue
        file_ok = 0
        for label, pattern in fc.patterns:
            total += 1
            if re.search(pattern, text):
                passed += 1
                file_ok += 1
            else:
                failures.append(f"{fc.path} :: {label} :: {pattern}")
        status = "ok" if file_ok == len(fc.patterns) else "DRIFT"
        print(f"[{status}] {fc.path} ({file_ok}/{len(fc.patterns)})")

    print(f"--- {passed}/{total} anchors hold ---")
    if failures:
        print("DRIFT DETECTED (fix dsh-shutup or pin upstream):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("upstream compatible with dsh-shutup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
