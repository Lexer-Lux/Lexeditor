"""Locally rendered inventory PNGs. One low-priority worker, no live icon canvas.

Cache identity comes from the full module/BRF/material/DDS dependency chain.
Only generated thumbnails and individual resolved textures are cached locally.
"""
from __future__ import annotations

from array import array
import hashlib
import math
from pathlib import Path
import queue
import threading
import time

from PIL import Image, ImageDraw

from . import model_preview as models

RENDER_VERSION = "inventory-orthographic-three-quarter-v1"
SIZE = 192


def icon_key(dependency_key: str) -> str:
    return hashlib.sha256(f"{RENDER_VERSION}|{SIZE}|{dependency_key}".encode()).hexdigest()


def render_icon(data: dict, texture: Path, destination: Path) -> None:
    """Small software z-buffer renderer; does not require a GPU or game window."""
    g = data["geometry"]
    yaw, pitch = .64, -.30
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)

    def rotate(v):
        # Warband Z-up to screen Y-up, matching the full preview's conversion.
        x, y, z = v[0], v[2], -v[1]
        x, z = cy*x+sy*z, -sy*x+cy*z
        return x, cp*y-sp*z, sp*y+cp*z

    points = [rotate(p) for p in g["positions"]]
    if not points or not g["triangles"] or not all(math.isfinite(v) for p in points for v in p):
        raise models.PreviewUnavailable("The mesh has no finite thumbnail geometry.")
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    scale = (SIZE-30)/max(xmax-xmin, ymax-ymin, .00001)
    center = ((xmin+xmax)/2, (ymin+ymax)/2)
    points = [((x-center[0])*scale+SIZE/2, SIZE/2-(y-center[1])*scale, z) for x,y,z in points]
    image = Image.new("RGBA", (SIZE,SIZE), (222,216,203,255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((35,SIZE-29,SIZE-35,SIZE-16), fill=(197,191,179,255))
    pixels = image.load()
    zbuffer = array("f", [float("inf")])*(SIZE*SIZE)
    with Image.open(texture) as source:
        tex = source.convert("RGBA")
    texels, tw, th = tex.load(), tex.width, tex.height
    normals = [rotate(n) for n in g["normals"]]
    for triangle in g["triangles"]:
        a,b,c = [points[i] for i in triangle]
        denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denominator)<1e-10:
            continue
        x0,x1 = max(0,math.floor(min(a[0],b[0],c[0]))), min(SIZE-1,math.ceil(max(a[0],b[0],c[0])))
        y0,y1 = max(0,math.floor(min(a[1],b[1],c[1]))), min(SIZE-1,math.ceil(max(a[1],b[1],c[1])))
        normal = [sum(normals[i][axis] for i in triangle)/3 for axis in range(3)]
        length = math.sqrt(sum(v*v for v in normal)) or 1
        # Consistent key light and ambient fill. Render both sides of thin gear.
        light = .48+.52*abs(sum(n*k for n,k in zip(normal,(-.3,.7,-.65)))/length)
        uv = [g["texCoords"][i] for i in triangle]
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                px,py = x+.5,y+.5
                w0 = ((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/denominator
                w1 = ((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/denominator
                w2 = 1-w0-w1
                if min(w0,w1,w2)<-1e-6:
                    continue
                z = w0*a[2]+w1*b[2]+w2*c[2]
                offset = y*SIZE+x
                if z>=zbuffer[offset]:
                    continue
                u = w0*uv[0][0]+w1*uv[1][0]+w2*uv[2][0]
                v = w0*uv[0][1]+w1*uv[1][1]+w2*uv[2][1]
                rgba = texels[min(tw-1,int((u%1)*tw)), min(th-1,int(((1-v)%1)*th))]
                if rgba[3]<32:
                    continue
                pixels[x,y] = tuple(min(255,round(channel*light)) for channel in rgba[:3])+(255,)
                zbuffer[offset] = z
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix(".tmp.png")
    image.save(temporary,"PNG",optimize=True)
    temporary.replace(destination)


class IconCache:
    """Dependency checks on requests; deduplicated generation on a daemon worker."""
    def __init__(self):
        self._lock = threading.Lock()
        self._queue = queue.PriorityQueue()
        self._pending: dict[str, tuple[int, int]] = {}
        self._active: set[str] = set()
        self._errors: dict[str, tuple[float,str]] = {}
        self._worker: threading.Thread | None = None
        self._sequence = 0
        self._warmed = False

    def request(self, mesh: str, *, priority: int = 0) -> Path | None:
        resolved = models.dependencies(mesh)
        key = icon_key(resolved["key"])
        target = models.CACHE_ROOT / "item-icons" / f"{key}.png"
        if target.is_file():
            return target
        with self._lock:
            error = self._errors.get(key)
            if error and time.monotonic()-error[0]<15:
                raise models.PreviewUnavailable(error[1])
            queued = self._pending.get(key)
            if queued is None or (priority < queued[0] and key not in self._active):
                self._sequence += 1
                self._pending[key] = (priority, self._sequence)
                self._queue.put((priority,self._sequence,key,mesh,target,resolved["key"]))
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run,name="warband-item-icons",daemon=True)
                self._worker.start()
        return None

    def warm(self, meshes) -> None:
        with self._lock:
            if self._warmed:
                return
            self._warmed = True
        def enqueue():
            for mesh in dict.fromkeys(meshes):
                if not mesh:
                    continue
                try:
                    self.request(mesh, priority=10)
                except (OSError, ValueError, models.PreviewUnavailable):
                    pass  # The visible item request supplies its own error message.
                time.sleep(.05)
        threading.Thread(target=enqueue,name="warband-icon-warmup",daemon=True).start()

    def _run(self):
        while True:
            _priority,_sequence,key,mesh,target,dependency = self._queue.get()
            with self._lock:
                if self._pending.get(key) != (_priority, _sequence):
                    self._queue.task_done()
                    continue  # superseded by a foreground request
                self._active.add(key)
            try:
                data = models.preview(mesh)
                # A source can change between enqueue and execution. Never cache
                # new pixels under the old dependency identity.
                if data["cacheKey"] != dependency:
                    continue
                texture = models.texture_path(data["cacheKey"])
                if texture is None:
                    raise models.PreviewUnavailable("The decoded inventory texture is unavailable.")
                render_icon(data,texture,target)
                with self._lock:
                    self._errors.pop(key,None)
            except Exception as error:
                with self._lock:
                    self._errors[key] = (time.monotonic(),str(error))
            finally:
                with self._lock:
                    self._pending.pop(key, None)
                    self._active.discard(key)
                self._queue.task_done()
            time.sleep(.03)


CACHE = IconCache()
