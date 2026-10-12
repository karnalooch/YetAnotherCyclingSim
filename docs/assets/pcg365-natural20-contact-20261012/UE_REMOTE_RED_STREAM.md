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
