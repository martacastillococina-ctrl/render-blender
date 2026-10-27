"""
Dos Mentes 05 — objetos del video, todos en código (sin imágenes ni modelos descargados).
Cada función devuelve un vacío raíz con todo adentro; se mueve/rota/escala desde afuera.
Unidades: el muñeco mide ~2,0; una mano ~0,25; un billete 0,36 x 0,17 (exagerado para que se lea).
"""
import bpy, bmesh, math
from mathutils import Vector
from motor import *

REG = {}      # sub-objetos con nombre (hoja de la puerta, tapas): REG['nombre.hoja']

C = dict(  # paleta plana
    madera="#6E5A48", madera_osc="#3E3A3A", madera_clara="#8C8F99", metal="#8E99A3", gris="#3A3F4A", gris_cl="#B9BFC7",
    verde_b="#2FAE4C", verde_cl="#8FE08F", crema="#9AA3B4", rojo="#E8332B", blanco="#F7F5F0", negro="#1C1F26",
    pan="#E3A857", pan_osc="#C27E34", jamon="#F29AA3", queso="#FFD24A", salame="#A63A30", lechuga="#79CC4A",
    tomate="#E8453C", kraft="#D9A35F", pared="#2E3646", piso="#1B212B", vereda="#2A303B", calle="#12151C",
)


def M(nombre, color, **kw):
    return material(nombre, color, **kw)


# ----------------------------------------------------------------------------- plata
def billete(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), detalle=True):
    r = vacio(nombre, padre, loc, rot)
    caja(nombre + "_b", (0.36, 0.17, 0.006), M("bill_base", C["verde_b"], emis=0.35), r, bisel=0.003)
    if detalle:
        caja(nombre + "_i", (0.32, 0.13, 0.0075), M("bill_in", C["verde_cl"]), r, bisel=0.003)
        esf(nombre + "_o", 1.0, M("bill_ov", "#E6F3D6"), r, (0, 0, 0.002), esc=(0.062, 0.05, 0.0045))
        t = texto(nombre + "_s", "$", 0.062, M("bill_tx", C["verde_b"]), r, (0, 0, 0.0085))
        for sx in (-1, 1):
            esf(f"{nombre}_c{sx}", 1.0, M("bill_ov", "#E6F3D6"), r, (sx * 0.125, 0, 0.0045), esc=(0.02, 0.02, 0.003))
    return r


def fajo(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), n=7):
    """Fajo de billetes con banda de papel. Largo en X."""
    r = vacio(nombre, padre, loc, rot)
    for i in range(n - 1):
        caja(f"{nombre}_h{i}", (0.355 - 0.002 * (i % 2), 0.168, 0.0075), M("bill_base", C["verde_b"], emis=0.35), r,
             loc=(0.002 * ((i * 3) % 3 - 1), 0.002 * ((i * 5) % 3 - 1), i * 0.0072), bisel=0.003)
    billete(nombre + "_top", r, (0, 0, (n - 1) * 0.0072 + 0.003))
    caja(nombre + "_banda", (0.07, 0.185, (n + 1) * 0.0075), M("banda", "#EFE0A6", rough=0.9), r, loc=(0, 0, (n - 1) * 0.0036 + 0.002), bisel=0.004)
    return r


def abanico(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), n=4, abre=0.30):
    """Billetes en abanico, articulados en un extremo (el pivote está en el origen; se abren hacia +X)."""
    r = vacio(nombre, padre, loc, rot)
    for i in range(n):
        a = (i - (n - 1) / 2) * abre
        piv = vacio(f"{nombre}_p{i}", r, (0, 0, i * 0.009), (0, 0, a))
        billete(f"{nombre}_{i}", piv, (0.15, 0, 0))
    return r


# ----------------------------------------------------------------------------- calzado
def zapatilla(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), color="#E8332B", escala=1.0):
    """Zapatilla suelta apoyada en el piso (punta hacia +Y)."""
    r = vacio(nombre, padre, loc, rot)
    construir_zapatilla(nombre + "_z", r, color, escala, loc=(0, 0, 0.09 * escala))
    return r


