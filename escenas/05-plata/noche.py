"""
Dos Mentes 05 — el look de noche (estilo del 02 "5 MINUTOS" mejorado): mundo azul marino, piso mojado con reflejos,
edificios grises low-poly con ventanas encendidas, luces de color por personaje y la posproducción (glow + carteles).
Todo en código. Lo usa escena.py.
"""
import bpy, math, os
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from motor import *
import motor as _mo

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE_CARTEL = os.path.join(AQUI, "fuentes", "JetBrainsMono-Bold.ttf")

AZUL = "#4DA6FF"
AMBAR = "#FFB020"
BLANCO = "#F2F6FF"


# ----------------------------------------------------------------------------- mundo y piso
def mundo_noche():
    sc = bpy.context.scene
    w = bpy.data.worlds.new("noche")
    sc.world = w
    w.use_nodes = True
    n = w.node_tree.nodes
    fondo = n["Background"]
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    rampa = n.new("ShaderNodeValToRGB")
    w.node_tree.links.new(tex.outputs["Generated"], sep.inputs[0])
    w.node_tree.links.new(sep.outputs["Z"], rampa.inputs[0])
    rampa.color_ramp.elements[0].position = 0.42
    rampa.color_ramp.elements[0].color = (*hexa("#1B3470"), 1)
    rampa.color_ramp.elements[1].position = 0.80
    rampa.color_ramp.elements[1].color = (*hexa("#030611"), 1)
    w.node_tree.links.new(rampa.outputs[0], fondo.inputs["Color"])
    fondo.inputs["Strength"].default_value = 0.8


def mat_gris(nombre, color, rough=0.85, emis=None, emis_color=None, spec=0.25):
    k = (nombre, color, rough, emis, emis_color, spec, "g")
    if k in _mo._MAT:
        return _mo._MAT[k]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexa(color), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    if emis:
        b.inputs["Emission Color"].default_value = (*hexa(emis_color or color), 1)
        b.inputs["Emission Strength"].default_value = emis
    _mo._MAT[k] = m
    return m


def mat_mojado(nombre, color, rough_min=0.06, rough_max=0.32, escala=2.2):
    """Piso mojado: brillante, con charcos (rugosidad que varía con un ruido) y reflejo de todo lo que brilla."""
    k = (nombre, color, "mojado")
    if k in _mo._MAT:
        return _mo._MAT[k]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexa(color), 1)
    b.inputs["Specular IOR Level"].default_value = 0.9
    b.inputs["Metallic"].default_value = 0.0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ru = nt.nodes.new("ShaderNodeTexNoise")
    ru.inputs["Scale"].default_value = escala
    ru.inputs["Detail"].default_value = 3.0
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].position = 0.40
    rp.color_ramp.elements[0].color = (rough_min,) * 3 + (1,)
    rp.color_ramp.elements[1].position = 0.62
    rp.color_ramp.elements[1].color = (rough_max,) * 3 + (1,)
    nt.links.new(tc.outputs["Object"], ru.inputs["Vector"])
    nt.links.new(ru.outputs["Fac"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], b.inputs["Roughness"])
    _mo._MAT[k] = m
    return m


def piso(nombre, centro, tam, color="#0D1119", mojado=True, z=0.0, rough=(0.035, 0.15)):
    mt = mat_mojado(nombre, color, *rough) if mojado else mat_gris(nombre, color)
    return caja(nombre, (tam[0], tam[1], 0.1), mt, loc=(centro[0], centro[1], z - 0.05), bisel=0)


