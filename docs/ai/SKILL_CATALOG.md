# YACS — reusable project skills

**Status:** current project instruction layer. These skills implement the existing
[agent router](README.md), [role registry](ROLE_REGISTRY.json) and
[task handoff](TASK_HANDOFF.md). They do not create another agent runtime,
authority registry, permission model or proof framework.

## Start with the coordinator

Load [`yacs-orchestrate`](../../.agents/skills/yacs-orchestrate/SKILL.md) for work
that crosses domains or resumes a partially completed task. Select the domain
owner by the data being changed, then load only the relevant skill and its
source map. Independent audits can run in parallel; each changed path has one
writer, and Unreal/GPU/home-runner operations retain existing host arbitration.

In an environment that loads repository skills, invoke the relevant `$yacs-*`
skill. Otherwise read its `SKILL.md` directly from the checked-out repository or
through GitHub at the task's verified commit, and follow its linked references.
Repository publication does not establish installation in a personal Skills
list or availability of a Windows/Unreal execution tool.

## Available skills

| Skill | Responsibility | Existing authority / role |
|---|---|---|
| [`yacs-orchestrate`](../../.agents/skills/yacs-orchestrate/SKILL.md) | Current state, scope, delegation, integration and closeout across the whole project | Router, task handoff, Product Requirements and Roadmap |
| [`yacs-world-data`](../../.agents/skills/yacs-world-data/SKILL.md) | Source geography, CRS, DTM/LiDAR, NoData, coverage, masks and provenance | `source-geodata` / `world-data` |
| [`yacs-road-bob`](../../.agents/skills/yacs-road-bob/SKILL.md) | Canonical route, road-physics profile, hairpins, earthworks and contact | `road-earthworks` / `road-bob` |
| [`yacs-houdini-world`](../../.agents/skills/yacs-houdini-world/SKILL.md) | Original SideFX workflows, HIP/HDA, source/manual/detail layers, cache and terrain transfer | `procedural-world` |
| [`yacs-materials-visual`](../../.agents/skills/yacs-materials-visual/SKILL.md) | IDMap, global colour, texture arrays, PBR, Material Forge and visual diagnosis | `visual-dcc` |
| [`yacs-unreal-integration`](../../.agents/skills/yacs-unreal-integration/SKILL.md) | UHT/UBT/DLL, target isolation, Houdini consumer, collision, reopen and Live Host | `unreal-integration` |
| [`yacs-physics-gameplay`](../../.agents/skills/yacs-physics-gameplay/SKILL.md) | Physics, fixed-step runtime, input, session and routing of later ride features | `physics-gameplay`, then the relevant activated roadmap owner |
| [`yacs-verify-evidence`](../../.agents/skills/yacs-verify-evidence/SKILL.md) | Source/run identity, proof coverage, native and visual boundaries, performance and archive integrity | `proof-review` / `proof-qa` |
| [`yacs-docs-governance`](../../.agents/skills/yacs-docs-governance/SKILL.md) | SSOT, decision precedence, source concordance, contradictory status and documentation guards | `docs-governance` / `docs-governor` |
| [`yacs-github-delivery`](../../.agents/skills/yacs-github-delivery/SKILL.md) | Existing issue/branch/PR, bounded changes, LFS, CI diagnosis and guarded delivery | Existing delivery/Git/CI policies; no new domain owner |

## Coverage and stage boundaries

The coordinator's source map routes all M0–M10 areas and post-MVP requests.
Physics/gameplay includes routing for cornering, HUD/session, rider/bike/camera,
mocap, weather/audio, save/FIT and trainer input. The Houdini skill covers the
Pegasus catalogue beyond Landscape lessons 6 and 7; material and world skills
also route later environment work.

This coverage is a way to find the right instructions. It does not activate
planned roles, open milestone dependencies or assert that a future feature has
already been implemented. Re-read the current Roadmap, issue state and owner
decisions before each change. A skill's source-review SHA records the revision
used to construct its source map; it is not a permanently current branch head
or a native acceptance result.

## Skill structure and maintenance

Each directory under `.agents/skills/` contains:

- `SKILL.md`: trigger metadata and the bounded execution procedure;
- `references/source-map.md`: existing source paths, relevant contracts and
  narrowly needed domain details;
- `agents/openai.yaml`: display metadata and an example invocation.

Keep procedures concise and references task-local. Reuse existing scripts and
validators instead of copying their implementations into skills. When a
source contract or script moves, update its affected source map in the same
change. Validate frontmatter/name, local links, referenced repository paths,
UI metadata and a representative use after material workflow changes.

The procedures use Polish for the owner's working context; code identifiers,
commit messages and GitHub issue/PR communication retain the repository's
English convention. Skills preserve current user authorization and report
actual capability failures; they do not introduce repeated approvals for
already authorized, reversible work.
