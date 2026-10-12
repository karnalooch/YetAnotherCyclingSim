# Minimum restart continuation — #365 / M3

**Owner-authorized plan:** the original 2026-10-12 transfer had no implementation.
The grouped three-session source candidate was subsequently committed in
[`f4d6c0ce`](https://github.com/karnalooch/YetAnotherCyclingSim/commit/f4d6c0ce4eeab8c2ed57280332dc97bfc7a84148)
and receives follow-up corrections on PR #474. **Native three-session execution,
clean exit markers and final GPU evidence remain UNVERIFIED until a current-head
run produces them.** The original transfer producer remains `1a02ac21`.
The owner requested the absolute minimum of restarts, only when required.

## Preserve the two required process boundaries

| Session | Fixed operations | Required proof |
|---|---|---|
| `collection-contact-prepare` | inspect → save Forge → save 20 meshes | One group marker after real exit 0 |
| `collection-contact-measure` | fresh Forge readback → fresh mesh readback → 100 contact cases | Completed prepare, fresh process, one group marker after real exit 0 |
| `collection-contact-review` | fresh aggregate/readback → 40 final UE PNGs | Completed measure, fresh process, final checks and one group marker after real exit 0 |

Prepare and measure use NullRHI; review starts with RenderOffscreen. Preserve the
420-second timeout per session. Save→fresh consumer and clean contact-producer
exit→fresh review remain real process boundaries. A restart after readback alone
does not add new durability evidence. Two sessions would merge contact and render
before the contact producer's clean exit; that changes an existing gate and is
not this authorized implementation plan.

## Bounded implementation

Use the current launcher, host ownership, staging and native helpers. Limit source
changes to `Invoke-YacsPcgNativeProbe.ps1`, `sa_calobra_pcg_native_probe.py`,
`sa_calobra_pcg_collection_contact.py`, a new fixed-action helper
`pcg365_three_session.py`, scoped offline tests, the opt-in native workflow and
process docs.
Three explicit actions have fixed phase sequences: no arbitrary action-list
interface, eval or second proof framework.

Retain phase receipts, inventory/binding/raw paths and exact HEAD/source/native
identities. A completed phase is not a completed process. Group receipts must
hash-bind all required phase receipts and session identity; the launcher writes
one group completion marker only after actual exit 0. Do not fabricate individual
phase exit markers. The reader must validate a closed phase→group mapping and
reject mixed legacy/grouped layouts or partial fallback.

During review, aggregate readback is a completed phase of that same fresh session;
capture can consume its authenticated result without pretending that the review
process has already exited. The entire review remains unadmitted until final
capture, conservation checks and genuine exit 0. Preserve all physical gates,
33/65/129 behavior, two views per mesh, warmups and source/terrain/Forge hashes.

## Timing evidence and required tests

Run04 log spans, not complete launcher timings or a benchmark:

| Existing action | Seconds |
|---|---:|
| inspect | 20.628 |
| material save | 16.182 |
| material reload | 13.026 |
| collection save | 79.267 |
| collection reload | 30.164 |
| contact all | 167.609 |
| contact reload, failed at exit | 35.586 |
| render | NOT RUN |

Current action spans sum to 116.077 seconds for proposed prepare and 210.799 for
measure. This suggests room within 420 seconds but is not a grouped native proof.
Review duration is UNKNOWN because render did not run. Do not claim it fits,
increase the timeout silently, or cut required images/warmups to make it pass.

Test missing/changed group receipts, nonzero or false exit codes, missing phases,
modified phase/raw hashes, mismatched HEAD/source/native build, mixed layouts and
reuse of the same session where a fresh consumer is required. Preserve existing
100-case coverage tests and prove failed review cannot receive a success marker.
Then run the committed exact producer in a new stage under existing host arbitration.

The post-log-close AV remains undiagnosed. Installed UE supports keep-alive plus
quit_editor; the current callback unregisters before quit. Normal log shutdown
precedes additional engine teardown. Reducing exits is not a root-cause repair.

## Post-transfer implementation and execution boundary

The code candidate has three fixed actions. `collection-contact-prepare` saves
Forge and twenty meshes after inspection; `collection-contact-measure` starts
fresh and validates both saved consumers before one 100-case producer; and
`collection-contact-review` starts fresh, verifies that producer's true exit,
then captures two final 1920x1080 Landscape PNGs per rock, plus two warmups.
The native launcher checks hashes and exact source revision, owns the process,
uses NullRHI for the first two sessions and RenderOffscreen for review, and
writes each session completion marker only after actual exit 0.

The opt-in workflow is
[`pcg365-natural20-contact-proof.yml`](../../../.github/workflows/pcg365-natural20-contact-proof.yml).
Only an owner push with `[pcg365-native-proof]` proceeds after successful
exact-SHA CyclingSim CI and Blender Material Forge reference proof. The Windows
runner is serialized with existing Unreal/Blender GPU work and explicitly checks
its host ownership; no existing local Editor may be terminated. Preflight and
capture failure remain BLOCKED or FAIL, never PASS. GPU images are evidence for
visual inspection, not admission of rejected contacts.

No rejected physical thresholds were relaxed; there is no scatter, map save,
Landscape/Base_DTM repair, new GPU benchmark, owner visual PASS, AV root-cause
repair or automatic runner cleanup (#475). Earlier run04 artifacts remain
immutable. The first group native exit and post-run visual inspection must be
reported against the exact execution SHA before changing this status.
