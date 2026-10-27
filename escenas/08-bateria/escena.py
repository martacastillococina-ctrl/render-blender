"""
Dos Mentes 08 — "Tu batería social es limitada" (réplica del reel de @neuronvisuals con nuestros personajes).

Blender 4.2 por código (bpy, Cycles en CPU: no hay GPU ni EGL). Plano fijo frontal, 1080x1920, 30 fps, 11,93 s.
`aplicar(t)` es una función pura del tiempo: coloca TODO para el segundo t.

CLI (contrato del repo `render-blender`):
  python escena.py --anim --start A --end B --samples N --escala E --carpeta frames   -> frames/f_0000.png ...
  python escena.py --still T --out x.png
  python escena.py --hoja prueba/hoja-personajes.png
"""
import bpy, bmesh, math, os, sys, time, argparse
from mathutils import Vector, Matrix, Quaternion

AQUI = os.path.dirname(os.path.abspath(__file__))
FPS = 30
NCUADROS = 358                    # 11,93 s como la referencia
T_FIN = NCUADROS / FPS
ANCHO, ALTO = 1080, 1920

ap = argparse.ArgumentParser()
ap.add_argument("--anim", action="store_true")
ap.add_argument("--start", type=int, default=0)
ap.add_argument("--end", type=int, default=None)
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--escala", type=float, default=1.0)
ap.add_argument("--carpeta", default=None)
ap.add_argument("--still", type=float, default=None)
ap.add_argument("--out", default=None)
ap.add_argument("--hoja", default=None)
ap.add_argument("--paso", type=int, default=1)
ap.add_argument("--glow", type=float, default=-0.7)
ARGS = vars(ap.parse_args(sys.argv[1:] if os.environ.get("ESCENA_SIN_PRINCIPAL") != "1" else []))

# ----------------------------------------------------------------------------- colores
BLANCO = "#FFFFFF"
AMBAR = "#FFB020"
AZUL_APAGADO = "#656D7B"       # gris azulado mate de los que drenan
AZUL_PAJA = "#7FA4FF"
ROJO = "#FF2A2A"
TXT_AZUL = "#8DB4FF"