# ----------------------------------------------------------------------------- escenografía low-poly
def edificio(nombre, x, y, w, prof, h, color="#2B313E", filas=None, cols=None, semilla=0, frente=-1, prob=0.55):
    """Caja gris con ventanas cuadradas (algunas encendidas, cálidas). La cara con ventanas mira a -Y."""
    mt = mat_gris(nombre + "_m", color, rough=0.95, spec=0.05)
    caja(nombre, (w + 1.2, prof, h), mt, loc=(x, y, h / 2), bisel=0.0)
    sp_x, sp_z = 1.45, 1.65
    nc = cols or max(1, int((w - 0.5) / sp_x))
    nf = filas or max(1, int((h - 1.4) / sp_z))
    yv = y - prof / 2 - 0.02
    for i in range(nc):
        for j in range(nf):
            r = ((i * 73856093) ^ (j * 19349663) ^ (semilla * 83492791)) % 100 / 100.0
            enc = r < prob
            cl = ["#FFE7B0", "#F4F1E6", "#DCE8FF"][(i + j + semilla) % 3]
            mv = mat_gris("vent_on" + cl, cl, emis=3.2, emis_color=cl, rough=0.6) if enc else mat_gris("vent_off", "#222A36", rough=0.5, spec=0.5)
            cx = x - (nc - 1) * sp_x / 2 + i * sp_x
            cz = 1.4 + j * sp_z
            caja(f"{nombre}_v{i}_{j}", (0.62, 0.05, 0.62), mv, loc=(cx, yv, cz), bisel=0.0)


def arbol_n(nombre, loc, esc=1.0, tipo=0):
    R = vacio(nombre, None, loc)
    R.scale = (esc, esc, esc)
    cil(nombre + "_tr", 0.13, 1.4, mat_gris("tr_n", "#1B1C22"), R, (0, 0, 0.7), r2=0.10, seg=7)
    mc = mat_gris("copa_n", "#1F2A33", rough=0.95, spec=0.05)
    for i, (x, y, z, r) in enumerate(((0, 0, 2.2, 1.05), (0.6, 0.1, 1.9, 0.7), (-0.6, -0.1, 1.95, 0.72), (0.1, 0.3, 2.8, 0.7))):
        o = obj(f"{nombre}_h{i}", m_icos(), mc, R, (x, y, z), esc=(r, r, r))
    return R


def m_icos():
    k = ("ico",)
    if k not in _mo._MESH:
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        me = bpy.data.meshes.new("ico")
        bm.to_mesh(me); bm.free()
        for p in me.polygons:
            p.use_smooth = False
        _mo._MESH[k] = me
    return _mo._MESH[k]


def farola_n(nombre, loc, color_luz="#FFF1CC", energia=900, alto=3.6, brazo=0.55, dir_=1):
    """Farola con brazo; la lámpara brilla y tira luz real. Devuelve la raíz."""
    R = vacio(nombre, None, loc)
    mn = mat_gris("farola_n", "#161A22", rough=0.5)
    cil(nombre + "_p", 0.05, alto, mn, R, (0, 0, alto / 2), r2=0.035, seg=10)
    cil(nombre + "_b", 0.10, 0.3, mn, R, (0, 0, 0.15), r2=0.06, seg=10)
    caja(nombre + "_br", (brazo, 0.07, 0.07), mn, R, (dir_ * brazo / 2, 0, alto), bisel=0.01)
    lx = dir_ * brazo
    cil(nombre + "_c", 0.22, 0.07, mn, R, (lx, 0, alto + 0.02), r2=0.12, seg=12)
    esf(nombre + "_l", 0.16, mat_gris("farola_l", color_luz, emis=14.0, rough=0.3), R, (lx, 0, alto - 0.07), esc=(1, 1, 0.45))
    luz(nombre + "_luz", 'POINT', (lx, 0, alto - 0.3), color_luz, energia, R, radio=0.12, reflejo=True)
    return R


def banco_n(nombre, loc, rot=(0, 0, 0), largo=1.7):
    R = vacio(nombre, None, loc, rot)
    mw = mat_gris("banco_n", "#3A404C", rough=0.7)
    mh = mat_gris("banco_h", "#1A1E26", rough=0.5)
    for i in range(4):
        caja(f"{nombre}_a{i}", (largo, 0.10, 0.04), mw, R, loc=(0, -0.20 + i * 0.12, 0.50), bisel=0.01)
    for i in range(3):
        caja(f"{nombre}_r{i}", (largo, 0.035, 0.12), mw, R, loc=(0, 0.20, 0.64 + i * 0.15), rot=(math.radians(-8), 0, 0), bisel=0.01)
    for sx in (-1, 1):
        caja(f"{nombre}_pa{sx}", (0.05, 0.06, 0.5), mh, R, loc=(sx * (largo / 2 - 0.1), -0.1, 0.25), bisel=0.01)
        caja(f"{nombre}_pb{sx}", (0.05, 0.06, 0.95), mh, R, loc=(sx * (largo / 2 - 0.1), 0.22, 0.47), bisel=0.01)
    return R


