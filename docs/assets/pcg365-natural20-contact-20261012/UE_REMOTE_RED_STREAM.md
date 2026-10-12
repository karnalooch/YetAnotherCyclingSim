# #365 — interactive red-site Unreal Level Editor handoff

This is distinct from the failed transient PNG reviewer run 38286602677. That run created the red markers in Unreal, but its BoulderCapture helper correctly refused images outside the original owned project, so neither PNG success nor a browser stream was proved.

## Persistent Pixel Streaming 2 path

- The fixed owner-only workflow is [.github/workflows/pcg365-live-editor-stream.yml](../../../.github/workflows/pcg365-live-editor-stream.yml). An exact-source owner commit tagged [pcg365-live-stream] awaits successful protected CI AND pinned Blender reference, then takes the single non-cancelling shared Windows host.
- The launcher [Start-YacsPcg365RedStream.ps1](../../../scripts/ue/Start-YacsPcg365RedStream.ps1) verifies the saved d361e765 producer stage and real contact phase SHA, saved map bytes, plugin pin, idle host, available ports, non-aliased paths, and disk reserve before launching anything.
- The [persistent Python bootstrap](../../../scripts/ue/bootstrap_pcg365_red_stream.py) loads the accepted isolated Sa Calobra Landscape and creates transient red TextRender labels P0-P4. It frames P3 and keeps the owned Editor/viewport alive, without terrain/road/asset save or screenshot process exit.
- PixelStreaming2 serves the LevelEditorViewport via the local viewer http://127.0.0.1/ and signalling at 127.0.0.1:8888. The existing Test-YacsLevelEditorStreamClient.ps1 must prove two increasing, nonzero live browser video frame counters; an HTTP response or PNG is insufficient. Only after that is the Editor handed to the owner.
- The owner opens http://127.0.0.1/ on the SAME Windows machine, or a proven LAN address from the session receipt when on the same private reachable network. The workflow does not open public ports/tunnels. The address is not claimed to work unless actual native stream and receiver PASS. Failure only terminates the specifically launched Editor PID+start-time identity.

The five marked points are historical rejected vegetation-selector diagnostic XY, NOT approved rock-scatter locations. The previous 100-case matrix remains rejected. No Landscape/Base_DTM, road, georeferencing, physics, or source asset is changed. Issue #365 OPEN, PR #474 DRAFT, performance deferred and all production placement flags false. Paused runner cleanup #475 is not modified.

## Joint decision

At every red label decide: preserve steep natural ground, exclude rocks, or separately investigate accepted rock masks and source-cap geometry. The diagnostic never auto-flattens mountains or relaxes burial/slope rules.

## Native initial stream attempt — producer marker validation failure

[Run 38290138808](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38290138808)
passed protected CI and Blender reference checks but the Windows host rejected
the authentic old launcher marker at `Start-YacsPcg365RedStream.ps1`. The
historical marker was independently inspected from the successful exact producer
artifact 11761550579: `action=collection-contact-review`,
`code_sha=d361e765...`, `exit_code=0`, `staged_bytes_unchanged=true` and
`proof_admission=LOCAL_DIAGNOSTIC_ONLY`. The new launcher erroneously required
PowerShell `-is [int]` even though PowerShell 7 may decode the JSON integer as
`System.Int64`. This is a **new launcher receipt-typing error**, not a source
producer crash. The editor was **not** launched in this failed attempt.

The updated strict helper
[`Assert-YacsPcg365NativeCompletion.ps1`](../../../scripts/ue/Assert-YacsPcg365NativeCompletion.ps1)
accepts only Int32 or Int64 exactly equal to zero; it still rejects
strings, booleans, fractional types, nonzero/negative exit codes, mismatched
action/SHA/proof scope, or changed staged files. The Windows workflow now
re-tests the *actual old marker* plus valid and invalid typed fixtures before
launching Unreal. Do not call interactive streaming PASS until the viewer and
real browser video-frame receipt succeed on the new exact-head run.


## Second owned live attempt — diagnosed Python fatal at startup

[82ed322 / run 38292122043](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38292122043)
passed exact-SHA protected CI, Blender Material Forge, 6 offline marker
tests, and the historical native marker (PowerShell JSON decoded an Int64 exit
code 0). The launched UE Editor exited status 3 before the browser received
any frame; no interactive owner handoff occurred.

The original **314,720-byte** `editor.log`, included in retained
[artifact 11767148249](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38292122043/artifacts/11767148249),
shows a **caught, reproducible integration issue**, not an unexplained GPU
crash: `bootstrap_pcg365_red_stream.py:33` raised
`RuntimeError: Live handoff requires a fresh empty session directory`.
Unreal itself created `editor.log` via `-AbsLog` before starting
`-ExecutePythonScript`. The bootstrap treated its own valid engine log as
an alien previous-session file. The `-ScriptErrorsAreFatal` launch option
then escalated the uncaught Python exception into
`EditorPythonExecuter.cpp:97: Python script executed with errors`, creating
the Epic Crash Reporter window. The owner-reported screenshot is consistent
with this exact log, not evidence of corrupt terrain or modified assets.

The correction keeps the immutable fresh-session boundary but allows
**only** an ordinary non-symlink `editor.log` plus an otherwise empty new
directory. Unknown receipts, prior session output, directories and aliases
remain rejected. The check now runs inside a handled Python
`try/except`, writes a bounded `red-live-error.json` on failure, and
logs a warning rather than triggering a Python fatal; the PowerShell owner
still rejects failed readiness and can stop only its own Editor.

Offline regression tests cover the true initial `-AbsLog` order, stale
artifacts, missing session, and bootstrap exception handling. No cache deletion,
relaunch without CI gates, source-scene save, terrain/road material modification
or production scatter admission is allowed.

The next native attempt must independently prove that P0–P4 red markers
and the real PixelStreaming2 viewer survive startup and that Edge/Chrome
receives live frames. Do not claim a working UE Remote address before that.
