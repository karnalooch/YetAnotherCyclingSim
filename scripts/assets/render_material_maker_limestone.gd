extends SceneTree

# The packaged 1.7 CLI crashes while loading even its bundled rock example.
# Wait for autoload initialization before loading the graph, then stop the
# renderer thread explicitly. This runner uses native MM graph/export APIs.
func _initialize():
	call_deferred("render_candidate")

func render_candidate():
	for i in range(8):
		await process_frame
	var arguments = OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected graph path and output prefix")
		quit(2)
		return
	var loader = root.get_node("mm_loader")
	var graph = await loader.load_gen(arguments[0])
	if graph == null:
		push_error("Graph load failed")
		quit(3)
		return
	root.add_child(graph)
	await process_frame
	var material = graph.get_node("PBR_Output")
	print("YACS_RENDER_START")
	await material.export_material(arguments[1], "YACS/Textures", 2048, true)
	var checks = {}
	var valid = true
	for suffix in ["BaseColor.png", "Normal_DX.png", "ORM.png", "Height.exr"]:
		var image = Image.load_from_file(arguments[1] + "_" + suffix)
		if image == null or image.is_empty():
			valid = false
			continue
		checks[suffix] = {"width": image.get_width(), "height": image.get_height(),
			"format": image.get_format()}
		valid = valid and image.get_width() == 2048 and image.get_height() == 2048
	var report = FileAccess.open(arguments[1] + "_native-check.json", FileAccess.WRITE)
	report.store_string(JSON.stringify({"valid": valid, "images": checks,
		"engine": Engine.get_version_info()}, "\t"))
	report.close()
	print("YACS_RENDER_COMPLETE valid=", valid)
	graph.queue_free()
	for i in range(8):
		await process_frame
	await root.get_node("mm_renderer").stop_rendering_thread()
	quit(0 if valid else 4)
