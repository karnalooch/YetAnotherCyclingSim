import { UeMcpGuard } from "ue-mcp/guard";

export const TOOLSET = "YacsTexturePrep.YacsTextureTools";
const JOB_TOOLS = new Set(["RenderPreview", "ExportPbrSet", "ValidateTexture", "GetJobStatus"]);
const plainObject = value => value !== null && typeof value === "object" && !Array.isArray(value);
const keysAre = (value, expected) => plainObject(value) && Object.keys(value).sort().join(",") === expected;
const between = (value, low, high) => typeof value === "number" && Number.isFinite(value) && value >= low && value <= high;
function validRecipe(r) {
  if (!keysAre(r, "colorGain,deLightStrength,heightStrength,macroVariation,normalStrength,resolution,roughnessMax,roughnessMin,seamBlendWidth,worldSizeMeters")) return false;
  return [128, 256, 512, 1024].includes(r.resolution)
    && keysAre(r.worldSizeMeters, "x,y")
    && between(r.worldSizeMeters.x, Number.MIN_VALUE, 1000)
    && between(r.worldSizeMeters.y, Number.MIN_VALUE, 1000)
    && keysAre(r.colorGain, "a,b,g,r") && r.colorGain.a === 1
    && ["r", "g", "b"].every(k => between(r.colorGain[k], 0, 2))
    && between(r.seamBlendWidth, 0, 0.25) && between(r.deLightStrength, 0, 1)
    && between(r.heightStrength, 0, 1) && between(r.normalStrength, 0, 2)
    && between(r.roughnessMin, 0, 1) && between(r.roughnessMax, r.roughnessMin, 1)
    && between(r.macroVariation, 0, 1);
}

// This profile is for an isolated proof editor, not the world-authoring profile.
export function permitsTextureCall(call) {
  const p = call.params ?? {};
  if (call.method === "epic_status") return true;
  if (call.method === "epic_describe_toolset") return p.toolset === TOOLSET;
  if (call.method !== "epic_call_tool" || p.toolset !== TOOLSET || p.inputJson != null) return false;
  if (!plainObject(p.input)) return false;
  const tool = String(p.tool ?? "");
  if (!tool.startsWith(TOOLSET + ".")) return false;
  const name = tool.slice(TOOLSET.length + 1);
  const input = p.input;
  const keys = Object.keys(input).sort().join(",");
  if (name === "InspectCapabilities") return keys === "";
  if (JOB_TOOLS.has(name)) return keys === "jobId" && /^[0-9a-f]{32}$/i.test(input.jobId);
  if (name === "PrepareTexture") {
    return keys === "recipe,sourceAssetPath"
      && typeof input.sourceAssetPath === "string"
      && /^\/Game\/[A-Za-z0-9_/]+\.[A-Za-z0-9_]+$/.test(input.sourceAssetPath)
      && validRecipe(input.recipe);
  }
  return false;
}

export default class YacsTextureGuard extends UeMcpGuard {
  get taskName() { return "yacs-texture-guard"; }
  async before(call) {
    return permitsTextureCall(call) ? this.allow()
      : this.deny("Texture proof profile permits only the six explicit YacsTextureTools operations; no Python, console, world or arbitrary asset writes.");
  }
}
