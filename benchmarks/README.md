# Release Benchmarks

`corpus.yml` is the frozen, local benchmark corpus. It uses the deterministic
server in `tests/acceptance/fixture_server.py`, so benchmark results do not
depend on public sites.

The benchmark runs every corpus case five times and writes a versioned JSON
result. `results/stable.json` is the previous stable source baseline, and
`results/stable-image.json` is the previous stable image baseline. Benchmarks
must compare within the same execution mode. A candidate fails strict comparison
when any body anchor, forbidden-noise,
structure, or metadata pass rate regresses, when any output exceeds 10 MiB, or
when total median time worsens by more than both 20% and one second or total
p95 worsens by more than 30%. An output-size increase greater than 25% is
reported for review without being a performance gate.

The checked-in image baseline was captured from the immutable image digest
`ghcr.io/kfstorm/carnivore@sha256:15be6da5a42510f6bc08c5ebf58d8d7c5f2ec316ea3539aba5a3c10d54733171`.

Changes to the corpus, assertions, thresholds, or stable baseline must be made
as a separate pull request with an explained evidence diff. The CI input review
workflow and `.github/CODEOWNERS` enforce the review boundary.

Run a local benchmark after installing the locked core tools:

```sh
python scripts/benchmark.py \
  --corpus benchmarks/corpus.yml \
  --runs 5 \
  --baseline benchmarks/results/stable.json \
  --out /tmp/carnivore-benchmark.json \
  --strict
```
