"""
Dos Mentes 05 — "LA PLATA PRESTADA" en Blender por código (PASO 1b: estilo del 02 "5 MINUTOS" mejorado).

Mismo contrato que el 07: toda la escena sale de este archivo y hay una función pura del tiempo `aplicar(t)`
(sin keyframes). En este paso `aplicar(t)` coloca la POSE CLAVE del momento del guion que corresponde a t;
el paso 2 la va a reemplazar por la animación continua usando los mismos rigs.

Look: de noche, stickmen blancos que brillan (sin cara), piso mojado con reflejos, escenarios grises low-poly, el que no
cumple con luz AZUL y el que cumple con luz ÁMBAR, carteles monoespaciados con glow (posproducción en `noche.py`).

Uso (bpy por pip; probado con 4.2 y 5.1):
    python escena.py --still 12 --out prueba/x.png            # el cuadro del segundo 12
    python escena.py --anim --start 0 --end 1079 --samples 24 --escala 1.0 --carpeta frames    # f_0000.png ... a 30 fps
    python escena.py --hoja personajes|poses|objetos --carpeta hoja/celdas   # celdas sueltas de las hojas
    python escena.py --storyboard --carpeta hoja/celdas                         # los 7 momentos
Opciones: --samples N  --escala 0.5  --out ruta.png  --carpeta dir
"""
import bpy, math, sys, os, time
from mathutils import Vector, Matrix
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from motor import *
import objetos as O
from objetos import C
import noche as N


# ----------------------------------------------------------------------------- argumentos
def leer_args():
    a = sys.argv
    a = a[a.index("--") + 1:] if "--" in a else a[1:]
    o = {"still": None, "frame": None, "anim": False, "start": 0, "end": None, "samples": 24, "escala": 1.0,
         "out": None, "carpeta": None, "hoja": None, "storyboard": False, "solo": None}
    i = 0
    while i < len(a):
        k = a[i]
        if k in ("--anim", "--storyboard"):
            o[k[2:]] = True
        elif k in ("--still", "--frame", "--start", "--end", "--samples", "--escala", "--out", "--carpeta", "--hoja", "--solo"):
            i += 1
            kk = k[2:]
            o[kk] = a[i] if kk in ("out", "carpeta", "hoja", "solo") else float(a[i])
        i += 1
    return o


ARGS = leer_args()
FPS = 30
DURACION = 36.0
NCUADROS = int(round(DURACION * FPS))      # 1080 cuadros
ANCHO, ALTO = 1080, 1920
FULL = (1080, 1920)

X_PLAZA, X_TIENDA, X_CALLE, X_PUESTO, X_ESTUDIO = 0.0, 60.0, 120.0, 180.0, 300.0

PJ = {}          # personajes
SETS = {}
PLAN = None      # vistas + carteles del cuadro actual (None = cámara libre, sin carteles)


# ----------------------------------------------------------------------------- render
def cfg_render(sc):
    sc.render.engine = 'CYCLES'
    c = sc.cycles
    c.device = 'CPU'
    c.samples = int(ARGS["samples"])
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    try:
        c.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    c.max_bounces = 5
    c.diffuse_bounces = 2
    c.glossy_bounces = 3
    c.transmission_bounces = 2
    c.sample_clamp_indirect = 10.0
    c.sample_clamp_direct = 0.0
    sc.render.resolution_x = ANCHO
    sc.render.resolution_y = ALTO
    sc.render.resolution_percentage = int(round(ARGS["escala"] * 100))
    sc.render.fps = FPS
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = -0.25
    sc.render.film_transparent = False
    sc.render.use_persistent_data = True


CAM = None
CAM_ACTUAL = [Vector((0, -5, 1.5))]


def camara(pos, objetivo, lente=35, dof=None, rot_z=0.0):
    """Cámara única: `dof`=(distancia de foco, f-stop) o None."""
    cam = CAM.data
    CAM.location = pos
    CAM_ACTUAL[0] = Vector(pos)
    d = Vector(objetivo) - Vector(pos)
    CAM.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.lens = lente
    if dof:
        cam.dof.use_dof = True
        cam.dof.focus_distance = dof[0]
        cam.dof.aperture_fstop = dof[1]
    else:
        cam.dof.use_dof = False


def dof_a(pos, objetivo, f=3.2):
    return ((Vector(objetivo) - Vector(pos)).length, f)


# ----------------------------------------------------------------------------- escenarios (de noche, grises, low-poly)
def luces_ambiente(x0, color, energia, y=2.0, z=7.0, tam=14):
    N.luz(f"amb_{x0}_{color}", 'AREA', (x0, y, z), color, energia, rot=(0, 0, 0), tam=tam)


def set_plaza():
    x0 = X_PLAZA
    N.piso("pl_piso", (x0, 6), (140, 140), "#141C2B", rough=(0.02, 0.10))
    N.cordon("pl_acera", x0, 5.8, 70, 3.2, 0.14, "#1E2430")
    N.cordon("pl_acera2", x0, 3.9, 70, 0.4, 0.14, "#303847")
    for i, (x, w, h, col) in enumerate(((-10.5, 5.0, 9.0, "#222836"), (-5.2, 4.2, 12.0, "#2A3140"), (0.0, 3.6, 7.5, "#202633"),
                                          (4.6, 4.8, 13.0, "#2A3140"), (10.0, 4.2, 9.5, "#222836"), (-15.5, 4.4, 11.0, "#2A3140"), (15.0, 4.4, 8.0, "#202633"))):
        N.edificio(f"pl_e{i}", x0 + x, 11.5, w, 3.0, h, col, semilla=i, prob=0.50)
    N.banco_n("pl_banco", (x0 + 3.9, 5.2, 0.14), rot=(0, 0, math.radians(-12)))
    N.farola_n("pl_far", (x0 + 4.9, 4.3, 0.14), "#FFEFC8", 650, alto=4.4, brazo=0.9, dir_=-1)
    N.arbol_n("pl_a1", (x0 - 5.6, 6.3, 0.14), 1.3)
    N.arbol_n("pl_a2", (x0 - 8.8, 5.6, 0.14), 1.1)
    N.arbol_n("pl_a3", (x0 + 8.5, 6.8, 0.14), 1.2)
    SETS["amb_plaza"] = N.luz("amb_plaza", 'AREA', (x0, 0.0, 8.0), "#3F66C8", 380, tam=18)
    SETS["calor"] = N.luz("calor_plaza", 'POINT', (x0, -1.6, 2.4), "#FF9A2A", 700, radio=0.5)
    for i in range(14):                      # luces lejanas: en el celular (POV con foco corto) se vuelven bokeh
        cl = ["#FFD9A0", "#7FE3F0", "#FF8FB8", "#FFF2C8", "#9FC4FF"][i % 5]
        SETS.setdefault("bokeh", []).append(esf(f"pl_bk{i}", 0.20, N.mat_gris("bk" + cl, cl, emis=16.0, rough=0.3), None, (x0 - 8.5 + i * 1.3, 8.6 + (i % 3) * 0.2, 1.0 + (i * 7 % 5) * 0.8)))


