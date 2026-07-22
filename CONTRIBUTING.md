# Contributing to printed-business-card

Thanks for being here. Issues, bug reports and pull requests are all welcome.

## The local loop

```bash
git clone https://github.com/noluyorAbi/printed-business-card
cd printed-business-card

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/python build_card.py
```

The tests must pass and `build_card.py` must run cleanly before a pull request
is reviewed. CI runs the same two commands on Linux, where the macOS Arial
font is absent; the script falls back to DejaVu Sans there, so do not hardcode
new font paths without a fallback.

## What a good pull request looks like

- One logical change per pull request.
- Conventional Commits messages (`fix:`, `feat:`, `docs:`, ...).
- If you change geometry, include the regenerated `assets/preview.png` and
  confirm the QR test still passes; a card that no longer scans is a
  regression even when it renders beautifully.

## Licensing of contributions

This project is licensed under the MIT License. By submitting a pull request
you agree that your contribution is licensed under the same terms. No separate
contributor agreement is required.

## House rules

No emoji, and no em dashes or en dashes as punctuation, anywhere in the
repository. CI enforces the dash rule.
