"""Bounded convex collision geometry, including planar hulls.

Faces keep the caller's vertex indices. Planes face outward and contain every
input point after float32 rounding; no external geometry runtime is needed.
"""
import math
import struct

from .collision_mopp import _float32
from .formats import FormatError

MAX_POINTS = 4096
MAX_WORK = 4_000_000


def _sub(a,b):
    return tuple(a[i]-b[i] for i in range(3))


def _dot(a,b):
    return sum(a[i]*b[i] for i in range(3))


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def _normal(value):
    length=math.sqrt(_dot(value,value))
    if not length:
        raise FormatError('A convex collision needs non-collinear vertices')
    return tuple(v/length for v in value)


def _plane(normal,points):
    normal=tuple(_float32(v) for v in normal)
    target=-max(_dot(normal,point) for point in points)
    offset=_float32(target)
    if offset>target:
        # Round toward the outside, including when the nearest value is -0.
        bits=struct.unpack('<I',struct.pack('<f',offset))[0]
        bits=(bits+1 if bits&0x80000000 else bits-1) if offset else 0x80000001
        offset=struct.unpack('<f',struct.pack('<I',bits))[0]
    return [*normal,offset]


def build(vertices):
    if not isinstance(vertices,list) or not 3<=len(vertices)<=MAX_POINTS:
        raise FormatError(f'A convex collision needs 3 to {MAX_POINTS} vertices')
    points=[]
    for vertex in vertices:
        if not isinstance(vertex,(list,tuple)) or len(vertex) not in (3,4):
            raise FormatError('A convex collision vertex needs three coordinates')
        if any(type(v) not in (int,float) for v in vertex[:3]):
            raise FormatError('Convex collision coordinates must be numbers')
        points.append(tuple(_float32(v) for v in vertex[:3]))
    unique=list(dict.fromkeys(points))
    if len(unique)<3:
        raise FormatError('A convex collision needs three distinct vertices')
    identities={point:i for i,point in reversed(list(enumerate(points)))}
    span=max(max(p[i] for p in unique)-min(p[i] for p in unique) for i in range(3))
    epsilon=max(span*1e-6,max(abs(v) for p in unique for v in p)*2**-22,1e-20)
    p0=unique[0]
    p1=max(unique,key=lambda p:_dot(_sub(p,p0),_sub(p,p0)))
    axis=_normal(_sub(p1,p0))
    p2=max(unique,key=lambda p:_dot(_cross(axis,_sub(p,p0)),_cross(axis,_sub(p,p0))))
    cross=_cross(axis,_sub(p2,p0))
    if math.sqrt(_dot(cross,cross))<=epsilon:
        raise FormatError('A convex collision needs non-collinear vertices')
    normal=_normal(cross)
    p3=max(unique,key=lambda p:abs(_dot(normal,_sub(p,p0))))
    if abs(_dot(normal,_sub(p3,p0)))<=epsilon:
        vertical=_cross(normal,axis)
        projected=sorted((_dot(_sub(p,p0),axis),_dot(_sub(p,p0),vertical),identities[p]) for p in unique)
        def half(sequence):
            result=[]
            for point in sequence:
                while len(result)>1:
                    a,b=result[-2:]
                    area=(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
                    if area>0:break
                    result.pop()
                result.append(point)
            return result
        boundary=[p[2] for p in half(projected)[:-1]+half(reversed(projected))[:-1]]
        if len(boundary)<3:
            raise FormatError('A convex collision needs non-collinear vertices')
        faces=[[boundary[0],boundary[i],boundary[i+1],0] for i in range(1,len(boundary)-1)]
        normals=[normal,tuple(-v for v in normal)]
        normals.extend(_normal(_cross(_sub(points[b],points[a]),normal))
                       for a,b in zip(boundary,boundary[1:]+boundary[:1]))
        return {'faces':faces,'planes':[_plane(n,points) for n in normals],'planar':True}
    seeds=[identities[p] for p in (p0,p1,p2,p3)]
    # Float32 quantization helps classify a nearly planar source, but must
    # not omit visible facets while extending a three-dimensional hull.
    visible_epsilon=max(span*1e-12,max(abs(v) for p in unique for v in p)*2**-44,1e-30)
    center=tuple(sum(points[index][axis] for index in seeds)/4 for axis in range(3))
    def face(a,b,c):
        cross=_cross(_sub(points[b],points[a]),_sub(points[c],points[a]))
        if math.sqrt(_dot(cross,cross))<=visible_epsilon*visible_epsilon:
            return None
        normal=_normal(cross)
        if _dot(normal,_sub(center,points[a]))>0:
            b,c=c,b
            normal=tuple(-v for v in normal)
        return (a,b,c,normal,-_dot(normal,points[a]))
    a,b,c,d=seeds
    faces=[face(a,b,c),face(a,d,b),face(a,c,d),face(b,d,c)]
    work=0
    for point in unique:
        index=identities[point]
        if index in seeds:continue
        work+=len(faces)
        if work>MAX_WORK:
            raise FormatError('This convex collision exceeds the hull calculation limit')
        visible=[i for i,f in enumerate(faces) if _dot(f[3],point)+f[4]>visible_epsilon]
        if not visible:continue
        horizon={}
        for i in visible:
            f=faces[i]
            for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
                key=tuple(sorted((a,b)))
                if key in horizon:horizon.pop(key)
                else:horizon[key]=(a,b)
        removed=set(visible)
        faces=[f for i,f in enumerate(faces) if i not in removed]
        for a,b in horizon.values():
            replacement=face(a,b,index)
            if replacement is not None:faces.append(replacement)
    normals={}
    for f in faces:
        plane=_plane(f[3],points)
        key=tuple(round(v,7) for v in plane[:3])+(round(plane[3]/epsilon),)
        normals.setdefault(key,plane)
    return {'faces':[[*f[:3],0] for f in faces],'planes':list(normals.values()),'planar':False}
