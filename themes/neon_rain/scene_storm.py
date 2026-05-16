"""
themes/neon_rain/scene_storm.py
────────────────────────────────
Blender Python scene builder — Heavy Storm variant.

Run inside Blender:
    blender.exe --background --python themes/neon_rain/scene_storm.py

Or from the Blender scripting tab (open file, click Run Script).

HOW TO USE:
    1. Edit SCENE_CONFIG below — all tunable values are here, nothing buried.
    2. Run the script. It builds the full scene from scratch.
    3. The script STOPS before rendering. You set the camera, make any
       final edits you want, then render manually (F12 or Timeline → Render).
    4. Save as scene_storm.blend when you're happy with the scene setup.

WHAT DIFFERS FROM scene_drizzle.py:
    - RAIN: higher count, faster velocity, steep angle, strong wind
    - FOG:  higher density, heavier scatter — visibility cuts to ~60%
    Everything else (lights, ground, scene geometry) is identical.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Euler


# ══════════════════════════════════════════════════════════════════════════════
#  SCENE_CONFIG — edit values here, nothing else needs to change
# ══════════════════════════════════════════════════════════════════════════════

SCENE_CONFIG = {

    # ── RAIN ─────────────────────────────────────────────────────────────────
    # Storm variant: high density, steep diagonal, strong wind.
    "RAIN": {
        "count":           8000,    # particle count — storm feel starts around 6000
        "velocity":        18.0,    # downward speed (m/s) — higher = faster streaks
        "angle_degrees":   25.0,    # tilt from vertical (0=straight down, 30=heavy wind)
        "streak_length":   0.18,    # length of each raindrop streak (meters)
        "streak_width":    0.004,   # width of streak — keep thin (0.002–0.008)
        "opacity":         0.55,    # 0.0–1.0 — storm can be slightly opaque
        "wind_force":      4.5,     # lateral wind force applied to particles
        "wind_turbulence": 1.8,     # random variation in wind — gusts
        "size":            0.006,   # particle object scale
        "lifetime":        80,      # frames each drop lives before recycling
        "emit_from_z":     12.0,    # height above ground particles spawn
        "emit_area_x":     30.0,    # horizontal spawn area width (x axis)
        "emit_area_y":     30.0,    # horizontal spawn area depth (y axis)
        "color":           (0.75, 0.82, 0.95, 1.0),  # RGBA — slightly blue-tinted
    },

    # ── FOG ──────────────────────────────────────────────────────────────────
    # Storm variant: thick, heavy. Cuts far-field visibility significantly.
    "FOG": {
        "density":         0.06,    # 0.0–0.2 — storm range: 0.04–0.10
        "scatter_color":   (0.55, 0.58, 0.72),  # RGB — cool blue-grey
        "absorption":      0.012,   # how much light the fog eats — keep low
        "anisotropy":      0.3,     # -1=backward scatter, 0=uniform, 1=forward
        "height_falloff":  0.15,    # fog thins above this height (meters)
        "step_size":       0.08,    # volumetric march step — lower=quality, higher=speed
    },

    # ── LIGHTS ───────────────────────────────────────────────────────────────
    # Identical in storm and drizzle — neon character stays consistent.
    "LIGHTS": {
        # Primary neon color (magenta/pink — classic cyberpunk)
        "neon_a_color":      (1.0,  0.08, 0.45),  # RGB — hot magenta
        "neon_a_intensity":  800.0,                # watts — neon signs are bright
        "neon_a_radius":     3.5,                  # light falloff radius (meters)

        # Secondary neon color (cyan/teal — complementary)
        "neon_b_color":      (0.05, 0.75, 0.95),  # RGB — electric cyan
        "neon_b_intensity":  600.0,
        "neon_b_radius":     4.0,

        # Accent neon (deep orange — distant signage warmth)
        "neon_c_color":      (1.0, 0.35, 0.02),   # RGB — sodium orange
        "neon_c_intensity":  350.0,
        "neon_c_radius":     5.0,

        # Flicker animation (applied to neon_a and neon_b)
        "flicker_enabled":   True,
        "flicker_speed":     12.0,  # higher = faster flicker
        "flicker_strength":  0.18,  # 0.0–1.0 — how much intensity varies

        # Ambient fill (very dim — preserves dark mood)
        "ambient_color":     (0.04, 0.04, 0.08),  # RGB — near-black cool blue
        "ambient_intensity": 0.6,                  # world shader strength

        # Street lamp (sodium yellow — one practical light source)
        "lamp_color":        (1.0,  0.78, 0.35),  # RGB — warm sodium
        "lamp_intensity":    250.0,
        "lamp_position":     (4.0, -3.0, 5.5),    # XYZ

        # Bloom (post-process glow — key to neon look)
        "bloom_threshold":   0.85,  # only pixels above this brightness glow
        "bloom_intensity":   1.4,   # glow strength
        "bloom_radius":      6.5,   # spread radius (pixels at 1440p)
    },

    # ── GROUND ───────────────────────────────────────────────────────────────
    # Wet asphalt with puddles and neon reflections.
    "GROUND": {
        "size":                  40.0,   # ground plane extent (meters, square)
        "wet_roughness":         0.04,   # 0.0=mirror, 1.0=matte — wet=0.02–0.08
        "reflection_strength":   0.85,   # 0.0–1.0 — how much light it bounces
        "base_color":            (0.04, 0.04, 0.05),  # RGB — dark wet asphalt
        "puddle_density":        0.65,   # 0.0–1.0 — fraction of ground covered
        "puddle_scale":          3.5,    # noise scale driving puddle shapes
        "puddle_ripple_speed":   0.8,    # animation speed of ripple rings
        "puddle_ripple_scale":   1.2,    # size of individual ripple rings
        "neon_tint_strength":    0.35,   # how strongly neon colors bleed into puddles
        "specular":              0.9,    # specular highlight intensity on wet surface
    },

    # ── SCENE GEOMETRY ───────────────────────────────────────────────────────
    # Building layout and world color. Camera is NOT set here — you place it.
    "SCENE": {
        "world_color":         (0.005, 0.005, 0.012),  # RGB — near-black night sky
        "world_strength":      0.8,
        "alley_width":         8.0,    # meters between building faces
        "alley_depth":         35.0,   # meters from front to back of scene
        "building_height_min": 12.0,   # meters — shortest building
        "building_height_max": 28.0,   # meters — tallest building
        "building_count":      6,      # buildings per side (left and right)
        "building_depth":      8.0,    # how deep each building block is
        "seed":                42,     # scene geometry randomisation seed
    },

    # ── RENDER DEFAULTS ──────────────────────────────────────────────────────
    # Applied to the scene but easily changed in Blender's Properties panel.
    "RENDER": {
        "engine":          "BLENDER_EEVEE_NEXT",
        "samples":         64,      # EEVEE samples — increase to 128+ for finals
        "resolution_x":    2560,
        "resolution_y":    1440,
        "fps":             30,
        "motion_blur":     True,    # ON for storm — rain streaks benefit from it
        "motion_blur_shutter": 0.35,  # shutter time — higher=longer streaks
        "use_volumetrics": True,
        "volumetric_samples": 64,
        "color_management_look": "High Contrast",  # Filmic look preset
        "exposure":        0.0,
        "gamma":           1.0,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  BUILDER — do not edit below unless you know what you're doing
# ══════════════════════════════════════════════════════════════════════════════

def reset_scene():
    """Remove everything from the default scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)


