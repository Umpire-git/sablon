"""Blender içinde çalışan fotogerçekçi render betiği.

İki şekilde çağrılır:
  * Blender Python paketi (pip install bpy) kuruluysa doğrudan: render_scene(veri, çıktı, kalite)
  * Normal Blender programıyla:  blender -b --factory-startup -P blender_render.py -- sahne.json cikti.png kalite
Yalnızca bpy, json ve math kullanır (Blender'ın kendi Python'unda çalışabilsin diye).
"""
import json
import math
import sys

import bpy
from mathutils import Vector

MM = 0.001  # sahne birimi: metre; model mm


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _principled(name, color, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.35
    return m, b


def _leather(name, base, crazy, bend=False):
    m, bsdf = _principled(name, base, 0.45 if crazy else 0.58, coat=0.25 if crazy else 0.05)
    nt, nodes, links = m.node_tree, m.node_tree.nodes, m.node_tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    mapn = nodes.new("ShaderNodeMapping")
    mapn.inputs["Scale"].default_value = (1000.0, 1000.0, 1000.0)  # UV metre → mm
    links.new(tex.outputs["UV"], mapn.inputs["Vector"])
    # renk dalgalanması (crazy horse'ta belirgin "pull-up" lekeleri)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.035 if crazy else 0.05
    noise.inputs["Detail"].default_value = 6.0
    links.new(mapn.outputs["Vector"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    k = 1.35 if bend and crazy else 1.0
    lo = tuple(min(1, c * (0.72 if crazy else 0.86) * k) for c in base)
    hi = tuple(min(1, c * (1.25 if crazy else 1.1) * k) for c in base)
    ramp.color_ramp.elements[0].color = (*lo, 1)
    ramp.color_ramp.elements[1].color = (*hi, 1)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    # gözenek / doku kabartısı
    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 2.2
    links.new(mapn.outputs["Vector"], vor.inputs["Vector"])
    fine = nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1.5
    links.new(mapn.outputs["Vector"], fine.inputs["Vector"])
    mix = nodes.new("ShaderNodeMath")
    mix.operation = "ADD"
    links.new(vor.outputs["Distance"], mix.inputs[0])
    links.new(fine.outputs["Fac"], mix.inputs[1])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.045 if crazy else 0.07
    bump.inputs["Distance"].default_value = 0.0003
    links.new(mix.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def build(data):
    _reset()
    sc = bpy.context.scene
    base = tuple(data["base"])
    crazy = data["crazy"]
    mats = [
        _principled("bos", (0.5, 0.5, 0.5))[0],                                   # 0 (kullanılmaz)
        _leather("deri", base, crazy),                                             # 1 LEATHER
        _principled("kenar", tuple(c * 0.42 for c in base), 0.32, coat=0.4)[0],   # 2 EDGE (perdahlı)
        _leather("kivrim", base, crazy, bend=True),                                # 3 BEND
        _principled("metal", (0.86, 0.82, 0.74), 0.22, metal=1.0)[0],             # 4 METAL
        _principled("kart", (0.10, 0.22, 0.48), 0.18, coat=0.8)[0],               # 5 CARD_TOP
        _principled("kart_kenar", (0.92, 0.92, 0.88), 0.5)[0],                    # 6 CARD_SIDE
        _principled("yarik", (0.02, 0.014, 0.01), 0.9)[0],                        # 7 DARK
    ]
    P, N, UV, M = data["P"], data["N"], data["UV"], data["M"]
    nt = len(M)
    verts = [(P[i * 3] * MM, P[i * 3 + 1] * MM, P[i * 3 + 2] * MM) for i in range(nt * 3)]
    faces = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(nt)]
    me = bpy.data.meshes.new("urun")
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", M)
    uv = me.uv_layers.new(name="UV")
    uv.data.foreach_set("uv", [v * MM for v in UV])
    me.update()
    me.shade_smooth()
    me.normals_split_custom_set([(N[i * 3], N[i * 3 + 1], N[i * 3 + 2]) for i in range(nt * 3)])
    ob = bpy.data.objects.new("urun", me)
    sc.collection.objects.link(ob)

    # zemin + arka plan (sonsuz stüdyo)
    zmin = data["zmin"] * MM
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(data["ctr"][0] * MM, data["ctr"][1] * MM, zmin - 0.0002))
    floor = bpy.context.active_object
    fm, fb = _principled("zemin", tuple(data["floor"]), 0.75)
    floor.data.materials.append(fm)

    # ışıklar
    r = data["radius"] * MM
    ctr = Vector([c * MM for c in data["ctr"]])

    def area(name, loc, power, size, color=(1, 1, 1)):
        li = bpy.data.lights.new(name, "AREA")
        li.energy = power
        li.size = size
        li.color = color
        o = bpy.data.objects.new(name, li)
        o.location = ctr + Vector(loc)
        o.rotation_euler = (o.location - ctr).to_track_quat("Z", "Y").to_euler()
        sc.collection.objects.link(o)

    s = max(r, 0.04) / 0.06
    area("ana", (-0.18 * s, -0.12 * s, 0.30 * s), 3.2 * s * s, 0.30 * s, (1.0, 0.96, 0.9))
    area("dolgu", (0.25 * s, 0.05 * s, 0.18 * s), 0.9 * s * s, 0.45 * s, (0.9, 0.95, 1.0))
    area("arka", (0.05 * s, 0.30 * s, 0.22 * s), 1.4 * s * s, 0.25 * s)
    w = bpy.data.worlds.new("dunya")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*data["floor"], 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.045
    sc.world = w

    # kamera
    cd = bpy.data.cameras.new("kamera")
    cd.lens = 85
    cam = bpy.data.objects.new("kamera", cd)
    cam.location = Vector([c * MM for c in data["eye"]])
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    cd.clip_start = 0.001
    sc.collection.objects.link(cam)
    sc.camera = cam
    cd.dof.use_dof = False
    return sc


def _eevee_name():
    items = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    for n in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if n in items:
            return n
    return None


def _use_gpu(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = "GPU"
                return kind
    except Exception:
        pass
    sc.cycles.device = "CPU"
    return "CPU"


def render_scene(data, out_path, quality="kaliteli"):
    sc = build(data)
    sc.render.resolution_x, sc.render.resolution_y = data["size"]
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = out_path
    vts = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in vts else "Filmic"
    try:
        sc.view_settings.look = "AgX - Punchy" if "AgX" in vts else "Medium High Contrast"
    except TypeError:
        sc.view_settings.look = "None"
    sc.view_settings.exposure = -0.6
    device = "CPU"
    eevee = _eevee_name()
    if quality == "hizli" and eevee:
        try:
            sc.render.engine = eevee
            sc.eevee.taa_render_samples = 32
            bpy.ops.render.render(write_still=True)
            return "eevee"
        except Exception:
            pass  # ekran kartı yoksa Cycles'a düş
    sc.render.engine = "CYCLES"
    device = _use_gpu(sc)
    import os
    default = 24 if quality.startswith("hizli") else 64
    sc.cycles.samples = int(os.environ.get("SABLON_ORNEK", default))
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = False
    bpy.ops.render.render(write_still=True)
    return f"cycles-{device.lower()}"


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with open(argv[0], encoding="utf-8") as f:
        payload = json.load(f)
    print("SABLON_RENDER", render_scene(payload, argv[1], argv[2] if len(argv) > 2 else "kaliteli"))
