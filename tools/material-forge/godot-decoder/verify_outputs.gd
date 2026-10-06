extends SceneTree

func _initialize():
	call_deferred("verify_outputs")

func verify_outputs():
	var arguments = OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected output prefix and resolution")
		quit(2)
		return

	var output_prefix = arguments[0]
	var resolution = int(arguments[1])
	if resolution != 2048:
		push_error("Material Forge decoder proof is pinned to 2048")
		quit(2)
		return

	var checks = {}
	var valid = true
	for suffix in [
		"BaseColor.png",
		"Normal_DX.png",
		"ORM.png",
		"Height.exr",
		"DetailMasks.png",
	]:
		var output_path = output_prefix + "_" + suffix
		var image = Image.load_from_file(output_path)
		if image == null or image.is_empty():
			valid = false
			continue
		var output_sha256 = FileAccess.get_sha256(output_path)
		if output_sha256.is_empty():
			valid = false
		checks[suffix] = {
			"width": image.get_width(),
			"height": image.get_height(),
			"format": image.get_format(),
			"sha256": output_sha256,
		}
		valid = valid and image.get_width() == resolution and image.get_height() == resolution

	var report_path = output_prefix + "_native-check.json"
	var report = FileAccess.open(report_path, FileAccess.WRITE)
	if report == null:
		push_error("Cannot create native decode receipt")
		quit(3)
		return
	report.store_string(JSON.stringify({
		"valid": valid,
		"images": checks,
		"engine": Engine.get_version_info(),
		"role": "native_image_decoder_only",
	}, "\t"))
	report.close()

	if valid:
		print("YACS_NATIVE_DECODE_PASS")
		quit(0)
	else:
		push_error("YACS_NATIVE_DECODE_FAILED")
		quit(4)
