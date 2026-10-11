# Outer-material preparation failure — 2ec534c

**Issue:** #364. **Status:** FAILED before save, reload or GPU capture.

[Protected CI 38119542097](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38119542097)
passed. The [native checkpoint 38119538994](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38119538994)
passed the baseline and reversible canary, then its prepare process exited 3
after 385.443 seconds, below the unchanged 420-second deadline. The selected
outer terrain plus band/paint controls produced no new saved map or PNG.

The [original host receipt](saved-road-host-receipt.json) and
[cache resolver result](cache-resolution.json) are unchanged source bytes.
The latter records `Mode: static`, `CompileKind: none` and
`Reason: verified-equivalent-proof`. This was not another C++ build.

[Stage observations](stage-observations.json) were extracted from the closed
original log. `terrain.verify_instance` completed at 07:05:28.604 UTC and
`terrain.authenticate` completed at 07:05:28.683 UTC. The last entered material
operation was `terrain.build_surface_terms` at 07:05:37.125 UTC; its after marker
is absent. D3D12 reported `E_OUTOFMEMORY` for a 33,554,432-byte resource at
07:10:00.338 UTC, followed by the fatal rendering-resource memory error.

This run locates the failing interval after successful frozen-terrain
authentication. It does not identify the exact expression node or establish
that a particular texture, shader worker, thread option or cache caused the
allocation. The failed resource is not proof of total physical VRAM usage.
The earlier WeightTex rejection and the 56c5 paging-file failure remain separate
observations. No strict check was relaxed and no blind retry was requested.

The original archive contains 31 files / 216,516 bytes, SHA-256
`7d27a4ea3bb3b10740d2bbda387a0370eec9e3edb5438c77161822db4bd6eb7c`.
The [manifest](source-artifact.json) records its retained members and the full
478,698-byte log identity. The full original log stays in
[artifact 11695610744](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38119538994/artifacts/11695610744).

The latest complete material view remains the parent
[b9fd checkpoint](../README.md). Its reuse for owner preview does not accept
the failed outer blend. Follow the [lighter iteration cadence](../../../CI_VALIDATION_TIERS.md#m3-road-material-iteration-cadence)
and diagnose a bounded material operation before requesting another complete
checkpoint. Owner audit is `PENDING_FINAL_M3`; `performance_pass: false`.
