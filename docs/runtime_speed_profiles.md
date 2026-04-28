# Runtime Speed Profiles

**最后更新**: 2026-04-28


This project supports three practical runtime profiles for different learning/usage styles.

## Profiles

- `fast`: lowest latency, lower depth. Good for rapid iteration and Q&A.
- `balanced`: recommended default. Good latency and good answer quality.
- `deep`: slower, stronger reasoning/rewrite/refinement. Good for difficult topics.

Profile files:

- `configs/runtime-profiles/fast.env`
- `configs/runtime-profiles/balanced.env`
- `configs/runtime-profiles/deep.env`

## Apply A Profile

Use the existing profile apply script:

```bash
python scripts/apply_rollback_profile.py --profile configs/runtime-profiles/fast.env --env-file .env
```

Replace `fast.env` with `balanced.env` or `deep.env` as needed.

## Important

- `use_reasoning` and `use_web_fallback` are request-level switches from API/frontend.
- These profiles tune backend defaults and runtime behavior, but they do not force every request to use reasoning/web.
- For OpenAI-style "slow but thorough" behavior, use `deep.env` and set request `use_reasoning=true`.