def set_tienda():
    x0 = X_TIENDA
    N.piso("ti_piso", (x0, 0), (40, 24), "#0F1626")
    mp = N.mat_gris("ti_pared", "#1C2638", rough=0.9, spec=0.1)
    caja("ti_fondo", (14, 0.25, 4.0), mp, loc=(x0, 2.75, 2.0), bisel=0)
    caja("ti_izq", (0.25, 9, 4.0), mp, loc=(x0 - 6.0, -1.5, 2.0), bisel=0)
    caja("ti_der", (0.25, 9, 4.0), mp, loc=(x0 + 6.0, -1.5, 2.0), bisel=0)
    caja("ti_techo", (14, 9, 0.2), mp, loc=(x0, -1.5, 4.1), bisel=0)
    caja("ti_zocalo", (14, 0.1, 0.18), N.mat_gris("ti_zoc", "#2B3A55", emis=1.0, emis_color="#3E6BD0"), loc=(x0, 2.6, 0.09), bisel=0)
    SETS["puerta"] = O.puerta_tienda("ti_puerta", loc=(x0 - 4.6, 2.62, 0), angulo=0.0, ancho=1.0, alto=2.3)
    SETS["estante"] = O.estante_zapatillas("ti_estante", loc=(x0 - 0.9, 2.42, 0), ancho=2.8, alto=2.3)
    SETS["estante2"] = O.estante_zapatillas("ti_estante2", loc=(x0 + 2.3, 2.42, 0), ancho=2.8, alto=2.3)
    SETS["mostrador"] = O.mostrador("ti_mostr", loc=(x0 + 1.05, 1.25, 0), rot=(0, 0, math.radians(-90)), ancho=2.2)
    for i, (dx, dy, dz) in enumerate(((-1.5, 0.9, 0.0), (-2.15, 1.35, 0.0), (-1.55, 1.9, 0.0))):       # pila de cajas
        O.caja_zapatillas(f"ti_cz{i}", loc=(x0 + dx - 1.5, dy, dz), rot=(0, 0, math.radians(8 * i - 6)), abierta=False)
        O.caja_zapatillas(f"ti_cy{i}", loc=(x0 + dx - 1.5, dy, dz + 0.16), rot=(0, 0, math.radians(-5 * i)), abierta=False)
    luces_ambiente(x0, "#3F83FF", 700, y=0.8, z=3.9, tam=8)
    N.luz("ti_foco", 'SPOT', (x0 + 0.4, -1.2, 3.7), "#6AA8FF", 160, spot=75).rotation_euler = (math.radians(20), 0, 0)
    N.luz("ti_est", 'POINT', (x0 + 0.4, 1.5, 3.4), "#7FB4FF", 250, radio=0.4)


def set_calle():
    x0 = X_CALLE
    N.piso("ca_calle", (x0, 0), (120, 6.2), "#0C0F15")
    N.piso("ca_fondoN", (x0, 12), (120, 20), "#0C1118", z=-0.01)
    N.piso("ca_fondoS", (x0, -12), (120, 20), "#0C1118", z=-0.01)
    for i in range(-9, 10):
        caja(f"ca_raya{i}", (1.2, 0.14, 0.004), N.mat_gris("raya", "#8A8F9C", emis=0.6), loc=(x0 + i * 2.6, 0.0, 0.004), bisel=0)
    N.cordon("ca_vN", x0, 5.5, 120, 4.8, 0.14, "#1E2430")
    N.cordon("ca_vS", x0, -5.5, 120, 4.8, 0.14, "#1E2430")
    for i, (x, w, h, col) in enumerate(((-9, 4.6, 9.5, "#222836"), (-4.2, 4.2, 12.0, "#2A3140"), (0.6, 4.6, 8.0, "#202633"), (5.4, 4.6, 11.5, "#2A3140"), (10.0, 4.2, 9.0, "#222836"))):
        N.edificio(f"ca_e{i}", x0 + x, 9.6, w, 3.0, h, col, semilla=i + 3, prob=0.5)
    N.farola_n("ca_f1", (x0 + 4.2, 3.6, 0.14), "#FFEFC8", 2400, alto=4.4, brazo=0.9, dir_=-1)
    N.farola_n("ca_f2", (x0 - 5.0, -3.9, 0.14), "#FFEFC8", 2400, alto=4.4, brazo=0.9, dir_=1)
    N.arbol_n("ca_a1", (x0 - 6.5, 5.3, 0.14), 1.0)
    luces_ambiente(x0, "#3F66C8", 380, y=0.0, z=8.0, tam=18)


