"""Convex surfaces contain their points and retain stable record indices."""
import itertools
import random

import pytest

from plugins.ds1 import collision_hull


def contained(result,points):
    return all(sum(plane[i]*point[i] for i in range(3))+plane[3]<=1e-9
               for plane in result['planes'] for point in points)


def test_planar_quad_planes_and_faces_keep_original_indices():
    points=[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0],[0,0,0],[-1,-1,0]]
    result=collision_hull.build(points)
    assert result['planar'] and len(result['faces'])==2 and len(result['planes'])==6
    assert {index for face in result['faces'] for index in face[:3]}=={0,1,2,3}
    assert contained(result,points)
    assert not contained(result,[[2,0,0]])
    assert not contained(result,[[0,0,.01]])


def test_cube_triangles_have_outward_winding_and_correct_volume():
    points=[list(point) for point in itertools.product((-1.,1.),repeat=3)]
    points.append([0,0,0])
    result=collision_hull.build(points)
    assert not result['planar'] and len(result['faces'])==12 and len(result['planes'])==6
    assert contained(result,points)
    edges={}
    volume=0
    for face in result['faces']:
        a,b,c=(points[index] for index in face[:3])
        normal=collision_hull._cross(collision_hull._sub(b,a),collision_hull._sub(c,a))
        assert collision_hull._dot(normal,a)>0
        volume+=collision_hull._dot(a,collision_hull._cross(b,c))/6
        for edge in zip(face[:3],face[1:3]+face[:1]):
            key=tuple(sorted(edge));edges[key]=edges.get(key,0)+1
    assert set(edges.values())=={2}
    assert volume==pytest.approx(8)


def test_long_thin_planar_hull_keeps_small_corners():
    points=[[-100000.125,-1,0],[1.234567,-1,0],[1,1,0],[-1,1,0]]
    hull=collision_hull.build(points)
    assert {index for face in hull['faces'] for index in face[:3]}=={0,1,2,3}


def test_random_hull_and_float32_plane_rounding():
    rng=random.Random(4)
    points=[[rng.uniform(-4,4)+400,rng.uniform(-2,2)-170,rng.uniform(-3,3)-100] for _ in range(90)]
    result=collision_hull.build(points)
    rounded=[[collision_hull._float32(v) for v in p] for p in points]
    assert contained(result,rounded)
    assert not contained(result,[[500,0,0]])
    assert collision_hull.build(points)==result


def test_nearly_coplanar_facets_remain_a_closed_convex_surface():
    points=[]
    rng=random.Random(8)
    for fixed in range(3):
        for side in (-1,1):
            for a,b in itertools.product(range(5),repeat=2):
                point=[0.,0.,0.]
                point[fixed]=side+rng.uniform(-1e-5,1e-5)
                free=[axis for axis in range(3) if axis!=fixed]
                point[free[0]]=a/2-1;point[free[1]]=b/2-1
                points.append([collision_hull._float32(v+shift) for v,shift in zip(point,(400,-170,-100))])
    result=collision_hull.build(points)
    edges={}
    for face in result['faces']:
        a,b,c=(points[index] for index in face[:3])
        normal=collision_hull._normal(collision_hull._cross(collision_hull._sub(b,a),collision_hull._sub(c,a)))
        assert max(collision_hull._dot(normal,collision_hull._sub(p,a)) for p in points)<1e-7
        for edge in zip(face[:3],face[1:3]+face[:1]):
            key=tuple(sorted(edge));edges[key]=edges.get(key,0)+1
    assert set(edges.values())=={2}


@pytest.mark.parametrize('points',[[[0,0,0]]*3,[[0,0,0],[1,0,0],[2,0,0]],
    [[0,0,0],[1,0,0],[0,float('nan'),0]],[[0,0,0]]*(collision_hull.MAX_POINTS+1)])
def test_invalid_hull_is_rejected(points):
    with pytest.raises(ValueError):collision_hull.build(points)
