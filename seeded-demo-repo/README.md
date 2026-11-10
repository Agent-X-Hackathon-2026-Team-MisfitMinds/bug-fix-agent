# Seeded Demo Repository

This repository contains three deterministic Python bugs for the
Bug-Fix Agent hackathon demo (Team MisfitMinds, Agent-X Hackathon 2026).

## Bugs

| # | Function | Bug type | Expected behaviour | Issue confidence |
|---|----------|----------|-------------------|------------------|
| 1 | `calculate_discount(100, 20)` | Off-by-one | Returns `80` | High |
| 2 | `validate_age(65)` | Wrong boundary | Returns `True` | Medium |
| 3 | `get_user_profile(999)` | Missing null check | Returns `None` | Low / could not reproduce |
| — | `get_user_profile(1)` | Missing null check | Returns `{"name": "Alice", "id": 1}` | — |

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

## Known fixes

1. `calculate_discount`: remove the `+ 1` → `return price - discount`
2. `validate_age`: change `age >= 65` to `age > 65`
3. `get_user_profile`: add null check → `return user if user else None`

## Issues to label

Create three GitHub issues in this repo, each with the `agent-fix` label:

- Issue 1: `calculate_discount` returns wrong result (off-by-one)
- Issue 2: `validate_age` rejects valid age 65 (wrong boundary)
- Issue 3: `get_user_profile` crashes on unknown user ID (missing null check)

Issue 3 is intentionally underspecified so the agent honestly reports
"couldn't reproduce" rather than inventing a fix.