def set_puesto():
    x0 = X_PUESTO
    N.piso("pu_piso", (x0, 6), (140, 140), "#1B1618")
    N.cordon("pu_acera", x0, 7.6, 70, 2.6, 0.14, "#24252C")
    for i, (x, w, h, col) in enumerate(((-9.6, 4.8, 10.0, "#25262E"), (-4.6, 4.2, 12.5, "#2D2E38"), (0.4, 3.8, 8.0, "#23242C"),
                                          (5.0, 4.8, 13.0, "#2D2E38"), (10.2, 4.2, 9.5, "#25262E"))):
        N.edificio(f"pu_e{i}", x0 + x, 11.0, w, 3.0, h, col, semilla=i + 7, prob=0.45)
    SETS["puesto"] = O.puesto("pu_puesto", loc=(x0, 2.2, 0))
    SETS["caja_plata"] = O.caja_plata("pu_caja", loc=(x0 + 0.75, 2.0, 1.02), rot=(0, 0, math.radians(-8)), llena=0.0)
    SETS["bandeja"] = []
    for i in range(3):
        SETS["bandeja"].append(O.sanguche(f"pu_san{i}", loc=(x0 - 0.95 + i * 0.05 - 0.15, 1.95, 1.02), largo=0.62))
    N.arbol_n("pu_a1", (x0 - 7.0, 8.0, 0.14), 1.3)
    N.arbol_n("pu_a2", (x0 + 8.0, 8.2, 0.14), 1.2)
    N.farola_n("pu_f1", (x0 - 4.6, 5.0, 0.0), "#FFD9A0", 1800, alto=4.4, brazo=0.9, dir_=1)
    # luz cálida bajo el toldo + ambiente ámbar
    N.luz("pu_toldo", 'POINT', (x0, 1.6, 2.35), "#FF9E3A", 450, radio=0.35)
    N.luz("pu_toldo2", 'POINT', (x0 + 0.6, 3.0, 2.0), "#FFB75A", 180, radio=0.3)
    N.luz("pu_frente", 'AREA', (x0, -3.2, 3.2), "#FFA64D", 220, tam=4.0).rotation_euler = (math.radians(70), 0, 0)
    luces_ambiente(x0, "#C8782A", 260, y=1.0, z=8.0, tam=16)
    N.luz("pu_suelo", 'AREA', (x0, -0.5, 5.0), "#FFA64D", 260, tam=9.0)


def set_estudio():
    x0 = X_ESTUDIO
    N.piso("es_piso", (x0, 0), (80, 80), "#0B0F18")
    caja("es_fondo", (80, 0.2, 18), N.mat_gris("es_fondo", "#0E1420", rough=1.0), loc=(x0, 14, 9), bisel=0)
    luces_ambiente(x0, "#4A78E0", 500, y=0.0, z=7.0, tam=14)


# ----------------------------------------------------------------------------- personajes
def crear_personajes():
    # `color` = tinte de la emisión; `base` = el blanco de la piel. El color real lo ponen además las luces (azul fría / ámbar cálida)
    PJ["azul"] = Personaje("azul", "#4F9BFF", dict(emis=0.38, base=(0.50, 0.68, 1.0)))
    PJ["ambar"] = Personaje("ambar", "#FFA21F", dict(emis=0.38, base=(1.0, 0.72, 0.36)))
    PJ["amigo"] = Personaje("amigo", "#FFFFFF", dict(emis=0.14, base=(0.86, 0.88, 0.92)))
    for n in ("rosa", "violeta", "coral", "blanco"):      # extras / clientes: blancos más tenues
        PJ[n] = Personaje(n, "#D5DDF0", dict(emis=0.04, base=(0.55, 0.58, 0.66)))
    N.crear_luces_pj(list(PJ.keys()))


# ----------------------------------------------------------------------------- poses base
def v3(*a):
    return Vector(a)


def sg_(lado):
    return 1 if lado == "d" else -1


def ease(x):
    return sm(x, 0.0, 1.0)


def pie_fase(u, S=0.72, H=0.17):
    """Pie en la fase u∈[0,1) del ciclo: 0 = apoyo del talón. Devuelve (tobillo (y,z), pitch). Apoyo sin deslizar."""
    hy, hz, ty, tz = -0.10, -ALTURA_TOBILLO, 0.20, -ALTURA_TOBILLO
    def apoyo(u):
        ya = S / 2 - S * (u / 0.6)
        if u < 0.08:
            p = 0.40 * (1 - sm(u, 0.0, 0.08))
            py, pz = hy, hz
        elif u < 0.42:
            return (ya, ALTURA_TOBILLO), 0.0
        else:
            p = -0.70 * sm(u, 0.42, 0.6)
            py, pz = ty, tz
        gy = ya + py
        c, s_ = math.cos(p), math.sin(p)
        ry, rz = py * c - pz * s_, py * s_ + pz * c
        return (gy - ry, -rz), p
    u = u % 1.0
    if u < 0.6:
        return apoyo(u)
    (y0, z0), p0 = apoyo(0.6)
    (y1, z1), p1 = apoyo(0.0)
    s_ = (u - 0.6) / 0.4
    e = sm(s_, 0.0, 1.0)
    return (y0 + (y1 - y0) * e, z0 + (z1 - z0) * e + H * math.sin(math.pi * s_) ** 0.9), p0 + (p1 - p0) * sm(s_, 0.0, 0.75)


