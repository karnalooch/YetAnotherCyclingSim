extends SceneTree

func _initialize():
	call_deferred("render_variant")

func render_variant():
	for i in range(8):
		await process_frame
	var arguments = OS.get_cmdline_user_args()
	if arguments.size() != 3:
		push_error("Expected graph path, output prefix and resolution")
		quit(2)
		return
	var graph_path = arguments[0]
	var output_prefix = arguments[1]
	var resolution = int(arguments[2])
	if resolution < 256 or resolution > 8192:
		push_error("Invalid Material Forge resolution")
		quit(2)
		return
	var loader = root.get_node("mm_loader")
	var graph = await loader.load_gen(graph_path)
	if graph == null:
		push_error("YACS_RENDER_FAILED graph load")
		quit(3)
		return
	root.add_child(graph)
	await process_frame
	var material = graph.get_node("PBR_Output")
	if material == null:
		push_error("YACS_RENDER_FAILED PBR_Output missing")
		quit(3)
		return
	print("YACS_RENDER_START")
	await material.export_material(output_prefix, "YACS/Textures", resolution, true)
	var checks = {}
	var valid = true
	for suffix in [
		"BaseColor.png",
		"Normal_DX.png",
		"ORM.png",
		"Height.exr",
		"DetailMasks.png",
	]:
		var image = Image.load_from_file(output_prefix + "_" + suffix)
		if image == null or image.is_empty():
			valid = false
			continue
		checks[suffix] = {
			"width": image.get_width(),
			"height": image.get_height(),
			"format": image.get_format(),
		}
		valid = valid and image.get_width() == resolution and image.get_height() == resolution
	var report = FileAccess.open(output_prefix + "_native-check.json", FileAccess.WRITE)
	report.store_string(JSON.stringify({
		"valid": valid,
		"images": checks,
		"engine": Engine.get_version_info(),
	}, "\t"))
	report.close()
	print("YACS_RENDER_COMPLETE valid=", valid)
	graph.queue_free()
	for i in range(8):
		await process_frame
	await root.get_node("mm_renderer").stop_rendering_thread()
	quit(0 if valid else 4)
