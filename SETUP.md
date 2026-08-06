# Pushing this repo

Commit in increments, not one drop. `initial commit` with 25 files tells a
different story than a build log. Suggested sequence:

```bash
cd financial-wellness-lab
git init -b main

git add README.md DECISIONS.md LIMITATIONS.md pyproject.toml .gitignore
git commit -m "scaffold: thesis, decision records, and stated limitations"

git add shared/
git commit -m "shared: explanation layer with an allowlisted fact boundary"

git add eligibility/rules.py eligibility/__init__.py
git commit -m "eligibility: deterministic rules, every denial carries a remedy"

git add eligibility/tests/
git commit -m "eligibility: assert the narrator cannot see decision inputs"

git add eligibility/demo.py eligibility/README.md
git commit -m "eligibility: runnable demo, degrades cleanly without an API key"

git add card_economics/assumptions.yaml card_economics/model.py card_economics/__init__.py
git commit -m "card economics: config-driven paths with pre-declared walk-away thresholds"

git add card_economics/tests/
git commit -m "card economics: assert every threshold actually binds"

git add card_economics/compare.py card_economics/README.md
git commit -m "card economics: comparison runner and memo layer"

git add ewa_sim/
git commit -m "ewa sim: scope note for the planned third module"
```

Then create the repo on GitHub (public) and push:

```bash
git remote add origin git@github.com:<you>/financial-wellness-lab.git
git push -u origin main
```

## Verify before you push

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                          # 23 passing
python -m eligibility.demo
python -m card_economics.compare
```

## Repo settings

- **Public** from day one. A private repo you have to grant access to during a
  call is a repo that does not exist.
- **Description:** "Where consumer-credit decisions should be deterministic,
  and where language belongs."
- **Topics:** `fintech`, `consumer-credit`, `product-strategy`, `llm`
- No company name anywhere, in the repo name or the description.

## Optional, worth ten minutes

Add `.github/workflows/test.yml` running `pytest` on push. A green badge in the
README does more for credibility than another module.