def caja_zapatillas(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), abierta=False, con_par=True):
    """Caja de zapatillas 0,56 x 0,32 x 0,2. Devuelve la raíz; `r.tapa` es el vacío de la tapa (bisagra atrás)."""
    r = vacio(nombre, padre, loc, rot)
    mc = M("caja_zap", "#4A5568", rough=0.8)
    mb = M("caja_zap_b", C["blanco"], rough=0.8)
    caja(nombre + "_base", (0.56, 0.32, 0.16), mc, r, loc=(0, 0, 0.08), bisel=0.01)
    tapa = vacio(nombre + "_tapa", r, (0, 0.16, 0.16), (math.radians(-110) if abierta else 0, 0, 0))
    REG[nombre + ".tapa"] = tapa
    caja(nombre + "_tp", (0.58, 0.34, 0.05), mc, tapa, loc=(0, -0.16, 0.025), bisel=0.01)
    caja(nombre + "_tp2", (0.20, 0.34 * 0.5, 0.052), mb, tapa, loc=(0, -0.16, 0.026), bisel=0.004)
    if abierta and con_par:
        caja(nombre + "_papel", (0.5, 0.26, 0.012), M("papel", "#FFFFFF", rough=0.9), r, loc=(0, 0, 0.15), bisel=0.005)
        zapatilla(nombre + "_zi", r, (-0.12, 0, 0.14), (0, 0, math.radians(90)), escala=0.7)
        zapatilla(nombre + "_zd", r, (0.12, 0, 0.14), (0, 0, math.radians(90)), escala=0.7)
    return r


