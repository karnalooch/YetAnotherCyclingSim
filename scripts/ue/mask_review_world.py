"""Select the live review world without loading or replacing an editor map."""


def require_existing_review_world(editor, expected_package):
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split('.', 1)[0] != expected_package:
        raise RuntimeError(
            'Open the expected mask-review map in the existing editor first; '
            'automatic map loading is forbidden because it discards transient roads.'
        )
    return world
