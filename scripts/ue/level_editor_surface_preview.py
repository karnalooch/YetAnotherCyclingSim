"""Bounded transient road/shoulder appearance; no geometry, imports or saves."""
from __future__ import annotations
import math

LIVE_SCRIPT_ABI = 1

ROOT = '/Game/Generated/YACS/RoadAsphaltConsumer/'
ASPHALT = ROOT + 'aged_mountain_asphalt/dry_varied/9c0a41f6e2ae/'
ROAD_MATERIAL = ASPHALT + 'MI_MaterialForge.MI_MaterialForge'
SHOULDER_MATERIAL = ROOT + 'ShoulderNetwork/MI_ShoulderNetwork.MI_ShoulderNetwork'
TEXTURES = {name: ASPHALT + 'T_MF_' + suffix + '.T_MF_' + suffix for name, suffix in
            (('BaseColor','BaseColor'),('Normal_DX','NormalDX'),('ORM','ORM'),('DetailMasks','DetailMasks'))}
GRAVEL_ROOT = '/Game/Generated/YACS/TextureMaterialPrep/Libraries/3d53743e48394f31beb35e4030dc8a87/'
GRAVEL = {'BaseColor': GRAVEL_ROOT+'Sources/T_Source_FillGravel.T_Source_FillGravel',
          'Normal_DX': GRAVEL_ROOT+'ProviderData/FillGravel/T_Normal.T_Normal',
          'Roughness': GRAVEL_ROOT+'ProviderData/FillGravel/T_Roughness.T_Roughness'}
PRESETS = {'worn': {'CrackGain': 2.5, 'PatchGain': .32, 'BinderGain': .22, 'EdgeStartCm': 1., 'EdgeBreakupCm': 5., 'EdgeFeatherCm': 2.},
           'strong': {'CrackGain': 4., 'PatchGain': .52, 'BinderGain': .35, 'EdgeStartCm': 0., 'EdgeBreakupCm': 6., 'EdgeFeatherCm': 2.}}


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_observation(state, initial=None):
    require(type(state) is dict and set(state) == {'schema_version','preset','targets','parameters'}, 'Surface observation schema differs')
    require(type(state['schema_version']) is int and state['schema_version'] == 1, 'Surface version differs')
    preset = state['preset']
    require(preset in ('original', *PRESETS), 'Unknown surface preset')
    rows = state['targets']
    require(type(rows) is list and len(rows) == 186, 'Surface target count differs')
    labels = []
    for row in rows:
        require(type(row) is dict and set(row) == {'label','component','slot','original','current'}, 'Surface binding schema differs')
        label = row['label']
        require(type(label) is str and (label == 'YACS_PERSIST_ROAD' or label.startswith('YACS_PERSIST_SUPPORT_') and len(label) == 24 and label[-3:].isdigit()), 'Surface label differs')
        require(type(row['slot']) is int and row['slot'] == (0 if label == 'YACS_PERSIST_ROAD' else 1), 'Surface slot differs')
        expected = ROAD_MATERIAL if label == 'YACS_PERSIST_ROAD' else SHOULDER_MATERIAL
        require(row['original'] == expected, 'Original surface material differs')
        require(type(row['component']) is str and row['component'].startswith('/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.') and len(row['component']) < 512, 'Surface component path differs')
        require(row['current'] == expected if preset == 'original' else type(row['current']) is str and row['current'].startswith('/Engine/Transient.') and len(row['current']) < 512, 'Surface binding is not expected transient')
        labels.append(label)
    require(len(set(labels)) == 186 and labels.count('YACS_PERSIST_ROAD') == 1, 'Duplicate or missing surface target')
    params = state['parameters']
    expected = {} if preset == 'original' else PRESETS[preset]
    require(type(params) is dict and set(params) == set(expected), 'Surface parameter schema differs')
    for name, value in params.items():
        require(type(value) in (int,float) and math.isfinite(value) and abs(value-expected[name]) < 1e-5, 'Surface parameter readback differs')
    if initial is not None:
        validate_observation(initial)
        require([{k:v for k,v in r.items() if k != 'current'} for r in rows] == [{k:v for k,v in r.items() if k != 'current'} for r in initial['targets']], 'Surface ownership changed')
    return state


