# CI And Release Acceptance

Carnivore keeps deterministic product regressions, public-site drift, and
performance changes in separate gates. The release workflows consume the same
scripts as local verification so an artifact can be reproduced without relying
on a GitHub-specific assertion.

## Gates

| Gate | Trigger | Budget | Blocking behavior |
| --- | --- | ---: | --- |
| Offline contract and fixture suite | Every push, pull request, and manual run | 30 minutes | Always blocks on failure |
| Live smoke | Daily schedule, manual run, and release candidate | 20 minutes | Three consecutive failures fail the run; not a pull-request gate |
| Benchmark | Weekly schedule, manual run, and release candidate | 120 minutes | Weekly failure alerts; an RC needs an independent confirming failure |
| Native RC acceptance | Release-candidate tag or manual run | 60 minutes | Requires amd64 and arm64 offline results plus cache evidence |

The five historical public-site tests in `carnivore-lib/tests/test.py` are
marked `live`. One pre-contract legacy timing test is an explicit expected
failure because the old archive CLI waits for network idle by design. The
offline command still executes it so the complete fixture suite is visible;
live site checks belong only to `scripts/live-smoke.sh` and the daily/RC
workflow.

## Live Smoke

The smoke script checks three fixed public pages: a static GitHub Pages article,
a dynamic Substack article, and a WeChat article. Each page is attempted once
and retried twice after failure. A page is reported as a failure only after all
three attempts fail consecutively. Evidence contains page names and statuses,
not page bodies or diagnostics.

## Benchmarks

`benchmarks/corpus.yml` is a versioned local corpus served by
`tests/acceptance/fixture_server.py`. Every case runs five times. Each result
records output size, body-anchor, forbidden-noise, structure, and metadata pass
rates, plus total median and p95 duration. The comparison uses
`benchmarks/results/stable.json` as the previous stable baseline.

Strict comparison rules are:

- Any quality pass-rate regression blocks.
- Any output above 10 MiB blocks.
- Total median time must not worsen by more than 20% and more than one second.
- Total p95 time must not worsen by more than 30%.
- An absolute median output-size change above 25% emits review evidence without being
  an automatic performance failure.

Release candidates run two independent benchmark jobs. The release gate blocks
only when both runs report a strict failure, which confirms timing and quality
regressions independently instead of treating one noisy runner as proof.

## Input Review Policy

Corpus cases, fixture behavior, benchmark thresholds, stable baselines, locked
image inputs, and Docker build behavior are CI inputs rather than ordinary
implementation changes. `.github/CODEOWNERS` assigns them maintainer review.
`CI Input Review` also fails a pull request that mixes a protected CI input with
other product changes, forcing the input update into a separate reviewed change.
The one-time introduction of a new CI input may also change the gate
implementation, but its pull request must include `CI input bootstrap:` in
addition to the rationale marker.

Every protected change must include an explained evidence diff: what changed,
why the old contract is no longer correct, and the relevant offline, smoke, or
benchmark result. The pull request body must contain the marker
`CI input change rationale:`. Do not update `stable.json` merely to make a
candidate pass.

## Local Verification

Run the offline suite with:

```sh
scripts/run-tests.sh
```

Run the benchmark with:

```sh
python scripts/benchmark.py \
  --corpus benchmarks/corpus.yml \
  --runs 5 \
  --baseline benchmarks/results/stable.json \
  --out /tmp/carnivore-benchmark.json \
  --strict
```

Run workflow shell checks with `shellcheck scripts/*.sh` and validate workflow
syntax with `actionlint .github/workflows/*.yml` when those tools are installed.
