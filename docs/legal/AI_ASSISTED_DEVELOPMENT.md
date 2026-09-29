# AI-Assisted Development Policy

**Status:** active project policy  
**Applies to:** code, tests, documentation, scripts, configuration and review
produced with ChatGPT, Codex or other generative AI tools

## 1. Principle

YACS may use generative AI as an engineering tool. AI output is treated as
**untrusted proposed work**, not as an authoritative source.

The maintainer remains responsible for product decisions, architecture,
acceptance criteria, review, testing, licensing decisions and merge approval.

Using AI does not waive any YACS rule for correctness, security, provenance,
performance or Unreal validation.

## 2. Required workflow

For AI-assisted changes:

1. a human defines the goal, constraints and acceptance criteria;
2. the model may propose or implement a change;
3. the diff is reviewed against the task and repository rules;
4. relevant tests/builds/static checks are run;
5. Unreal/runtime/performance proof is executed whenever the normal project
   rules require it;
6. third-party provenance is checked before copied/adapted material is accepted;
7. failures and unverified behavior are reported explicitly;
8. only reviewed and validated changes are merged.

A passing model-generated explanation is never proof that code works.

## 3. Third-party and copyright hygiene

Do not assume AI output is original, copyright-free or license-free.

When output contains a recognizable external implementation, unusual comment,
copyright header, project-specific identifier, substantial verbatim-looking
fragment, or was intentionally prompted from an external repository:

- stop treating the output as source-neutral;
- identify the upstream source;
- verify its license and exact revision;
- record it in `DEPENDENCY_PROVENANCE.md`;
- preserve notices required by that license;
- replace the implementation with an independently written version when the
  upstream terms are unsuitable or unclear.

Reference-only projects must never be converted into copied code merely by
asking an AI model to “rewrite” them.

## 4. Secrets and private data

Never provide an AI tool with credentials, signing keys, access tokens,
passwords, private user data or production secrets.

For non-public proprietary material, personal data or other confidential
inputs, use only an account/workspace whose data-handling terms and settings
are approved for that material. When in doubt, redact or avoid uploading it.

Repository rules prohibiting credentials and private user data apply equally
to prompts, attachments, logs and model context.

## 5. AI-generated assets and content

Generated images, audio, text, meshes or other assets must have:

- a recorded generation/source workflow where practical;
- a review for third-party marks, recognizable protected material and unsafe
  resemblance to supplied references;
- the same performance and asset validation as manually produced assets;
- separate provenance records when external source assets or datasets were used.

Do not label an asset as wholly project-created when it incorporates an
external licensed source.

## 6. Attribution and disclosure

YACS does not require every commit or source file to carry an “AI generated”
label solely because an AI tool assisted the work.

Any disclosure required by a specific upstream license, contract, platform
rule, dataset term or applicable law still takes precedence.

The important repository evidence is the reviewed diff, test/proof history and
third-party provenance — not a percentage estimate of how much text a model
typed.

## 7. Review responsibility

The maintainer must be able to explain what a merged change does and why it is
acceptable. If a generated change cannot be meaningfully reviewed, it is too
large or too opaque to merge.

Prefer small AI-assisted changes with deterministic tests over broad autonomous
rewrites.

## 8. Related policy

- repository working rules: `AGENTS.md`;
- third-party notices: `THIRD_PARTY_NOTICES.md`;
- source/dependency provenance: `docs/legal/DEPENDENCY_PROVENANCE.md`;
- source-asset lifecycle: `docs/ASSET_PLAN.md`.
