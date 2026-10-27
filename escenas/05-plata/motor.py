"""
Dos Mentes 05 — motor Blender (bpy 4.2): primitivas, materiales y el muñeco con rig por código.

El muñeco es el del dibujo de Dante llevado a 3D: cabeza redonda grande, extremidades de tubo grueso con puntas
redondeadas, color plano, cara con ojos/cejas/boca y manos con dedos. No hay huesos de Blender: cada parte es un objeto
y `Personaje.poner(...)` las coloca desde cero (función pura de la pose): IK de 2 huesos para brazos, piernas y pulgar,
cadena FK para los otros dedos. Las longitudes de hueso son constantes, así que cada cápsula es un mesh fijo (sin escalar).
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Quaternion

AQUI = os.path.dirname(os.path.abspath(__file__))
_MAT, _MESH = {}, {}


# ----------------------------------------------------------------------------- base
def limpiar():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MAT.clear(); _MESH.clear()


def hexa(s):
    """'#33C4FF' (sRGB) -> color lineal (r,g,b) para Blender."""
    s = s.lstrip("#")
    c = [int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def material(nombre, color, rough=0.8, metal=0.0, emis=None, alpha=None, spec=0.2):
    """Material plano tipo toon (Principled opaco, rugosidad alta). `color` = '#RRGGBB'. `emis`=fuerza (pantallas, letras)."""
    k = (nombre, color, rough, metal, emis, alpha, spec)
    if k in _MAT:
        return _MAT[k]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n = m.node_tree.nodes
    b = n["Principled BSDF"]
    c = hexa(color)
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if emis:
        b.inputs["Emission Color"].default_value = (*c, 1)
        b.inputs["Emission Strength"].default_value = emis
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
    _MAT[k] = m
    return m


def material_glow(nombre, tinte, emis=0.55, base=(0.80, 0.82, 0.86)):
    """Blanco que brilla: base casi blanca + emisión tintada (el tinte es apenas visible; el color real lo ponen las luces)."""
    k = (nombre, tinte, emis, base, "glow")
    if k in _MAT:
        return _MAT[k]
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    c = hexa(tinte)
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.25
    b.inputs["Emission Color"].default_value = (*c, 1)
    b.inputs["Emission Strength"].default_value = emis
    _MAT[k] = m
    return m


def _fin(bm, nombre, suave=True, ang=0.8):
    """bmesh -> mesh; suaviza las caras y deja filosas las aristas de más de `ang` rad."""
    if suave:
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0) > ang:
                e.smooth = False
        for f in bm.faces:
            f.smooth = True
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    return me


# ----------------------------------------------------------------------------- mallas (cacheadas)
def m_esfera(seg=24):
    k = ("esf", seg)
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
        _MESH[k] = _fin(bm, "esfera", ang=3.2)
    return _MESH[k]


def m_capsula(L, r, seg=14):
    """Cápsula a lo largo de +Z desde z=0 hasta z=L (más las puntas redondas de radio r)."""
    k = ("cap", round(L, 4), round(r, 4), seg)
    if k not in _MESH:
        bm = bmesh.new()
        nv = seg // 2 | 1                      # impar: sin anillo en el ecuador
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=nv, radius=r)
        for v in bm.verts:
            if v.co.z > 0:
                v.co.z += L
        _MESH[k] = _fin(bm, "cap", ang=3.2)
    return _MESH[k]


def m_caja(sx, sy, sz, bisel=0.02, seg=3):
    k = ("caja", round(sx, 4), round(sy, 4), round(sz, 4), round(bisel, 4), seg)
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= sx; v.co.y *= sy; v.co.z *= sz
        b = min(bisel, 0.49 * min(sx, sy, sz))
        if b > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=seg, profile=0.7, affect='EDGES')
        _MESH[k] = _fin(bm, "caja", ang=0.8)
    return _MESH[k]


def m_cil(r, h, seg=24, r2=None, bisel=0.0):
    """Cilindro (o tronco de cono) de eje Z centrado en el origen."""
    k = ("cil", round(r, 4), round(h, 4), seg, None if r2 is None else round(r2, 4), round(bisel, 4))
    if k not in _MESH:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
        if bisel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bisel, segments=2, profile=0.7, affect='EDGES')
        _MESH[k] = _fin(bm, "cil", ang=0.9)
    return _MESH[k]


def m_toro(R, r, seg=24, seg2=10):
    k = ("toro", round(R, 4), round(r, 4))
    if k not in _MESH:
        bm = bmesh.new()
        verts = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            row = []
            for j in range(seg2):
                b = 2 * math.pi * j / seg2
                rr = R + r * math.cos(b)
                row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), r * math.sin(b))))
            verts.append(row)
        for i in range(seg):
            for j in range(seg2):
                bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % seg2], verts[i][(j + 1) % seg2]))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        _MESH[k] = _fin(bm, "toro", ang=3.2)
    return _MESH[k]


def m_poly(puntos, grosor, nombre="poly"):
    """Prisma: polígono 2D (x,y) extruido en Z de -grosor/2 a +grosor/2."""
    bm = bmesh.new()
    top = [bm.verts.new((x, y, grosor / 2)) for x, y in puntos]
    bot = [bm.verts.new((x, y, -grosor / 2)) for x, y in puntos]
    bm.faces.new(top)
    bm.faces.new(bot[::-1])
    n = len(puntos)
    for i in range(n):
        bm.faces.new((top[i], bot[i], bot[(i + 1) % n], top[(i + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return _fin(bm, nombre, ang=0.6)


# ----------------------------------------------------------------------------- objetos
def vacio(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    o = bpy.data.objects.new(nombre, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    if padre is not None:
        o.parent = padre
    return o


def poner_mat(o, mat):
    """Material por objeto (los meshes se comparten entre objetos de distinto color)."""
    if not o.data.materials:
        o.data.materials.append(mat)
    o.material_slots[0].link = 'OBJECT'
    o.material_slots[0].material = mat


def obj(nombre, malla, mat=None, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), esc=(1, 1, 1)):
    o = bpy.data.objects.new(nombre, malla)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        poner_mat(o, mat)
    o.location = loc
    o.rotation_euler = rot
    o.scale = esc
    if padre is not None:
        o.parent = padre
    return o


def esf(nombre, r, mat, padre=None, loc=(0, 0, 0), esc=(1, 1, 1), rot=(0, 0, 0)):
    return obj(nombre, m_esfera(), mat, padre, loc, rot, (r * esc[0], r * esc[1], r * esc[2]))


def caja(nombre, tam, mat, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), bisel=0.02):
    return obj(nombre, m_caja(*tam, bisel=bisel), mat, padre, loc, rot)


def cil(nombre, r, h, mat, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), r2=None, seg=24, bisel=0.0):
    return obj(nombre, m_cil(r, h, seg, r2, bisel), mat, padre, loc, rot)


def toro(nombre, R, r, mat, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), esc=(1, 1, 1)):
    return obj(nombre, m_toro(R, r), mat, padre, loc, rot, esc)


def rot_z_a(d):
    """Cuaternión que lleva +Z a la dirección d."""
    d = Vector(d).normalized()
    return Vector((0, 0, 1)).rotation_difference(d)


def colocar_cap(o, a, b):
    """Coloca la cápsula `o` (a lo largo de +Z, ya con su largo) con la punta en a, apuntando a b (en coordenadas del padre)."""
    a = Vector(a); d = Vector(b) - a
    q = rot_z_a(d) if d.length > 1e-6 else Quaternion()
    o.matrix_basis = Matrix.Translation(a) @ q.to_matrix().to_4x4()


def cap(nombre, a, b, r, mat, padre=None):
    """Cápsula estática entre dos puntos (largo = |b-a|)."""
    L = (Vector(b) - Vector(a)).length
    o = obj(nombre, m_capsula(L, r), mat, padre)
    colocar_cap(o, a, b)
    return o


def texto(nombre, s, tam, mat, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), ancho_max=None, centrado=True, negrita=True):
    cur = bpy.data.curves.new(nombre, 'FONT')
    cur.body = s
    cur.font = bpy.data.fonts.load(os.path.join(AQUI, "fuentes", "LiberationSans-Bold.ttf"))
    cur.size = tam
    cur.extrude = 0.0015
    if centrado:
        cur.align_x = 'CENTER'
    cur.align_y = 'CENTER'
    cur.materials.append(mat)
    o = bpy.data.objects.new(nombre, cur)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    if padre is not None:
        o.parent = padre
    return o


def ancho_texto(o):
    bpy.context.view_layer.update()
    return o.dimensions.x


FALTAS = []        # (largo del hueso 1, cuánto faltó para llegar): lo llena ik2, lo lee animar.py


def ik2(a, objetivo, l1, l2, polo):
    """IK de 2 huesos: devuelve (medio, extremo). `polo` = hacia dónde apunta la articulación (codo/rodilla)."""
    a = Vector(a)
    d = Vector(objetivo) - a
    dist = d.length
    if dist > l1 + l2 + 0.01:
        FALTAS.append((round(l1, 3), round(dist - l1 - l2, 3)))
    dist = min(max(dist, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    dn = d.normalized() if d.length > 1e-6 else Vector((0, 0, -1))
    x = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    p = Vector(polo)
    p = p - dn * p.dot(dn)
    if p.length < 1e-4:
        p = Vector((0, 1, 0)) - dn * dn.y
    p.normalize()
    return a + dn * x + p * h, a + dn * dist


def mat_rot(frente, arriba):
    """Matriz 3x3 con Z=frente, Y=arriba (ortogonalizado), X=Y×Z."""
    z = Vector(frente).normalized()
    y = Vector(arriba) - z * Vector(arriba).dot(z)
    if y.length < 1e-4:
        y = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((0, 1, 0))
        y = y - z * y.dot(z)
    y.normalize()
    x = y.cross(z)
    return Matrix(((x.x, y.x, z.x), (x.y, y.y, z.y), (x.z, y.z, z.z)))


def sm(x, a=0.0, b=1.0):
    x = min(1.0, max(0.0, (x - a) / (b - a)))
    return x * x * (3 - 2 * x)


# ----------------------------------------------------------------------------- el muñeco
R_MIEMBRO = 0.041
R_TORSO = 0.074
R_CAB = 0.200
SHX = 0.135                             # separación del hombro respecto del eje del torso
L_BRAZO, L_ANTEB = 0.36, 0.34
L_MUSLO, L_PANT = 0.50, 0.50
L_TORSO = 0.50
ALTURA_TOBILLO = 0.09
HM = 1.12                               # escala de la mano (manos grandes: se leen mejor en cuadro)
LF = (0.075, 0.062)                     # largo de cada falange
LONG_DEDO = (1.0, 1.08, 1.0, 0.8)       # índice, medio, anular, meñique

CARAS = {  # k: curvatura de la boca (+ sonrisa), ab: abierta 0..1, ce: ceja (altura, inclinación interior)
    "neutra": dict(k=0.9, ab=0.0, ce=(0.0, 0.0)),
    "alegre": dict(k=2.8, ab=0.0, ce=(0.25, 0.0)),
    "sonrisa": dict(k=2.0, ab=0.0, ce=(0.1, 0.0)),
    "triste": dict(k=-1.6, ab=0.0, ce=(0.1, 0.55)),
    "culpa": dict(k=-1.2, ab=0.0, ce=(0.2, 0.6)),
    "sorpresa": dict(k=0.0, ab=0.8, ce=(0.55, 0.0)),
    "seria": dict(k=0.0, ab=0.0, ce=(-0.15, -0.25)),
    "preocupado": dict(k=-0.8, ab=0.15, ce=(0.3, 0.5)),
    "enojo": dict(k=-1.0, ab=0.0, ce=(-0.2, -0.6)),
}


class Mano:
    """Mano con dedos: palma + 4 dedos de 2 falanges (FK por curvatura) + pulgar de 2 falanges (IK a un punto)."""

    def __init__(s, nombre, mat, sg):
        s.sg = sg                                   # +1 derecha (pulgar hacia +X de la mano), -1 izquierda
        s.mat = mat
        s.raiz = vacio(nombre + "_mano")
        h = HM
        s.palma = esf(nombre + "_palma", 0.5, mat, s.raiz, (0, 0.0, 0.055 * h), esc=(0.078 * h * 2, 0.040 * h * 2, 0.075 * h * 2))
        s.pulg_base = Vector((sg * 0.062 * h, 0.006 * h, 0.032 * h))
        s.l_pulg = (0.07 * h, 0.062 * h)
        s.dedos = []
        for i in range(4):
            x = sg * (0.0525 - 0.035 * i) * h
            f = LONG_DEDO[i]
            r = 0.030 * h * (0.93 if i == 3 else 1.0)
            b = vacio(f"{nombre}_d{i}", s.raiz, (x, 0, 0.100 * h))
            p1 = obj(f"{nombre}_d{i}p", m_capsula(LF[0] * h * f, r), mat, b)
            m = vacio(f"{nombre}_d{i}m", b, (0, 0, LF[0] * h * f))
            p2 = obj(f"{nombre}_d{i}q", m_capsula(LF[1] * h * f, r * 0.97), mat, m)
            s.dedos.append((b, m, f))
        r = 0.018 * h
        s.t1 = obj(nombre + "_p1", m_capsula(s.l_pulg[0], r), mat, s.raiz)
        s.t2 = obj(nombre + "_p2", m_capsula(s.l_pulg[1], r * 0.95), mat, s.raiz)

    def poner(s, curl=(0.15, 0.15, 0.15, 0.15), pulgar=None, sep=0.0):
        h = HM
        for i, (b, m, f) in enumerate(s.dedos):
            c = curl[i] if not isinstance(curl, (int, float)) else curl
            cb, cm = c if isinstance(c, (tuple, list)) else (c, c)
            b.rotation_euler = (-math.radians(78 * cb), math.radians(sep * (1.5 - i) * -s.sg * 9), 0)
            m.rotation_euler = (-math.radians(98 * cm), 0, 0)
        # pulgar: punto objetivo en coordenadas de la mano
        if pulgar is None:
            pulgar = (s.sg * 0.115 * h, 0.035 * h, 0.15 * h)
        polo = Vector((s.sg * 0.3, 1.0, -0.2))
        med, fin = ik2(s.pulg_base, pulgar, s.l_pulg[0], s.l_pulg[1], polo)
        colocar_cap(s.t1, s.pulg_base, med)
        colocar_cap(s.t2, med, fin)
        # ajuste: la segunda falange arranca donde termina la primera (ya lo hace ik2)


class Personaje:
    def __init__(s, nombre, color, rasgos=None):
        s.nombre = nombre
        s.color = color
        s.rasgos = rasgos or {}
        # stickman blanco que brilla: `color` es el tinte apenas visible del glow; `rasgos["emis"]` = fuerza (extras más tenues)
        s.mat = material_glow("pj_" + nombre, color, (rasgos or {}).get("emis", 0.55), (rasgos or {}).get("base", (0.80, 0.82, 0.86)))
        s.mat_osc = s.mat
        s.mat_negro = material("pupila", "#14161C", rough=0.4, spec=0.3)
        s.mat_blanco = material("ojo", "#FAFAFA", rough=0.35, spec=0.3)
        s.mat_lab = material("boca", "#2A1418", rough=0.5)
        s.M = Matrix.Identity(4)
        # cuerpo
        s.torso = obj(nombre + "_torso", m_capsula(L_TORSO, R_TORSO), s.mat)
        s.pelvis = esf(nombre + "_pelvis", 1.0, s.mat, esc=(R_TORSO * 1.0, R_TORSO * 0.95, R_TORSO * 0.9))
        s.cabeza = vacio(nombre + "_cabeza")
        esf(nombre + "_craneo", R_CAB, s.mat, s.cabeza)
        s.ojos, s.boca, s.boca_ab = [], [], None        # sin cara (estilo 02)
        s.brazo = {}
        s.pierna = {}
        for lado, sg in (("d", 1), ("i", -1)):
            s.brazo[lado] = dict(
                a=obj(f"{nombre}_br{lado}", m_capsula(L_BRAZO, R_MIEMBRO), s.mat),
                b=obj(f"{nombre}_an{lado}", m_capsula(L_ANTEB, R_MIEMBRO * 0.96), s.mat),
                mano=Mano(f"{nombre}_{lado}", s.mat, -sg))
            s.pierna[lado] = dict(
                a=obj(f"{nombre}_mu{lado}", m_capsula(L_MUSLO, R_MIEMBRO * 1.08), s.mat),
                b=obj(f"{nombre}_pa{lado}", m_capsula(L_PANT, R_MIEMBRO), s.mat),
                pie=vacio(f"{nombre}_pie{lado}"))
        s._calzado("plano")
        s.delantal = s.mochila = None

    # ---- cara ----
    def _cara(s):
        c = s.cabeza
        s.ojos = []
        for lado, sg in (("d", 1), ("i", -1)):
            blanco = esf(f"{s.nombre}_oj{lado}", 1.0, s.mat_blanco, c)
            pup = esf(f"{s.nombre}_pu{lado}", 1.0, s.mat_negro, c)
            ceja = obj(f"{s.nombre}_ce{lado}", m_capsula(0.08, 0.013), s.mat_negro, c)
            s.ojos.append((sg, blanco, pup, ceja))
        s.boca = [esf(f"{s.nombre}_bo{i}", 0.0135, s.mat_lab, c) for i in range(17)]
        s.boca_ab = esf(s.nombre + "_boab", 1.0, s.mat_lab, c)

    def _sobre_cabeza(s, yaw, pit, extra=0.0):
        """Punto sobre el cráneo (coordenadas de la cabeza: adelante=+Y) y su normal."""
        n = Vector((math.sin(yaw) * math.cos(pit), math.cos(yaw) * math.cos(pit), math.sin(pit)))
        return n * (R_CAB + extra), n

    def cara(s, expr="neutra", mirada=(0.0, 0.0), parpadeo=0.0, boca_k=None):
        e = CARAS[expr]
        for sg, blanco, pup, ceja in s.ojos:
            p, n = s._sobre_cabeza(sg * 0.40, 0.10, -0.012)
            blanco.location = p
            blanco.rotation_mode = 'QUATERNION'; blanco.rotation_quaternion = rot_z_a(n)
            blanco.scale = (0.060, 0.078 * (1 - 0.92 * parpadeo), 0.030)
            mx, mz = mirada                       # mirada en -1..1 (derecha/arriba)
            pp, pn = s._sobre_cabeza(sg * 0.40 + mx * 0.07, 0.10 + mz * 0.08, 0.016)
            pup.location = pp
            pup.rotation_mode = 'QUATERNION'; pup.rotation_quaternion = rot_z_a(pn)
            pup.scale = (0.034, 0.044 * (1 - 0.9 * parpadeo), 0.020)
            # ceja: cápsula de afuera hacia adentro; inclinación > 0 = el lado de adentro más alto (triste / culpa)
            cp, _ = s._sobre_cabeza(sg * 0.40, 0.10 + 0.27 + 0.10 * e["ce"][0], 0.0)
            inc = e["ce"][1] * 0.55
            din = Vector((-sg * math.cos(inc), 0.0, math.sin(inc)))
            pa = (cp - din * 0.04).normalized() * (R_CAB + 0.008)
            pb = (cp + din * 0.04).normalized() * (R_CAB + 0.008)
            colocar_cap(ceja, pa, pb)
        # boca: parábola de esferitas
        k = e["k"] if boca_k is None else boca_k
        w = 0.105
        for i, b in enumerate(s.boca):
            u = (i / (len(s.boca) - 1)) * 2 - 1
            ang = u * 0.44
            z0 = -0.40 + 0.17 * k * (u * u - 0.4) * 0.5
            p, _ = s._sobre_cabeza(ang, z0 - 0.0, 0.002)
            b.location = p
            b.scale = (0.0145,) * 3
            b.hide_render = False
        ab = e["ab"]
        if ab > 0.01:
            p, n = s._sobre_cabeza(0.0, -0.42, -0.004)
            s.boca_ab.location = p
            s.boca_ab.rotation_mode = 'QUATERNION'; s.boca_ab.rotation_quaternion = rot_z_a(n)
            s.boca_ab.scale = (0.06 * (0.8 + 0.4 * ab), 0.045 * ab + 0.01, 0.02)
            s.boca_ab.hide_render = False
        else:
            s.boca_ab.hide_render = True
        # con la boca abierta, la línea sobra
        if ab > 0.5:
            for b in s.boca:
                b.hide_render = True

    # ---- calzado ----
    def _calzado(s, tipo, color_zapa="#E8332B"):
        s.tipo_calzado = tipo
        s.color_zapa = color_zapa
        for lado in "di":
            pie = s.pierna[lado]["pie"]
            for h in list(pie.children_recursive):
                bpy.data.objects.remove(h)
        for lado in "di":
            pie = s.pierna[lado]["pie"]
            if tipo == "plano":                 # pie redondeado y chato, del mismo material
                esf(f"{s.nombre}_pz{lado}", 1.0, s.mat, pie, (0, 0.05, -0.034), esc=(0.058, 0.135, 0.050))
            else:
                construir_zapatilla(f"{s.nombre}_zp{lado}", pie, color_zapa)

    def _accesorios(s):
        r = s.rasgos
        c = s.cabeza
        hc = material("pelo_" + s.nombre, r.get("pelo", "#2B2118"), rough=0.9)
        if r.get("pelo") and r.get("peinado", "corto") != "ninguno":
            if r["peinado"] == "largo":
                esf(s.nombre + "_pelo", R_CAB * 1.045, hc, c, (0, -0.062, 0.05), esc=(1.0, 0.98, 0.93))
                esf(s.nombre + "_melena", R_CAB * 0.86, hc, c, (0, -0.145, -0.07), esc=(1.0, 0.55, 1.15))
            elif r["peinado"] == "rodete":
                esf(s.nombre + "_pelo", R_CAB * 1.04, hc, c, (0, -0.058, 0.06), esc=(1.0, 0.98, 0.9))
                esf(s.nombre + "_rodete", 0.105, hc, c, (0, -0.10, R_CAB * 0.93))
            else:
                esf(s.nombre + "_pelo", R_CAB * 1.04, hc, c, (0, -0.06, 0.055), esc=(1.0, 0.98, 0.88))
        if r.get("gorra"):
            mg = material("gorra_" + s.nombre, r["gorra"], rough=0.85)
            esf(s.nombre + "_gorra", R_CAB * 1.06, mg, c, (0, -0.02, 0.085), esc=(1.0, 1.0, 0.72))
            obj(s.nombre + "_visera", m_cil(0.15, 0.022, 28, bisel=0.008), mg, c, (0, 0.215, 0.115), (math.radians(-12), 0, 0), esc=(1.0, 1.15, 1.0))
        if r.get("gorro"):
            mg = material("gorro_" + s.nombre, r["gorro"], rough=0.9)
            mb = material("gorro_b_" + s.nombre, "#FFFFFF", rough=0.9)
            esf(s.nombre + "_gorro", R_CAB * 1.07, mg, c, (0, -0.02, 0.07), esc=(1.0, 1.0, 0.85))
            obj(s.nombre + "_gorro_b", m_toro(R_CAB * 0.97, 0.034), mg, c, (0, -0.005, 0.105), esc=(1.0, 1.0, 1.0))
            esf(s.nombre + "_pompon", 0.062, mb, c, (0, -0.02, R_CAB * 1.17))
        if r.get("lentes"):
            ml = material("lentes", "#1B1B22", rough=0.4)
            for sg in (1, -1):
                p, n = s._sobre_cabeza(sg * 0.40, 0.10, 0.012)
                o = obj(f"{s.nombre}_len{sg}", m_toro(0.068, 0.0095), ml, c, p)
                o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = rot_z_a(n)
            cap(s.nombre + "_puente", (-0.03, 0.238, 0.04), (0.03, 0.238, 0.04), 0.009, ml, c)
        if r.get("vincha"):
            mv = material("vincha_" + s.nombre, r["vincha"], rough=0.7)
            obj(s.nombre + "_vincha", m_toro(R_CAB * 1.01, 0.02), mv, c, (0, -0.02, 0.09), (math.radians(-18), 0, 0))
        if r.get("delantal"):
            md = material("delantal", r["delantal"], rough=0.85)
            s.delantal = obj(s.nombre + "_delantal", m_caja(0.27, 0.07, 0.40, 0.03), md)
        else:
            s.delantal = None
        if r.get("bigote"):
            mb = material("bigote", "#2B2118", rough=0.9)
            for sg in (1, -1):
                p, n = s._sobre_cabeza(sg * 0.12, -0.26, 0.012)
                o = obj(f"{s.nombre}_big{sg}", m_capsula(0.06, 0.016), mb, c, p)
                o.rotation_mode = 'QUATERNION'
                o.rotation_quaternion = rot_z_a(Vector((sg * 1.0, 0.0, -0.25)))
        if r.get("mochila"):
            mm = material("mochila", r["mochila"], rough=0.85)
            s.mochila = obj(s.nombre + "_mochila", m_caja(0.28, 0.12, 0.34, 0.05), mm)
        else:
            s.mochila = None

    # ---- pose ----
    def poner(s, pos=(0, 0, 0), yaw=0.0, pelvis=(0, 0, 1.05), pelvis_rot=(0, 0, 0), torso_rot=(0, 0, 0),
              cabeza_rot=(0, 0, 0), expr="neutra", mirada=(0, 0), parpadeo=0.0, boca_k=None,
              md=None, mi=None, pd=None, pi=None):
        """Todo en coordenadas del personaje (x derecha, y adelante, z arriba, origen en el piso bajo la pelvis).
        pelvis_rot/torso_rot = (cabeceo x, balanceo y, giro z) en rad.  md/mi = dict(p=muñeca, dedos=dir, palma=dir,
        curl=(4), pulgar=punto en la mano, polo=dir del codo).  pd/pi = dict(p=tobillo, pitch, yaw, roll, polo)."""
        from mathutils import Euler
        M = Matrix.Translation(Vector(pos)) @ Matrix.Rotation(yaw, 4, 'Z')
        s.M = M
        W = lambda v: M @ Vector(v)
        fx = lambda r: (-r[0], r[1], r[2])          # cabeceo positivo = inclinarse hacia adelante
        Rp = Euler(fx(pelvis_rot), 'XYZ').to_matrix()
        Rtr = Rp @ Euler(fx(torso_rot), 'XYZ').to_matrix()
        P = Vector(pelvis)
        cuello = P + Rtr @ Vector((0, 0, L_TORSO))
        # torso y pelvis
        colocar_cap(s.torso, W(P), W(cuello))
        s.pelvis.matrix_world = M @ Matrix.Translation(P) @ Rp.to_4x4() @ Matrix.Diagonal((R_TORSO * 1.0, R_TORSO * 0.95, R_TORSO * 0.9, 1))
        # cabeza
        Rh = Rtr @ Euler(fx(cabeza_rot), 'XYZ').to_matrix()
        s.cabeza.matrix_world = M @ Matrix.Translation(cuello + Rh @ Vector((0, 0, R_CAB * 0.97))) @ Rh.to_4x4()
        # accesorios del cuerpo
        if s.delantal:
            s.delantal.matrix_world = M @ Matrix.Translation(P + Rtr @ Vector((0, R_TORSO - 0.01, 0.27))) @ Rtr.to_4x4()
        if s.mochila:
            s.mochila.matrix_world = M @ Matrix.Translation(P + Rtr @ Vector((0, -R_TORSO - 0.05, 0.30))) @ Rtr.to_4x4()
        # brazos
        defecto_man = dict(curl=(0.2, 0.2, 0.2, 0.2))
        for lado, sg, d in (("d", 1, md), ("i", -1, mi)):
            sh = P + Rtr @ Vector((sg * SHX, 0, L_TORSO - 0.06))
            if d is None:
                d = dict(p=(sg * 0.30, 0.04, 0.80))
            d = {**defecto_man, **d}
            Mi = M.inverted()
            if "w" in d:
                d["p"] = Mi @ Vector(d["w"])
            if "dedos_w" in d:
                d["dedos"] = Mi.to_3x3() @ Vector(d["dedos_w"])
            if "palma_w" in d:
                d["palma"] = Mi.to_3x3() @ Vector(d["palma_w"])
            if "pulgar_w" in d:
                d["pulgar"] = None   # se resuelve abajo en la mano
            polo = Vector(d.get("polo", (sg * 0.55, -1.0, -0.35)))
            muneca = Vector(d["p"])
            codo, fin = ik2(sh, muneca, L_BRAZO, L_ANTEB, polo)
            br = s.brazo[lado]
            colocar_cap(br["a"], W(sh), W(codo))
            colocar_cap(br["b"], W(codo), W(fin))
            dedos = Vector(d.get("dedos", (fin - codo).normalized()))
            palma = Vector(d.get("palma", (-sg, 0.25, 0)))
            Rm = mat_rot(dedos, palma)
            br["mano"].raiz.matrix_world = M @ Matrix.Translation(fin) @ Rm.to_4x4()
            br["mano"].poner(d["curl"], d.get("pulgar"), d.get("sep", 0.0))
        # piernas
        for lado, sg, d in (("d", 1, pd), ("i", -1, pi)):
            cad = P + Rp @ Vector((sg * 0.07, 0, -0.03))
            if d is None:
                d = dict(p=(sg * 0.09, 0.0, ALTURA_TOBILLO))
            tob = Vector(d["p"])
            rod, fin = ik2(cad, tob, L_MUSLO, L_PANT, Vector(d.get("polo", (sg * 0.12, 1.0, 0.0))))
            pr = s.pierna[lado]
            colocar_cap(pr["a"], W(cad), W(rod))
            colocar_cap(pr["b"], W(rod), W(fin))
            Rf = (Matrix.Rotation(d.get("yaw", 0.0), 3, 'Z') @ Matrix.Rotation(d.get("pitch", 0.0), 3, 'X')
                  @ Matrix.Rotation(d.get("roll", 0.0), 3, 'Y'))
            pr["pie"].matrix_world = M @ Matrix.Translation(fin) @ Rf.to_4x4()

    def calzado(s, tipo, color="#E8332B"):
        if getattr(s, "tipo_calzado", None) == tipo and getattr(s, "color_zapa", None) == color:
            return
        s.color_zapa = color
        s._calzado(tipo, color)

    def ocultar(s, v=True):
        for o in bpy.data.objects:
            if o.name.startswith(s.nombre + "_"):
                o.hide_render = v
        s.cabeza.hide_render = v


def construir_zapatilla(nombre, padre, color="#E8332B", escala=1.0, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Zapatilla reconocible, en el marco del pie (tobillo en el origen, punta hacia +Y, suela en z=-0.09)."""
    r = vacio(nombre, padre, loc, rot)
    mc = material("zapa_" + color, color, rough=0.6, spec=0.3)
    mb = material("zapa_blanco", "#F5F5F2", rough=0.55, spec=0.25)
    mo = material("zapa_cordon", "#FFFFFF", rough=0.5)
    s = escala
    sz = lambda v: tuple(x * s for x in v)
    obj(nombre + "_cuerpo", m_esfera(), mc, r, sz((0, 0.055, -0.012)), esc=sz((0.078, 0.17, 0.066)))
    obj(nombre + "_suela", m_caja(0.15 * s, 0.31 * s, 0.03 * s, 0.014 * s), mb, r, sz((0, 0.05, -0.075)))
    esf(nombre + "_puntera", 1.0, mb, r, sz((0, 0.175, -0.036)), esc=sz((0.074, 0.085, 0.052)))
    obj(nombre + "_cuello", m_cil(0.052 * s, 0.075 * s, 20, bisel=0.01 * s), mc, r, sz((0, -0.045, 0.012)), esc=(1.15, 1.0, 1.0))
    esf(nombre + "_lengua", 1.0, mb, r, sz((0, 0.075, 0.046)), esc=sz((0.04, 0.05, 0.016)), rot=(0.35, 0, 0))
    for i in range(3):
        cap(f"{nombre}_cord{i}", sz((-0.05, 0.035 + i * 0.04, 0.052 - i * 0.003)), sz((0.05, 0.035 + i * 0.04, 0.052 - i * 0.003)), 0.0075 * s, mo, r)
    cap(nombre + "_raya", sz((0.081, -0.02, -0.01)), sz((0.081, 0.10, 0.012)), 0.014 * s, mb, r)
    cap(nombre + "_rayai", sz((-0.081, -0.02, -0.01)), sz((-0.081, 0.10, 0.012)), 0.014 * s, mb, r)
    return r