def make_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def link(obj, collection):
    collection.objects.link(obj)
    bpy.context.scene.collection.objects.unlink(obj) if obj.name in bpy.context.scene.collection.objects else None


# ── Ground ────────────────────────────────────────────────────────────────────

def build_ground(cfg: dict, col: bpy.types.Collection) -> bpy.types.Object:
    g = cfg["GROUND"]
    s = g["size"] / 2

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Ground"
    plane.scale = (g["size"], g["size"], 1)
    bpy.ops.object.transform_apply(scale=True)
    link(plane, col)

    mat = bpy.data.materials.new("MAT_Ground")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out      = nodes.new("ShaderNodeOutputMaterial")
    bsdf     = nodes.new("ShaderNodeBsdfPrincipled")
    noise    = nodes.new("ShaderNodeTexNoise")
    coloramp = nodes.new("ShaderNodeValToRGB")
    mix      = nodes.new("ShaderNodeMixShader")
    glossy   = nodes.new("ShaderNodeBsdfGlossy")
    coord    = nodes.new("ShaderNodeTexCoord")
    mapping  = nodes.new("ShaderNodeMapping")

    # Positions
    coord.location    = (-800, 0)
    mapping.location  = (-600, 0)
    noise.location    = (-400, 0)
    coloramp.location = (-200, 0)
    bsdf.location     = (0, 100)
    glossy.location   = (0, -100)
    mix.location      = (300, 0)
    out.location      = (500, 0)

    # Base asphalt
    bsdf.inputs["Base Color"].default_value   = (*g["base_color"], 1.0)
    bsdf.inputs["Roughness"].default_value    = g["wet_roughness"]
    bsdf.inputs["Specular IOR Level"].default_value = g["specular"] if "Specular IOR Level" in bsdf.inputs else 0.9
    bsdf.inputs["Metallic"].default_value     = 0.0

    # Glossy for wet reflection
    glossy.inputs["Roughness"].default_value  = g["wet_roughness"]
    glossy.inputs["Color"].default_value      = (1.0, 1.0, 1.0, 1.0)

    # Noise drives puddle mask
    noise.inputs["Scale"].default_value     = g["puddle_scale"]
    noise.inputs["Detail"].default_value    = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    noise.inputs["Distortion"].default_value = 0.3

    # ColorRamp shapes puddle edges (hard threshold = puddle boundary)
    cr = coloramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 1.0 - g["puddle_density"]
    cr.elements[0].color    = (0, 0, 0, 1)
    cr.elements[1].position = min((1.0 - g["puddle_density"]) + 0.15, 1.0)
    cr.elements[1].color    = (1, 1, 1, 1)

    mix.inputs["Fac"].default_value = g["reflection_strength"]

    links.new(coord.outputs["UV"],          mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"],    noise.inputs["Vector"])
    links.new(noise.outputs["Fac"],         coloramp.inputs["Fac"])
    links.new(coloramp.outputs["Color"],    mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"],         mix.inputs[1])
    links.new(glossy.outputs["BSDF"],       mix.inputs[2])
    links.new(mix.outputs["Shader"],        out.inputs["Surface"])

    plane.data.materials.append(mat)
    print(f"[Scene] Ground built ({g['size']}m × {g['size']}m, wet roughness={g['wet_roughness']})")
    return plane


# ── Buildings ─────────────────────────────────────────────────────────────────

def build_buildings(cfg: dict, col: bpy.types.Collection):
    s   = cfg["SCENE"]
    rng = random.Random(s["seed"])

    half_alley = s["alley_width"] / 2
    n          = s["building_count"]
    depth      = s["alley_depth"]
    step       = depth / n

    building_mat = bpy.data.materials.new("MAT_Building")
    building_mat.use_nodes = True
    bn = building_mat.node_tree.nodes
    bb = building_mat.node_tree.links
    bn.clear()
    b_out  = bn.new("ShaderNodeOutputMaterial")
    b_bsdf = bn.new("ShaderNodeBsdfPrincipled")
    b_bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1.0)
    b_bsdf.inputs["Roughness"].default_value  = 0.85
    b_bsdf.inputs["Metallic"].default_value   = 0.1
    bb.new(b_bsdf.outputs["BSDF"], b_out.inputs["Surface"])

    for side in (-1, 1):  # -1 = left, 1 = right
        x_base = side * (half_alley + s["building_depth"] / 2)
        for i in range(n):
            h = rng.uniform(s["building_height_min"], s["building_height_max"])
            y = -depth / 2 + i * step + step / 2
            w = rng.uniform(3.5, 7.0)

            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(x_base + side * rng.uniform(-0.5, 0.5),
                           y,
                           h / 2)
            )
            obj = bpy.context.active_object
            obj.name = f"Building_{side}_{i}"
            obj.scale = (s["building_depth"], w, h)
            bpy.ops.object.transform_apply(scale=True)
            obj.data.materials.append(building_mat)
            link(obj, col)

    print(f"[Scene] Buildings built ({n * 2} total, seed={s['seed']})")


