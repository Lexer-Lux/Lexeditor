"""Bounded FF8 battle-model decoding and GLB export using the credited decoder."""
from __future__ import annotations

import math
import base64
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace

from . import assets
from .vendor.ff8ue.monsterdata import BoneSection, GeometrySection, AnimationSection
from .vendor.ff8ue.gltfexporter import GltfExporter, _transform_point


class ModelExporter(GltfExporter):
    """Retain colored primitives which the upstream monster exporter omits."""
    def _collect_triangulated_faces(self):
        if hasattr(self, '_resolved_faces'):
            return [face for face in self._resolved_faces if not getattr(self, '_textures_only', False) or face[2] >= 0]
        faces=super()._collect_triangulated_faces()
        if getattr(self,'_textures_only',False): return faces
        offset=0
        for obj in self.ifrit_manager.enemy.geometry_data.object_data:
            for primitive in obj.colored_triangles+obj.colored_quads:
                if primitive.is_hidden(): continue
                indices=[index+offset for index in primitive.vertex_indexes]
                color=-(primitive.color_command & 0xffffff)-2
                triangles=((indices[2],indices[0],indices[1]),) if len(indices)==3 else (
                    (indices[0],indices[1],indices[3]),(indices[0],indices[2],indices[3]))
                faces.extend((triangle,((0.,0.),)*3,color) for triangle in triangles)
            offset+=sum(group.nb_vertices for group in obj.vertices_data)
        return faces

    def _build_materials(self,builder,gltf):
        self._textures_only=True
        try: mapping=super()._build_materials(builder,gltf)
        finally: self._textures_only=False
        for color in sorted({face[2] for face in self._collect_triangulated_faces() if face[2]<0}):
            rgb=-color-2
            mapping[color]=len(gltf['materials'])
            gltf['materials'].append({'name':f'color_{rgb:06x}',
                'pbrMetallicRoughness':{'baseColorFactor':[(rgb>>shift & 255)/255 for shift in (0,8,16)]+[1.],
                    'metallicFactor':0.,'roughnessFactor':1.},'doubleSided':True})
        return mapping


def decode(filename: str, data: bytes, *, animations: bool = True, object_id: int | None = None):
    if len(data) > 16*1024*1024:
        raise ValueError('Model exceeds the 16 MB decoding limit')
    parts = assets.effect_model_parts(filename, data)
    if parts:
        selected = 0 if object_id is None else object_id
        if not 0 <= selected < len(parts):
            raise ValueError('Unknown model part')
        part = parts[selected]
        data = data[part['offset']:part['offset'] + part['size']]
    elif object_id is not None:
        raise ValueError('This model has no selectable parts')
    sections = assets.parse_dat_sections(data)
    if sections is None:
        raise ValueError('This file is not a supported battle model')
    kind,names = assets._section_names(filename,len(sections))
    geometry_section = assets._geometry_section(kind,sections)
    if geometry_section is None or assets._geometry_counts(data,geometry_section) is None:
        raise ValueError('This file has no verified model geometry')
    def section(name):
        if not names or name not in names: return b''
        span = sections[names.index(name)]
        return data[span['offset']:span['offset']+span['size']]
    skeleton = BoneSection()
    raw_bones = section('Skeleton')
    if raw_bones:
        if len(raw_bones)<16 or len(raw_bones)<16+raw_bones[0]*48:
            raise ValueError('Truncated model skeleton')
        skeleton.analyze(raw_bones)
        for index,bone in enumerate(skeleton.bones):
            # The native skeleton and decoder traverse parent-before-child.
            if bone.parent_id != 0xffff and not 0<=bone.parent_id<index:
                raise ValueError('Unsupported model bone hierarchy')
    geometry = GeometrySection()
    geometry.analyze(section('Model geometry'))
    animation = AnimationSection()
    raw_animation = section('Model animation')
    if raw_animation and skeleton.bones:
        if len(raw_animation)<4: raise ValueError('Truncated model animation header')
        count, = struct.unpack_from('<I',raw_animation)
        if count>256 or 4+4*count>len(raw_animation):
            raise ValueError('Unsupported model animation count')
        offsets = struct.unpack_from(f'<{count}I',raw_animation,4)
        if any(offset<4+4*count or offset>=len(raw_animation) for offset in offsets):
            raise ValueError('Invalid model animation offset')
        if animations and sum(raw_animation[offset] for offset in offsets)*len(skeleton.bones)>100000:
            raise ValueError('Model animation exceeds the decoded frame limit')
        if animations:
            animation.analyze(raw_animation,skeleton)
        elif offsets:
            # The preview only needs animation zero's initial pose. Do not
            # expand every animation merely to show a model thumbnail drawer.
            from .vendor.ff8ue.monsterdata import Animation, BitReader
            first = next((offset for offset in offsets if raw_animation[offset]),None)
            if first is not None:
                pose = Animation()
                pose.add_frame(BitReader(raw_animation,start_byte=first+1),skeleton)
                animation.animations=[pose]
    enemy = SimpleNamespace(bone_data=skeleton,geometry_data=geometry,
        animation_data=animation,info_stat_data={'monster_name':filename})
    textures=[]
    texture_section = assets._texture_section(kind,sections)
    if texture_section:
        layouts=assets._texture_layouts(data,texture_section)
        if layouts is None: raise ValueError('Invalid model texture section')
        start=texture_section['offset']
        count,=struct.unpack_from('<I',data,start)
        offsets=struct.unpack_from(f'<{count+1}I',data,start+4)
        for texture in layouts:
            textures.append(SimpleNamespace(texture_image=assets.tim_png_bytes(data,start+offsets[texture['index']]),index=texture['index']))
    exporter=ModelExporter(SimpleNamespace(enemy=enemy,texture_data=textures))
    positions,bones=exporter._collect_vertices()
    if len(positions)>100000 or not positions:
        raise ValueError('Unsupported model vertex count')
    frames=[frame for anim in animation.animations for frame in anim.frames]
    if frames and any(not 0<=bone<len(skeleton.bones) for bone in bones):
        raise ValueError('Model vertex refers to an absent bone')
    faces=exporter._collect_triangulated_faces()
    if len(faces)>200000 or any(not 0<=index<len(positions) for face in faces for index in face[0]):
        raise ValueError('Model face refers to an absent vertex')
    return exporter