def caminata(fase, S=0.72, brazos=0.30, encorvado=0.0, peso=1.0):
    """Pose de caminata humana (fase 0..1 del ciclo de la pierna derecha): rodilla, talón-punta, balanceo de brazos y cadera."""
    ph = fase % 1.0
    kw = {}
    zp = 1.080 + 0.030 * (0.5 - 0.5 * math.cos(4 * math.pi * ph)) * peso
    kw["pelvis"] = (0.030 * math.sin(2 * math.pi * ph) * peso, 0.0, zp)
    yaw_p = 0.11 * math.cos(2 * math.pi * ph)
    kw["pelvis_rot"] = (0.0, 0.03 * math.sin(2 * math.pi * ph), yaw_p)
    kw["torso_rot"] = (0.05 + encorvado * 0.55, -0.02 * math.sin(2 * math.pi * ph), -0.95 * yaw_p)
    kw["cabeza_rot"] = (-0.06 - encorvado * 0.35 + 0.03 * math.cos(4 * math.pi * ph), 0.0, 0.0)
    for lado, off in (("d", 0.0), ("i", 0.5)):
        sg = sg_(lado)
        (y, z), p = pie_fase(ph + off, S)
        kw["p" + lado] = dict(p=(sg * 0.09, y, z), pitch=p, polo=(sg * 0.08, 1.0, 0.0))
        # el brazo de un lado va con la pierna del otro
        sw = -math.cos(2 * math.pi * (ph + off))
        wy = 0.03 + brazos * sw
        wz = 0.86 + 0.09 * max(0.0, sw) + 0.0
        wx = sg * (0.27 - 0.02 * max(0.0, sw))
        kw["m" + lado] = dict(p=(wx, wy, wz), curl=0.28, palma=(-sg, 0.2, 0.0), polo=(sg * 0.5, -1.0, -0.2 - 0.6 * max(0.0, sw)))
    return kw


def parado(**extra):
    kw = dict(pelvis=(0, 0, 1.095), torso_rot=(0.03, 0, 0), pd=dict(p=(0.11, 0.0, ALTURA_TOBILLO)), pi=dict(p=(-0.11, 0.0, ALTURA_TOBILLO)))
    kw.update(extra)
    return kw


CURL_ABIERTA = (0.08, 0.1, 0.12, 0.15)
CURL_PUNO = (1.0, 1.0, 1.0, 1.0)
CURL_MENIQUE = (1.0, 1.0, 1.0, (0.12, 1.0))      # el meñique estirado y enganchado


def adjuntar(o, mano, loc=(0, 0, 0), rot=None):
    """Pega `o` (vacío raíz de un objeto) a la mano: marco de la mano (dedos=+Z, palma=+Y, pulgar según el lado)."""
    o.parent = mano.raiz
    R = rot if rot is not None else Matrix.Identity(3)
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = Matrix.Translation(Vector(loc)) @ R.to_4x4()


# rotación que acuesta un objeto "plano" (X largo, Z normal) sobre la palma con el largo hacia los dedos
R_PLANO_PALMA = Matrix(((0, 1, 0), (0, 0, 1), (1, 0, 0)))          # X→Z_mano, Y→X_mano, Z→Y_mano
R_PLANO_ANCHO = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))          # X→X_mano, Z→Y_mano


def hacia(a, b):
    return (Vector(b) - Vector(a)).normalized()


# ----------------------------------------------------------------------------- construcción general
R_PLANO_LADO = Matrix(((0, 0, 1), (0, -1, 0), (1, 0, 0)))          # X→Z_mano, Z→X_mano (billetes tomados de canto)


def vis(o, v):
    """Muestra/oculta un objeto y todos sus hijos."""
    o.hide_render = not v
    for h in o.children_recursive:
        h.hide_render = not v


def construir():
    global CAM
    limpiar()
    sc = bpy.context.scene
    cfg_render(sc)
    N.mundo_noche()
    cam = bpy.data.cameras.new("cam")
    cam.sensor_width = 36
    cam.sensor_fit = 'HORIZONTAL'
    CAM = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(CAM)
    sc.camera = CAM


def resolucion(w, h):
    global ANCHO, ALTO
    ANCHO, ALTO = w, h
    sc = bpy.context.scene
    sc.render.resolution_x = w
    sc.render.resolution_y = h


# =============================================================================== el guion, momento por momento
GUION = [  # (inicio, fin, nombre)
    (0.0, 3.0, "plaza · LA MISMA PLATA: el amigo les da lo mismo a los dos, promesa de meñique"),
    (3.0, 10.0, "pantalla dividida · arriba LA HIZO CRECER (ámbar, puestito) / abajo SE LA GASTÓ (azul, zapatillas)"),
    (10.0, 16.0, "celular del amigo · VISTO: ¿Y la plata? / Visto / ¿Hola? / tengo que pagar unas cuentas"),
    (16.0, 19.0, "calle · el azul (zapatillas nuevas, bolsa) se cruza de vereda y no lo saluda"),
    (19.0, 27.0, "puesto en grande · LA HIZO CRECER: clientes, sánguches, la caja se llena"),
    (27.0, 33.0, "plaza · CUMPLIÓ: el ámbar devuelve la plata con las dos manos, choque de puño; el azul mira de lejos"),
    (33.0, 36.0, "vuelta al plano 1 (bucle, corte limpio)"),
]
T_CLAVE = [1.0, 6.0, 12.0, 17.0, 23.0, 30.0, 34.0]
# rótulos de los carteles por momento (se leen en la hoja y en el video)
CARTELES = {
    0: [("cartel", "LA MISMA PLATA", N.BLANCO, 0.105, 112)],
    2: [("cartel", "VISTO", N.AZUL, 0.095, 150)],
    3: [("cartel", "NI LO MIRA", N.AZUL, 0.095, 120)],
    4: [("cartel", "LA HIZO CRECER", N.AMBAR, 0.095, 112), ("rotulo", "VENDE SÁNGUCHES", N.AMBAR, 0.145, 46)],
    5: [("cartel", "CUMPLIÓ", N.AMBAR, 0.095, 170)],
    6: [("cartel", "LA MISMA PLATA", N.BLANCO, 0.105, 112)],
}


def libre():
    global PLAN
    PLAN = None


def plan(vistas, carteles=(), linea=None):
    global PLAN
    PLAN = dict(vistas=vistas, carteles=list(carteles), linea=linea)
    v = vistas[0]
    camara(v["pos"], v["obj"], v["lente"], v["dof"])


def vista(pos, obj, lente, dof=True, tam=FULL, orig=(0, 0), f=3.5):
    pos, obj = Vector(pos), Vector(obj)
    return dict(pos=pos, obj=obj, lente=lente, dof=dof_a(pos, obj, f) if dof is True else dof, tam=tam, orig=orig)


def ilumina(cam_pos, *nombres):
    for n in nombres:
        N.luces_a(PJ[n], cam_pos)


