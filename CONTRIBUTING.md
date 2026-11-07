# Contributing

Thanks for your interest in BiteSIze!

## Setup

1. Fork and clone the repo.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your local credentials (never commit `.env`).

## Running tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov
```

Add or update tests when changing behavior. CI runs the suite plus coverage, `pip-audit`, and gitleaks.

## Pull requests

- Keep changes focused and include tests for behavior changes.
- Do not commit secrets: `.env`, `data/`, `token.json`, or `credentials.json`.
- Run the full test suite before opening a PR.
- Commit messages and PR titles use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `<type>(<optional scope>): <description>`, lowercase, imperative, no trailing period. Mark breaking changes with `!` and a `BREAKING CHANGE:` footer.
- Fill in the PR template's **Release impact** boxes; they decide the next version.

## Releases

Releases are [SemVer](https://semver.org/) tags (`vMAJOR.MINOR.PATCH`) on `main`, each with a GitHub Release holding its notes. A breaking change bumps MAJOR (MINOR before `v1.0.0`), a new feature bumps MINOR, anything else bumps PATCH.

## Security

See [SECURITY.md](SECURITY.md) for the threat model and how to report vulnerabilities.