# ── Neon sign geometry (emissive planes on building faces) ────────────────────

def build_neon_signs(cfg: dict, col: bpy.types.Collection):
    s   = cfg["SCENE"]
    l   = cfg["LIGHTS"]
    rng = random.Random(cfg["SCENE"]["seed"] + 1)

    half_alley = s["alley_width"] / 2
    sign_colors = [
        (*l["neon_a_color"], 1.0),
        (*l["neon_b_color"], 1.0),
        (*l["neon_c_color"], 1.0),
    ]

    for i in range(8):
        side   = 1 if i % 2 == 0 else -1
        x      = side * half_alley + side * 0.05
        y      = rng.uniform(-s["alley_depth"] / 2 + 2, s["alley_depth"] / 2 - 2)
        z      = rng.uniform(2.5, 7.0)
        w      = rng.uniform(1.0, 2.5)
        h_sign = rng.uniform(0.3, 0.8)
        color  = rng.choice(sign_colors)

        bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, z))
        sign = bpy.context.active_object
        sign.name = f"NeonSign_{i}"
        sign.scale = (0.02, w, h_sign)
        sign.rotation_euler = Euler((0, math.radians(90), 0))
        bpy.ops.object.transform_apply(scale=True, rotation=True)
        link(sign, col)

        mat = bpy.data.materials.new(f"MAT_NeonSign_{i}")
        mat.use_nodes = True
        sn = mat.node_tree.nodes
        sl = mat.node_tree.links
        sn.clear()
        s_out  = sn.new("ShaderNodeOutputMaterial")
        s_emit = sn.new("ShaderNodeEmission")
        s_emit.inputs["Color"].default_value    = color
        s_emit.inputs["Strength"].default_value = rng.uniform(8.0, 20.0)
        sl.new(s_emit.outputs["Emission"], s_out.inputs["Surface"])
        sign.data.materials.append(mat)

    print("[Scene] Neon signs built (8 emissive planes on building faces)")