def ocultar_todos():
    SETS["amb_plaza"].data.energy = 380.0
    SETS["calor"].hide_render = True
    N.ESCALA_LUZ[0] = 1.0
    for p in PJ.values():
        p.ocultar(True)
    for f, r in N.LUCES_PJ.values():
        f.hide_render = r.hide_render = True
    for k in ("fajo_a", "fajo_b", "fajo_c", "abanico", "bolsa", "san_m", "zapa_m"):
        if k in SETS:
            vis(SETS[k], False)
    if "celular" in SETS:
        vis(SETS["celular"].raiz, False)
    for o in SETS.get("bokeh", []):
        o.hide_render = True


def mostrar(*nombres):
    for n in nombres:
        PJ[n].ocultar(False)


def m1_plaza(s=1.0):
    """LA MISMA PLATA: el amigo (centro) con un fajo en la palma de cada mano; el azul (izq) y el ámbar (der) las reciben."""
    x0 = X_PLAZA
    mostrar("azul", "amigo", "ambar")
    A, G, B = PJ["azul"], PJ["amigo"], PJ["ambar"]
    A.calzado("plano"); B.calzado("plano")
    cen_a, cen_g, cen_b = v3(x0 - 1.30, 0.0, 0.14), v3(x0, 0.0, 0.14), v3(x0 + 1.30, 0.0, 0.14)
    mano_a = v3(x0 - 0.58, -0.45, 1.28)
    mano_b = v3(x0 + 0.58, -0.45, 1.28)
    G.poner(pos=cen_g, yaw=math.pi, **parado(torso_rot=(0.02, 0, 0)),
            md=dict(w=mano_a, dedos_w=(-1, -0.5, 0.0), palma_w=(0, 0, 1), curl=(0.08, 0.08, 0.08, 0.08), polo=(0.3, -0.2, -1)),
            mi=dict(w=mano_b, dedos_w=(1, -0.5, 0.0), palma_w=(0, 0, 1), curl=(0.08, 0.08, 0.08, 0.08), polo=(-0.3, -0.2, -1)))
    A.poner(pos=cen_a, yaw=-3 * math.pi / 4 + 0.2, **parado(cabeza_rot=(0, 0, 0.75), torso_rot=(0.05, 0, -0.1)),
            md=dict(w=mano_a + v3(-0.30, 0.05, 0.0), dedos_w=(1, -0.5, 0.0), palma_w=(0, 0, 1), curl=(0.08, 0.08, 0.08, 0.08)),
            mi=dict(p=(-0.26, 0.04, 0.86), curl=0.3))
    B.poner(pos=cen_b, yaw=3 * math.pi / 4 - 0.2, **parado(cabeza_rot=(0, 0, -0.75), torso_rot=(0.05, 0, 0.1)),
            mi=dict(w=mano_b + v3(0.30, 0.05, 0.0), dedos_w=(-1, -0.5, 0.0), palma_w=(0, 0, 1), curl=(0.08, 0.08, 0.08, 0.08)),
            md=dict(p=(0.26, 0.04, 0.86), curl=0.3))
    for lado, k in (("d", "fajo_a"), ("i", "fajo_b")):
        vis(SETS[k], True)
        adjuntar(SETS[k], G.brazo[lado]["mano"], (0.0, 0.062 * HM, 0.12 * HM), R_PLANO_PALMA)
    cam = v3(x0 + 0.1, -2.85, 1.20)
    plan([vista(cam, (x0, 0.0, 1.30), 28)], CARTELES[0])
    ilumina(cam, "azul", "amigo", "ambar")