def bolsa(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Bolsa de compras de papel kraft con manijas y etiqueta (se ve de lejos). Asa arriba en z≈0,5."""
    r = vacio(nombre, padre, loc, rot)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        top = v.co.z > 0
        v.co.x *= 0.40 if top else 0.34
        v.co.y *= 0.17 if top else 0.14
        v.co.z = 0.44 * v.co.z
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.012, segments=2, profile=0.7, affect='EDGES')
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    obj(nombre + "_cuerpo", me, M("kraft", C["kraft"], rough=0.9), r, loc=(0, 0, 0.22))
    for sx in (-0.09, 0.09):
        toro(f"{nombre}_asa{sx}", 0.075, 0.009, M("asa", "#6B4A2A", rough=0.9), r, (sx, 0, 0.47), (math.radians(90), 0, 0), esc=(1.0, 1.0, 1.0))
    # etiqueta rojo + zapatilla blanca esquemática
    caja(nombre + "_et", (0.24, 0.006, 0.16), M("etiq", C["rojo"], rough=0.7), r, loc=(0, -0.1, 0.24), bisel=0.01)
    esf(nombre + "_et2", 1.0, M("etiq_b", C["blanco"]), r, (0, -0.106, 0.245), esc=(0.075, 0.004, 0.035))
    return r


# ----------------------------------------------------------------------------- tienda
def puerta_tienda(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), angulo=0.0, ancho=1.1, alto=2.3):
    """Marco + hoja con bisagra a la izquierda. `r.hoja.rotation_euler.z` = ángulo (+ abre hacia la cámara, -Y)."""
    r = vacio(nombre, padre, loc, rot)
    mm = M("marco_puerta", "#2A3242", rough=0.7)
    for sx in (-1, 1):
        caja(f"{nombre}_j{sx}", (0.10, 0.22, alto + 0.1), mm, r, loc=(sx * (ancho / 2 + 0.05), 0, (alto + 0.1) / 2), bisel=0.01)
    caja(nombre + "_dintel", (ancho + 0.2, 0.22, 0.12), mm, r, loc=(0, 0, alto + 0.04), bisel=0.01)
    h = vacio(nombre + "_hoja", r, (-ancho / 2, 0, 0), (0, 0, angulo))
    REG[nombre + ".hoja"] = h
    for sx in (0.04, ancho - 0.04):
        caja(f"{nombre}_hv{sx}", (0.08, 0.06, alto - 0.04), mm, h, loc=(sx, 0, alto / 2 - 0.02), bisel=0.01)
    for z in (0.04, alto - 0.08):
        caja(f"{nombre}_hh{z}", (ancho, 0.06, 0.08), mm, h, loc=(ancho / 2, 0, z + 0.04 if z < 1 else z), bisel=0.01)
    caja(nombre + "_vidrio", (ancho - 0.12, 0.012, alto - 0.28), M("vidrio", "#BFE4F5", rough=0.05, alpha=0.28, spec=0.8), h, loc=(ancho / 2, 0, alto / 2 + 0.02), bisel=0)
    cap(nombre + "_manija", (ancho - 0.14, -0.07, 1.0), (ancho - 0.14, -0.07, 1.30), 0.022, M("manija", C["metal"], rough=0.3, metal=0.8), h)
    caja(nombre + "_cartel", (0.34, 0.012, 0.16), M("cartel_ab", C["blanco"]), h, loc=(ancho / 2, -0.04, 1.62), bisel=0.01)
    texto(nombre + "_cartel_t", "ABIERTO", 0.058, M("cartel_t", "#1A2030"), h, (ancho / 2, -0.05, 1.62), (math.radians(90), 0, 0))
    return r


def estante_zapatillas(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), ancho=2.6, alto=2.2):
    """Estante de pared con 3 repisas y zapatillas de colores con etiqueta de precio (sin números). Mira hacia -Y."""
    r = vacio(nombre, padre, loc, rot)
    mw = M("estante", C["madera"], rough=0.75)
    mo = M("estante_o", C["madera_osc"], rough=0.8)
    caja(nombre + "_fondo", (ancho, 0.04, alto), mo, r, loc=(0, 0.2, alto / 2), bisel=0.01)
    for sx in (-1, 1):
        caja(f"{nombre}_l{sx}", (0.06, 0.40, alto), mw, r, loc=(sx * (ancho / 2 - 0.03), 0, alto / 2), bisel=0.01)
    cols = ["#E6E8EE", "#FFFFFF", "#9AA3B4", "#CBD1DC", "#7A8396", "#F2F4F8", "#5C6578", "#D6DAE3", "#3A4152"]
    for k, z in enumerate((0.05, 0.78, 1.51)):
        caja(f"{nombre}_r{k}", (ancho, 0.40, 0.05), mw, r, loc=(0, 0, z + 0.025), bisel=0.01)
        for j in range(3):
            x = (j - 1) * 0.84
            zapatilla(f"{nombre}_z{k}{j}", r, (x, -0.02, z + 0.05), (0, 0, math.radians(180 - 28 + 14 * j)), color=cols[(k * 3 + j) % 9], escala=1.05)
            caja(f"{nombre}_p{k}{j}", (0.20, 0.008, 0.09), M("etiq_p", "#FFFFFF"), r, loc=(x, -0.185, z + 0.105), rot=(math.radians(-10), 0, 0), bisel=0.004)
            esf(f"{nombre}_pp{k}{j}", 1.0, M("etiq_r", "#8791A6"), r, (x, -0.192, z + 0.11), esc=(0.045, 0.003, 0.016))
    return r


def mostrador(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), ancho=2.0, con_caja=True):
    """Mostrador (0,95 de alto) con caja registradora: cuerpo, teclas, pantalla con texto y cajón. Frente hacia -Y."""
    r = vacio(nombre, padre, loc, rot)
    caja(nombre + "_cuerpo", (ancho, 0.7, 0.92), M("mostr", "#2E3648", rough=0.7), r, loc=(0, 0, 0.46), bisel=0.02)
    caja(nombre + "_tapa", (ancho + 0.08, 0.78, 0.06), M("mostr_t", "#4A5468", rough=0.5), r, loc=(0, 0, 0.95), bisel=0.015)
    caja(nombre + "_zocalo", (ancho - 0.2, 0.02, 0.5), M("mostr_f", C["madera_osc"], rough=0.8), r, loc=(0, -0.355, 0.5), bisel=0.01)
    if con_caja:
        z0 = 0.98
        cx = ancho * 0.18
        mk = M("reg", "#4A5361", rough=0.5, spec=0.35)
        caja(nombre + "_reg", (0.52, 0.42, 0.16), mk, r, loc=(cx, 0.0, z0 + 0.08), bisel=0.03)
        caja(nombre + "_tec", (0.52, 0.30, 0.05), mk, r, loc=(cx, -0.11, z0 + 0.19), rot=(math.radians(-22), 0, 0), bisel=0.02)
        for i in range(4):
            for j in range(3):
                caja(f"{nombre}_k{i}{j}", (0.06, 0.05, 0.02), M("tecla", "#DADFE6" if (i + j) % 4 else "#E8A33B", rough=0.5), r,
                     loc=(cx - 0.18 + i * 0.12, -0.17 + j * 0.065 + 0.04, z0 + 0.195 + j * 0.026), rot=(math.radians(-22), 0, 0), bisel=0.006)
        caja(nombre + "_pie", (0.08, 0.06, 0.2), mk, r, loc=(cx, 0.10, z0 + 0.25), bisel=0.01)
        caja(nombre + "_pant", (0.40, 0.04, 0.22), M("pant_marco", "#232933"), r, loc=(cx, 0.10, z0 + 0.42), rot=(math.radians(-10), 0, 0), bisel=0.015)
        caja(nombre + "_vis", (0.36, 0.01, 0.17), M("pant_verde", "#8EF0A8", emis=1.4), r, loc=(cx, 0.078, z0 + 0.42), rot=(math.radians(-10), 0, 0), bisel=0.004)
        texto(nombre + "_pt", "$ 25.000", 0.06, M("pant_tx", "#0E3B22"), r, (cx, 0.066, z0 + 0.42), (math.radians(80), 0, 0))
        caja(nombre + "_cajon", (0.46, 0.28, 0.07), M("cajon", "#3B4350"), r, loc=(cx, -0.38, z0 + 0.02), bisel=0.01)
        caja(nombre + "_cajon_b", (0.40, 0.2, 0.03), M("cajon_b", "#2A2F38"), r, loc=(cx, -0.38, z0 + 0.04), bisel=0.01)
        caja(nombre + "_ticket", (0.07, 0.003, 0.2), M("ticket", "#FFFFFF"), r, loc=(cx + 0.30, 0.0, z0 + 0.26), rot=(0, 0, math.radians(8)), bisel=0.001)
    return r


# ----------------------------------------------------------------------------- celular con chat
PANTALLAS = [   # (texto por renglones, lado, estilo)
    [("¿Y la plata?", "d")],
    [("¿Y la plata?", "d"), ("Visto", "v")],
    [("¿Hola?", "d"), ("Visto", "v")],
    [("tengo que\npagar unas\ncuentas", "d")],
]


class Celular:
    """Celular 0,15 x 0,30. Marco local: X ancho, Y largo (arriba de la pantalla), Z normal de la pantalla (+Z).
    Letra enorme y de 1 a 2 mensajes por pantalla (el chat del amigo)."""
    W, H = 0.15, 0.30

    def __init__(s, nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0)):
        s.raiz = vacio(nombre, padre, loc, rot)
        r = s.raiz
        caja(nombre + "_cuerpo", (s.W, s.H, 0.014), M("cel", "#1B1E25", rough=0.35, spec=0.5), r, bisel=0.016)
        caja(nombre + "_pant", (s.W - 0.014, s.H - 0.022, 0.003), M("cel_pant", "#F4F6FA", emis=0.9), r, loc=(0, 0, 0.0075), bisel=0.002)
        caja(nombre + "_bar", (s.W - 0.014, 0.034, 0.0035), M("cel_bar", "#E4E8F0", emis=0.8), r, loc=(0, s.H / 2 - 0.035, 0.0078), bisel=0.002)
        esf(nombre + "_av", 1.0, M("cel_av", "#7BD04C", emis=0.6), r, (-0.045, s.H / 2 - 0.035, 0.0095), esc=(0.013, 0.013, 0.002))
        texto(nombre + "_nom", "Mi amigo", 0.017, M("cel_t0", "#2B2F38", emis=1.0), r, (0.012, s.H / 2 - 0.035, 0.0098), centrado=False)
        s.grupos = []
        mazul = M("burb_az", "#CDD2DA", emis=0.55)
        mtx = M("burb_tx", "#14171F", emis=0.0, rough=0.6)
        mv = M("burb_v", "#5B6272", emis=0.3)
        for i, msgs in enumerate(PANTALLAS):
            g = []
            y = 0.085
            for txt, lado in msgs:
                if lado == "v":
                    t = texto(f"{nombre}_v{i}", "Visto", 0.019, mv, r, (s.W / 2 - 0.016, y + 0.012, 0.0098), centrado=False)
                    t.data.align_x = 'RIGHT'
                    g.append(t)
                    y -= 0.04
                    continue
                lineas = txt.split("\n")
                tam = 0.030 if len(lineas) == 1 else 0.024
                tam = min(tam, 0.118 / (max(len(l) for l in lineas) * 0.56)) if len(lineas) == 1 else tam
                alto = tam * 1.25 * len(lineas) + 0.03
                ancho = min(s.W - 0.03, max(len(l) for l in lineas) * tam * 0.56 + 0.04)
                bub = caja(f"{nombre}_bub{i}", (ancho, alto, 0.004), mazul, r,
                           loc=(s.W / 2 - 0.012 - ancho / 2, y - alto / 2 + 0.01, 0.0095), bisel=0.01)
                g.append(bub)
                for k, l in enumerate(lineas):
                    t = texto(f"{nombre}_t{i}{k}", l, tam, mtx, r,
                              (s.W / 2 - 0.012 - ancho / 2, y - 0.015 - tam * 0.62 - k * tam * 1.25 + 0.01, 0.0105))
                    g.append(t)
                y -= alto + 0.025
            s.grupos.append(g)
        s.mostrar(0)

    def mostrar(s, i):
        for k, g in enumerate(s.grupos):
            for o in g:
                o.hide_render = (k != i)


# ----------------------------------------------------------------------------- comida
def pan_frances(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), largo=0.5, r=0.075):
    """Pan francés con cortes, largo en X."""
    R = vacio(nombre, padre, loc, rot)
    mp = M("pan", C["pan"], rough=0.9)
    o = obj(nombre + "_c", m_capsula(largo, r), mp, R, loc=(-largo / 2, 0, 0), rot=(0, math.radians(90), 0), esc=(0.78, 1.0, 1.0))
    for i in range(4):
        x = -largo / 2 + 0.08 + i * (largo - 0.16) / 3
        esf(f"{nombre}_cor{i}", 1.0, M("pan_osc", C["pan_osc"], rough=0.9), R, (x, 0, r * 0.7), esc=(0.045, 0.012, 0.006), rot=(0, 0, math.radians(35)))
    return R


def lechuga(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), ancho=0.34, fondo=0.20):
    """Hoja de lechuga ondulada (malla propia) con nervadura."""
    R = vacio(nombre, padre, loc, rot)
    bm = bmesh.new()
    nx, ny = 22, 10
    vs = []
    for i in range(nx + 1):
        row = []
        for j in range(ny + 1):
            u = i / nx * 2 - 1
            v = j / ny * 2 - 1
            x = u * ancho / 2
            y = v * fondo / 2 * math.sqrt(max(0.0, 1 - 0.8 * u * u))
            z = 0.012 * math.sin(7 * u * math.pi + 2 * v) * (0.5 + abs(v)) + 0.02 * u * u
            row.append(bm.verts.new((x, y, z)))
        vs.append(row)
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.005)
    me = bpy.data.meshes.new(nombre)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    obj(nombre + "_h", me, M("lechuga", C["lechuga"], rough=0.6), R)
    return R


def feta(nombre, color, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), tam=0.16):
    """Feta redonda de fiambre (jamón) algo plegada."""
    R = vacio(nombre, padre, loc, rot)
    m = M("feta_" + color, color, rough=0.5, spec=0.3)
    esf(nombre + "_a", 1.0, m, R, (0, 0, 0), esc=(tam, tam * 0.8, 0.008))
    esf(nombre + "_b", 1.0, m, R, (tam * 0.25, 0, 0.012), esc=(tam * 0.55, tam * 0.7, 0.010), rot=(0, 0, 0.5))
    return R


def queso(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), tam=0.17):
    R = vacio(nombre, padre, loc, rot)
    caja(nombre + "_q", (tam, tam, 0.011), M("queso", C["queso"], rough=0.45, spec=0.3), R, rot=(0, 0, math.radians(0)), bisel=0.004)
    for x, y in ((-0.03, 0.02), (0.035, -0.03)):
        esf(f"{nombre}_ojo{x}", 1.0, M("queso_o", "#E2A826", rough=0.5), R, (x, y, 0.006), esc=(0.016, 0.016, 0.003))
    return R


def tomate_rodaja(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), r=0.058):
    R = vacio(nombre, padre, loc, rot)
    cil(nombre + "_t", r, 0.016, M("tomate", C["tomate"], rough=0.35, spec=0.4), R, bisel=0.004)
    for a in range(3):
        esf(f"{nombre}_s{a}", 1.0, M("tomate_s", "#F7C7A0"), R, (math.cos(a * 2.1) * r * 0.45, math.sin(a * 2.1) * r * 0.45, 0.008), esc=(0.012, 0.012, 0.004))
    return R


def salame(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), largo=0.4, r=0.055):
    R = vacio(nombre, padre, loc, rot)
    obj(nombre + "_c", m_capsula(largo, r), M("salame", C["salame"], rough=0.6), R, loc=(-largo / 2, 0, 0), rot=(0, math.radians(90), 0))
    for i in range(10):
        a = i * 2.4
        esf(f"{nombre}_p{i}", 1.0, M("grasa", "#F2E2D2", rough=0.7), R, (-largo / 2 + 0.03 + i * (largo - 0.06) / 9, math.sin(a) * r * 0.8, math.cos(a) * r * 0.8), esc=(0.012, 0.012, 0.012))
    cap(nombre + "_soga", (-largo / 2 - 0.03, 0, 0.0), (-largo / 2 - 0.03, 0, 0.16), 0.006, M("soga", "#6B4A2A"), R)
    return R


def sanguche(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), largo=0.62):
    """Sánguche grande de pan francés: pan arriba y abajo, lechuga, jamón, queso y tomate que asoman por el costado.
    Largo en X, frente (lo que se ve) hacia -Y."""
    R = vacio(nombre, padre, loc, rot)
    mp = M("pan", C["pan"], rough=0.9)
    r0 = 0.085
    L = largo - 2 * r0
    obj(nombre + "_pb", m_capsula(L, r0), mp, R, loc=(-L / 2, 0, 0.045), rot=(0, math.radians(90), 0), esc=(0.52, 1.0, 1.0))
    obj(nombre + "_pt", m_capsula(L, r0), mp, R, loc=(-L / 2, 0, 0.185), rot=(0, math.radians(90), 0), esc=(0.62, 1.0, 1.0))
    for i in range(4):
        esf(f"{nombre}_cor{i}", 1.0, M("pan_osc", C["pan_osc"], rough=0.9), R, (-L / 2 + 0.07 + i * (L - 0.14) / 3, 0.0, 0.25), esc=(0.04, 0.012, 0.007), rot=(0, 0, math.radians(35)))
    # relleno: capas visibles de frente
    lechuga(nombre + "_l1", R, (0.0, -0.045, 0.098), (math.radians(8), 0, 0), ancho=largo * 0.85, fondo=0.20)
    feta(nombre + "_j1", C["jamon"], R, (-0.12, -0.05, 0.118), (math.radians(14), 0, 0.2), tam=0.13)
    feta(nombre + "_j2", C["jamon"], R, (0.10, -0.052, 0.122), (math.radians(14), 0, -0.1), tam=0.13)
    queso(nombre + "_q", R, (0.0, -0.045, 0.142), (math.radians(10), 0, math.radians(45)), tam=0.15)
    for i, x in enumerate((-0.17, 0.0, 0.17)):
        tomate_rodaja(f"{nombre}_t{i}", R, (x, -0.04, 0.153), (math.radians(80), 0, 0), r=0.052)
    return R


# ----------------------------------------------------------------------------- puesto y caja de plata
def caja_plata(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), llena=0.0, tapa=1.0):
    """Caja de plata de chapa (0,5 x 0,34 x 0,16) con billetes y monedas; `llena` 0..1 sube el montón; `tapa` 1 = abierta."""
    R = vacio(nombre, padre, loc, rot)
    mm = M("lata", "#7A8791", rough=0.4, metal=0.6)
    caja(nombre + "_base", (0.5, 0.34, 0.14), mm, R, loc=(0, 0, 0.07), bisel=0.012)
    caja(nombre + "_int", (0.44, 0.28, 0.02), M("lata_i", "#31383F"), R, loc=(0, 0, 0.142), bisel=0.004)
    tp_ = vacio(nombre + "_tapa", R, (0, 0.17, 0.14), (math.radians(-100 * tapa), 0, 0))
    REG[nombre + ".tapa"] = tp_
    caja(nombre + "_tp", (0.5, 0.34, 0.025), mm, tp_, loc=(0, -0.17, 0.0125), bisel=0.01)
    n = int(2 + 10 * llena)
    for i in range(n):
        caja(f"{nombre}_b{i}", (0.20, 0.10, 0.012), M("bill_base", C["verde_b"], emis=0.35), R, loc=(-0.12 + 0.002 * i, -0.03 + 0.012 * (i % 3), 0.155 + i * 0.011), rot=(0, 0, math.radians(((i * 37) % 21) - 10)), bisel=0.004)
    for i in range(int(2 + 8 * llena)):
        cil(f"{nombre}_m{i}", 0.026, 0.006, M("moneda", "#E3B83A", rough=0.3, metal=0.9), R, (0.10 + 0.04 * (i % 4) - 0.04, 0.05 - 0.05 * (i // 4), 0.155 + 0.0065 * (i % 3)), (0, 0, 0))
    return R


def puesto(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Puestito de sánguches: carro con toldo a rayas, cartel y mostrador. Frente (clientes) hacia -Y, vendedor en +Y.
    Mostrador a 1,0 de altura, 2,2 de ancho."""
    R = vacio(nombre, padre, loc, rot)
    mm = M("puesto_c", "#7A5636", rough=0.8)
    mw = M("puesto_m", C["madera"], rough=0.8)
    caja(nombre + "_cuerpo", (2.2, 0.95, 0.80), mm, R, loc=(0, 0, 0.55), bisel=0.03)
    caja(nombre + "_zocalo", (2.2, 0.95, 0.10), M("puesto_z", "#4A3322", rough=0.8), R, loc=(0, 0, 0.20), bisel=0.02)
    caja(nombre + "_tapa", (2.3, 1.05, 0.06), mw, R, loc=(0, 0, 0.98), bisel=0.02)
    for sx in (-1, 1):
        cil(f"{nombre}_rueda{sx}", 0.20, 0.07, M("rueda", C["gris"], rough=0.9), R, (sx * 0.85, -0.50, 0.20), (0, math.radians(90), 0), bisel=0.01)
        cil(f"{nombre}_rueda{sx}b", 0.20, 0.07, M("rueda", C["gris"], rough=0.9), R, (sx * 0.85, 0.50, 0.20), (0, math.radians(90), 0), bisel=0.01)
    # cartel pintado en el frente
    caja(nombre + "_cartel", (1.6, 0.04, 0.40), M("cartel_p", "#D9C9A6", rough=0.7), R, loc=(0, -0.49, 0.62), bisel=0.02)
    texto(nombre + "_ct", "SÁNGUCHES", 0.20, M("cartel_t", "#3A2418"), R, (0, -0.515, 0.62), (math.radians(90), 0, 0))
    for sx in (-1, 1):
        cil(f"{nombre}_poste{sx}", 0.03, 1.7, M("poste", "#4A3A2C"), R, (sx * 1.1, -0.45, 1.85))
        cil(f"{nombre}_posteb{sx}", 0.03, 1.7, M("poste", "#4A3A2C"), R, (sx * 1.1, 0.45, 1.85))
    # toldo a rayas (inclinado hacia adelante)
    toldo = vacio(nombre + "_toldo", R, (0, 0, 2.62), (math.radians(8), 0, 0))
    for i in range(10):
        col = "#4A2A1A" if i % 2 == 0 else "#E8CFA0"
        caja(f"{nombre}_ray{i}", (0.26, 1.7, 0.05), M("toldo_" + col, col, rough=0.8), toldo, loc=(-1.17 + i * 0.26, 0, 0), bisel=0.008)
        esf(f"{nombre}_fest{i}", 1.0, M("toldo_" + col, col, rough=0.8), toldo, (-1.17 + i * 0.26, -0.87, -0.04), esc=(0.13, 0.05, 0.10))
    return R


# ----------------------------------------------------------------------------- plaza y calle
def banco_plaza(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), largo=1.7):
    """Banco de plaza: tablas de madera y dos laterales de hierro a los costados (nada cruza a quien se siente).
    Asiento a 0,5 de alto; el respaldo está en +Y."""
    R = vacio(nombre, padre, loc, rot)
    mw = M("banco_m", "#4A505C", rough=0.8)
    mh = M("banco_h", "#2C3138", rough=0.5, metal=0.4)
    for i in range(4):
        caja(f"{nombre}_a{i}", (largo, 0.10, 0.04), mw, R, loc=(0, -0.20 + i * 0.12, 0.50), bisel=0.01)
    for i in range(3):
        caja(f"{nombre}_r{i}", (largo, 0.035, 0.12), mw, R, loc=(0, 0.20, 0.64 + i * 0.15), rot=(math.radians(-8), 0, 0), bisel=0.01)
    pts = [(-0.30, 0.0), (-0.22, 0.0), (-0.18, 0.46), (0.22, 0.48), (0.26, 0.95), (0.20, 0.95), (0.14, 0.56), (-0.16, 0.54), (-0.26, 0.04)]
    pts = [(-0.30, 0.0), (-0.22, 0.0), (-0.20, 0.46), (0.20, 0.47), (0.26, 0.92), (0.19, 0.92), (0.14, 0.53), (-0.22, 0.52), (-0.28, 0.0)]
    for sx in (-1, 1):
        obj(f"{nombre}_lat{sx}", m_poly(pts, 0.05, "lat"), mh, R, (sx * (largo / 2 + 0.02), 0, 0), (math.radians(90), 0, math.radians(90)))
    return R


