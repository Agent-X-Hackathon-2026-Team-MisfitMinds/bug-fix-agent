# Seeded Demo Repository

Small Python project used as the target repository for the Bug-Fix Agent
demo (Team MisfitMinds, Agent-X Hackathon 2026).

`src/app.py` holds three shop utilities:

- `calculate_discount(price, discount_percent)`
- `validate_age(age)`
- `get_user_profile(user_id)`

## Running tests

```bash
pip install pytest==8.3.4
pytest tests/ -v
```

The suite uses the Python standard library only.

## Reporting a bug

Open an issue with steps to reproduce, expected behaviour and actual
behaviour. Adding the `agent-fix` label asks the Bug-Fix Agent to attempt a
fix and open a draft pull request. A human reviews and merges.