def m2_dividida(s=6.0):
    """Pantalla dividida horizontal como el 02. Arriba el puesto (ámbar vende, un cliente compra); abajo la tienda (el azul
    compra las zapatillas rojas y paga). Las dos mitades se renderizan aparte (1080x960) y se pegan con la línea blanca."""
    xp, xt = X_PUESTO, X_TIENDA
    mostrar("ambar", "blanco", "azul", "violeta")
    Am, Cl, A, V = PJ["ambar"], PJ["blanco"], PJ["azul"], PJ["violeta"]
    Am.calzado("plano"); Cl.calzado("plano"); V.calzado("plano"); A.calzado("zapa")
    O.REG["pu_caja.tapa"].rotation_euler.x = -math.radians(100)
    vis(SETS["san_m"], True)
    for o in SETS["bandeja"]:
        vis(o, True)
    # --- arriba: el puesto
    Am.poner(pos=v3(xp - 0.15, 3.05, 0), yaw=math.pi - 0.25, **parado(torso_rot=(0.08, 0, 0.0), cabeza_rot=(0, 0, 0.3)),
             md=dict(w=v3(xp - 0.75, 2.0, 1.30), dedos_w=(-0.6, -1, 0.0), palma_w=(0, 0, 1), curl=(0.1, 0.1, 0.1, 0.1), polo=(0.5, 0.4, -1)),
             mi=dict(w=v3(xp + 0.45, 2.15, 1.20), dedos_w=(0, -1, 0), palma_w=(0, 0, 1), curl=0.25, polo=(-0.3, 0.3, -1)))
    adjuntar(SETS["san_m"], Am.brazo["d"]["mano"], (0.0, 0.06 * HM, 0.02), R_PLANO_PALMA)
    Cl.poner(pos=v3(xp - 1.85, 1.75, 0), yaw=-math.pi / 2 - 0.45, **parado(torso_rot=(0.05, 0, 0.0), cabeza_rot=(0, 0, 0.4)),
             md=dict(w=v3(xp - 1.15, 1.9, 1.30), dedos_w=(1, 0.2, 0), palma_w=(0, 0, 1), curl=(0.1, 0.1, 0.1, 0.1), polo=(0, -1, -0.4)),
             mi=dict(p=(-0.26, 0.04, 0.86), curl=0.3))
    cam1 = v3(xp - 0.1, -0.55, 1.9)
    # --- abajo: la tienda
    bill = v3(xt + 1.02, 1.25, 1.27)
    A.poner(pos=v3(xt + 0.38, 1.25, 0), yaw=-math.pi / 2 - 0.55, **parado(torso_rot=(0.08, 0, 0.0), cabeza_rot=(0, 0, 0.5)),
            md=dict(w=bill + v3(-0.02, 0, 0), dedos_w=(1, 0.1, -0.2), palma_w=(0, -1, 0.4), curl=(0.4, 0.4, 0.4, 0.4), polo=(0, -1, -0.3)),
            mi=dict(w=v3(xt + 0.05, 0.55, 1.28), dedos_w=(0.3, 0.7, 0.5), palma_w=(0, 0, 1), curl=(0.2, 0.2, 0.2, 0.2), polo=(-0.4, -0.2, -1)))
    vis(SETS["abanico"], True)
    adjuntar(SETS["abanico"], A.brazo["d"]["mano"], (0.0, 0.0, 0.10 * HM), R_PLANO_LADO)
    vis(SETS["zapa_m"], True)
    adjuntar(SETS["zapa_m"], A.brazo["i"]["mano"], (0.0, 0.04, 0.10), Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))))
    V.poner(pos=v3(xt + 1.72, 1.25, 0), yaw=math.pi / 2 + 0.45, **parado(torso_rot=(0.08, 0, 0), cabeza_rot=(0, 0, -0.3)),
            mi=dict(w=bill + v3(0.12, 0.0, -0.02), dedos_w=(-1, 0, 0.3), palma_w=(0, 0, 1), curl=(0.1, 0.1, 0.1, 0.1)),
            md=dict(p=(0.26, 0.04, 0.86), curl=0.3))
    cam2 = v3(xt + 1.05, -1.4, 1.65)
    mitad = (1080, 960)
    v_top = vista(cam1, (xp - 0.1, 2.0, 2.12), 28, tam=mitad, orig=(0, 0), f=3.0)
    v_bot = vista(cam2, (xt + 1.05, 1.25, 1.36), 28, tam=mitad, orig=(0, 960), f=4.0)
    plan([v_top, v_bot], [("cartel", "LA HIZO CRECER", N.AMBAR, 0.060, 84), ("rotulo", "VENDE SÁNGUCHES", N.AMBAR, 0.095, 38),
                           ("cartel", "SE LA GASTÓ", N.AZUL, 0.563, 84), ("rotulo", "COMPRA ZAPATILLAS", N.AZUL, 0.598, 38)], linea=960)
    N.luces_a(Am, cam1); N.luces_a(Cl, cam1); N.luces_a(A, cam2); N.luces_a(V, cam2)


def m3_celular(s=12.0):
    """Primer plano del celular en la mano del amigo, de POV (la cámara está donde tiene los ojos): la mano envuelve el
    teléfono por el borde derecho y el pulgar toca la pantalla abajo (no tapa el texto). Letra enorme, 1-2 mensajes por pantalla."""
    x0 = X_PLAZA
    mostrar("amigo")
    G = PJ["amigo"]
    ph = SETS["celular"]
    vis(ph.raiz, True)
    ph.mostrar(1)
    for o in SETS["bokeh"]:
        o.hide_render = False
    ojos = v3(x0 + 0.02, 0.22, 1.80)
    centro = v3(x0 + 0.05, 0.58, 1.56)                  # centro del celular
    palma = (ojos - centro).normalized()
    dedos = v3(1.0, 0.0, 0.0)
    Rm = mat_rot(dedos, palma)
    muneca = centro - Rm @ v3(0.0, 0.062 * HM, 0.05)
    G.poner(pos=v3(x0, 0.0, 0.14), yaw=0.0, **parado(torso_rot=(0.10, 0, 0), cabeza_rot=(0.5, 0, 0)),
            md=dict(w=muneca, dedos_w=dedos, palma_w=palma, curl=((0.55, 0.3),) * 4,
                    pulgar=(-0.165, 0.086, 0.06), polo=(1.0, -0.2, -0.6)),
            mi=dict(p=(-0.26, 0.03, 0.84), curl=0.3))
    vis(G.cabeza, False)
    adjuntar(ph.raiz, G.brazo["d"]["mano"], (0.0, 0.062 * HM, 0.05), R_PLANO_PALMA)
    ojos = ojos + (centro - ojos) * -0.06
    N.ESCALA_LUZ[0] = 0.55
    bpy.context.view_layer.update()
    centro = ph.raiz.matrix_world.translation.copy()
    plan([vista(ojos, centro, 40, dof=((centro - ojos).length, 2.2))], CARTELES[2])
    N.luces_a(G, ojos)
    # el POV no ve el cuerpo: la luz de relleno viene de la cámara hacia la mano
    f, r = N.LUCES_PJ["amigo"]
    f.location = ojos + v3(0.0, -0.1, 0.25)
    r.location = ojos + v3(0.5, 0.5, 0.2)
    N.apuntar(r, centro)


def m4_calle(s=16.0):
    """Calle: el azul (zapatillas nuevas, bolsa) se cruza por la calzada hacia la vereda de enfrente; el amigo lo ve y lo saluda;
    el azul mira para otro lado. Entre los dos hay distancia: no se atraviesan."""
    x0 = X_CALLE
    mostrar("azul", "amigo")
    A, G = PJ["azul"], PJ["amigo"]
    A.calzado("zapa")
    vis(SETS["bolsa"], True)
    kw = caminata(0.30, S=0.70, brazos=0.26)
    A.poner(pos=v3(x0 + 0.7, -2.3, 0), yaw=-math.pi / 2 + 0.55, **{**kw, "cabeza_rot": (0.0, 0, -0.9)})
    adjuntar(SETS["bolsa"], A.brazo["d"]["mano"], (0.0, 0.0, 0.02), Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))))
    G.poner(pos=v3(x0 - 1.6, 4.4, 0.14), yaw=0.0 + math.pi - 0.35, **parado(cabeza_rot=(-0.03, 0, 0.7)),
            md=dict(p=(0.27, 0.04, 0.85), curl=0.25),
            mi=dict(w=v3(x0 - 1.6 + 0.25, 4.4, 2.55), dedos_w=(0.2, 0.0, 1), palma_w=(0.2, -1, 0), curl=(0.08, 0.08, 0.08, 0.08), polo=(0.6, -0.3, 0.2)))
    cam = v3(x0 + 0.2, -5.6, 1.6)
    plan([vista(cam, (x0 + 0.2, -1.0, 1.4), 30, f=5.0)], CARTELES[3])
    ilumina(cam, "azul", "amigo")