def arbol(nombre, padre=None, loc=(0, 0, 0), esc=1.0, tipo=0):
    R = vacio(nombre, padre, loc)
    R.scale = (esc, esc, esc)
    cil(nombre + "_tr", 0.16, 1.5, M("tronco", "#7A5230", rough=0.9), R, (0, 0, 0.75), r2=0.12)
    verdes = ["#4FAE5A", "#62C167", "#3E9A4F"]
    for i, (x, y, z, r) in enumerate(((0, 0, 2.2, 1.05), (0.55, 0.1, 1.9, 0.7), (-0.55, -0.1, 1.95, 0.72), (0.1, 0.3, 2.75, 0.7))):
        esf(f"{nombre}_h{i}", r, M("copa" + str(i), verdes[(i + tipo) % 3], rough=0.9), R, (x, y, z))
    return R


def farola(nombre, padre=None, loc=(0, 0, 0)):
    R = vacio(nombre, padre, loc)
    mn = M("farola", "#2C3138", rough=0.5, metal=0.5)
    cil(nombre + "_p", 0.05, 3.2, mn, R, (0, 0, 1.6), r2=0.035)
    cil(nombre + "_b", 0.11, 0.3, mn, R, (0, 0, 0.15), r2=0.07)
    esf(nombre + "_l", 0.20, M("farola_l", "#FFF2C2", emis=2.5), R, (0, 0, 3.3), esc=(1, 1, 1.15))
    cil(nombre + "_t", 0.26, 0.05, mn, R, (0, 0, 3.55), r2=0.12)
    return R


