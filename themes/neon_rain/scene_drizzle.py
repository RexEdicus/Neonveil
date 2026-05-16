"""
themes/neon_rain/scene_drizzle.py
───────────────────────────────────
Blender Python scene builder — Atmospheric Drizzle variant.

Run inside Blender:
    blender.exe --background --python themes/neon_rain/scene_drizzle.py

Or from the Blender scripting tab (open file, click Run Script).

HOW TO USE:
    1. Edit SCENE_CONFIG below — all tunable values are here, nothing buried.
    2. Run the script. It builds the full scene from scratch.
    3. The script STOPS before rendering. You set the camera, make any
       final edits you want, then render manually (F12 or Timeline → Render).
    4. Save as scene_drizzle.blend when you're happy with the scene setup.

WHAT DIFFERS FROM scene_storm.py:
    - RAIN: low count, slow velocity, near-vertical, almost no wind
    - FOG:  lower density, more forward scatter — neon glow bleeds through
    Everything else (lights, ground, scene geometry) is identical to storm.
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
    # Drizzle variant: sparse, slow, near-vertical. Contemplative, not dramatic.
    "RAIN": {
        "count":           1800,    # low count — drizzle is sparse
        "velocity":        7.0,     # slower fall speed — softer feel
        "angle_degrees":   5.0,     # nearly vertical — calm night, no wind
        "streak_length":   0.08,    # shorter streaks — less motion energy
        "streak_width":    0.003,   # slightly thinner than storm
        "opacity":         0.35,    # more transparent — mist-like quality
        "wind_force":      0.4,     # barely any wind
        "wind_turbulence": 0.3,     # very subtle variation
        "size":            0.004,   # smaller particles
        "lifetime":        120,     # longer lifetime — drops drift slowly
        "emit_from_z":     10.0,    # slightly lower emitter
        "emit_area_x":     30.0,
        "emit_area_y":     30.0,
        "color":           (0.82, 0.88, 0.98, 1.0),  # RGBA — paler, more mist-like
    },

    # ── FOG ──────────────────────────────────────────────────────────────────
    # Drizzle variant: light, atmospheric. Neon glow bleeds through beautifully.
    "FOG": {
        "density":         0.018,   # much lower — barely there
        "scatter_color":   (0.62, 0.65, 0.78),  # slightly warmer grey
        "absorption":      0.004,   # very little absorption — light passes through
        "anisotropy":      0.55,    # forward scatter — makes neon glow diffuse outward
        "height_falloff":  0.25,    # fog rises higher — ground mist effect
        "step_size":       0.12,    # larger steps = faster render (less dense fog needs less precision)
    },

    # ── LIGHTS ───────────────────────────────────────────────────────────────
    # Identical to scene_storm.py — same neon character across both variants.
    "LIGHTS": {
        "neon_a_color":      (1.0,  0.08, 0.45),
        "neon_a_intensity":  800.0,
        "neon_a_radius":     3.5,

        "neon_b_color":      (0.05, 0.75, 0.95),
        "neon_b_intensity":  600.0,
        "neon_b_radius":     4.0,

        "neon_c_color":      (1.0, 0.35, 0.02),
        "neon_c_intensity":  350.0,
        "neon_c_radius":     5.0,

        "flicker_enabled":   True,
        "flicker_speed":     8.0,   # slightly slower flicker for calmer mood
        "flicker_strength":  0.12,  # subtler — drizzle is more peaceful

        "ambient_color":     (0.04, 0.04, 0.08),
        "ambient_intensity": 0.6,

        "lamp_color":        (1.0,  0.78, 0.35),
        "lamp_intensity":    250.0,
        "lamp_position":     (4.0, -3.0, 5.5),

        "bloom_threshold":   0.75,  # lower threshold — more glow bleeds through mist
        "bloom_intensity":   1.8,   # stronger bloom — mist diffuses the light halos
        "bloom_radius":      8.0,   # wider radius — neon haloes are a signature look
    },

    # ── GROUND ───────────────────────────────────────────────────────────────
    # Identical to scene_storm.py.
    "GROUND": {
        "size":                  40.0,
        "wet_roughness":         0.04,
        "reflection_strength":   0.85,
        "base_color":            (0.04, 0.04, 0.05),
        "puddle_density":        0.65,
        "puddle_scale":          3.5,
        "puddle_ripple_speed":   0.5,   # slower ripples for drizzle — lighter impacts
        "puddle_ripple_scale":   0.9,   # smaller rings — lighter drops
        "neon_tint_strength":    0.35,
        "specular":              0.9,
    },

    # ── SCENE GEOMETRY ───────────────────────────────────────────────────────
    # Identical to scene_storm.py.
    "SCENE": {
        "world_color":         (0.005, 0.005, 0.012),
        "world_strength":      0.8,
        "alley_width":         8.0,
        "alley_depth":         35.0,
        "building_height_min": 12.0,
        "building_height_max": 28.0,
        "building_count":      6,
        "building_depth":      8.0,
        "seed":                42,     # same seed = same building layout as storm
    },

    # ── RENDER DEFAULTS ──────────────────────────────────────────────────────
    "RENDER": {
        "engine":          "BLENDER_EEVEE_NEXT",
        "samples":         64,
        "resolution_x":    2560,
        "resolution_y":    1440,
        "fps":             30,
        "motion_blur":     False,   # OFF for drizzle — slow drops don't need blur
        "motion_blur_shutter": 0.2,
        "use_volumetrics": True,
        "volumetric_samples": 64,
        "color_management_look": "Medium High Contrast",  # softer than storm
        "exposure":        0.15,    # slight exposure lift — mist brightens the scene
        "gamma":           1.0,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  BUILDER — identical functions to scene_storm.py
#  (shared geometry, different RAIN + FOG values from config above)
# ══════════════════════════════════════════════════════════════════════════════

def reset_scene():
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


def build_ground(cfg: dict, col: bpy.types.Collection) -> bpy.types.Object:
    g = cfg["GROUND"]

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

    coord.location    = (-800, 0)
    mapping.location  = (-600, 0)
    noise.location    = (-400, 0)
    coloramp.location = (-200, 0)
    bsdf.location     = (0, 100)
    glossy.location   = (0, -100)
    mix.location      = (300, 0)
    out.location      = (500, 0)

    bsdf.inputs["Base Color"].default_value   = (*g["base_color"], 1.0)
    bsdf.inputs["Roughness"].default_value    = g["wet_roughness"]
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = g["specular"]
    bsdf.inputs["Metallic"].default_value     = 0.0

    glossy.inputs["Roughness"].default_value  = g["wet_roughness"]
    glossy.inputs["Color"].default_value      = (1.0, 1.0, 1.0, 1.0)

    noise.inputs["Scale"].default_value     = g["puddle_scale"]
    noise.inputs["Detail"].default_value    = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    noise.inputs["Distortion"].default_value = 0.3

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
    print(f"[Scene] Ground built ({g['size']}m × {g['size']}m)")
    return plane


def build_buildings(cfg: dict, col: bpy.types.Collection):
    s   = cfg["SCENE"]
    rng = random.Random(s["seed"])  # same seed = same layout as storm

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

    for side in (-1, 1):
        x_base = side * (half_alley + s["building_depth"] / 2)
        for i in range(n):
            h = rng.uniform(s["building_height_min"], s["building_height_max"])
            y = -depth / 2 + i * step + step / 2
            w = rng.uniform(3.5, 7.0)

            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(x_base + side * rng.uniform(-0.5, 0.5), y, h / 2)
            )
            obj = bpy.context.active_object
            obj.name = f"Building_{side}_{i}"
            obj.scale = (s["building_depth"], w, h)
            bpy.ops.object.transform_apply(scale=True)
            obj.data.materials.append(building_mat)
            link(obj, col)

    print(f"[Scene] Buildings built ({n * 2} total, seed={s['seed']})")


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

    print("[Scene] Neon signs built (8 emissive planes)")


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

    half = s["alley_width"] / 2
    add_point("Light_NeonA_L", l["neon_a_color"], l["neon_a_intensity"], l["neon_a_radius"], (-half, -4.0, 3.5))
    add_point("Light_NeonA_R", l["neon_a_color"], l["neon_a_intensity"], l["neon_a_radius"], ( half,  2.0, 4.0))
    add_point("Light_NeonB_L", l["neon_b_color"], l["neon_b_intensity"], l["neon_b_radius"], (-half,  5.0, 2.5))
    add_point("Light_NeonB_R", l["neon_b_color"], l["neon_b_intensity"], l["neon_b_radius"], ( half, -6.0, 3.0))
    add_point("Light_NeonC",   l["neon_c_color"], l["neon_c_intensity"], l["neon_c_radius"], (  0.0, 10.0, 5.0))
    add_point("Light_StreetLamp", l["lamp_color"], l["lamp_intensity"], 1.0, l["lamp_position"])

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

    print(f"[Scene] Lights built (flicker={l['flicker_enabled']}, bloom_radius={l['bloom_radius']})")


def build_rain(cfg: dict, col: bpy.types.Collection):
    r = cfg["RAIN"]

    bpy.ops.mesh.primitive_cylinder_add(
        radius=r["streak_width"],
        depth=r["streak_length"],
        vertices=6,
        location=(0, 0, -9999)
    )
    drop = bpy.context.active_object
    drop.name = "RainDrop_Template"
    bpy.ops.object.transform_apply(rotation=True)
    link(drop, col)

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

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, r["emit_from_z"]))
    emitter = bpy.context.active_object
    emitter.name = "Rain_Emitter"
    emitter.scale = (r["emit_area_x"], r["emit_area_y"], 1)
    bpy.ops.object.transform_apply(scale=True)
    emitter.hide_render = True
    emitter.display_type = "WIRE"
    link(emitter, col)

    bpy.ops.object.particle_system_add()
    psys      = emitter.particle_systems[0]
    psys.name = "RainSystem_Drizzle"
    ps        = psys.settings

    ps.type            = "EMITTER"
    ps.count           = r["count"]
    ps.lifetime        = r["lifetime"]
    ps.lifetime_random = 0.4
    ps.emit_from       = "FACE"
    ps.distribution    = "RAND"
    ps.normal_factor   = -r["velocity"]
    ps.factor_random   = 0.2   # more random variation — drizzle is irregular

    ps.render_type     = "OBJECT"
    ps.instance_object = drop
    ps.particle_size   = r["size"]
    ps.size_random     = 0.35  # more size variation — drops vary more in drizzle

    ps.use_rotations        = True
    ps.rotation_mode        = "VEL"
    ps.use_dynamic_rotation = True
    ps.use_self_effect      = False
    ps.use_die_on_hit       = False
    ps.frame_start          = 1
    ps.frame_end            = 1
    ps.use_modifier_stack   = True

    # Very gentle wind — barely perceptible
    bpy.ops.object.effector_add(type="WIND", location=(0, 0, r["emit_from_z"] / 2))
    wind = bpy.context.active_object
    wind.name = "Wind_Drizzle"
    wind.field.strength    = r["wind_force"]
    wind.field.noise       = r["wind_turbulence"]
    wind.field.seed        = cfg["SCENE"]["seed"]
    wind.rotation_euler    = Euler((0, math.radians(90), math.radians(r["angle_degrees"])))
    wind.hide_render       = True
    link(wind, col)

    print(
        f"[Scene] Rain system built — Drizzle variant\n"
        f"        count={r['count']}  velocity={r['velocity']}  "
        f"angle={r['angle_degrees']}°  wind={r['wind_force']}"
    )


def build_fog(cfg: dict, col: bpy.types.Collection):
    f  = cfg["FOG"]
    sc = cfg["SCENE"]

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, f["height_falloff"] * 10))
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

    f_out = fn.new("ShaderNodeOutputMaterial")
    f_vol = fn.new("ShaderNodeVolumePrincipled")

    f_vol.inputs["Density"].default_value         = f["density"]
    f_vol.inputs["Color"].default_value           = (*f["scatter_color"], 1.0)
    f_vol.inputs["Absorption Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    f_vol.inputs["Anisotropy"].default_value      = f["anisotropy"]
    if "Emission Strength" in f_vol.inputs:
        f_vol.inputs["Emission Strength"].default_value = 0.0

    fl.new(f_vol.outputs["Volume"], f_out.inputs["Volume"])
    fog_cube.data.materials.append(mat)

    print(
        f"[Scene] Fog volume built — Drizzle variant\n"
        f"        density={f['density']}  anisotropy={f['anisotropy']} (forward scatter)"
    )


def apply_render_settings(cfg: dict):
    r     = cfg["RENDER"]
    scene = bpy.context.scene

    scene.render.engine       = r["engine"]
    scene.render.resolution_x = r["resolution_x"]
    scene.render.resolution_y = r["resolution_y"]
    scene.render.resolution_percentage = 100
    scene.render.fps          = r["fps"]

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

        if hasattr(scene.render, "use_motion_blur"):
            scene.render.use_motion_blur     = r["motion_blur"]
            scene.render.motion_blur_shutter = r["motion_blur_shutter"]

        if hasattr(eevee, "shadow_cube_size"):
            eevee.shadow_cube_size    = "2048"
        if hasattr(eevee, "shadow_cascade_size"):
            eevee.shadow_cascade_size = "2048"

    scene.view_settings.view_transform = "Filmic"
    if hasattr(scene.view_settings, "look"):
        scene.view_settings.look  = r["color_management_look"]
    scene.view_settings.exposure      = r["exposure"]
    scene.view_settings.gamma         = r["gamma"]

    print(
        f"[Scene] Render settings applied\n"
        f"        engine={r['engine']}  samples={r['samples']}  "
        f"motion_blur={r['motion_blur']}  exposure={r['exposure']}"
    )


def main():
    print("\n[Neonveil] ═══ Building scene_drizzle ═══")
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

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end   = 300

    print("\n[Neonveil] ═══ Scene ready ═══")
    print("[Neonveil] Set your camera, make any edits, then render (F12 or Ctrl+F12).")
    print("[Neonveil] Save as themes/neon_rain/scene_drizzle.blend when happy.")


main()
