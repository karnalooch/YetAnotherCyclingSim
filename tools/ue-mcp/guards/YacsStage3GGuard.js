import { UeMcpGuard } from "ue-mcp/guard";

const TRANSIENT_PREFIX = "YACS_MCP_";

const SAFE_METHODS = new Set([
  "destroy_transient_actor",
  "list_transient_actors",
  "get_world_outliner",
  "get_current_level",
  "get_actor_details",
  "get_component_details",
  "get_component_tree",
  "get_actor_bounds",
  "get_spline_info",
  "get_viewport_state",
  "redraw_viewport",
]);

const VIEWPORT_MUTATIONS = new Set([
  "set_view_mode",
  "set_game_view",
  "set_realtime",
  "set_viewport",
  "set_viewport_view",
  "set_viewport_exposure",
]);

function normalizePath(value) {
  return String(value ?? "").replaceAll("\\", "/");
}

function isSavedOutput(value) {
  const path = normalizePath(value);
  return path === "Saved"
    || path.startsWith("Saved/")
    || path.includes("/Saved/");
}

export default class YacsStage3GGuard extends UeMcpGuard {
  get taskName() {
    return "yacs-stage3g-guard";
  }

  async before(call) {
    const method = call.method;
    const params = call.params ?? {};

    if (SAFE_METHODS.has(method)) {
      return this.allow();
    }

    if (method === "spawn_transient_actor") {
      const label = String(params.label ?? "");
      if (!label.startsWith(TRANSIENT_PREFIX)) {
        return this.deny(
          `Transient verification actors must use label prefix '${TRANSIENT_PREFIX}'.`,
        );
      }
      return this.allow();
    }

    if (method === "capture_scene_png" || method === "capture_screenshot") {
      const output = params.outputPath ?? params.filename;
      if (!isSavedOutput(output)) {
        return this.deny(
          "Stage 3G MCP proof captures must write only under the project's Saved/ directory.",
        );
      }
      return this.allow();
    }

    if (VIEWPORT_MUTATIONS.has(method)) {
      return this.allow();
    }

    return this.deny(
      `Stage 3G MCP spike is verification-only. Mutation '${method}' is blocked until #85 Phase A validation is green and the persistent /Game/Generated/YACS sandbox is implemented.`,
    );
  }
}