def cordon(nombre, x, y, largo, ancho=0.5, z=0.12, color="#2A303C"):
    caja(nombre, (largo, ancho, z), mat_mojado("cordon_" + color, color, 0.05, 0.22), loc=(x, y, z / 2), bisel=0.01)


# ----------------------------------------------------------------------------- luces
def luz(nombre, tipo, loc, color, energia, padre=None, radio=0.1, rot=None, tam=None, spot=None, reflejo=False):
    l = bpy.data.lights.new(nombre, tipo)
    l.color = hexa(color)
    l.energy = energia
    if tipo == 'AREA':
        l.size = tam or 2.0
    else:
        l.shadow_soft_size = radio
    if tipo == 'SPOT':
        l.spot_size = math.radians(spot or 60)
        l.spot_blend = 0.6
    o = bpy.data.objects.new(nombre, l)
    bpy.context.scene.collection.objects.link(o)
    o.visible_glossy = reflejo          # las luces auxiliares no se reflejan en el piso (si no, manchas gigantes)
    o.location = loc
    if rot is not None:
        o.rotation_euler = rot
    if padre is not None:
        o.parent = padre
    return o


# colores de rol: (relleno, contraluz, energía relleno, energía contraluz)
ROLES = {
    "azul": ("#3E86FF", "#2A63FF", 300.0, 420.0),
    "ambar": ("#FFA630", "#FF8A10", 280.0, 380.0),
    "amigo": ("#F4F8FF", "#DCE8FF", 260.0, 380.0),
    "extra": ("#C9D6F2", "#9DB4E0", 90.0, 140.0),
}
ROL_DE = dict(azul="azul", ambar="ambar", amigo="amigo")
LUCES_PJ = {}
ESCALA_LUZ = [1.0]       # <1 en los primeros planos de manos (si no se queman)
BASE_E = {}


def crear_luces_pj(nombres):
    for n in nombres:
        rol = ROLES[ROL_DE.get(n, "extra")]
        f = luz(f"luz_f_{n}", 'POINT', (0, 0, 0), rol[0], rol[2], radio=0.35)
        r = luz(f"luz_r_{n}", 'SPOT', (0, 0, 0), rol[1], rol[3], radio=0.2, spot=70)
        LUCES_PJ[n] = (f, r)
        BASE_E[n] = (rol[2], rol[3])


def apuntar(o, destino):
    d = Vector(destino) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def luces_a(p, cam_loc):
    """Relleno desde el lado de la cámara y contraluz desde atrás, cada uno del color de su rol."""
    f, r = LUCES_PJ[p.nombre]
    pos = Vector(p.M.translation)
    d = Vector(cam_loc) - pos
    d.z = 0
    d = d.normalized() if d.length > 1e-4 else Vector((0, -1, 0))
    lado = Vector((-d.y, d.x, 0))
    f.location = pos + d * 1.5 + lado * 0.9 + Vector((0, 0, 1.7))
    r.location = pos - d * 1.6 - lado * 0.8 + Vector((0, 0, 1.9))
    apuntar(r, pos + Vector((0, 0, 1.0)))
    f.data.energy = BASE_E[p.nombre][0] * ESCALA_LUZ[0]
    r.data.energy = BASE_E[p.nombre][1] * ESCALA_LUZ[0]
    vis = not p.cabeza.hide_render
    f.hide_render = r.hide_render = not vis


# ----------------------------------------------------------------------------- posproducción: glow + carteles
def _blur(a, rad):
    """Gauss sobre un array float (H,W,3) 0..1 usando Pillow en 8 bits."""
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(rad)), dtype=np.float32) / 255.0