class SurfacePreview:
    def __init__(self, api, world, manifest):
        self.api, self.world = api, world
        require(manifest['material_instance'] == ROAD_MATERIAL and manifest['texture_objects'] == TEXTURES, 'Asphalt source differs')
        shoulder = manifest['shoulder_network']
        require(manifest.get('outer_terrain_enabled') is False and shoulder['material']['assets']['instance'] == SHOULDER_MATERIAL and shoulder['material']['texture_objects'] == GRAVEL, 'Shoulder source differs')
        owners = shoulder['owners']
        require(len(owners) == 186 and [r['support_label'] for r in owners] == [f'YACS_PERSIST_SUPPORT_{i:03d}' for i in range(186)], 'Shoulder owner inventory differs')
        require(sum(r['material_target'] is True for r in owners) == 185 and sum(r['material_target'] is False and r['kind'] == 'parapet' for r in owners) == 1, 'Shoulder exclusion differs')
        expected = {'YACS_PERSIST_ROAD': (0, ROAD_MATERIAL)}
        expected.update({r['support_label']:(1,SHOULDER_MATERIAL) for r in owners if r['material_target']})
        self.targets, seen = [], set()
        for actor in api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors():
            label = actor.get_actor_label()
            if label not in expected:
                continue
            require(label not in seen and isinstance(actor,api.DynamicMeshActor), 'Surface actor differs')
            seen.add(label)
            component = actor.get_dynamic_mesh_component()
            slot, path = expected[label]
            require(component.get_num_materials() == slot+1, 'Surface slot inventory differs')
            original = component.get_material(slot)
            require(original is not None and original.get_path_name() == path, 'Surface original binding differs')
            parent=original.get_editor_property('parent')
            parent_path=ASPHALT+'M_MaterialForge.M_MaterialForge' if slot==0 else ROOT+'ShoulderNetwork/M_ShoulderNetwork.M_ShoulderNetwork'
            require(parent is not None and parent.get_path_name()==parent_path, 'Surface original parent differs')
            self.targets.append((label,component,slot,original))
        require(seen == set(expected), 'Surface native target census differs')
        self.targets.sort(key=lambda row:row[0])
        self.preset, self.materials, self.mids = 'original', {}, {}
        self.initial = self.observe()

    def _graph(self, shoulder):
        a, lib = self.api, self.api.MaterialEditingLibrary
        master = a.Material()
        require(master.get_path_name().startswith('/Engine/Transient.'), 'Surface master must be transient')
        master.set_editor_property('tangent_space_normal', True)
        def node(name, **props):
            result = lib.create_material_expression(master,getattr(a,'MaterialExpression'+name))
            require(result is not None, 'Surface node creation failed')
            for key,value in props.items(): result.set_editor_property(key,value)
            return result
        def link(src,pin,dst,target):
            require(lib.connect_material_expressions(src,pin,dst,target), 'Surface graph connection failed')
        def scalar(name): return node('ScalarParameter',parameter_name=name,default_value=PRESETS['worn'][name])
        def const(value): return node('Constant',r=value)
        def binary(name,x,y):
            out=node(name); link(x,'',out,'A'); link(y,'',out,'B'); return out
        def unary(name,x):
            out=node(name); link(x,'',out,''); return out
        def channel(x,index):
            out=node('ComponentMask',r=index==0,g=index==1,b=index==2,a=False); link(x,'',out,''); return out
        def lerp(x,y,alpha):
            out=node('LinearInterpolate'); link(x,'',out,'A'); link(y,'',out,'B'); link(alpha,'',out,'Alpha'); return out
        def project(path,name,normal=False,masks=False,tile=400.):
            texture=a.load_asset(path)
            require(isinstance(texture,a.Texture2D) and texture.get_path_name()==path,'Surface texture identity differs')
            tex=node('TextureObjectParameter',parameter_name=name,texture=texture,sampler_type=a.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else a.MaterialSamplerType.SAMPLERTYPE_MASKS if masks else a.MaterialSamplerType.SAMPLERTYPE_COLOR)
            fn=a.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/'+('WorldAlignedNormal' if normal else 'WorldAlignedTexture'))
            require(fn is not None,'Surface projection unavailable')
            call=node('MaterialFunctionCall'); require(call.set_material_function(fn),'Surface function assignment failed')
            link(tex,'',call,'TextureObject'); link(const(tile),'',call,'TextureSize')
            if normal: link(node('StaticBool',value=False),'',call,'WorldSpace')
            out=node('Multiply',const_b=1.); link(call,'XYZ Texture',out,'A'); return out
        base=project(TEXTURES['BaseColor'],'BaseColorTex')
        normal=project(TEXTURES['Normal_DX'],'NormalTex',normal=True)
        orm=project(TEXTURES['ORM'],'ORMTex',masks=True)
        detail=project(TEXTURES['DetailMasks'],'DetailMasksTex',masks=True)
        # Source masks retain their original 4 m scale: R cracks, G patches, B binder variation.
        crack=unary('Saturate',binary('Multiply',channel(detail,0),scalar('CrackGain')))
        patches=binary('Multiply',channel(detail,1),scalar('PatchGain'))
        binder=binary('Multiply',channel(detail,2),scalar('BinderGain'))
        darkening=unary('Saturate',binary('Add',binary('Multiply',crack,const(.85)),patches))
        color=binary('Multiply',base,binary('Add',binary('Subtract',const(1.),darkening),binder))
        rough=unary('Saturate',binary('Add',channel(orm,1),binary('Multiply',crack,const(.04))))
        ao=binary('Multiply',channel(orm,0),binary('Subtract',const(1.),binary('Multiply',crack,const(.25))))
        if shoulder:
            gravel=project(GRAVEL['BaseColor'],'GravelBaseColorTex',tile=150.)
            gn=project(GRAVEL['Normal_DX'],'GravelNormalTex',normal=True,tile=150.)
            gr=project(GRAVEL['Roughness'],'GravelRoughnessTex',masks=True,tile=150.)
            uv=node('TextureCoordinate',coordinate_index=0,u_tiling=1.,v_tiling=1.)
            noise=unary('Saturate',binary('Multiply',channel(gravel,0),const(4.)))
            threshold=binary('Add',scalar('EdgeStartCm'),binary('Multiply',binary('Subtract',const(1.),noise),scalar('EdgeBreakupCm')))
            alpha=unary('Saturate',binary('Divide',binary('Subtract',channel(uv,0),threshold),scalar('EdgeFeatherCm')))
            color=lerp(color,gravel,alpha); normal=lerp(normal,gn,alpha); rough=lerp(rough,channel(gr,0),alpha); ao=lerp(ao,const(1.),alpha)
        for value,prop in ((color,'MP_BASE_COLOR'),(unary('Normalize',normal),'MP_NORMAL'),(rough,'MP_ROUGHNESS'),(ao,'MP_AMBIENT_OCCLUSION'),(const(.2),'MP_SPECULAR'),(const(0.),'MP_METALLIC')):
            require(lib.connect_material_property(value,'',getattr(a.MaterialProperty,prop)), 'Surface material output failed')
        require(not lib.recompile_material(master), 'Surface shader compilation failed')
        expected_scalars=set(PRESETS['worn']) if shoulder else {n for n in PRESETS['worn'] if not n.startswith('Edge')}
        require({str(n) for n in lib.get_scalar_parameter_names(master)}==expected_scalars, 'Surface scalar graph inventory differs')
        expected_textures={'BaseColorTex','NormalTex','ORMTex','DetailMasksTex'} | ({'GravelBaseColorTex','GravelNormalTex','GravelRoughnessTex'} if shoulder else set())
        require({str(n) for n in lib.get_texture_parameter_names(master)}==expected_textures, 'Surface texture graph inventory differs')
        return master

    def observe(self):
        rows=[]
        for label,component,slot,original in self.targets:
            current=component.get_material(slot)
            expected=original if self.preset=='original' else self.mids[slot]
            require(current==expected,'Surface native binding changed externally')
            rows.append({'label':label,'component':component.get_path_name(),'slot':slot,'original':original.get_path_name(),'current':current.get_path_name()})
        params={}
        if self.preset!='original':
            for key,expected in PRESETS[self.preset].items():
                values=[mid.get_scalar_parameter_value(key) for slot,mid in self.mids.items() if slot==1 or not key.startswith('Edge')]
                require(values and all(math.isfinite(v) and abs(v-expected)<1e-5 for v in values),'Surface native scalar readback differs: '+key)
                params[key]=float(values[0])
        return validate_observation({'schema_version':1,'preset':self.preset,'targets':rows,'parameters':params},getattr(self,'initial',None))

    def prepare(self):
        """Compile once before handoff; leaves every original binding untouched."""
        self.observe()
        if len(self.mids) == 2:
            return
        materials, mids = {}, {}
        for slot in (0,1):
            master=self._graph(slot==1)
            materials[slot]=master
            mid=self.api.MaterialLibrary.create_dynamic_material_instance(self.world,master,creation_flags=self.api.MIDCreationFlags.TRANSIENT)
            require(isinstance(mid,self.api.MaterialInstanceDynamic) and mid.get_editor_property('parent')==master and mid.get_path_name().startswith('/Engine/Transient.'),'Surface MID allocation failed')
            paths={'BaseColorTex':TEXTURES['BaseColor'],'NormalTex':TEXTURES['Normal_DX'],'ORMTex':TEXTURES['ORM'],'DetailMasksTex':TEXTURES['DetailMasks']}
            if slot==1: paths.update({'GravelBaseColorTex':GRAVEL['BaseColor'],'GravelNormalTex':GRAVEL['Normal_DX'],'GravelRoughnessTex':GRAVEL['Roughness']})
            for name,path in paths.items():
                texture=mid.get_texture_parameter_value(name)
                require(texture is not None and texture.get_path_name()==path,'Surface native texture readback differs')
            mids[slot]=mid
        self.materials, self.mids = materials, mids

    def apply(self,preset):
        require(preset in PRESETS,'Unknown surface preset')
        self.observe()
        try:
            self.prepare()
            for slot,mid in self.mids.items():
                for name,value in PRESETS[preset].items():
                    if slot==1 or not name.startswith('Edge'): mid.set_scalar_parameter_value(name,value)
            for _,component,slot,_ in self.targets: component.set_material(slot,self.mids[slot])
            self.preset=preset
            return self.observe()
        except Exception:
            # Fail back to authenticated original bindings, never retain a partial application.
            self.restore(check=False)
            raise

    def restore(self,check=True):
        if check: self.observe()
        failures=[]
        for label,component,slot,original in self.targets:
            try:
                current=component.get_material(slot)
                require(current==original or current==self.mids.get(slot), 'Foreign material preserved; refusing restore overwrite')
                component.set_material(slot,original)
                require(component.get_material(slot)==original,'Native restore readback differs')
            except Exception as exc: failures.append(label+': '+str(exc))
        self.preset='original'
        require(not failures,'Surface restore incomplete: '+'; '.join(failures))
        return self.observe()