def scene(filename: str, dataset: str = 'current', object_id: int | None = None, texture_source: str | None = None, frame: int = 0) -> dict:
    from . import effect_mesh
    if effect_mesh.FILENAME.fullmatch(filename):
        from . import effect_preview
        return effect_preview.scene(filename, dataset, object_id)
    if filename.startswith('mag') and filename.casefold() not in assets.EFFECT_MODEL_FILES:
        from . import effect_surface
        return effect_surface.scene(filename, assets.model_dat_bytes(filename, dataset), dataset, object_id, frame)
    if filename.casefold().startswith('a0stg') and filename.casefold().endswith('.x'):
        from . import battle_stage
        return battle_stage.scene(filename, assets.model_dat_bytes(filename, dataset))
    exporter=decode(filename,assets.model_dat_bytes(filename,dataset),animations=False,object_id=object_id)
    if filename.casefold() in assets.EFFECT_MODEL_FILES:
        from . import effect_model_textures
        effect_model_textures.resolve(exporter, effect_model_textures.sources(filename, dataset), texture_source)
    positions,bones=exporter._collect_vertices()
    animations=exporter.ifrit_manager.enemy.animation_data.animations
    frame=next((animation.frames[0] for animation in animations if animation.frames),None)
    if frame:
        matrices=exporter._global_bone_matrices(frame)
        positions=[_transform_point(matrices[bone],(x,-y,-z)) for (x,y,z),bone in zip(positions,bones)]
    if not all(math.isfinite(value) for position in positions for value in position):
        raise ValueError('Model contains an invalid transformed position')
    faces=exporter._collect_triangulated_faces()
    texture_ids=sorted({face[2] for face in faces if face[2]>=0})
    texture_count=len(exporter.ifrit_manager.texture_data)
    texture_map={key:min(index,texture_count-1) for index,key in enumerate(texture_ids)}
    return {'file':filename,'positions':positions,
        'triangles':[{'indices':indices,'uv':uv,'texture':texture_map[texture] if texture>=0 else texture} for indices,uv,texture in faces],
        'textures':[texture.index for texture in exporter.ifrit_manager.texture_data],
        'bones':len(exporter.ifrit_manager.enemy.bone_data.bones),
        **({'textureImages':['data:image/png;base64,' + base64.b64encode(texture.texture_image).decode('ascii') for texture in exporter.ifrit_manager.texture_data],
            'unmappedFaces': exporter.unmapped_effect_faces,
            'textureChoices': exporter.effect_texture_choices} if hasattr(exporter, '_resolved_faces') else {})}


def glb(filename: str, dataset: str = 'current', object_id: int | None = None, texture_source: str | None = None) -> bytes:
    exporter=decode(filename,assets.model_dat_bytes(filename,dataset),object_id=object_id)
    if filename.casefold() in assets.EFFECT_MODEL_FILES:
        from . import effect_model_textures
        effect_model_textures.resolve(exporter, effect_model_textures.sources(filename, dataset), texture_source)
    with tempfile.TemporaryDirectory(prefix='ff8-model-export-') as directory:
        target=Path(directory)/'model.glb'
        exporter.export(str(target))
        return target.read_bytes()