def m5_puesto(s=22.0):
    """Puesto de sánguches en grande: la ámbar atiende, clientes (nadie se encima), la caja de plata llena."""
    x0 = X_PUESTO
    mostrar("ambar", "rosa", "coral", "blanco")
    Am, R_, Co, Bl = PJ["ambar"], PJ["rosa"], PJ["coral"], PJ["blanco"]
    for p in (Am, R_, Co, Bl):
        p.calzado("plano")
    vis(SETS["san_m"], True)
    for o in SETS["bandeja"]:
        vis(o, True)
    Am.poner(pos=v3(x0 - 0.2, 3.25, 0), yaw=math.pi - 0.35, **parado(torso_rot=(0.06, 0, 0.0), cabeza_rot=(0, 0, 0.3)),
             md=dict(w=v3(x0 - 0.95, 2.0, 1.28), dedos_w=(-1, -0.4, 0.0), palma_w=(0, 0, 1), curl=(0.1, 0.1, 0.1, 0.1), polo=(0.5, 0.4, -1)),
             mi=dict(w=v3(x0 + 0.35, 2.1, 1.15), dedos_w=(0, -1, 0), palma_w=(0, 0, 1), curl=0.25, polo=(-0.3, 0.3, -1)))
    adjuntar(SETS["san_m"], Am.brazo["d"]["mano"], (0.0, 0.06 * HM, 0.02), R_PLANO_PALMA)
    R_.poner(pos=v3(x0 - 1.85, 1.95, 0), yaw=-math.pi / 2 - 0.45, **parado(torso_rot=(0.05, 0, 0.0), cabeza_rot=(0, 0, 0.7)),
             md=dict(w=v3(x0 - 1.15, 1.9, 1.25), dedos_w=(1, 0.2, 0), palma_w=(0, 0, 1), curl=(0.1, 0.1, 0.1, 0.1), polo=(-0.5, -0.5, -1)),
             mi=dict(p=(-0.26, 0.04, 0.84), curl=0.3))
    Co.poner(pos=v3(x0 + 1.85, 1.95, 0), yaw=math.pi / 2 + 0.45, **parado(torso_rot=(0.04, 0, 0), cabeza_rot=(0, 0, -0.7)),
             mi=dict(w=v3(x0 + 1.15, 1.9, 1.28), dedos_w=(-1, 0.2, 0), palma_w=(0, -1, 0.2), curl=0.45, polo=(-0.3, -0.8, -0.3)),
             md=dict(p=(0.26, 0.04, 0.84), curl=0.3))
    kw = caminata(0.25, S=0.66, brazos=0.22)
    Bl.poner(pos=v3(x0 + 3.3, 1.6, 0), yaw=-math.pi / 2 + 0.35, **{**kw, "cabeza_rot": (0, 0, 0.5)})
    O.REG["pu_caja.tapa"].rotation_euler.x = -math.radians(100)
    cam = v3(x0 + 0.0, -1.2, 1.75)
    plan([vista(cam, (x0 - 0.1, 2.0, 1.55), 24, f=3.5)], CARTELES[4])
    ilumina(cam, "ambar", "rosa", "coral", "blanco")


def m6_choque(s=30.0):
    """CUMPLIÓ: choque de puño de perfil en la plaza (la ámbar y el amigo se miran), él con el fajo en la otra mano;
    el azul, chiquito y encorvado al fondo, mira."""
    x0 = X_PLAZA
    mostrar("ambar", "amigo", "azul")
    B, G, A = PJ["ambar"], PJ["amigo"], PJ["azul"]
    B.calzado("plano"); A.calzado("zapa")
    p_ch = v3(x0, -0.05, 1.25)
    puño = (1, 1, 1, 1)
    G.poner(pos=v3(x0 - 0.72, 0.0, 0.14), yaw=-math.pi / 2 - 0.12, **parado(torso_rot=(0.0, 0, 0.1), cabeza_rot=(0, 0, 0.2)),
            md=dict(w=p_ch + v3(-0.17, 0.0, 0.0), dedos_w=(1, 0, 0), palma_w=(0, 1, 0), curl=puño, pulgar=(-0.03, 0.105, 0.115), polo=(0, -0.4, -1)),
            mi=dict(w=v3(x0 - 0.72 - 0.38, -0.30, 1.02), dedos_w=(0, -0.2, -1), palma_w=(1, 0, 0), curl=0.25, polo=(-0.5, 0.2, -0.3)))
    vis(SETS["fajo_c"], True)
    adjuntar(SETS["fajo_c"], G.brazo["i"]["mano"], (0.0, 0.0, 0.10 * HM), R_PLANO_LADO)
    B.poner(pos=v3(x0 + 0.72, 0.0, 0.14), yaw=math.pi / 2 + 0.12, **parado(torso_rot=(0.0, 0, -0.1), cabeza_rot=(0, 0, -0.2)),
            mi=dict(w=p_ch + v3(0.17, 0.0, 0.0), dedos_w=(-1, 0, 0), palma_w=(0, 1, 0), curl=puño, pulgar=(0.03, 0.105, 0.115), polo=(0, -0.4, -1)),
            md=dict(p=(0.28, 0.02, 0.84), curl=0.3))
    A.poner(pos=v3(x0 - 3.4, 5.2, 0.14), yaw=-math.pi / 2 - 0.9, **parado(cabeza_rot=(0.5, 0, 0.2), torso_rot=(0.30, 0, 0)),
            md=dict(p=(0.24, 0.0, 0.70), curl=0.3), mi=dict(p=(-0.24, 0.0, 0.70), curl=0.3))
    cam = v3(x0 + 0.1, -3.4, 1.20)
    plan([vista(cam, (x0, 0.0, 1.32), 28, f=3.5)], CARTELES[5])
    ilumina(cam, "ambar", "amigo", "azul")
    SETS["amb_plaza"].data.energy = 120.0          # CUMPLIÓ: la plaza se entibia, todo dorado como en el 02
    SETS["calor"].hide_render = False


