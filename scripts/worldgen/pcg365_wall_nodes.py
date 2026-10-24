"""Configure the inspected wall graph through official PCGEx/PCG MCP tools.

These are native node settings and connections, not geometry or blending algorithms.
The source raster adapter is separate from PCGEx hull/containment/topology decisions.
"""
import json

from scripts.worldgen import pcg365_pcgex_graph as g


def configure_blend(a, surface):
    def update(n, p):
        assert a.call(g.PCG, 'UpdateNode', dict(node=a.state['nodes'][n], nodeTitle='', jsonParams=json.dumps(p)))

    def put(name, cls, props=None):
        if name not in a.state['nodes']:
            a.create(name, cls, props)
        elif props:
            update(name, props)

    def disconnect(s, t, sp='Out', tp='In'):
        return a.call(g.PCG, 'DisconnectNodePins', dict(fromNode=a.state['nodes'][s], fromPinLabel=sp, toNode=a.state['nodes'][t], toPinLabel=tp))

    def copy(name, source, target, upstream):
        new = name not in a.state['nodes']
        put(name, 'UPCGCopyAttributesSettings', dict(bCopyAllAttributes=False, inputSource=source, outputTarget=target))
        if new:
            a.edge(upstream, name, 'Out', 'Source')
            a.edge(upstream, name, 'Out', 'Target')

    def remap(name, source, target, lo, hi, upstream):
        new = name not in a.state['nodes']
        put(name, 'UPCGExAttributeRemapSettings', dict(attributes=dict(source=source, bOutputToDifferentName=True, target=target), baseRemap=dict(inputClampDetails=dict(bApplyClampMin=True, clampMinValue=lo, bApplyClampMax=True, clampMaxValue=hi), remapDetails=dict(bUseInMin=True, inMin=lo, bUseInMax=True, inMax=hi, bUseAbsoluteRange=False, bPreserveSign=False, scale=1, bUseLocalCurve=True, localScoreCurve=dict(editorCurveData=dict(keys=[dict(time=0, value=0, interpMode='RCIM_Linear'), dict(time=1, value=1, interpMode='RCIM_Linear')])), truncateOutput='None', postTruncateScale=1, offset=0), outputClampDetails=dict(bApplyClampMin=True, clampMinValue=0, bApplyClampMax=True, clampMaxValue=1))))
        if new:
            a.edge(upstream, name)

    update('spawn_wall', dict(templateDescriptor=dict(bVisible=False)))
    projection = dict(method='Normal', projectionVector=g.const(g.v(0, 0, 1)))
    update('wall_envelope', dict(bOutputClusters=False, projectionDetails=projection))
    update('inside_wall', dict(projectionDetails=projection, sampleInputs='ClosedLoopOnly',
        bAlwaysSampleWhenInside=True, bOnlySampleWhenInside=True, heightInclusion=0,
        bPruneFailedSamples=True, applySampling=dict(bApplyTransform=False, bApplyLookAt=False),
        bWriteSuccess=True, successAttributeName='InsideWall', bWriteDistance=True,
        distanceAttributeName='WallBoundaryDistance'))
    doc = surface
    for chunk, start in enumerate(range(0, len(doc['records']), 4000)):
        pts = [dict(transform=dict(location=g.v(c*50, r*50, 1000000), scale=g.v(1, 1, 1)), density=1, boundsMin=g.v(-1, -1, -1), boundsMax=g.v(1, 1, 1), color=dict(x=1, y=1, z=1, w=clearance), seed=r*4033+c, steepness=1, metadataEntry=-1) for r, c, _, clearance in doc['records'][start:start+4000]]
        update('surface_grid_' + str(chunk), dict(pointsToCreate=pts))
    copy('clearance_attribute', '$Color.W', 'SourceClearanceCm', 'inside_wall')
    remap('hull_fade', 'WallBoundaryDistance', 'HullBlend', 75, 500, 'clearance_attribute')
    remap('clearance_fade', 'SourceClearanceCm', 'ClearanceBlend', 200, 600, 'hull_fade')
    new = 'wall_blend' not in a.state['nodes']
    put('wall_blend', 'UPCGExBlendAttributesSettings')
    opnew = 'wall_blend_min' not in a.state['nodes']
    put('wall_blend_min', 'UPCGExBlendOpFactoryProviderSettings', dict(config=dict(blendMode='Min', operandA='HullBlend', bUseOperandB=True, operandB='ClearanceBlend', outputMode='New', outputTo='WallBlend', outputType='A')))
    if new:
        a.edge('clearance_fade', 'wall_blend')
    if opnew:
        a.edge('wall_blend_min', 'wall_blend', 'Blend Op', 'Blend Ops')
    copy('encode_wall_blend', 'WallBlend', '$Color.W', 'wall_blend')
    update('connected_cells', dict(importDetails=dict(bImportVertexColor=True)))
    copy('preserve_wall_blend', '$Color.W', 'WallBlend', 'project_normals')
    copy('restore_wall_blend', 'WallBlend', '$Color.W', 'encode_normals')
    if not a.state.get('material_blend_wired'):
        assert disconnect('inside_wall', 'source_grid')
        a.edge('encode_wall_blend', 'source_grid')
        for pin in ['Source', 'Target']:
            assert disconnect('project_normals', 'encode_normals', 'Out', pin)
            a.edge('preserve_wall_blend', 'encode_normals', 'Out', pin)
        assert disconnect('encode_normals', 'wall_surface', 'Out', 'Vtx')
        a.edge('restore_wall_blend', 'wall_surface', 'Out', 'Vtx')
        a.state['material_blend_wired'] = True
        a.save()


def configure_material(a, state):
    """Reuse the original five-role graph; native vertex alpha selects limestone."""
    tool = "editor_toolset.toolsets.material.MaterialTools"
    material = state["material"]
    sample = g.ref(material["refPath"] + ":MaterialExpressionTextureSampleParameter2D_0")
    g.require(a.call(g.OBJECT, "get_properties", dict(instance=sample, properties=["ParameterName"]))["ParameterName"] == "WeightTex", "Original weight sampler differs")
    def link(source, output, target, pin):
        a.call(tool, "connect_expressions", dict(from_expression=source,
            from_output_name=output, to_expression=target, to_input_name=pin))
        inputs = a.call(tool, "get_expression_inputs", dict(material_or_function=material, expression=target))
        g.require(any(i["expression"] == source and (i["input_name"] == pin or (not pin and i["input_name"] == "None")) for i in inputs), "Material connection did not apply")
    nodes = state["nodes"]
    g.require(a.call(g.OBJECT, "set_properties", dict(instance=nodes["rock"], values=json.dumps({"Constant": {"r": 0, "g": 0, "b": 1, "a": 0}}))), "ExposedRock weight setup failed")
    link(sample, "RGBA", nodes["weights"], "A")
    link(nodes["rock"], "", nodes["weights"], "B")
    link(nodes["vertex"], "A", nodes["weights"], "Alpha")
    for target in state["targets"]:
        link(nodes["weights"], "", target, "")
    a.call(tool, "recompile", dict(material_or_function=material))
