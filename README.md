# YetAnotherCyclingSim

Realistic indoor cycling simulator built with Unreal Engine 5.

YACS combines deterministic cycling physics with a real-data-first Unreal Engine world pipeline currently focused on Sa Calobra / Coll dels Reis, Mallorca. The selected MDT50cm dataset is available; Unreal terrain, Ma-2141 road, visual and performance acceptance remain pending.

Owner decision, 2026-10-09: measure performance after the assembled M3 world
is closed out. Intermediate material/MCP/road handoffs retain visual, saved/fresh
consumer and technical gates; performance is deferred, with existing budgets
and final measurement still required. See the [current delivery order](docs/ROADMAP.md#post-road-world-finishing-sequence).

## Documentation

**Start with the [documentation map](docs/README.md).**

Quick links:

- [Product requirements](docs/PRODUCT_REQUIREMENTS.md)
- [MVP roadmap](docs/ROADMAP.md)
- [World Building Bible](docs/WORLD_BUILDING_BIBLE.md)
- [Road physics profile](docs/ROAD_PHYSICS_PROFILE.md)
- [World authoring library](docs/YACS_WORLD_AUTHORING_LIBRARY.md)
- [CI validation tiers](docs/CI_VALIDATION_TIERS.md)
- [Local workspace, runner and checkpoints](docs/tooling/LOCAL_WORKSPACE.md) — canonical home environment at `D:\yacs`, with the active repository at `D:\yacs\project`.

Historical Stage 3G / R4.1 documents remain available as execution/proof history, but new planning uses M0-M10 milestones plus named workstreams and GitHub Issues.

## Governance

- [AI-assisted development policy](docs/legal/AI_ASSISTED_DEVELOPMENT.md)
- [Third-party provenance ledger](docs/legal/DEPENDENCY_PROVENANCE.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
