# Gumball promotion candidates

Consumer repositories may use this directory to record reusable engineering improvements discovered downstream.

Each candidate should be a small JSON document containing at least:

```json
{
  "id": "ci-example",
  "source": "owner/repository",
  "category": "ci",
  "problem": "What failed or cost too much?",
  "invariant": "What reusable property should always hold?",
  "evidence": ["PR #123", "CI run ..."],
  "do_not_copy": ["product-specific implementation details"],
  "failure_behavior": "How must the generalized contract fail?",
  "status": "candidate"
}
```

Valid lifecycle states are `candidate`, `proven` and `platform`.

The candidate file is evidence and a promotion request, not an automatic permission to modify Gumball.

