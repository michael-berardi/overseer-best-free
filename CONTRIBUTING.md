# Contributing

Thanks for your interest in improving `overseer-best-free`.

## Ground rules

- **Zero runtime dependencies.** Standard library only. If a change needs a dependency, it needs a very strong argument.
- **Offline tests.** `python -m unittest discover -s tests -v` must pass without network access; add fixtures under `tests/fixtures/` rather than live calls.
- **Keep the public surface small.** The value of this package is that it is trivial to vendor and audit.

## Workflow

1. Fork, create a feature branch.
2. Make the change with tests.
3. Run the full suite and `python -m overseer_best_free --top 3 --json` as a live smoke check.
4. Open a pull request describing the behavior change.

## Reporting bugs

Open an issue with the catalog output (`--json`) at the time of the problem — stale or surprising rankings are almost always catalog-shape questions, and the fixture makes them reproducible.