def bloom(img, fuerza=1.0):
    if os.environ.get("NOBLOOM") == "1":
        return img
    """Resplandor suave: lo muy brillante se desenfoca en tres escalas y se suma (glow de los stickmen y de los carteles)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    W = img.size[0]
    k = W / 1080.0
    lum = a.max(axis=2, keepdims=True)
    br = a * np.clip((lum - 0.90) / 0.10, 0, 1)
    pequeno = np.asarray(Image.fromarray((br * 255).astype(np.uint8)).resize((max(1, img.size[0] // 2), max(1, img.size[1] // 2)), Image.BILINEAR), dtype=np.float32) / 255.0
    g = np.zeros_like(pequeno)
    for rad, pe in ((4 * k, 0.30), (12 * k, 0.26), (34 * k, 0.24)):
        g += _blur(pequeno, max(0.5, rad / 2)) * pe
    g = np.asarray(Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR), dtype=np.float32) / 255.0
    out = np.clip(a + g * fuerza, 0, 1)
    return Image.fromarray((out * 255).astype(np.uint8))


def _texto_ancho(txt, tam, sep):
    f = ImageFont.truetype(FUENTE_CARTEL, tam)
    w = sum(f.getlength(c) + sep for c in txt) - sep
    return f, w


def cartel(img, txt, color, cy, tam=None, ancho_max=0.86, brillo=1.0, cx=None, sep_rel=0.12, recorte=None, n=None, oscurecer=0.0):
    """Cartel monoespaciado con glow (como el 02). `cy` = centro vertical en fracción del alto de `img`."""
    if n is not None and n <= 0:
        return img
    W, H = img.size
    k = W / 1080.0
    tam = int((tam or 112) * k)
    sep = tam * sep_rel
    f, w = _texto_ancho(txt, tam, sep)
    if w > W * ancho_max:
        tam = int(tam * W * ancho_max / w)
        f, w = _texto_ancho(txt, tam, sep)
    capa = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(capa)
    x = (W * (0.5 if cx is None else cx)) - w / 2
    y = H * cy - tam * 0.55
    for i, c in enumerate(txt):
        if n is not None and i >= n:
            break                       # tipeo: el diseño usa el texto entero, solo se dibujan las primeras n letras
        d.text((x, y), c, font=f, fill=255)
        x += f.getlength(c) + sep
    base = np.asarray(capa, dtype=np.float32) / 255.0
    col = np.array(hexa_srgb(color), dtype=np.float32)
    blanco = np.array((1.0, 1.0, 1.0), dtype=np.float32)
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    halo = np.zeros_like(base)
    for rad, pe in ((tam * 0.06, 0.9), (tam * 0.18, 0.7), (tam * 0.45, 0.5)):
        halo += np.asarray(Image.fromarray((base * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rad)), dtype=np.float32) / 255.0 * pe
    if np.allclose(col, blanco, atol=0.05):
        nucleo = blanco
    else:
        nucleo = col * 0.35 + blanco * 0.65             # centro casi blanco, borde con el color (neón)
    if oscurecer > 0:                                  # bajar el brillo del fondo detrás de las letras (luces desenfocadas)
        full = Image.new("L", (W, H), 0)
        dd = ImageDraw.Draw(full)
        xx = (W * (0.5 if cx is None else cx)) - w / 2
        for i, c in enumerate(txt):
            if n is not None and i >= n:
                break
            dd.text((xx, y), c, font=f, fill=255)
            xx += f.getlength(c) + sep
        m = np.asarray(full.filter(ImageFilter.GaussianBlur(tam * 0.22)), dtype=np.float32) / 255.0
        a = a * (1 - oscurecer * np.clip(m * 4.0, 0, 1))[..., None]
    out = a + halo[..., None] * col * 0.85 * brillo
    out = out * (1 - base[..., None]) + (nucleo * base[..., None])
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def hexa_srgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rotulo(img, txt, color, cy, tam=44, brillo=0.6, n=None, oscurecer=0.0):
    """Rótulo chico de acción debajo del cartel (como 'COMPRA ZAPATILLAS' del 02)."""
    return cartel(img, txt, color, cy, tam=tam, ancho_max=0.7, brillo=brillo, sep_rel=0.18, n=n, oscurecer=oscurecer)


def linea_division(img, y, color="#FFFFFF"):
    W, H = img.size
    k = W / 1080.0
    capa = np.zeros((H, W), dtype=np.float32)
    yy = int(y)
    capa[max(0, yy - int(3 * k)):yy + int(3 * k), :] = 1.0
    halo = _blur(np.repeat(capa[..., None], 3, axis=2), 10 * k)[..., 0] + _blur(np.repeat(capa[..., None], 3, axis=2), 3 * k)[..., 0]
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    out = a + halo[..., None] * 0.9
    out = out * (1 - capa[..., None]) + capa[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
