# YACS — bounded delegation and result handoff

This is a reviewable contract for task envelopes, not an automated agent runtime or proof acceptance service.

## Input envelope
- `issue`: current GitHub issue, actual dependency status and `milestone`.
- `domain`: one domain key in [ROLE_REGISTRY.json](ROLE_REGISTRY.json); do not select a role by tool preference.
- `base_sha`: exact existing 40-character commit; never assume another agent's unmerged branch has become authority.
- `scope`, `forbidden`, `read_docs`, `inputs`, `required_proofs`, `resource_claims` and expected outputs.

Example for a read-only audit (substitute the **real** SHA before use):

```json
{
  "issue": 468,
  "milestone": "M3",
  "domain": "proof-review",
  "base_sha": "<verified SHA>",
  "scope": ["docs/ai/"],
  "forbidden": ["Source/", "Content/", "proof admission", "merge"],
  "read_docs": ["docs/README.md", "docs/CI_VALIDATION_TIERS.md"],
  "required_proofs": ["hosted script tests", "docs guards"],
  "resource_claims": []
}
```

## Return envelope
`role`, `issue`, `head_sha`, `changed_paths`, `validation`, `evidence_refs`, `unverified`, `rollback`, `blockers`, `recommended_next_action`.

Validation entries use `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`. A reviewer may recommend acceptance but cannot convert its own output into protected CI, native Unreal proof, owner visual signoff or merge authorization.

**Fail closed:** missing active role, blocked dependency, uncertain authority, unverifiable evidence, conflicting writers or occupied exclusive host resource → report BLOCKED before mutation. M3 performance remains `DEFERRED_AFTER_M3` and `performance_pass: false` pending measured benchmark.

The coordinator owns assignment and integration; it cannot grant itself privileges not available through approved tools, owner decisions or GitHub protections.
