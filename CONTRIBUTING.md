# Contributing

This is a personal portfolio project, but PRs are welcome — particularly
ones that fix bugs in the failover/failback logic or improve the
realism of the simulation.

## Local development

```bash
make up           # bring up the stack
make pool         # check origin states
make drill-failover
make drill-failback
make down
```

## Running tests

```bash
make test
```

## Submitting a change

1. Fork, branch from `main`.
2. Keep changes scoped — one concern per PR.
3. If changing the canary or health-check logic, add a test that covers
   the new behaviour. The unit tests in `router/tests/test_canary.py`
   are the model.
4. Open a PR against `main`. CI must be green.

## Style

- Python 3.12, formatted by ruff
- 100-char line limit
- Async everywhere on the I/O path
- Type annotations on every public function
