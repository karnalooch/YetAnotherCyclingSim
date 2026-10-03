"""Guarded project startup hook for the interactive YACS owner handoff."""

import importlib
import os
import sys

import unreal


if os.environ.get("YACS_OWNER_HANDOFF") == "1":
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    if project not in sys.path:
        sys.path.insert(0, project)
    importlib.import_module("scripts.ue.owner_handoff_startup")