# ── Lights ────────────────────────────────────────────────────────────────────

def build_lights(cfg: dict, col: bpy.types.Collection):
    l = cfg["LIGHTS"]
    s = cfg["SCENE"]

    def add_point(name, color, energy, radius, location):
        bpy.ops.object.light_add(type="POINT", location=location)
        light = bpy.context.active_object
        light.name = name
        light.data.color   = color
        light.data.energy  = energy
        light.data.shadow_soft_size = radius
        if hasattr(light.data, "use_shadow"):
            light.data.use_shadow = True
        link(light, col)
        return light

    # Primary neon lights — positioned at sign faces
    half  = s["alley_width"] / 2
    add_point("Light_NeonA_L", l["neon_a_color"], l["neon_a_intensity"], l["neon_a_radius"], (-half, -4.0, 3.5))
    add_point("Light_NeonA_R", l["neon_a_color"], l["neon_a_intensity"], l["neon_a_radius"], ( half,  2.0, 4.0))
    add_point("Light_NeonB_L", l["neon_b_color"], l["neon_b_intensity"], l["neon_b_radius"], (-half,  5.0, 2.5))
    add_point("Light_NeonB_R", l["neon_b_color"], l["neon_b_intensity"], l["neon_b_radius"], ( half, -6.0, 3.0))
    add_point("Light_NeonC",   l["neon_c_color"], l["neon_c_intensity"], l["neon_c_radius"], (  0.0, 10.0, 5.0))

    # Street lamp
    add_point("Light_StreetLamp", l["lamp_color"], l["lamp_intensity"], 1.0, l["lamp_position"])

    # Flicker animation on primary neons (neon_a only — others steady)
    if l["flicker_enabled"]:
        for light_name in ("Light_NeonA_L", "Light_NeonA_R"):
            obj = bpy.data.objects.get(light_name)
            if obj:
                obj.data.animation_data_create()
                action = bpy.data.actions.new(f"Action_Flicker_{light_name}")
                obj.data.animation_data.action = action
                fc = action.fcurves.new(data_path="energy", index=0)
                base = l["neon_a_intensity"]
                amp  = base * l["flicker_strength"]
                spd  = l["flicker_speed"]
                for frame in range(0, 250, max(1, int(250 / spd))):
                    import random as _r
                    _rng = _r.Random(frame + 7)
                    val  = base + _rng.uniform(-amp, amp)
                    fc.keyframe_points.insert(frame, val, options={"NEEDED"})
                fc.extrapolation = "CYCLIC"

    # World (ambient)
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    wn = world.node_tree.nodes
    wl = world.node_tree.links
    wn.clear()
    w_out = wn.new("ShaderNodeOutputWorld")
    w_bg  = wn.new("ShaderNodeBackground")
    w_bg.inputs["Color"].default_value    = (*l["ambient_color"], 1.0)
    w_bg.inputs["Strength"].default_value = l["ambient_intensity"]
    wl.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

    print(f"[Scene] Lights built (5 neon points, 1 lamp, flicker={l['flicker_enabled']})")