def cartel_precio(nombre, texto_s, padre=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    R = vacio(nombre, padre, loc, rot)
    caja(nombre + "_c", (0.5, 0.03, 0.3), M("carteli", C["crema"]), R, bisel=0.01)
    texto(nombre + "_t", texto_s, 0.10, M("cartelt", "#1A2030"), R, (0, -0.02, 0), (math.radians(90), 0, 0))
    return R


# ----------------------------------------------------------------------------- almacén
def almacen_fondo(nombre, padre=None, loc=(0, 0, 0)):
    """Pared de fondo del almacén: estante con gaseosas y latas, fiambres colgando. Frente hacia -Y. 3,4 de ancho."""
    R = vacio(nombre, padre, loc)
    mw = M("alm_est", C["madera"], rough=0.75)
    caja(nombre + "_fondo", (3.4, 0.05, 2.4), M("alm_f", "#E7DCC4"), R, loc=(0, 0.25, 1.2), bisel=0.01)
    for k, z in enumerate((0.5, 1.15, 1.8)):
        caja(f"{nombre}_r{k}", (3.4, 0.42, 0.05), mw, R, loc=(0, 0.04, z), bisel=0.01)
    cols = ["#E8332B", "#FFC83D", "#33B26B", "#2D5BA8", "#F28A2E"]
    for k, z in enumerate((0.5, 1.15)):
        for j in range(9):
            c = cols[(j + k * 2) % 5]
            if (j + k) % 3 == 0:
                cil(f"{nombre}_bot{k}{j}", 0.07, 0.30, M("g_" + c, c, rough=0.35, spec=0.4), R, (-1.4 + j * 0.35, 0.05, z + 0.17), r2=0.07)
                cil(f"{nombre}_cu{k}{j}", 0.03, 0.08, M("g_t", C["blanco"]), R, (-1.4 + j * 0.35, 0.05, z + 0.34))
            else:
                cil(f"{nombre}_lata{k}{j}", 0.055, 0.16, M("g_" + c, c, rough=0.3, metal=0.5), R, (-1.4 + j * 0.35, 0.05, z + 0.105))
    for j, x in enumerate((-1.2, -0.3, 0.6, 1.3)):
        pan_frances(f"{nombre}_pan{j}", R, (x, 0.04, 1.84), (0, 0, math.radians(10 * (j % 3 - 1))), largo=0.42)
    for j, x in enumerate((-1.3, -0.65, 0.0, 0.65, 1.3)):
        salame(f"{nombre}_sal{j}", R, (x, -0.02, 2.2), (0, 0, 0), largo=0.34)
    return R


def vitrina(nombre, padre=None, loc=(0, 0, 0), rot=(0, 0, 0), ancho=1.8):
    """Mostrador del almacén con vitrina de vidrio con fiambres (jamón, queso, salame) y una canasta de pan."""
    R = vacio(nombre, padre, loc, rot)
    caja(nombre + "_cuerpo", (ancho, 0.75, 0.92), M("vit_c", "#F2EBDD", rough=0.7), R, loc=(0, 0, 0.46), bisel=0.02)
    caja(nombre + "_zoc", (ancho, 0.77, 0.10), M("vit_z", "#2D5BA8"), R, loc=(0, 0, 0.05), bisel=0.01)
    caja(nombre + "_tapa", (ancho + 0.06, 0.82, 0.05), M("vit_t", C["madera_clara"], rough=0.6), R, loc=(0, 0, 0.945), bisel=0.01)
    caja(nombre + "_vid", (ancho - 0.1, 0.62, 0.40), M("vit_v", "#CFEAF6", rough=0.05, alpha=0.22, spec=0.8), R, loc=(0, 0, 1.18), bisel=0.005)
    caja(nombre + "_bd", (ancho - 0.1, 0.6, 0.03), M("vit_b", "#E8E8E8", rough=0.4), R, loc=(0, 0, 0.99), bisel=0.005)
    for i, x in enumerate((-0.6, -0.2, 0.2)):
        feta(f"{nombre}_j{i}", C["jamon"], R, (x, -0.1, 1.03 + 0.012 * (i % 2)), (math.radians(3), 0, 0.3 * i), tam=0.15)
        queso(f"{nombre}_q{i}", R, (x + 0.12, 0.12, 1.02), (0, 0, 0.5 * i), tam=0.16)
    salame(f"{nombre}_sa", R, (0.55, 0.0, 1.05), (0, 0, math.radians(90)), largo=0.34, r=0.06)
    return R


def canasta_pan(nombre, padre=None, loc=(0, 0, 0)):
    R = vacio(nombre, padre, loc)
    cil(nombre + "_c", 0.26, 0.16, M("cesta", "#B98A52", rough=0.95), R, (0, 0, 0.08), r2=0.30, seg=20)
    for i in range(3):
        pan_frances(f"{nombre}_p{i}", R, (0.0, -0.08 + i * 0.08, 0.20 + i * 0.02), (0, 0, math.radians(8 * i - 8)), largo=0.34, r=0.06)
    return R