def hexa(s):
    s = s.lstrip("#")
    c = [int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def mezclar(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


# ----------------------------------------------------------------------------- helpers de tiempo
def lim(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def sm(t, a, b):
    """smoothstep de 0 a 1 entre a y b."""
    u = lim((t - a) / (b - a)) if b != a else (1.0 if t >= b else 0.0)
    return u * u * (3 - 2 * u)


def eo(t, a, b):
    """ease-out cúbico."""
    u = lim((t - a) / (b - a))
    return 1 - (1 - u) ** 3


def kf(t, pts):
    """Interpolación suave entre claves [(t, v), ...]."""
    if t <= pts[0][0]:
        return pts[0][1]
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            return pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * sm(t, pts[i - 1][0], pts[i][0])
    return pts[-1][1]


def kv(t, pts):
    """Igual que kf pero con Vector."""
    if t <= pts[0][0]:
        return Vector(pts[0][1])
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            k = sm(t, pts[i - 1][0], pts[i][0])
            return Vector(pts[i - 1][1]).lerp(Vector(pts[i][1]), k)
    return Vector(pts[-1][1])


# ----------------------------------------------------------------------------- base bpy
_MESH = {}


def limpiar():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MESH.clear()


def _fin(bm, nombre):
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    return me


def m_esfera(seg=32):
    k = ("esf", seg)
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
        _MESH[k] = _fin(bm, "esfera")
    return _MESH[k]


def m_capsula(L, r, seg=24):
    """Cápsula a lo largo de +Z de z=0 a z=L (más las puntas redondas)."""
    k = ("cap", round(L, 4), round(r, 4), seg)
    if k not in _MESH:
        bm = bmesh.new()
        nv = seg // 2 | 1
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=nv, radius=r)
        for v in bm.verts:
            if v.co.z > 0:
                v.co.z += L
        _MESH[k] = _fin(bm, "cap")
    return _MESH[k]


def m_tubo(seg=12):
    """Cilindro de radio 1 y alto 1 (z de 0 a 1): se escala para sorbetes y cable."""
    k = ("tubo", seg)
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1.0, radius2=1.0, depth=1.0)
        for v in bm.verts:
            v.co.z += 0.5
        _MESH[k] = _fin(bm, "tubo")
    return _MESH[k]


def m_caja():
    k = ("caja",)
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        me = bpy.data.meshes.new("caja")
        bm.to_mesh(me)
        bm.free()
        _MESH[k] = me
    return _MESH[k]


def objeto(nombre, malla, mat=None, loc=(0, 0, 0), esc=(1, 1, 1)):
    o = bpy.data.objects.new(nombre, malla)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        o.data.materials.append(mat)
        o.material_slots[0].link = 'OBJECT'
        o.material_slots[0].material = mat
    o.location = loc
    o.scale = esc
    o.rotation_mode = 'QUATERNION'
    return o


def mat_principled(nombre, color, rough=0.8, spec=0.2, emis=0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexa(color), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Emission Color"].default_value = (*hexa(color), 1)
    b.inputs["Emission Strength"].default_value = emis
    return m


def mat_brillo(nombre, color, fuerza, borde=0.55):
    """Emisivo con los bordes del tubo algo más oscuros: separa las extremidades que se superponen."""
    m = mat_principled(nombre, color, rough=0.6, spec=0.1, emis=1.0)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation = 'MULTIPLY_ADD'
    ma.inputs[1].default_value = -borde
    ma.inputs[2].default_value = 1.0
    nt.links.new(lw.outputs["Fresnel"], ma.inputs[0])
    mu = nt.nodes.new("ShaderNodeMath")
    mu.operation = 'MULTIPLY'
    mu.inputs[1].default_value = fuerza
    nt.links.new(ma.outputs["Value"], mu.inputs[0])
    nt.links.new(mu.outputs["Value"], b.inputs["Emission Strength"])
    return m


def mat_emision(nombre, color="#FFFFFF", fuerza=1.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*hexa(color), 1)
    e.inputs["Strength"].default_value = fuerza
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
    return m


def set_emision(m, rgb, fuerza):
    e = m.node_tree.nodes["Emission"]
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = fuerza


def set_principled(m, rgb, emis, rgb_emis=None):
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Emission Color"].default_value = (*(rgb_emis or rgb), 1)
    b.inputs["Emission Strength"].default_value = emis


def colocar_tubo(o, a, b, r):
    """Tubo (cilindro escalado) de a a b con radio r."""
    a = Vector(a)
    d = Vector(b) - a
    L = d.length
    if L < 1e-5:
        o.hide_render = True
        return
    o.hide_render = False
    o.location = a
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    o.scale = (r, r, L)


def colocar_cap(o, a, b):
    a = Vector(a)
    d = Vector(b) - a
    q = Vector((0, 0, 1)).rotation_difference(d) if d.length > 1e-6 else Quaternion()
    o.matrix_basis = Matrix.Translation(a) @ q.to_matrix().to_4x4()


def ik2(a, objetivo, l1, l2, polo):
    """IK de 2 huesos: (medio, extremo). `polo` = hacia dónde apunta la articulación."""
    a = Vector(a)
    d = Vector(objetivo) - a
    dist = d.length
    dist = min(max(dist, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    dn = d.normalized() if d.length > 1e-6 else Vector((0, 0, -1))
    x = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    p = Vector(polo)
    p = p - dn * p.dot(dn)
    if p.length < 1e-4:
        p = Vector((0, -1, 0)) - dn * dn.y
    p.normalize()
    return a + dn * x + p * h, a + dn * dist


# ----------------------------------------------------------------------------- el muñeco plano
L_LUM, L_TOR, L_CUE = 0.28, 0.27, 0.12
L_BR, L_AB = 0.30, 0.29
L_MUS, L_PAN = 0.43, 0.42
PIE_Z = 0.055


def dir_esp(ax, ay):
    """Dirección de un tramo de columna: ax = inclina hacia +x, ay = hacia la cámara (-y)."""
    return Vector((math.sin(ax), -math.sin(ay), math.cos(ax) * math.cos(ay))).normalized()


class Muneco:
    """Tubos lisos y cabeza esfera, sin cara. La pose se arma desde cero cada cuadro (columna FK, brazos y piernas IK)."""

    def __init__(s, nombre, mat, rt=0.12, rl=0.07, ra=0.05, rh=0.14):
        s.nombre, s.mat, s.rt, s.rl, s.ra, s.rh = nombre, mat, rt, rl, ra, rh
        mk = lambda n, L, r: objeto(f"{nombre}_{n}", m_capsula(L, r), mat)
        s.lum = mk("lum", L_LUM, rt * 0.92)
        s.tor = mk("tor", L_TOR, rt)
        s.cue = mk("cue", L_CUE, 0.045)
        s.cab = objeto(nombre + "_cab", m_esfera(), mat, esc=(rh, rh, rh))
        s.br = [mk(f"br{i}", L_BR, ra) for i in range(2)]
        s.ab = [mk(f"ab{i}", L_AB, ra * 0.95) for i in range(2)]
        s.mu = [mk(f"mu{i}", L_MUS, rl * 1.05) for i in range(2)]
        s.pa = [mk(f"pa{i}", L_PAN, rl) for i in range(2)]
        s.pie = [objeto(f"{nombre}_pie{i}", m_esfera(), mat) for i in range(2)]
        s.todos = [s.lum, s.tor, s.cue, s.cab] + s.br + s.ab + s.mu + s.pa + s.pie
        s.hombro_x = 0.175

    def ocultar(s, v):
        for o in s.todos:
            o.hide_render = v

    def poner(s, P):
        """P: x,y,hz,f (0 = de frente, ±1 = de perfil mirando a ese lado), lum/tor/cab = (ax, ay) absolutos,
        mano0/mano1 (Vector o función de J), polo0/polo1, pie0/pie1, rodilla. Devuelve las articulaciones."""
        f = P["f"]
        H = Vector((P["x"], P["y"], P["hz"]))
        W = H + dir_esp(*P["lum"]) * L_LUM
        S = W + dir_esp(*P["tor"]) * L_TOR
        dc = dir_esp(*P["cab"])
        N = S + dc * L_CUE
        Hc = S + dc * (L_CUE + s.rh * 0.95)
        ax_t = P["tor"][0]
        if f == 0:
            u = Vector((math.cos(ax_t), 0, -math.sin(ax_t)))
            sh = [S - u * s.hombro_x, S + u * s.hombro_x]
            cad = [H + Vector((-0.085, 0, 0)), H + Vector((0.085, 0, 0))]
        else:
            sh = [S + Vector((0, -0.055, 0)), S + Vector((0, 0.055, 0))]
            cad = [H + Vector((0, -0.04, 0)), H + Vector((0, 0.04, 0))]
        J = dict(H=H, W=W, S=S, N=N, Hc=Hc, sh=sh, cad=cad)
        colocar_cap(s.lum, H, W)
        colocar_cap(s.tor, W, S)
        colocar_cap(s.cue, S, N)
        s.cab.location = Hc
        for i in range(2):
            m = P[f"mano{i}"]
            m = m(J) if callable(m) else Vector(m)
            codo, mano = ik2(sh[i], m, L_BR, L_AB, P[f"polo{i}"])
            colocar_cap(s.br[i], sh[i], codo)
            colocar_cap(s.ab[i], codo, mano)
            J[f"codo{i}"], J[f"mano{i}"] = codo, mano
            pie = Vector(P[f"pie{i}"])
            rod, tob = ik2(cad[i], pie, L_MUS, L_PAN, P["rodilla"])
            colocar_cap(s.mu[i], cad[i], rod)
            colocar_cap(s.pa[i], rod, tob)
            J[f"pie{i}"] = tob
            if f == 0:
                s.pie[i].location = tob + Vector((0, -0.06, -0.0))
                s.pie[i].scale = (s.rl * 1.05, 0.15, PIE_Z)
            else:
                s.pie[i].location = tob + Vector((f * 0.05, 0, 0))
                s.pie[i].scale = (0.15, s.rl * 1.05, PIE_Z)
        return J


# ----------------------------------------------------------------------------- batería, texto, sorbetes, cable
class Bateria:
    ANCHO, ALTO, GRUESO = 0.52, 0.21, 0.022
    CENTRO = Vector((-0.02, 0.0, 2.43))

    def __init__(s):
        s.m_marco = mat_emision("bat_marco", BLANCO, 1.6)
        c, w, h, g = s.CENTRO, s.ANCHO, s.ALTO, s.GRUESO
        caja = lambda n, loc, esc, m: objeto("bat_" + n, m_caja(), m, loc, esc)
        s.piezas = [
            caja("arr", (c.x, 0, c.z + h / 2 - g / 2), (w, 0.03, g), s.m_marco),
            caja("aba", (c.x, 0, c.z - h / 2 + g / 2), (w, 0.03, g), s.m_marco),
            caja("izq", (c.x - w / 2 + g / 2, 0, c.z), (g, 0.03, h), s.m_marco),
            caja("der", (c.x + w / 2 - g / 2, 0, c.z), (g, 0.03, h), s.m_marco),
            caja("punta", (c.x + w / 2 + 0.018, 0, c.z), (0.036, 0.03, 0.09), s.m_marco),
        ]
        interior = w - 2 * g - 0.04
        gap = 0.012
        s.bw = (interior - 4 * gap) / 5
        s.bh = h - 2 * g - 0.04
        s.x0 = c.x - interior / 2
        s.barras, s.m_barras = [], []
        for i in range(5):
            m = mat_emision(f"bat_barra{i}", BLANCO, 1.6)
            o = caja(f"barra{i}", (s.x0 + s.bw / 2 + i * (s.bw + gap), 0, c.z), (s.bw, 0.03, s.bh), m)
            s.barras.append(o)
            s.m_barras.append(m)
        s.gap = gap

    def poner(s, t):
        # estado del marco: blanco, rojo en el tramo crítico (3,8 s a 9,4 s)
        rojo = (3.85 <= t < 9.4)
        c_marco = hexa(ROJO) if rojo else hexa(BLANCO)
        set_emision(s.m_marco, c_marco, 1.6 if not rojo else 2.2)
        # cuántas barras (con su nivel 0..1)
        niv = [1, 1, 1, 1, 0]
        niv[3] = 1 - sm(t, 1.15, 1.45)
        niv[2] = 1 - sm(t, 2.7, 2.95)
        niv[1] = 1 - sm(t, 3.8, 4.0)
        carga = [kf(t, [(9.35, 0), (9.45, 1)]), sm(t, 9.62, 9.78), sm(t, 9.9, 10.05), sm(t, 10.15, 10.3), sm(t, 10.4, 10.55)]
        if t >= 9.35:
            niv = carga
        blanco_fin = sm(t, 10.6, 11.1)         # el ámbar termina blanco brillante
        for i, (o, m) in enumerate(zip(s.barras, s.m_barras)):
            k = lim(niv[i])
            if k < 0.01:
                o.hide_render = True
                continue
            o.hide_render = False
            o.scale = (s.bw * k, 0.03, s.bh)
            o.location.x = s.x0 + i * (s.bw + s.gap) + s.bw * k / 2
            if t >= 9.35:
                col = mezclar(hexa(AMBAR), hexa(BLANCO), blanco_fin)
                if i == 0:
                    col = mezclar(hexa(BLANCO), hexa(AMBAR), sm(t, 9.4, 9.55))
                    col = mezclar(col, hexa(BLANCO), blanco_fin)
                fu = 1.9
            elif rojo:
                col = hexa(ROJO)
                fu = 1.9
                if i == 0 and 4.0 <= t < 5.0:          # titila el último tramo
                    fu = 1.2 + 1.5 * (0.5 + 0.5 * math.sin((t - 4.0) * 2 * math.pi / 0.42))
            else:
                col = hexa(BLANCO)
                fu = 1.6 * (0.35 + 0.65 * k) if k < 1 else 1.6
            set_emision(m, col, fu)


class Texto:
    def __init__(s, nombre, cadena, color, z, fuerza=1.7):
        s.cadena = cadena
        cur = bpy.data.curves.new(nombre, 'FONT')
        cur.font = bpy.data.fonts.load(os.path.join(AQUI, "fuentes", "DejaVuSansMono-Bold.ttf"))
        cur.size = 0.128
        cur.align_x = 'LEFT'
        cur.align_y = 'CENTER'
        cur.body = cadena
        s.mat = mat_emision("txt_" + nombre, color, fuerza)
        cur.materials.append(s.mat)
        s.o = bpy.data.objects.new(nombre, cur)
        bpy.context.scene.collection.objects.link(s.o)
        s.o.rotation_euler = (math.pi / 2, 0, 0)
        bpy.context.view_layer.update()
        ancho = s.o.dimensions.x
        s.o.location = (-ancho / 2, 0, z)
        s.cur = cur

    def poner(s, n, cursor=False):
        n = int(n)
        if n <= 0:
            s.o.hide_render = True
            return
        s.o.hide_render = False
        s.cur.body = s.cadena[:n] + ("_" if cursor and n < len(s.cadena) else "")


class Linea:
    """Cadena de tubos (sorbete o cable), cada uno con su material para poder poner pulsos de luz."""

    def __init__(s, nombre, n, r, color, fuerza, uno_solo=False):
        s.r, s.n = r, n
        s.mats = [mat_emision(f"{nombre}{i}", color, fuerza) for i in range(1 if uno_solo else n)]
        s.tubos = [objeto(f"{nombre}_t{i}", m_tubo(), s.mats[0 if uno_solo else i]) for i in range(n)]
        s.nudos = [objeto(f"{nombre}_n{i}", m_esfera(16), s.mats[0 if uno_solo else min(i, len(s.mats) - 1)]) for i in range(n + 1)]
        s.uno = uno_solo

    def ocultar(s):
        for o in s.tubos + s.nudos:
            o.hide_render = True

    def poner(s, pts):
        for i, o in enumerate(s.tubos):
            colocar_tubo(o, pts[i], pts[i + 1], s.r)
        for i, o in enumerate(s.nudos):
            o.hide_render = False
            o.location = pts[i]
            o.scale = (s.r,) * 3


# ----------------------------------------------------------------------------- escena
E = {}


def camara(sc, dist=21.0, zt=1.43, cab=4.0, lens=85.0):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.sensor_height = 24.0
    cam.data.clip_end = 100
    sc.camera = cam
    E["cam"] = cam
    camara_a(dist, zt, cab)


def camara_a(dist, zt, cab=4.0):
    cam = E["cam"]
    p = math.radians(cab)
    tgt = Vector((0, 0, zt))
    cam.location = tgt + Vector((0, -dist * math.cos(p), dist * math.sin(p)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()


def luz(nombre, tipo, loc, tgt, color, watts, tam):
    l = bpy.data.lights.new(nombre, tipo)
    l.energy = watts
    l.color = color
    if tipo == 'AREA':
        l.size = tam
    else:
        l.shadow_soft_size = tam
    o = bpy.data.objects.new(nombre, l)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def construir_escena():
    limpiar()
    sc = bpy.context.scene
    E["sc"] = sc
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.world = w
    camara(sc)

    # piso negro con un leve reflejo mojado + sombra elíptica difusa
    piso_m = bpy.data.materials.new("piso")
    piso_m.use_nodes = True
    pn = piso_m.node_tree
    for n in list(pn.nodes):
        pn.nodes.remove(n)
    tcp, rmp, mpp, grp, rap, brp, trp, mxp, outp = (pn.nodes.new(x) for x in (
        "ShaderNodeNewGeometry", "ShaderNodeMapping", "ShaderNodeMapping", "ShaderNodeTexGradient", "ShaderNodeValToRGB",
        "ShaderNodeBsdfGlossy", "ShaderNodeBsdfTransparent", "ShaderNodeMixShader", "ShaderNodeOutputMaterial"))
    pn.nodes.remove(rmp)
    mpp.inputs["Location"].default_value = (0.0, 0.0, 0)
    mpp.inputs["Scale"].default_value = (1 / 1.9, 1 / 1.2, 1)
    pn.links.new(tcp.outputs["Position"], mpp.inputs["Vector"])
    pn.links.new(mpp.outputs["Vector"], grp.inputs["Vector"])
    grp.gradient_type = 'SPHERICAL'
    rap.color_ramp.elements[0].position = 0.0
    rap.color_ramp.elements[0].color = (0, 0, 0, 1)
    rap.color_ramp.elements[1].position = 0.75
    rap.color_ramp.elements[1].color = (1, 1, 1, 1)
    pn.links.new(grp.outputs["Fac"], rap.inputs["Fac"])
    brp.inputs["Color"].default_value = (0.16, 0.16, 0.19, 1)
    brp.inputs["Roughness"].default_value = 0.22
    pn.links.new(rap.outputs["Color"], mxp.inputs["Fac"])
    pn.links.new(trp.outputs["BSDF"], mxp.inputs[1])
    pn.links.new(brp.outputs["BSDF"], mxp.inputs[2])
    emp = pn.nodes.new("ShaderNodeEmission")
    emp.inputs["Strength"].default_value = 0.008
    rs = pn.nodes.new("ShaderNodeMath")
    rs.operation = 'MULTIPLY'
    pn.links.new(rap.outputs["Color"], rs.inputs[0])
    rs.inputs[1].default_value = 1.0
    pn.links.new(rap.outputs["Color"], emp.inputs["Color"])
    adp = pn.nodes.new("ShaderNodeAddShader")
    pn.links.new(mxp.outputs["Shader"], adp.inputs[0])
    pn.links.new(emp.outputs["Emission"], adp.inputs[1])
    pn.links.new(adp.outputs["Shader"], outp.inputs["Surface"])
    piso = objeto("piso", m_caja(), piso_m, (0, 0, -0.05), (14, 14, 0.1))
    piso.visible_shadow = False
    # personajes
    E["proto"] = Muneco("proto", mat_brillo("proto", BLANCO, 1.25), rt=0.12, rl=0.07, ra=0.05)
    E["amigo"] = Muneco("amigo", mat_brillo("amigo", AMBAR, 1.0), rt=0.085, rl=0.065, ra=0.05)
    E["dren"] = []
    for k, (nom, rt) in enumerate((("dA", 0.085), ("dB", 0.085), ("dC", 0.085))):
        m = mat_principled(nom, AZUL_APAGADO, rough=0.85, spec=0.15, emis=0.22)
        E["dren"].append(Muneco(nom, m, rt=rt, rl=0.062, ra=0.048))
    E["paja"] = [Linea(f"paja{i}", 2, 0.016, AZUL_PAJA, 0.9, uno_solo=True) for i in range(3)]
    E["cable"] = Linea("cable", 30, 0.014, AMBAR, 1.4)
    E["bat"] = Bateria()
    E["txt1"] = Texto("l1", "TU BATERÍA SOCIAL ES LIMITADA.", BLANCO, 3.32)
    E["txt2"] = Texto("l2", "CUIDA QUIÉN TE LA DESCARGA", TXT_AZUL, 3.17)
    E["txt3"] = Texto("l3", "Y QUIÉN TE LA CARGA.", AMBAR, 3.03)

    # luces: relleno frío suave, contraluces azules para el borde de los que drenan, tibia del amigo
    luz("rell", 'AREA', (0, -7, 5), (0, 0, 1.2), (0.9, 0.92, 1.0), 300, 5)
    luz("rimL", 'AREA', (-3.5, 3, 2.6), (-0.8, 0, 1.2), (0.30, 0.50, 1.0), 480, 2.5)
    luz("rimR", 'AREA', (3.5, 3, 2.6), (0.8, 0, 1.2), (0.30, 0.50, 1.0), 480, 2.5)
    E["luz_amigo"] = luz("amb", 'POINT', (1.2, -1.6, 1.4), (0, 0, 1.2), hexa(AMBAR), 0, 0.4)
    configurar_render(sc)


def configurar_render(sc):
    sc.render.engine = 'CYCLES'
    c = sc.cycles
    c.device = 'CPU'
    c.samples = int(ARGS["samples"])
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.03
    c.use_denoising = True
    try:
        c.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    c.max_bounces = 3
    c.diffuse_bounces = 1
    c.glossy_bounces = 2
    c.transmission_bounces = 0
    c.volume_bounces = 0
    c.sample_clamp_indirect = 4.0
    c.sample_clamp_direct = 0.0
    sc.render.threads_mode = 'AUTO'
    sc.render.resolution_x = ANCHO
    sc.render.resolution_y = ALTO
    sc.render.resolution_percentage = int(round(ARGS["escala"] * 100))
    sc.render.fps = FPS
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.film_transparent = False
    # bloom solo en lo que brilla (valores > 1): los personajes apagados no pasan el umbral
    sc.use_nodes = True
    nt = sc.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    gl = nt.nodes.new("CompositorNodeGlare")
    try:
        gl.glare_type = 'BLOOM'
    except Exception:
        gl.glare_type = 'FOG_GLOW'
    gl.quality = 'MEDIUM'
    gl.threshold = 1.0
    gl.size = 6
    gl.mix = float(ARGS["glow"])
    co = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], gl.inputs["Image"])
    nt.links.new(gl.outputs["Image"], co.inputs["Image"])


# ----------------------------------------------------------------------------- animación
Z0 = 0.86          # altura de cadera de pie
PROTO_X = 0.0
EN_PIE = [Vector((-0.085, -0.02, PIE_Z)), Vector((0.085, -0.02, PIE_Z))]


def pose_proto(t):
    """Protagonista (de frente): se encorva en arco C entre 1,4 y 3,6 s, se agarra la cabeza ~5,3, revolea los brazos ~5,7,
    baja agotado, y al cargar se endereza con rebote."""
    pes = kf(t, [(0, 0.0), (1.4, 0.0), (3.6, 1.0), (4.85, 1.0), (5.15, 0.0), (6.8, 0.0), (7.3, 0.3),
                 (9.35, 0.3), (9.8, -0.16), (10.25, 0.04), (10.7, 0.0)])
    ax_l = 0.05 * pes
    # los brazos
    # posiciones relativas al hombro; elbows hacia afuera
    d = lambda i: -1 if i == 0 else 1
    reposo = lambda i: Vector((d(i) * 0.04, -0.02, -0.57))
    a_cabeza = lambda i: Vector((d(i) * 0.0, -0.07, 0.31))
    en_alto = lambda i: Vector((d(i) * 0.30, 0.0, 0.43))
    afuera = lambda i: Vector((d(i) * 0.57, 0.0, 0.08))
    manos = []
    for i in (0, 1):
        pts = [(0, reposo(i)), (4.85, reposo(i) + Vector((0, 0, 0)))]
        r = reposo(i) + Vector((d(i) * 0.02, -0.14 * pes, 0.0))
        v = r
        v = v.lerp(a_cabeza(i), sm(t, 5.12, 5.4))
        v = v.lerp(en_alto(i), sm(t, 5.62, 5.85)) if t >= 5.4 else v
        if t >= 6.2:
            if i == 1:                                        # el brazo derecho se extiende hacia el amigo antes de bajar
                v = en_alto(i).lerp(afuera(i), sm(t, 6.45, 6.7)).lerp(r, sm(t, 6.8, 7.15))
            else:
                v = en_alto(i).lerp(r, sm(t, 6.55, 7.05))
        manos.append(v)
    ha, hb = manos
    P = dict(x=PROTO_X + 0.07 * pes, y=0.0, hz=Z0 - 0.03 * pes, f=0,
             lum=(ax_l, 0.32 * pes), tor=(0.08 * pes, 0.62 * pes), cab=(0.17 * pes, 0.80 * pes),
             polo0=Vector((-1, 0.3, -0.35)), polo1=Vector((1, 0.3, -0.35)),
             pie0=EN_PIE[0], pie1=EN_PIE[1], rodilla=Vector((0, -1, 0)))
    P["mano0"] = lambda J, v=ha: J["sh"][0] + v
    P["mano1"] = lambda J, v=hb: J["sh"][1] + v
    # los pies no se mueven aunque la cadera baje
    return P


def andar(xf, t, d, A=0.22, ciclo=0.9, x_ref=None):
    """Pasos de un caminante que va por xf(t) hacia el lado d. Devuelve (pies, swing_brazos, w)."""
    v = abs(xf(t + 0.02) - xf(t - 0.02)) / 0.04
    w = lim(v / 0.35)
    dist = abs(xf(t) - (x_ref if x_ref is not None else xf(0)))
    s = dist / ciclo
    pies, bra = [], []
    for k in (0, 1):
        sk = (s + 0.5 * k) % 1.0
        if sk < 0.5:
            off, alz = d * A * (1 - 4 * sk), 0.0
        else:
            u = (sk - 0.5) * 2
            off, alz = -d * A + d * 2 * A * (u * u * (3 - 2 * u)), 0.10 * math.sin(math.pi * u)
        stand = d * 0.04 * (1 if k == 0 else -1)
        pies.append((stand + (off - stand) * w, alz * w))
        bra.append(0.40 * math.sin(2 * math.pi * (s + 0.5 * k)) * w)
    return pies, bra, w


def friend_x(t):
    return kv(t, [(6.4, (2.1, 0, 0)), (7.05, (1.25, 0, 0)), (7.6, (0.82, 0, 0)), (8.0, (0.66, 0, 0))]).x if t < 8.0 else 0.66


def pose_amigo(t, Jp):
    d = -1
    x = friend_x(t)
    pies, bra, w = andar(friend_x, t, d, x_ref=2.1)
    asom = sm(t, 7.6, 8.3)
    corte = sm(t, 9.5, 9.9)           # baja el brazo al terminar la conexión
    inc = 0.05 * asom
    P = dict(x=x + d * 0.02 * asom, y=-0.02, hz=Z0 + 0.035 + 0.012 * math.sin(t * 9.0) * w,
             f=d, lum=(d * (0.02 + inc * 0.5), 0.0), tor=(d * (0.04 + inc), 0.0), cab=(d * (0.12 + 0.06 * asom), 0.0),
             rodilla=Vector((d, 0, 0.1)))
    for k in (0, 1):
        P[f"pie{k}"] = Vector((x + pies[k][0], 0.0 + (-0.04 if k == 0 else 0.04), PIE_Z + pies[k][1]))
    # brazos: swing al caminar; el de adelante (0, más cerca de la cámara) sube a la cabeza del protagonista
    alto = sm(t, 8.25, 8.75) * (1 - corte)
    objetivo = Jp["Hc"] + Vector((0.19, -0.05, 0.13))

    def mano(i):
        def f(J):
            sh = J["sh"][i]
            q = bra[i]
            camina = sh + Vector((d * math.sin(q) * 0.52, 0.0, -math.cos(q) * 0.52))
            if i == 0:
                return camina.lerp(objetivo, alto)
            return camina.lerp(sh + Vector((d * 0.05, 0.1, -0.55)), asom)
        return f
    P["mano0"], P["mano1"] = mano(0), mano(1)
    P["polo0"] = Vector((0.2, -0.2, -1)) if alto < 0.5 else Vector((0.4, -0.6, -1))
    P["polo1"] = Vector((0.2, 0.2, -1))
    return P


def pose_dren(k, t):
    """k = 0 (izquierda), 1 (derecha), 2 (el de atrás, que entra a 1 s). De perfil mirando al protagonista."""
    if k == 0:
        f, x0, y = 1, -0.80, 0.12
    elif k == 1:
        f, x0, y = -1, 0.80, 0.12
    else:
        f, x0, y = 1, -0.38, 0.62
    suelta = sm(t, 5.72, 6.05) if k < 2 else sm(t, 5.8, 6.1)
    atras = eo(t, 5.75, 6.15)
    x = x0 + (-f) * 0.16 * sm(t, 5.9, 7.0)              # se abren un poco al irse
    if k == 2:
        # entra por detrás desde la izquierda, caminando
        xf = lambda tt: kv(tt, [(0.95, (-0.95, 0, 0)), (1.95, (-0.38, 0, 0))]).x
        x = xf(t)
        pies, bra, w = andar(xf, t, 1, A=0.18, x_ref=-0.95)
        x = x + (-f) * 0.12 * sm(t, 6.0, 7.2)
    else:
        w = 0.0
        pies = [(0.18, 0.0), (-0.16, 0.0)] if k == 0 else [(-0.18, 0.0), (0.16, 0.0)]
        pies = [(f * 0.17, 0.0), (-f * 0.15, 0.0)]
    # leve vaivén de succión
    bob = 0.012 * math.sin(t * 7.0 + k * 1.7) * (1 - suelta)
    lean = 1 - 1.9 * atras
    P = dict(x=x, y=y, hz=0.835 + bob, f=f,
             lum=(f * 0.10 * lean, 0.0), tor=(f * 0.19 * lean, 0.0), cab=(f * 0.30 * lean, 0.0),
             rodilla=Vector((f, 0, 0.0)))
    for i in (0, 1):
        P[f"pie{i}"] = Vector((x + pies[i][0], y + (-0.04 if i == 0 else 0.04), PIE_Z + pies[i][1]))
    # brazos: las dos manos al sorbete (cerca de la boca); al soltar, caen a los costados; el de atrás se pone en jarra
    jarra = sm(t, 6.0, 6.3) if k == 2 else 0.0

    def mano(i):
        def fn(J):
            boca = J["Hc"] + Vector((f * 0.17, 0.0, -0.10))
            sorb = boca + Vector((-f * 0.02 * i, -0.035 + 0.075 * i, -0.04 - 0.06 * i))
            lado = J["sh"][i] + Vector((-f * 0.04, 0, -0.55))
            cad = J["H"] + Vector((f * 0.03, (-0.13 if i == 0 else 0.13), 0.04))
            v = sorb.lerp(lado, suelta)
            return v.lerp(cad, jarra)
        return fn
    P["mano0"], P["mano1"] = mano(0), mano(1)
    P["polo0"] = Vector((-f * 0.3, -0.2, -1)) if jarra < 0.5 else Vector((0, -1, 0))
    P["polo1"] = Vector((-f * 0.3, 0.2, -1)) if jarra < 0.5 else Vector((0, 1, 0))
    vis = 1.0
    if k < 2:
        vis = 1 - sm(t, 6.25, 7.1)
    else:
        vis = kf(t, [(1.0, 0.0), (1.35, 0.45), (1.95, 0.78), (6.4, 0.78), (7.35, 0.0)])
    return P, f, suelta, vis


def aplicar(t):
    """Coloca TODO para el segundo t."""
    E["luz_amigo"].data.energy = 55 * sm(t, 6.6, 7.6)
    # --- protagonista
    Pp = pose_proto(t)
    Jp = E["proto"].poner(Pp)
    # --- amigo
    va = t >= 6.35
    E["amigo"].ocultar(not va)
    Ja = None
    if va:
        Ja = E["amigo"].poner(pose_amigo(t, Jp))
    # --- los que drenan
    straw = E["paja"]
    for k in range(3):
        m = E["dren"][k]
        P, f, suelta, vis = pose_dren(k, t)
        if vis < 0.01:
            m.ocultar(True)
            straw[k].ocultar()
            continue
        m.ocultar(False)
        J = m.poner(P)
        set_principled(m.mat, mezclar((0, 0, 0), hexa(AZUL_APAGADO), vis * (1.0 if k < 2 else 0.9)),
                       0.22 * vis, mezclar((0, 0, 0), hexa("#34425C"), 1.0))
        # sorbete: de la boca al cráneo del protagonista; al soltarlo cae a 45 grados desde la mano
        lado = -f           # -1 si el que chupa está a la izquierda
        boca = J["Hc"] + Vector((f * 0.15, 0.0, -0.03))
        pes = kf(t, [(0, 0.0), (1.4, 0.0), (3.6, 1.0), (4.85, 1.0), (5.15, 0.0)])
        cab = Jp["Hc"]
        n = Vector((-f * 0.72, 0.0 if k < 2 else 0.12, 0.62)).normalized()
        cont = cab + n * (E["proto"].rh * 0.92)
        carpa = 1.0 - 0.88 * pes
        if k == 2:
            carpa = 1.0 - 0.9 * sm(t, 1.4, 2.4) - 0.1 * pes
        apice = boca.lerp(cont, 0.62) + Vector((0, 0, 0.03 + 0.13 * carpa))
        mano = J["mano0"]
        caida = mano + Vector((-f * 0.0, 0, 0))
        d1 = Vector((-f * 0.7, 0, -0.7)).normalized()
        p0 = mano
        pts_suelta = [p0, p0 + d1 * 0.30, p0 + d1 * 0.62 + Vector((0, 0, 0.0))]
        pts_pega = [boca, apice, cont]
        s_ = eo(t, 5.72, 6.1) if k < 2 else eo(t, 5.8, 6.14)
        pts = [Vector(a).lerp(Vector(b), s_) for a, b in zip(pts_pega, pts_suelta)]
        # la del que entra por detrás se arma recién a la mitad del camino
        if k == 2 and t < 1.0:
            straw[k].ocultar()
        else:
            if k == 2:
                pts = [Vector(a).lerp(Vector(b), sm(t, 1.0, 1.9)) if i == 2 else Vector(a) for i, (a, b) in enumerate(zip(pts, [boca, apice, cont]))]
                pts[2] = boca.lerp(pts[2], sm(t, 1.0, 1.9)) if t < 1.9 else pts[2]
            straw[k].poner(pts)
            set_emision(straw[k].mats[0], mezclar((0, 0, 0), hexa(AZUL_PAJA), vis), 0.45 * vis)
    # --- batería y texto
    E["bat"].poner(t)
    E["txt1"].poner(30)
    n2 = lim((t - 5.7) / (6.4 - 5.7)) * 26
    E["txt2"].poner(n2, cursor=0 < n2 < 26)
    n3 = lim((t - 9.3) / (9.9 - 9.3)) * 20
    E["txt3"].poner(n3, cursor=0 < n3 < 20)
    # --- cable ámbar de la cabeza del amigo a la del protagonista
    cab = E["cable"]
    g = sm(t, 9.0, 9.4)
    if Ja is None or g <= 0.01:
        cab.ocultar()
    else:
        A = Ja["Hc"] + Vector((0, 0, E["amigo"].rh * 0.97))
        B0 = Jp["Hc"] + Vector((0.0, 0, E["proto"].rh * 0.97))
        B = B0
        N = cab.n
        pts = []
        for i in range(N + 1):
            u = i / N * g
            base = A.lerp(B, u)
            sag = -0.26 * (1 - (2 * u - 1) ** 2) if u < 1 else 0
            riser = 0.07 * (math.exp(-u / 0.05) + math.exp(-(1 - u) / 0.05))
            pts.append(base + Vector((0, -0.03 * math.sin(math.pi * u), sag + riser)))
        cab.poner(pts)
        # pulsos de luz viajando hacia el protagonista mientras carga
        activo = sm(t, 9.45, 9.7) * (1 - sm(t, 11.5, 11.9) * 0.0)
        for i, m in enumerate(cab.mats):
            u = (i + 0.5) / N
            inten = 1.1
            for q in range(3):
                c = (t * 0.85 + q / 3.0) % 1.0
                inten += 5.0 * activo * math.exp(-((u - c) / 0.06) ** 2)
            set_emision(m, hexa(AMBAR), inten)
    bpy.context.view_layer.update()


def aplicar_hoja():
    """Hoja de personajes: los tres de frente y quietos."""
    for o in bpy.data.objects:
        if o.type in ('MESH', 'FONT') and o.name != "piso":
            o.hide_render = True
    ep = [Vector((-0.085, -0.02, PIE_Z)), Vector((0.085, -0.02, PIE_Z))]

    def base(x, mat_muneco, pes=0.0):
        P = dict(x=x, y=0.0, hz=Z0, f=0, lum=(0, 0), tor=(0, 0), cab=(0, 0),
                 polo0=Vector((-1, 0.3, -0.35)), polo1=Vector((1, 0.3, -0.35)), rodilla=Vector((0, -1, 0)))
        P["pie0"], P["pie1"] = ep[0] + Vector((x, 0, 0)), ep[1] + Vector((x, 0, 0))
        P["mano0"] = lambda J: J["sh"][0] + Vector((-0.05, -0.02, -0.57))
        P["mano1"] = lambda J: J["sh"][1] + Vector((0.05, -0.02, -0.57))
        return P
    E["proto"].ocultar(False)
    E["proto"].poner(base(-1.15, None))
    E["dren"][0].ocultar(False)
    set_principled(E["dren"][0].mat, hexa(AZUL_APAGADO), 0.22, hexa("#2C4577"))
    E["dren"][0].poner(base(0.0, None))
    E["amigo"].ocultar(False)
    E["amigo"].poner(base(1.15, None))


def renderizar(t, ruta):
    aplicar(t)
    E["sc"].render.filepath = ruta
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0


def principal():
    construir_escena()
    if ARGS["hoja"]:
        sc = E["sc"]
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        camara_a(9.5, 1.0, 3.0)
        aplicar_hoja()
        sc.render.filepath = os.path.abspath(ARGS["hoja"])
        os.makedirs(os.path.dirname(sc.render.filepath), exist_ok=True)
        bpy.ops.render.render(write_still=True)
        return
    if ARGS["still"] is not None:
        t = ARGS["still"]
        ruta = os.path.abspath(ARGS["out"] or os.path.join(AQUI, "prueba", f"cuadro-{t:.2f}.png"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        seg = renderizar(t, ruta)
        print(f"[escena] t={t:.2f}s -> {ruta} en {seg:.1f}s")
    elif ARGS["anim"]:
        carpeta = os.path.abspath(ARGS["carpeta"] or os.path.join(AQUI, "salida", "frames"))
        os.makedirs(carpeta, exist_ok=True)
        fin = ARGS["end"] if ARGS["end"] is not None else NCUADROS - 1
        for f in range(ARGS["start"], fin + 1, ARGS["paso"]):
            ruta = os.path.join(carpeta, f"f_{f:04d}.png")
            if os.path.exists(ruta):
                continue
            seg = renderizar(f / FPS, ruta)
            print(f"[escena] cuadro {f}/{NCUADROS - 1}  {seg:.1f}s", flush=True)
    else:
        print("Falta --still T, --hoja ruta o --anim")


if os.environ.get("ESCENA_SIN_PRINCIPAL") != "1":
    principal()