# ── Rain particle system ──────────────────────────────────────────────────────

def build_rain(cfg: dict, col: bpy.types.Collection):
    r = cfg["RAIN"]

    # ── Raindrop mesh (elongated cylinder = streak) ──────────────────────────
    bpy.ops.mesh.primitive_cylinder_add(
        radius=r["streak_width"],
        depth=r["streak_length"],
        vertices=6,
        location=(0, 0, -9999)   # hidden off-screen
    )
    drop = bpy.context.active_object
    drop.name = "RainDrop_Template"
    # Tilt so the long axis points in the fall direction
    drop.rotation_euler = Euler((0, 0, 0))
    bpy.ops.object.transform_apply(rotation=True)
    link(drop, col)

    # Rain material — semi-transparent, slightly blue
    mat = bpy.data.materials.new("MAT_Rain")
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.shadow_method = "NONE"
    rn = mat.node_tree.nodes
    rl = mat.node_tree.links
    rn.clear()
    r_out  = rn.new("ShaderNodeOutputMaterial")
    r_bsdf = rn.new("ShaderNodeBsdfPrincipled")
    r_bsdf.inputs["Base Color"].default_value  = r["color"]
    r_bsdf.inputs["Roughness"].default_value   = 0.05
    r_bsdf.inputs["Metallic"].default_value    = 0.0
    r_bsdf.inputs["Alpha"].default_value       = r["opacity"]
    if "Transmission Weight" in r_bsdf.inputs:
        r_bsdf.inputs["Transmission Weight"].default_value = 0.85
    rl.new(r_bsdf.outputs["BSDF"], r_out.inputs["Surface"])
    drop.data.materials.append(mat)

    # ── Emitter plane (large invisible plane high above ground) ──────────────
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0, 0, r["emit_from_z"])
    )
    emitter = bpy.context.active_object
    emitter.name = "Rain_Emitter"
    emitter.scale = (r["emit_area_x"], r["emit_area_y"], 1)
    bpy.ops.object.transform_apply(scale=True)
    emitter.hide_render = True
    emitter.display_type = "WIRE"
    link(emitter, col)

    # ── Particle system ──────────────────────────────────────────────────────
    bpy.ops.object.particle_system_add()
    psys      = emitter.particle_systems[0]
    psys.name = "RainSystem_Storm"
    ps        = psys.settings

    ps.type            = "EMITTER"
    ps.count           = r["count"]
    ps.lifetime        = r["lifetime"]
    ps.lifetime_random = 0.3
    ps.emit_from       = "FACE"
    ps.distribution    = "RAND"
    ps.normal_factor   = -r["velocity"]   # downward (negative Z)
    ps.factor_random   = 0.12             # slight velocity variation

    # Render as the RainDrop_Template object
    ps.render_type     = "OBJECT"
    ps.instance_object = drop
    ps.particle_size   = r["size"]
    ps.size_random     = 0.2

    ps.use_rotations          = True
    ps.rotation_mode          = "VEL"    # align to velocity direction
    ps.use_dynamic_rotation   = True

    ps.use_self_effect = False
    ps.use_die_on_hit  = False

    ps.frame_start = 1
    ps.frame_end   = 1          # burst from frame 1 (emitter handles timing)
    ps.use_modifier_stack = True

    # ── Wind force field ─────────────────────────────────────────────────────
    bpy.ops.object.effector_add(type="WIND", location=(0, 0, r["emit_from_z"] / 2))
    wind = bpy.context.active_object
    wind.name = "Wind_Storm"
    wind.field.strength    = r["wind_force"]
    wind.field.noise       = r["wind_turbulence"]
    wind.field.seed        = cfg["SCENE"]["seed"]
    wind.rotation_euler    = Euler((0, math.radians(90), math.radians(r["angle_degrees"])))
    wind.hide_render       = True
    link(wind, col)

    print(
        f"[Scene] Rain system built — Storm variant\n"
        f"        count={r['count']}  velocity={r['velocity']}  "
        f"angle={r['angle_degrees']}°  wind={r['wind_force']}"
    )


