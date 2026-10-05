import test from "node:test";
import assert from "node:assert/strict";
import { permitsTextureCall, TOOLSET } from "./YacsTextureGuard.js";

const call = (tool, input = {}) => ({
  method: "epic_call_tool", params: { toolset: TOOLSET, tool: TOOLSET + "." + tool, input },
});
const recipe = {
  resolution: 128, worldSizeMeters: { x: 2, y: 2 }, colorGain: { r: 1, g: 1, b: 1, a: 1 },
  seamBlendWidth: 0.05, deLightStrength: 0, heightStrength: 0.5, normalStrength: 1,
  roughnessMin: 0.55, roughnessMax: 0.9, macroVariation: 0,
};

test("permits only known typed operations", () => {
  assert.equal(permitsTextureCall(call("InspectCapabilities")), true);
  for (const name of ["RenderPreview", "ExportPbrSet", "ValidateTexture", "GetJobStatus"]) {
    assert.equal(permitsTextureCall(call(name, { jobId: "a".repeat(32) })), true);
  }
  assert.equal(permitsTextureCall(call("PrepareTexture", { sourceAssetPath: "/Game/Test.T", recipe })), true);
});

test("rejects unsupported, incomplete and misspelled recipes", () => {
  for (const r of [{}, { ...recipe, seed: 1 }, { ...recipe, resolution: 8192 },
    { ...recipe, normalStrength: NaN }, { ...recipe, roughnessMin: 1, roughnessMax: 0 },
    { ...recipe, worldSizeMeters: { x: 0, y: 2 } }]) {
    assert.equal(permitsTextureCall(call("PrepareTexture", { sourceAssetPath: "/Game/Test.T", recipe: r })), false);
  }
});

test("blocks transport escape hatches and toolset substitution", () => {
  for (const method of ["execute_python", "execute_command", "save_asset", "spawn_actor", "epic_list_toolsets"]) {
    assert.equal(permitsTextureCall({ method, params: {} }), false);
  }
  const changed = call("InspectCapabilities");
  changed.params.toolset = "Other.Tools";
  assert.equal(permitsTextureCall(changed), false);
  assert.equal(permitsTextureCall(call("DeleteEverything")), false);
});

test("rejects extra parameters, invalid identities and alternate JSON channel", () => {
  assert.equal(permitsTextureCall(call("RenderPreview", { jobId: "../bad" })), false);
  assert.equal(permitsTextureCall(call("RenderPreview", { jobId: "a".repeat(32), path: "/Game/World" })), false);
  const raw = call("InspectCapabilities");
  raw.params.inputJson = "{}";
  assert.equal(permitsTextureCall(raw), false);
  assert.equal(permitsTextureCall(call("PrepareTexture", { sourceAssetPath: "/Game/../Engine/T.T", recipe: {} })), false);
});