def m7_bucle(s=34.0):
    m1_plaza(s)
    plan(PLAN["vistas"], CARTELES[6])


MOMENTOS = [m1_plaza, m2_dividida, m3_celular, m4_calle, m5_puesto, m6_choque, m7_bucle]


def aplicar(t):
    """Función pura del tiempo: coloca TODO para el segundo t. Paso 2: animación continua (animar.py)."""
    import animar
    animar.aplicar(t, sys.modules[__name__])


def aplicar_claves(t):
    """Paso 1b: pose clave del momento del guion (la usan --storyboard y las hojas)."""
    t = t % DURACION
    for i, (a, b, _) in enumerate(GUION):
        if a <= t < b:
            break
    ocultar_todos()
    SETS["amb_plaza"].data.energy = 380.0
    SETS["calor"].hide_render = True
    N.ESCALA_LUZ[0] = 1.0
    MOMENTOS[i](t - a)
    bpy.context.view_layer.update()


def construir_todo():
    construir()
    set_plaza(); set_tienda(); set_calle(); set_puesto(); set_estudio()
    crear_personajes()
    SETS["fajo_a"] = O.fajo("fajo_a", n=7)
    SETS["fajo_b"] = O.fajo("fajo_b", n=7)
    SETS["fajo_c"] = O.fajo("fajo_c", n=7)
    SETS["abanico"] = O.abanico("abanico", n=4)
    for k in ("fajo_a", "fajo_b", "fajo_c"):
        SETS[k].scale = (1.6, 1.6, 1.6)
    SETS["bolsa"] = O.bolsa("bolsa")
    SETS["san_m"] = O.sanguche("san_m")
    SETS["zapa_m"] = O.zapatilla("zapa_m", escala=1.15)
    SETS["celular"] = O.Celular("celular")
    ocultar_todos()


# ----------------------------------------------------------------------------- render
def _post(canvas):
    canvas = N.bloom(canvas)
    if PLAN is not None:
        if PLAN["linea"]:
            canvas = N.linea_division(canvas, PLAN["linea"] * ARGS["escala"])
        for c in PLAN["carteles"]:
            fn = N.cartel if c[0] == "cartel" else N.rotulo
            canvas = fn(canvas, c[1], c[2], c[3], c[4], **(c[5] if len(c) > 5 else {}))
    return canvas


def renderizar(ruta):
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    t0 = time.time()
    esc = ARGS["escala"]
    if PLAN is None:
        for n, p in PJ.items():                       # cámara libre (hojas): cada personaje visible con su luz de rol
            f, r = N.LUCES_PJ[n]
            if p.cabeza.hide_render:
                f.hide_render = r.hide_render = True
            else:
                f.hide_render = r.hide_render = False
                N.luces_a(p, CAM_ACTUAL[0])
        sc.render.filepath = ruta
        bpy.ops.render.render(write_still=True)
        im = N.bloom(Image.open(ruta).convert("RGB"))
        im.save(ruta)
    else:
        canvas = Image.new("RGB", (int(round(FULL[0] * esc)), int(round(FULL[1] * esc))))
        tmp = ruta + ".tmp.png"
        for v in PLAN["vistas"]:
            camara(v["pos"], v["obj"], v["lente"], v["dof"])
            sc.render.resolution_x, sc.render.resolution_y = v["tam"]
            sc.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            canvas.paste(Image.open(tmp).convert("RGB"), (int(round(v["orig"][0] * esc)), int(round(v["orig"][1] * esc))))
        os.remove(tmp)
        sc.render.resolution_x, sc.render.resolution_y = FULL
        _post(canvas).save(ruta)
    seg = time.time() - t0
    print(f"[escena] {ruta} en {seg:.1f}s", flush=True)
    return seg


def principal():
    construir_todo()
    if ARGS["still"] is not None or ARGS["frame"] is not None:
        t = ARGS["still"] if ARGS["still"] is not None else ARGS["frame"] / FPS
        aplicar(t)
        renderizar(ARGS["out"] or os.path.join(AQUI, "prueba", f"cuadro-{t:.2f}.png"))
    elif ARGS["anim"]:
        carpeta = ARGS["carpeta"] or os.path.join(AQUI, "salida", "frames")
        os.makedirs(carpeta, exist_ok=True)
        fin = int(ARGS["end"]) if ARGS["end"] is not None else NCUADROS - 1
        for f in range(int(ARGS["start"]), fin + 1):
            ruta = os.path.join(carpeta, f"f_{f:04d}.png")
            if os.path.exists(ruta):
                continue
            aplicar(f / FPS)
            renderizar(ruta)
    elif ARGS["storyboard"]:
        carpeta = ARGS["carpeta"] or os.path.join(AQUI, "hoja", "celdas")
        for i, t in enumerate(T_CLAVE):
            if ARGS["solo"] and str(i + 1) not in ARGS["solo"].split(","):
                continue
            aplicar_claves(t)
            renderizar(os.path.join(carpeta, f"sb_{i + 1}.png"))
    elif ARGS["hoja"]:
        import hojas
        hojas.hacer(ARGS["hoja"], ARGS["carpeta"] or os.path.join(AQUI, "hoja", "celdas"), ARGS["solo"], sys.modules[__name__])
    else:
        print("Falta --still T, --frame N, --anim, --storyboard o --hoja NOMBRE")


if os.environ.get("ESCENA_SIN_PRINCIPAL") != "1":
    principal()