# ── Fog volume ────────────────────────────────────────────────────────────────

def build_fog(cfg: dict, col: bpy.types.Collection):
    f  = cfg["FOG"]
    sc = cfg["SCENE"]

    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(0, 0, f["height_falloff"] * 10)
    )
    fog_cube = bpy.context.active_object
    fog_cube.name = "Fog_Volume"
    fog_cube.scale = (sc["alley_width"] * 4, sc["alley_depth"] * 2, f["height_falloff"] * 20)
    bpy.ops.object.transform_apply(scale=True)
    fog_cube.display_type = "WIRE"
    link(fog_cube, col)

    mat = bpy.data.materials.new("MAT_Fog")
    mat.use_nodes = True
    fn = mat.node_tree.nodes
    fl = mat.node_tree.links
    fn.clear()

    f_out     = fn.new("ShaderNodeOutputMaterial")
    f_vol     = fn.new("ShaderNodeVolumePrincipled")

    f_vol.inputs["Density"].default_value         = f["density"]
    f_vol.inputs["Color"].default_value           = (*f["scatter_color"], 1.0)
    f_vol.inputs["Absorption Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    f_vol.inputs["Anisotropy"].default_value      = f["anisotropy"]

    if "Emission Strength" in f_vol.inputs:
        f_vol.inputs["Emission Strength"].default_value = 0.0

    fl.new(f_vol.outputs["Volume"], f_out.inputs["Volume"])
    fog_cube.data.materials.append(mat)

    print(
        f"[Scene] Fog volume built — Storm variant\n"
        f"        density={f['density']}  anisotropy={f['anisotropy']}"
    )


# ── Render settings ───────────────────────────────────────────────────────────

def apply_render_settings(cfg: dict):
    r     = cfg["RENDER"]
    scene = bpy.context.scene

    scene.render.engine          = r["engine"]
    scene.render.resolution_x    = r["resolution_x"]
    scene.render.resolution_y    = r["resolution_y"]
    scene.render.resolution_percentage = 100
    scene.render.fps             = r["fps"]

    if r["engine"] == "BLENDER_EEVEE_NEXT":
        eevee = scene.eevee
        eevee.taa_render_samples = r["samples"]

        if hasattr(eevee, "use_bloom"):
            eevee.use_bloom = True
        if hasattr(eevee, "bloom_threshold"):
            eevee.bloom_threshold = cfg["LIGHTS"]["bloom_threshold"]
        if hasattr(eevee, "bloom_intensity"):
            eevee.bloom_intensity = cfg["LIGHTS"]["bloom_intensity"]
        if hasattr(eevee, "bloom_radius"):
            eevee.bloom_radius    = cfg["LIGHTS"]["bloom_radius"]

        if hasattr(eevee, "use_volumetric_lights"):
            eevee.use_volumetric_lights = r["use_volumetrics"]
        if hasattr(eevee, "volumetric_samples"):
            eevee.volumetric_samples    = r["volumetric_samples"]
        if hasattr(eevee, "volumetric_start"):
            eevee.volumetric_start      = 0.1
        if hasattr(eevee, "volumetric_end"):
            eevee.volumetric_end        = 80.0
        if hasattr(eevee, "volumetric_tile_size"):
            eevee.volumetric_tile_size  = "4"

        if hasattr(scene, "render") and hasattr(scene.render, "use_motion_blur"):
            scene.render.use_motion_blur          = r["motion_blur"]
            scene.render.motion_blur_shutter      = r["motion_blur_shutter"]

        if hasattr(eevee, "shadow_cube_size"):
            eevee.shadow_cube_size    = "2048"
        if hasattr(eevee, "shadow_cascade_size"):
            eevee.shadow_cascade_size = "2048"

    # Color management
    scene.view_settings.view_transform = "Filmic"
    if hasattr(scene.view_settings, "look"):
        scene.view_settings.look       = r["color_management_look"]
    scene.view_settings.exposure        = r["exposure"]
    scene.view_settings.gamma           = r["gamma"]

    print(
        f"[Scene] Render settings applied\n"
        f"        engine={r['engine']}  samples={r['samples']}  "
        f"res={r['resolution_x']}×{r['resolution_y']}  "
        f"motion_blur={r['motion_blur']}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[Neonveil] ═══ Building scene_storm ═══")
    print(f"[Scene] Rain count : {SCENE_CONFIG['RAIN']['count']}")
    print(f"[Scene] Fog density: {SCENE_CONFIG['FOG']['density']}")
    print(f"[Scene] Seed       : {SCENE_CONFIG['SCENE']['seed']}")

    reset_scene()

    col_env   = make_collection("Environment")
    col_rain  = make_collection("Rain")
    col_light = make_collection("Lights")

    build_ground(SCENE_CONFIG,      col_env)
    build_buildings(SCENE_CONFIG,   col_env)
    build_neon_signs(SCENE_CONFIG,  col_env)
    build_fog(SCENE_CONFIG,         col_env)
    build_lights(SCENE_CONFIG,      col_light)
    build_rain(SCENE_CONFIG,        col_rain)
    apply_render_settings(SCENE_CONFIG)

    # Frame range (default 10s preview — change in Timeline before final render)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end   = 300

    print("\n[Neonveil] ═══ Scene ready ═══")
    print("[Neonveil] Set your camera, make any edits, then render (F12 or Ctrl+F12).")
    print("[Neonveil] Save as themes/neon_rain/scene_storm.blend when happy.")


main()
