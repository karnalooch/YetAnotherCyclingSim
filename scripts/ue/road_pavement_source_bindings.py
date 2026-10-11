"""Explicit road addresses from the one authenticated checkpoint slab producer.

The retained 3393-byte ``network_pavement.py`` is evidence, never executable
input. Its ``pavement_slab`` appends top then bottom vertices and interleaves
two top / two bottom triangles in each of the 24 cells. Perimeter faces follow
all cells. ``create_accepted_scene_checkpoint.py`` appends those complete slabs
in authenticated window order: 184 network windows, then accepted-hairpin.

The source loader preserves that order while inserting one support-only Nudo
parapet. Consequently support labels are identities, not road mesh offsets.
This module counts every complete slab, excludes that parapet, and returns only
the explicit top faces used by the clipped edge paint. Native consumers still
must compare every addressed tid, ordered vid and position against the road.
No archived producer, native API, geometry authoring or proximity search runs.
"""

from __future__ import annotations

import hashlib

from scripts.ue import road_edge_marking_geometry as geometry
from scripts.ue import road_shoulder_network as network
from scripts.ue import road_shoulder_sources as sources

PRODUCER_PATH = "support-consumers/network_pavement.py"
PRODUCER_IDENTITY = dict(sources.PRODUCERS["network_pavement.py"])
QUAD_TRIANGLES = ((0, 1, 2), (1, 3, 2))
MAX_BINDINGS = 250000


def require(value, message):
    if not value:
        raise ValueError(message)


def _slab_layout(source_plan):
    identity, owners = source_plan.get("source_identity", {}), source_plan.get("owners")
    require(isinstance(identity, dict)
            and identity.get("support_source_schema_version") == 1
            and identity.get("geometry_consumers_executed") is False
            and identity.get("geometry_authored") is False
            and identity.get("producer_files", {}).get(PRODUCER_PATH) == PRODUCER_IDENTITY,
            "Road bindings require the authenticated read-only pavement source identity")
    require(isinstance(owners, (list, tuple)) and len(owners) == sources.OWNER_COUNT
            and all(isinstance(owner, dict) for owner in owners)
            and [owner.get("support_label") for owner in owners]
            == [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(sources.OWNER_COUNT)],
            "Road binding owner inventory is missing, duplicated or reordered")
    layout, windows = {}, set()
    vertex_offset = triangle_offset = section_count = parapets = 0
    for owner in owners:
        target, kind = owner.get("material_target"), owner.get("kind")
        require(type(target) is bool, "Road binding owner target must be explicit")
        if not target:
            require(kind == "parapet", "Only the source-owned parapet may be excluded")
            parapets += 1
            continue
        count, window = owner.get("section_count"), owner.get("window_id")
        require(kind in ("ordinary", "nudo", "hairpin")
                and type(count) is int and 3 <= count <= sources.MAX_SECTIONS
                and isinstance(window, str) and window and window not in windows,
                "Pavement owner kind, row count or window identity differs")
        require((kind == "hairpin") == (window == "accepted-hairpin"),
                "Hairpin pavement source identity differs")
        windows.add(window)
        # Actual producer: count top vertices, then the same count for bottom.
        # Each quad contributes top0, top1, bottom0, bottom1. Its perimeter has
        # two 24-edge ends and two (N-1)-edge sides, with two faces per edge.
        vertices = 2 * 25 * count
        triangles = 4 * 24 * (count - 1) + 2 * (2 * 24 + 2 * (count - 1))
        require(vertices == 50 * count and triangles == 100 * count - 4,
                "Retained pavement slab count derivation differs")
        layout[owner["support_label"]] = (count, vertex_offset, triangle_offset)
        vertex_offset += vertices
        triangle_offset += triangles
        section_count += count
    require(len(layout) == sources.NETWORK_COUNT + 1 and parapets == 1
            and owners[-1].get("kind") == "hairpin"
            and owners[-1].get("window_id") == "accepted-hairpin"
            and section_count == sources.PROFILE_PAVEMENT_ROW_COUNT
            and (vertex_offset, triangle_offset) == network.ROAD_COUNTS,
            "Complete source slabs do not account for the accepted native road buffers")
    require(identity.get("support_count") == sources.OWNER_COUNT
            and identity.get("material_target_count") == len(layout)
            and identity.get("excluded_parapet_count") == parapets,
            "Source identity and road owner inventory disagree")
    return layout


def prepare_bindings(source_plan, *, producer_bytes):
    """Return exact topology and eight-field native addresses for clipped paint.

    ``[owner, section, lateral_cell, slot, native_tid, vid0, vid1, vid2]``
    rows are deterministic and retain separate ownership at coincident seams.
    The caller supplies ``road_shoulder_sources.load_sources()`` unchanged.
    Any different producer bytes invalidate this closed, reviewed derivation.
    """
    require(type(producer_bytes) is bytes
            and len(producer_bytes) == PRODUCER_IDENTITY["size_bytes"]
            and hashlib.sha256(producer_bytes).hexdigest() == PRODUCER_IDENTITY["sha256"],
            "Road bindings need the exact retained pavement producer bytes")
    require(isinstance(source_plan, dict), "Road bindings require the authenticated source plan")
    layout = _slab_layout(source_plan)
    build = geometry.build_markings(source_plan, quad_triangles=QUAD_TRIANGLES)
    needed = {(mesh.owner_label, *fragment.source_triangle)
              for mesh in build.meshes for fragment in mesh.fragments}
    require(0 < len(needed) <= MAX_BINDINGS, "Clipped source face inventory is empty or unbounded")
    rows, seen_tids = [], set()
    for key in sorted(needed):
        require(len(key) == 4 and isinstance(key[0], str) and key[0] in layout
                and all(type(value) is int and value >= 0 for value in key[1:]),
                "Clipped source face lacks a bounded pavement owner/address")
        label, section, cell, slot = key
        count, vertex_offset, triangle_offset = layout[label]
        require(section < count - 1 and cell < 24 and slot < 2,
                "Clipped source face is outside its source pavement slab")
        a = section * 25 + cell
        corners = (a, a + 1, a + 25, a + 26)
        tid = triangle_offset + 4 * (section * 24 + cell) + slot
        vids = tuple(vertex_offset + corners[corner] for corner in QUAD_TRIANGLES[slot])
        require(tid not in seen_tids and tid < triangle_offset + 96 * (count - 1)
                and all(vertex_offset <= vid < vertex_offset + 25 * count for vid in vids),
                "Source top binding reaches a bottom/perimeter face or duplicate native address")
        seen_tids.add(tid)
        rows.append((*key, tid, *vids))
    return {"quad_triangles": QUAD_TRIANGLES, "triangle_bindings": tuple(rows)}
