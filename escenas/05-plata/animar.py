"""
Dos Mentes 05 — PASO 2: animación continua de los 7 momentos (36 s, 30 fps).

`aplicar(t, E)` es función pura de t (E = módulo escena.py). Nada de estado entre cuadros: todo sale de curvas por
tiempo (Hermite con tangentes Catmull-Rom, sin frenar en cada tecla), caminatas con la fase atada a la distancia
recorrida (los pies no patinan) y objetos que viajan de mano en mano mezclando matrices (nada se teletransporta).
Los carteles se tipean y entran con un golpe de brillo. El último cuadro empalma con el primero (bucle).
"""
import bpy, math
from mathutils import Vector, Matrix
from motor import *
import motor as _mo
import objetos as O
import noche as N

E = None
EX = {}          # objetos extra (se crean una vez)
FALTAS = _mo.FALTAS
BLANCO, AZUL, AMBAR = N.BLANCO, N.AZUL, N.AMBAR


def v3(*a):
    return Vector(a)


# ----------------------------------------------------------------------------- curvas
def cl(x, a=0.0, b=1.0):
    return min(b, max(a, x))


def seg(t, a, b):
    return cl((t - a) / (b - a))


def eio(u):
    return u * u * (3 - 2 * u)


def eo(u):
    return 1 - (1 - u) ** 3


def _l(v):
    if isinstance(v, (int, float)):
        return [float(v)]
    return [float(x) for x in v]


def _como(l, v):
    if isinstance(v, (int, float)):
        return l[0]
    if isinstance(v, Vector):
        return Vector(l)
    return tuple(l)


def kf(t, ks):
    """Interpola [(t, valor)] (número, tupla o Vector) con Hermite/Catmull-Rom: sin frenar en cada tecla, frena en los
    extremos y donde dos teclas seguidas valen lo mismo (manos quietas = quietas)."""
    n = len(ks)
    if t <= ks[0][0]:
        return ks[0][1]
    if t >= ks[-1][0]:
        return ks[-1][1]
    i = 0
    while not (ks[i][0] <= t <= ks[i + 1][0]):
        i += 1
    t0, v0 = ks[i]
    t1, v1 = ks[i + 1]
    h = t1 - t0
    if h <= 1e-9:
        return v1
    u = (t - t0) / h
    a, b = _l(v0), _l(v1)

    def tg(j):
        vj = _l(ks[j][1])
        if j == 0 or j == n - 1:
            return [0.0] * len(vj)
        vp, vn = _l(ks[j - 1][1]), _l(ks[j + 1][1])
        if vp == vj or vn == vj:
            return [0.0] * len(vj)
        dt = ks[j + 1][0] - ks[j - 1][0]
        return [(vn[k] - vp[k]) / dt for k in range(len(vj))]
    m0, m1 = tg(i), tg(i + 1)
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    out = [h00 * a[k] + h10 * h * m0[k] + h01 * b[k] + h11 * h * m1[k] for k in range(len(a))]
    return _como(out, v0)


def _curl8(c):
    if isinstance(c, (int, float)):
        return [float(c)] * 8
    out = []
    for x in c:
        if isinstance(x, (tuple, list)):
            out += [float(x[0]), float(x[1])]
        else:
            out += [float(x), float(x)]
    return out


def mano(t, ks):
    """Mano animada. ks = [(t, dict(w=muñeca mundo, d=dirección de dedos, p=normal de la palma, c=curl, po=polo, pu=pulgar))];
    lo que una tecla no dice lo hereda de la anterior. Devuelve el dict que entiende Personaje.poner."""
    cur, filas = {}, []
    for tt, d in ks:
        cur = {**cur, **d}
        filas.append((tt, dict(cur)))
    campos = {}
    for k in filas[0][1]:
        campos[k] = [(tt, (_curl8(f[k]) if k == "c" else (v3(*f[k]) if k in ("w", "d", "p", "po") else f[k]))) for tt, f in filas]
    out = {}
    for k, lst in campos.items():
        if k == "c":
            l = kf(t, [(tt, tuple(v)) for tt, v in lst])
            out["curl"] = tuple((l[2 * i], l[2 * i + 1]) for i in range(4))
        elif k == "w":
            out["w"] = kf(t, lst)
        elif k == "d":
            out["dedos_w"] = kf(t, lst)
        elif k == "p":
            out["palma_w"] = kf(t, lst)
        elif k == "po":
            out["polo"] = kf(t, lst)
        elif k == "pu":
            out["pulgar"] = kf(t, lst)
    return out


def mix(a, b, u):
    if isinstance(a, dict):
        return {k: (mix(a[k], b[k], u) if (k in a and k in b) else (a[k] if k in a else b[k])) for k in set(a) | set(b)}
    if isinstance(a, (tuple, list)):
        return tuple(mix(x, y, u) for x, y in zip(a, b))
    return a + (b - a) * u


# ----------------------------------------------------------------------------- caminos y marcha
class Camino:
    """Camino suave (Catmull-Rom) por puntos (x, y); `en(d)` da posición y rumbo a d metros del inicio."""

    def __init__(s, pts, n=120):
        P = [Vector((p[0], p[1], 0.0)) for p in pts]
        ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
        S = []
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            for k in range(n):
                u = k / n
                S.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
        S.append(P[-1])
        cum = [0.0]
        for a, b in zip(S, S[1:]):
            cum.append(cum[-1] + (b - a).length)
        s.S, s.cum, s.L = S, cum, cum[-1]

    def en(s, d):
        d = cl(d, 0.0, s.L)
        lo, hi = 0, len(s.cum) - 1
        while hi - lo > 1:
            m = (lo + hi) // 2
            if s.cum[m] <= d:
                lo = m
            else:
                hi = m
        seg_ = s.cum[hi] - s.cum[lo]
        u = 0.0 if seg_ < 1e-9 else (d - s.cum[lo]) / seg_
        pos = s.S[lo].lerp(s.S[hi], u)
        tg = (s.S[hi] - s.S[lo]).normalized()
        return pos, math.atan2(-tg.x, tg.y)


def perfil(t, t0, T, D, ta=0.35, td=0.4):
    """Distancia recorrida en el instante t: arranca en t0, dura T, recorre D, con rampas suaves de salida y llegada."""
    u = t - t0
    if u <= 0:
        return 0.0
    if u >= T:
        return D
    v = D / (T - (ta + td) / 2)
    if u < ta:
        return v * u * u / (2 * ta)
    if u < T - td:
        return v * ta / 2 + v * (u - ta)
    r = T - u
    return D - v * r * r / (2 * td)


def estar():
    """Pose parado completa (mismas claves que `caminata`, para poder mezclarlas)."""
    return dict(pelvis=(0, 0, 1.095), pelvis_rot=(0, 0, 0), torso_rot=(0.03, 0, 0), cabeza_rot=(0, 0, 0),
                pd=dict(p=(0.11, 0.0, ALTURA_TOBILLO), pitch=0.0, polo=(0.08, 1.0, 0.0)),
                pi=dict(p=(-0.11, 0.0, ALTURA_TOBILLO), pitch=0.0, polo=(-0.08, 1.0, 0.0)),
                md=dict(p=(0.26, 0.04, 0.86), curl=0.28, palma=(-1, 0.2, 0.0), polo=(0.5, -1.0, -0.2)),
                mi=dict(p=(-0.26, 0.04, 0.86), curl=0.28, palma=(1, 0.2, 0.0), polo=(-0.5, -1.0, -0.2)))


def marcha(cam, d, S=0.85, brazos=0.30, enc=0.0, ini=True, fin=True, z=0.0):
    """Pose de caminata en el metro d del camino. Fase = d·0,6/S: los pies apoyados no patinan. Se mezcla con parado
    al arrancar y al frenar. Devuelve (pos, rumbo, kw)."""
    pos, yaw = cam.en(d)
    kw = E.caminata(d * 0.6 / S, S=S, brazos=brazos, encorvado=enc)
    w = 1.0
    if ini:
        w = min(w, eio(cl(d / 0.5)))
    if fin:
        w = min(w, eio(cl((cam.L - d) / 0.5)))
    if w < 1.0:
        kw = mix(estar(), kw, w)
    pos = Vector((pos.x, pos.y, z))
    return pos, yaw, kw


def ang(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def mirar(pos, yaw, objetivo, lim=1.2, k=1.0):
    """Giro de cabeza (z) para mirar un punto del mundo, relativo al rumbo del cuerpo."""
    d = Vector(objetivo) - Vector(pos)
    h = math.atan2(-d.x, d.y)
    return cl(ang(h - yaw) * k, -lim, lim)


def rumbo(pos, objetivo):
    d = Vector(objetivo) - Vector(pos)
    return math.atan2(-d.x, d.y)


def P(n, pos, yaw, t=0.0, md=None, mi=None, cab=(0, 0, 0), lean=0.0, base=None, ph=0.0, **extra):
    """Pone al personaje n. `base` = kw de marcha (o parado). lean 0..1 = inclinarse hacia delante para llegar lejos.
    Respiración con período de 3 s (36 es múltiplo: el bucle cierra)."""
    kw = dict(base) if base is not None else estar()
    resp = 0.5 + 0.5 * math.sin(2 * math.pi * (t % 3.0) / 3.0 + ph)
    pel = kw["pelvis"]
    kw["pelvis"] = (pel[0], pel[1] + 0.20 * lean, pel[2] + 0.004 * resp - 0.03 * lean)
    tr = kw["torso_rot"]
    kw["torso_rot"] = (tr[0] + 0.32 * lean + 0.012 * resp, tr[1], tr[2])
    cr = kw["cabeza_rot"]
    kw["cabeza_rot"] = (cr[0] + cab[0] - 0.12 * lean, cr[1] + cab[1], cr[2] + cab[2])
    kw.update(extra)
    if md is not None:
        kw["md"] = md
    if mi is not None:
        kw["mi"] = mi
    E.PJ[n].poner(pos=pos, yaw=yaw, **kw)
    return E.PJ[n]


def lean_para(pos, objetivos, base=0.55, rango=0.30):
    """0..1 según qué tan lejos (en horizontal) están las manos del cuerpo."""
    m = 0.0
    for o in objetivos:
        d = Vector(o) - Vector(pos)
        d.z = 0
        m = max(m, d.length)
    return cl((m - base) / rango)


def H(n, lado):
    return E.PJ[n].brazo[lado]["mano"].raiz.matrix_world


def en_mano(n, lado, off=(0, 0.067, 0.04), yaw=0.0, tilt=0.0, esc=1.0):
    """Matriz mundo de un objeto sostenido por la mano: posición = mano + `off` (en el marco de la mano), orientación
    alineada al mundo (rumbo `yaw`, inclinación `tilt`): lo que se carga se queda derecho aunque la muñeca gire."""
    p = H(n, lado) @ Vector(off)
    R = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X')
    return Matrix.Translation(p) @ R @ Matrix.Scale(esc, 4)


def fijo(loc, yaw=0.0, tilt=0.0, esc=1.0):
    return Matrix.Translation(Vector(loc)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(tilt, 4, 'X') @ Matrix.Scale(esc, 4)


def poner_mundo(o, M, v=True):
    o.parent = None
    o.matrix_world = M
    E.vis(o, v)


def llevar(o, t, tramos, bl=0.20):
    """Objeto que viaja de portador en portador. tramos = [(t_ini, fn(t)->Matrix)]; al pasar de uno a otro se mezcla la
    matriz durante `bl` s (la mano lo agarra y la otra lo suelta: no hay salto). Antes del primer t_ini queda oculto."""
    if t < tramos[0][0]:
        E.vis(o, False)
        return None
    k = 0
    for i, (ti, _) in enumerate(tramos):
        if t >= ti:
            k = i
    M = tramos[k][1](t)
    if k > 0:
        u = (t - tramos[k][0]) / bl
        if u < 1.0:
            M = tramos[k - 1][1](t).lerp(M, eio(u))
    poner_mundo(o, M)
    return M


# ----------------------------------------------------------------------------- carteles con tipeo y golpe
def cartel(t, t0, txt, color, cy, tam, vel=16.0, kind="cartel", brillo0=1.0, osc=0.55):
    """Cartel que se tipea a `vel` letras/s desde t0 y, al completarse, pega un golpe de brillo que se apaga."""
    n = int((t - t0) * vel) + 1
    if t < t0:
        return (kind, txt, color, cy, tam, dict(n=0))
    n = min(n, len(txt))
    t_full = t0 + len(txt) / vel
    kw = dict(n=n)
    if osc:
        kw["oscurecer"] = osc
    b = brillo0 * (1.0 + 1.1 * math.exp(-max(0.0, t - t_full) * 7.0)) if n >= len(txt) else brillo0
    kw["brillo"] = b
    return (kind, txt, color, cy, tam, kw)


def cartel_fijo(txt, color, cy, tam, kind="cartel"):
    return (kind, txt, color, cy, tam, {})


# ----------------------------------------------------------------------------- preparación única
def preparar():
    if EX:
        return
    EX["listo"] = True
    EX["bill"] = [O.billete(f"x_bill{i}") for i in range(6)]
    mc = material("chispa", "#FFB020", emis=14.0)
    EX["chispa"] = esf("x_chispa", 1.0, mc, None, (0, 0, -50))
    EX["anillo"] = toro("x_anillo", 1.0, 0.035, mc, None, (0, 0, -50), (math.radians(90), 0, 0))
    EX["caja"] = O.caja_plata("pu_cajaN", loc=(0, 0, -50), llena=1.0)
    sp = E.SETS["puesto"]
    sp.scale = (1.0, 0.5, 1.0)                       # mostrador menos hondo: la vendedora llega a todo
    # hijos de san_m: posición final (local) de cada parte
    hijos = {}
    for o in E.SETS["san_m"].children:
        hijos[o.name] = o.matrix_basis.copy()
    EX["san_base"] = hijos
    EX["bandeja_base"] = {}
    for b in E.SETS["bandeja"]:
        b.scale = (0.86, 0.86, 0.86)
    EX["shoe_grey"] = bpy.data.objects.get("ti_estante_z11")


def ocultar_extras():
    for b in EX["bill"]:
        E.vis(b, False)
    for k in ("chispa", "anillo"):
        EX[k].hide_render = True
    E.vis(EX["caja"], False)
    E.vis(E.SETS["caja_plata"], False)
    for o in E.SETS["bandeja"]:
        E.vis(o, False)
    E.vis(E.SETS["san_m"], False)
    for o in E.SETS["san_m"].children:               # cada parte a su sitio (la animación las desplaza después)
        o.matrix_basis = EX["san_base"][o.name]
    E.vis(E.SETS["celular"].raiz, False)
    E.SETS["zapa_m"].hide_render = True


# ----------------------------------------------------------------------------- cámara
def cam_vista(pos, obj, lente, f=3.5, tam=None, orig=(0, 0), dof=True):
    if tam is None:
        return E.vista(pos, obj, lente, dof=dof, f=f)
    return E.vista(pos, obj, lente, dof=dof, tam=tam, orig=orig, f=f)


# =============================================================================== 1 · plaza (0–3 s) y bucle (33–36 s)
R_PL = {}      # reservado


def pos_plaza_g(x0):
    return v3(x0, 0.0, 0.0)


def _plaza_ancha(t, tau, x0, cartel_txt=True):
    """Plaza ancha: el amigo extiende los dos fajos, cada uno agarra el suyo. tau<0 = tramo final (bucle): el amigo
    espera con los fajos al pecho, idéntico al cuadro 0."""
    E.mostrar("azul", "amigo", "ambar")
    A, G, B = E.PJ["azul"], E.PJ["amigo"], E.PJ["ambar"]
    A.calzado("plano"); B.calzado("plano")
    pg, pa, pb = v3(x0, 0, 0), v3(x0 - 1.18, 0, 0), v3(x0 + 1.18, 0, 0)
    ya, yb, yg = -3 * math.pi / 4 + 0.2, 3 * math.pi / 4 - 0.2, math.pi
    rest_a = Matrix.Translation(pa) @ Matrix.Rotation(ya, 4, 'Z') @ v3(0.26, 0.04, 0.86)
    rest_b = Matrix.Translation(pb) @ Matrix.Rotation(yb, 4, 'Z') @ v3(-0.26, 0.04, 0.86)
    tt = max(tau, 0.0)
    # --- el amigo (md hacia el azul, mi hacia el ámbar): pecho -> atrás (anticipación) -> extiende -> suelta -> vuelve
    def amigo(sg):
        ks = [(0.0, dict(w=(x0 + sg * 0.30, -0.24, 1.12), d=(sg, -0.5, 0.0), p=(0, 0, 1), c=0.10, po=(sg * 0.3, -0.2, -1))),
              (0.40, dict(w=(x0 + sg * 0.30, -0.24, 1.12))),
              (0.62, dict(w=(x0 + sg * 0.22, -0.14, 1.07))),
              (0.98, dict(w=(x0 + sg * 0.64, -0.40, 1.26))),
              (1.30, dict(w=(x0 + sg * 0.66, -0.40, 1.27), c=0.10)),
              (1.55, dict(w=(x0 + sg * 0.40, -0.26, 1.10), c=0.30)),
              (2.00, dict(w=(x0 + sg * 0.30, -0.24, 1.10)))]
        return mano(tt, ks)
    mdg, mig = amigo(-1), amigo(1)
    # --- el azul y el ámbar estiran la mano por encima del fajo y lo agarran
    def recibe(sg, t0, rest):
        ks = [(0.0, dict(w=rest, d=(0, -0.3, -1), p=(-sg, 0.2, 0), c=0.30, po=(-sg * 0.4, -0.3, -1))),
              (t0, dict(w=rest)),
              (t0 + 0.40, dict(w=(x0 + sg * 0.78, -0.40, 1.42), d=(-sg, -0.2, -0.45), p=(0, -0.5, -1), c=0.15)),
              (t0 + 0.62, dict(w=(x0 + sg * 0.62, -0.40, 1.36), c=0.15)),
              (t0 + 0.74, dict(w=(x0 + sg * 0.62, -0.40, 1.34), c=0.75)),
              (t0 + 1.20, dict(w=(x0 + sg * 0.90, -0.30, 1.14), d=(-sg, -0.6, 0.0), p=(0, 0.2, 1), c=0.40)),
              (t0 + 1.60, dict(w=(x0 + sg * 0.80, -0.30, 1.12)))]
        return mano(tt, ks)
    ta0, tb0 = 0.62, 0.74
    ma, mb = recibe(-1, ta0, rest_a), recibe(1, tb0, rest_b)
    lean_a = cl(seg(tt, ta0, ta0 + 0.5)) * (1 - seg(tt, ta0 + 0.9, ta0 + 1.5))
    lean_b = cl(seg(tt, tb0, tb0 + 0.5)) * (1 - seg(tt, tb0 + 0.9, tb0 + 1.5))
    cab_g = (0.0, 0.0, 0.0)
    P("amigo", pg, yg, t, md=mdg, mi=mig, cab=cab_g, lean=0.0, ph=0.0)
    ra = E.PJ  # noqa
    # la cabeza del azul / ámbar sigue al amigo y luego a su plata
    # al final del video (tau<0) el azul y el ámbar llegan caminando a su lugar; en el cuadro 0 ya están ahí (bucle)
    for nm, sg, pf, yf, mn, ln, ph_, cabx in (("azul", -1, pa, ya, ma, lean_a, 1.0, seg(tt, 1.6, 2.0)), ("ambar", 1, pb, yb, mb, lean_b, 2.0, seg(tt, 1.7, 2.1))):
        cmn = Camino([(x0 + sg * 2.8, 0.0), (x0 + sg * 2.1, 0.0), (pf.x, 0.0)])
        d = perfil(tau, -3.0, 1.6, cmn.L, ta=0.3, td=0.5)
        llegado = d >= cmn.L - 1e-6
        pos_, yaw_, kw_ = marcha(cmn, d, S=0.80, brazos=0.26, ini=True, fin=True)
        yaw_ = yaw_ + ang(yf - yaw_) * eio(seg(d / cmn.L, 0.7, 1.0))
        mir = mirar(pos_, yaw_, v3(x0, 0, 1.7))
        kk = dict(md=mn) if (sg < 0 and llegado) else (dict(mi=mn) if llegado else {})
        P(nm, pos_ if not llegado else pf, yaw_ if not llegado else yf, t, base=(kw_ if not llegado else None),
          cab=(0.12 * cabx, 0, mir), lean=(ln if llegado else 0.0), ph=ph_, **kk)
    # --- los fajos: palma del amigo -> mano de cada uno (pasan de mano en mano)
    for k, lado, rec, nm, t0 in (("fajo_a", "d", "d", "azul", ta0), ("fajo_b", "i", "i", "ambar", tb0)):
        o = E.SETS[k]
        ya_ = 0.0
        sc = 1.25
        def en_g(tx, lado=lado):
            return en_mano("amigo", lado, off=(0, 0.075, 0.06), yaw=math.pi / 2 if lado == "d" else math.pi / 2, esc=sc)
        def en_x(tx, nm=nm, lado=lado):
            return en_mano(nm, lado, off=(0, 0.04, 0.09), yaw=math.pi / 2, tilt=0.35, esc=sc)
        llevar(o, tt, [(0.0, en_g), (t0 + 0.80, en_x)], bl=0.22)
    return A, G, B


def plaza_primer_plano(t, tau_c, x0):
    """Corte a primer plano: dos meñiques que se enganchan (promesa), y un par de sacudidas."""
    E.mostrar("azul", "amigo")
    A, G = E.PJ["azul"], E.PJ["amigo"]
    A.calzado("plano")
    yp, zA = -0.20, 1.10
    pm = (1.0, 1.0, 1.0, (0.0, 0.95))
    a = seg(tau_c, 0.0, 0.50)
    ap = eo(a)
    sh = 0.028 * math.sin(2 * math.pi * 2.0 * max(0.0, tau_c - 0.55)) * seg(tau_c, 0.55, 0.62) * (1 - seg(tau_c, 0.88, 1.0))
    ax = (x0 - 0.015) - 0.40 * (1 - ap)
    gx = (x0 + 0.020) + 0.42 * (1 - ap)
    az = zA + 0.06 * (1 - ap) + sh
    gz = zA - 0.028 + 0.06 * (1 - ap) + sh
    pA = v3(x0 - 0.50, 0, 0)
    P("azul", pA, -math.pi / 2 + 0.35, t, cab=(0, 0, 0.3),
      md=dict(w=v3(ax, yp + 0.0525 * HM, az), dedos_w=(0, 0, 1), palma_w=(1, 0, 0), curl=pm, pulgar=(0.0, 0.05, 0.12), polo=(0, -1, -0.5)),
      mi=dict(p=(-0.28, 0.02, 0.84), curl=0.3))
    P("amigo", v3(x0 + 0.50, 0, 0), math.pi / 2 + 0.25, t, cab=(0, 0, 0.3),
      mi=dict(w=v3(gx, yp - 0.0525 * HM, gz), dedos_w=(0, 0, 1), palma_w=(-1, 0, 0), curl=pm, pulgar=(0.0, 0.05, 0.12), polo=(0, -1, -0.5)),
      md=dict(p=(0.28, 0.02, 0.84), curl=0.3))
    E.N.ESCALA_LUZ[0] = 0.30
    p0 = v3(x0 + 0.03, -1.30 + 0.08 * tau_c, 1.22)
    return cam_vista(p0, v3(x0, yp, 1.14), 85, dof=((v3(x0, yp, 1.14) - p0).length, 9.0))


def m1(t):
    x0 = E.X_PLAZA
    if t < 2.0:
        _plaza_ancha(t, t, x0)
        cam = v3(x0 + 0.1, -2.70 + 0.06 * t, 1.20)
        E.plan([cam_vista(cam, v3(x0, 0, 1.30), 28)], [cartel_fijo("LA MISMA PLATA", N.BLANCO, 0.105, 112)])
        E.ilumina(cam, "azul", "amigo", "ambar")
    else:
        v = plaza_primer_plano(t, t - 2.0, x0)
        E.plan([v], [cartel_fijo("LA MISMA PLATA", N.BLANCO, 0.105, 112)])
        E.ilumina(v["pos"], "azul", "amigo")


def m7(t):
    """Bucle: el amigo espera con los fajos al pecho; la cámara avanza igual que en el cuadro 0 (empalme limpio)."""
    x0 = E.X_PLAZA
    tau = t - 36.0
    _plaza_ancha(t, tau, x0)
    cam = v3(x0 + 0.1, -2.70 + 0.06 * tau, 1.20)
    E.plan([cam_vista(cam, v3(x0, 0, 1.30), 28)], [cartel_fijo("LA MISMA PLATA", N.BLANCO, 0.105, 112)])
    E.ilumina(cam, "azul", "amigo", "ambar")


# =============================================================================== 6 · CUMPLIÓ (27–33 s)
def m6(t):
    x0 = E.X_PLAZA
    tau = t - 27.0 + 0.9           # corte en acción: el ámbar ya viene caminando
    E.mostrar("ambar", "amigo", "azul")
    B, G, A = E.PJ["ambar"], E.PJ["amigo"], E.PJ["azul"]
    B.calzado("plano"); A.calzado("zapa")
    pg = v3(x0 - 0.62, 0, 0)
    yg = -math.pi / 2 - 0.10
    pbF = v3(x0 + 0.62, 0, 0)
    ybF = math.pi / 2 + 0.10
    MG = Matrix.Translation(pg) @ Matrix.Rotation(yg, 4, 'Z')
    MB = Matrix.Translation(pbF) @ Matrix.Rotation(ybF, 4, 'Z')
    Gl = lambda x, y, z: MG @ v3(x, y, z)
    Bl = lambda x, y, z: MB @ v3(x, y, z)
    # ---- luz que se entibia en CUMPLIÓ
    uw = eio(seg(tau, 1.7, 2.6))
    E.SETS["amb_plaza"].data.energy = 380.0 - 260.0 * uw
    E.SETS["calor"].hide_render = uw < 0.01
    E.SETS["calor"].data.energy = 700.0 * uw
    # ---- el ámbar llega caminando con los fajos en las palmas
    cam_b = Camino([(x0 + 2.7, 0.30), (x0 + 1.6, 0.12), (pbF.x, pbF.y)])
    T_LL = 1.9
    d = perfil(tau, 0.0, T_LL, cam_b.L, ta=0.3, td=0.55)
    carry_d = dict(p=(0.15, 0.30, 1.0), dedos=(0, 1, 0), palma=(0, 0, 1), curl=0.1, polo=(0.4, -0.3, -1))
    carry_i = dict(p=(-0.15, 0.30, 1.0), dedos=(0, 1, 0), palma=(0, 0, 1), curl=0.1, polo=(-0.4, -0.3, -1))
    pos_b, yaw_b, kwb = marcha(cam_b, d, S=0.82, brazos=0.0, ini=False, fin=True)
    yaw_b = yaw_b + 0.10 * eio(seg(d / cam_b.L, 0.6, 1.0))
    carry_w = dict(md=(Bl(0.15, 0.30, 1.0), None), mi=(Bl(-0.15, 0.30, 1.0), None))
    # manos del ámbar después de llegar: entrega, retira, y choque de puño con la mano de la cámara (mi)
    puno = (1, 1, 1, 1)
    ta = T_LL
    p_ch = v3(x0, -0.05, 1.25)
    tc = 4.02
    carry_a = dict(w=Bl(-0.15, 0.30, 1.0), d=MB.to_3x3() @ v3(0, 1, 0), p=v3(0, 0, 1), c=0.1, po=(-0.4, -0.3, -1))
    carry_b = dict(w=Bl(0.15, 0.30, 1.0), d=MB.to_3x3() @ v3(0, 1, 0), p=v3(0, 0, 1), c=0.1, po=(0.4, -0.3, -1))
    mi_b = mano(tau, [(ta, carry_a),
                      (ta + 0.30, dict(w=(x0 + 0.04, -0.17, 1.14), d=(-1, 0, 0), c=0.1)),
                      (ta + 0.62, dict(w=(x0 + 0.04, -0.17, 1.14))),
                      (ta + 0.95, dict(w=Bl(-0.15, 0.30, 1.0))),
                      (3.20, dict(w=Bl(-0.26, 0.04, 0.86), d=MB.to_3x3() @ v3(0, 0, -1), p=MB.to_3x3() @ v3(1, 0.2, 0), c=0.3)),
                      (3.38, dict(w=(x0 + 0.52, -0.10, 1.06), d=(-1, 0, 0), p=(0, 1, 0), c=puno, pu=(0.03, 0.095, 0.09), po=(0, -0.4, -1))),
                      (tc, dict(w=p_ch + v3(0.17, 0.0, 0.0))),
                      (tc + 0.10, dict(w=p_ch + v3(0.22, 0.0, 0.0))),
                      (4.9, dict(w=p_ch + v3(0.24, 0.0, -0.02))),
                      (5.4, dict(w=Bl(-0.26, 0.04, 0.86), d=MB.to_3x3() @ v3(0, 0, -1), p=MB.to_3x3() @ v3(1, 0.2, 0), c=0.3))])
    md_b = mano(tau, [(ta, carry_b),
                      (ta + 0.34, dict(w=(x0 + 0.04, 0.20, 1.14), d=(-1, 0, 0), c=0.1)),
                      (ta + 0.66, dict(w=(x0 + 0.04, 0.20, 1.14))),
                      (ta + 1.0, dict(w=Bl(0.28, 0.02, 0.84), d=MB.to_3x3() @ v3(0, 0, -1), p=MB.to_3x3() @ v3(-1, 0.2, 0), c=0.3, po=(0.5, -1, -0.2)))])
    # ---- el amigo
    def g_mano(sg, quien):
        rest = dict(w=Gl(sg * 0.26, 0.04, 0.86), d=MG.to_3x3() @ v3(0, 0, -1), p=MG.to_3x3() @ v3(-sg, 0.2, 0), c=0.28, po=(sg * 0.5, -1, -0.2))
        y_ = -0.17 if sg > 0 else 0.20
        recibe = dict(w=(x0 - 0.04, y_, 1.12), d=(1, 0, 0.0), p=(0, 0, 1), c=0.12, po=(sg * 0.4, -0.3, -1))
        bolsillo = dict(w=Gl(sg * 0.24, 0.07, 0.92), d=MG.to_3x3() @ v3(0, 0.3, -1), p=MG.to_3x3() @ v3(-sg, 0.2, 0), c=0.4)
        ks = [(0.0, rest), (1.35, rest), (1.9, recibe), (2.40, recibe), (2.75, bolsillo), (2.95, bolsillo), (3.35, rest)]
        if quien == "d":
            ks += [(3.45, dict(w=(x0 - 0.55, -0.10, 1.05), d=(1, 0, 0), p=(0, 1, 0), c=puno, pu=(-0.03, 0.095, 0.09), po=(0, -0.4, -1))),
                   (tc, dict(w=p_ch + v3(-0.17, 0.0, 0.0))),
                   (tc + 0.10, dict(w=p_ch + v3(-0.22, 0.0, 0.0))),
                   (4.9, dict(w=p_ch + v3(-0.24, 0.0, -0.02))),
                   (5.4, rest)]
        return mano(tau, ks)
    md_g, mi_g = g_mano(-1, "d"), g_mano(1, "i")
    # g_mano(-1) -> sg=-1 corresponde a la derecha del amigo? (el amigo mira +x: su derecha es -y = hacia la cámara)
    md_g = g_mano(1, "d")
    mi_g = g_mano(-1, "i")
    # cabezas
    azul_p = v3(x0 - 1.7, 4.4, 1.6)
    mira_az = eio(seg(tau, 4.75, 5.3))
    lg = mirar(pg, yg, pos_b + v3(0, 0, 1.7) if tau < T_LL else v3(x0 + 0.62, 0, 1.7)) * (1 - mira_az) + mirar(pg, yg, azul_p) * mira_az
    P("amigo", pg, yg, t, md=md_g, mi=mi_g, cab=(0.10 * seg(tau, 2.0, 2.4) * (1 - seg(tau, 2.6, 3.0)), 0, lg), lean=0.35 * eio(seg(tau, 1.5, 1.9)) * (1 - seg(tau, 2.5, 2.9)))
    if tau < T_LL:
        P("ambar", pos_b, yaw_b, t, base=kwb, md=carry_d, mi=carry_i, cab=(0, 0, mirar(pos_b, yaw_b, v3(pg.x, 0, 1.7))))
    else:
        P("ambar", pbF, ybF, t, md=md_b, mi=mi_b, cab=(0.08 * seg(tau, 2.8, 3.2), 0, mirar(pbF, ybF, v3(x0 - 0.62, 0, 1.7)) * (1 - mira_az) + mirar(pbF, ybF, azul_p) * mira_az),
          lean=0.30 * eio(seg(tau, T_LL, T_LL + 0.3)) * (1 - seg(tau, T_LL + 0.95, T_LL + 1.3)))
    # el azul, chiquito al fondo: mira, y al final baja la cabeza
    pz = v3(x0 - 1.7, 4.4, 0.14)
    yz = -math.pi / 2 - 0.5
    baja = eio(seg(tau, 5.9, 6.7))
    P("azul", pz, yz, t, cab=(0.50 * baja + 0.10, 0, mirar(pz, yz, v3(x0, 0, 1.6)) * (1 - 0.4 * baja)),
      torso_rot=(0.16 + 0.34 * baja, 0, 0), md=dict(p=(0.24, 0.05, 0.80), curl=0.3), mi=dict(p=(-0.24, 0.05, 0.80), curl=0.3), ph=1.5)
    # ---- fajos (dos): mano del ámbar -> palma del amigo -> bolsillo (se achican al entrar)
    for k, nb, lb, gl, sgp in (("fajo_a", "ambar", "i", "d", 1), ("fajo_b", "ambar", "d", "i", -1)):
        o = E.SETS[k]
        if tau >= 2.9:
            E.vis(o, False)
            continue
        t_tr = ta + (0.30 if k == "fajo_a" else 0.34) + 0.18
        sc = 1.25 * (1.0 - 0.6 * eio(seg(tau, 2.62, 2.9)))
        def en_b(tx, nb=nb, lb=lb):
            return en_mano(nb, lb, off=(0, 0.075, 0.06), yaw=math.pi / 2, esc=1.25)
        def en_g(tx, gl=gl, sc=sc):
            return en_mano("amigo", gl, off=(0, 0.075, 0.06), yaw=math.pi / 2, esc=sc)
        llevar(o, tau, [(0.0, en_b), (t_tr, en_g)], bl=0.22)
    # ---- chispa ámbar en el choque
    if tc - 0.02 <= tau <= tc + 0.5:
        u = (tau - tc) / 0.40
        r = 0.05 * math.sin(math.pi * cl(u * 0.9 + 0.1)) ** 0.7 if u < 1 else 0
        EX["chispa"].hide_render = False
        EX["chispa"].location = p_ch + v3(0, -0.07, 0.01)
        EX["chispa"].scale = (max(r, 1e-4),) * 3
        EX["anillo"].hide_render = False
        EX["anillo"].location = p_ch + v3(0, -0.08, 0.01)
        ra = 0.05 + 0.34 * eo(cl(u))
        EX["anillo"].scale = (ra, ra, ra)
        EX["anillo"].rotation_euler = (math.radians(90), 0, 0)
    # ---- cámara: ancha con avance lento; corte al primer plano del puño justo antes del contacto
    cartel_ = [cartel(tau, 1.9, "CUMPLIÓ", AMBAR, 0.095, 170, vel=14.0)]
    if 3.80 <= tau < 4.75:
        k = tau - 3.80
        cp = v3(x0 + 0.10, -1.55 + 0.14 * k, 1.45)
        v = cam_vista(cp, v3(x0, -0.05, 1.27), 52, dof=(1.45, 3.4))
        E.N.ESCALA_LUZ[0] = 0.34
        E.plan([v], cartel_)
        E.ilumina(cp, "ambar", "amigo")
    elif tau >= 5.6:                                           # el azul, chiquito y solo, baja la cabeza
        cp = v3(x0 - 1.0, 0.5, 1.45)
        E.plan([cam_vista(cp, v3(x0 - 1.7, 4.4, 1.30), 50, f=4.0)], cartel_)
        E.ilumina(cp, "azul")
    else:
        cp = v3(x0 + 0.1, -2.6 + 0.08 * (tau - 0.9), 1.20)
        E.plan([cam_vista(cp, v3(x0, 0, 1.32), 28)], cartel_)
        E.ilumina(cp, "ambar", "amigo", "azul")


# =============================================================================== 4 · calle (16–19 s)
def m4(t):
    x0 = E.X_CALLE
    tau = t - 16.0
    E.mostrar("azul", "amigo")
    A, G = E.PJ["azul"], E.PJ["amigo"]
    A.calzado("zapa")
    cam_a = Camino([(x0 - 2.6, -2.8), (x0 + 0.2, -1.9), (x0 + 3.4, -1.0)])
    d = 0.9 + 1.75 * tau                                   # ya viene caminando: no arranca de cero
    pos, yaw, kw = marcha(cam_a, d, S=0.95, brazos=0.26, ini=False, fin=False)
    giro = -0.9 * eo(seg(tau, 0.55, 1.05))                 # gira la cabeza para el otro lado (hacia la cámara)
    P("azul", pos, yaw, t, base=kw, cab=(0, 0, giro))
    E.vis(E.SETS["bolsa"], True)
    # bolsa colgando de la mano derecha: se balancea con la marcha, derecha como un péndulo
    grip = H("azul", "d") @ Vector((0, 0, 0.10 * HM))
    sw = 0.22 * math.sin(2 * math.pi * d * 0.6 / 0.95 + 0.4)
    Mb = Matrix.Translation(grip) @ Matrix.Rotation(sw, 4, 'Y') @ Matrix.Translation((0, 0, -0.46))
    poner_mundo(E.SETS["bolsa"], Mb)
    # el amigo (vereda de enfrente): lo ve, levanta la mano, saluda, y al no tener respuesta baja el brazo
    pg = v3(x0 - 0.2, 3.7, 0.14)
    yg = math.pi - 0.35
    xs = pg.x + 0.25
    onda = 0.16 * math.sin(2 * math.pi * 2.6 * max(0.0, tau - 0.75)) * seg(tau, 0.75, 0.95) * (1 - seg(tau, 1.9, 2.3))
    mi = mano(tau, [(0.0, dict(w=Matrix.Translation(pg) @ Matrix.Rotation(yg, 4, 'Z') @ v3(-0.26, 0.04, 0.86), d=(0, 0, -1), p=(1, 0.2, 0), c=0.3, po=(-0.5, -1, -0.2))),
                    (0.22, dict(w=(xs, 3.55, 1.15), d=(0.1, 0.0, -1))),                          # anticipación: baja un poco
                    (0.70, dict(w=(xs + 0.05, 3.7, 2.28), d=(0.2, 0.0, 1), p=(0.2, -1, 0), c=0.08, po=(0.6, -0.3, 0.2))),
                    (1.95, dict(w=(xs + 0.05, 3.7, 2.28))),
                    (2.70, dict(w=(xs + 0.02, 3.65, 1.30), d=(0.1, 0, -0.6), c=0.25)),
                    (3.0, dict(w=Matrix.Translation(pg) @ Matrix.Rotation(yg, 4, 'Z') @ v3(-0.26, 0.04, 0.86), d=(0, 0, -1), p=(1, 0.2, 0), c=0.3, po=(-0.5, -1, -0.2)))])
    mi["w"] = mi["w"] + v3(onda, 0, 0)
    baja = eio(seg(tau, 2.0, 2.8))
    P("amigo", pg, yg, t, mi=mi, md=dict(p=(0.27, 0.04, 0.85), curl=0.25),
      cab=(0.35 * baja, 0, mirar(pg, yg, pos + v3(0, 0, 1.0))), torso_rot=(0.03 + 0.18 * baja, 0, 0), ph=2.0)
    cp = v3(x0 - 0.5 + 1.0 * tau / 3.0, -5.7 + 0.3 * tau / 3.0, 1.6)
    ob = v3(x0 + 0.1 + 0.9 * tau / 3.0, -1.0, 1.4)
    E.plan([cam_vista(cp, ob, 30, f=5.0)], [cartel(tau, 0.85, "NI LO MIRA", AZUL, 0.095, 120)])
    E.ilumina(cp, "azul", "amigo")


# =============================================================================== puesto: servicio de mostrador (momentos 2 y 5)
def puesto_vars():
    xp = E.X_PUESTO
    V = dict(xp=xp, V0=v3(xp - 0.45, 2.62, 0), yV=math.pi - 0.08, C=v3(xp - 0.85, 1.25, 0), Bp=v3(xp - 0.98, 1.98, 1.22),
             Sp=v3(xp - 0.66, 1.98, 1.17), BOX=v3(xp - 1.0, 2.25, 1.01))
    V["MV"] = Matrix.Translation(V["V0"]) @ Matrix.Rotation(V["yV"], 4, 'Z')
    return V


def caja_llena(V, n):
    """La caja de plata (nueva, con 12 billetes y 10 monedas escondidos de más): se muestran n billetes."""
    root = EX["caja"]
    poner_mundo(root, fijo(V["BOX"], math.radians(-8)))
    O.REG["pu_cajaN.tapa"].rotation_euler.x = -math.radians(100)
    for i in range(12):
        o = bpy.data.objects.get(f"pu_cajaN_b{i}")
        if o:
            o.hide_render = i >= n
    for i in range(10):
        o = bpy.data.objects.get(f"pu_cajaN_m{i}")
        if o:
            o.hide_render = i >= int(2 + (n - 3) * 0.9)


def cliente_xy(V, s, T_arr=2.6, T_sal=3.3):
    """Caminos de un cliente que se detiene en el punto de atención en el instante s y se va 1,95 s después."""
    xp = V["xp"]
    ca = Camino([(xp - 5.2, 1.25), (xp - 3.0, 1.25), (V["C"].x, 1.25)])
    cs = Camino([(V["C"].x, 1.25), (V["C"].x + 0.6, 0.75), (xp + 1.8, 0.45), (xp + 5.5, 0.45)])
    return ca, cs


def servicio(tau, V, ventas, vmd_pre=(), vmi_pre=(), sand_pos=None, cab_pend=None):
    """Mostrador completo. ventas = [dict(n=nombre del cliente, s=instante en que se detiene, san=objeto sándwich,
    san_t=(posición donde está el sándwich, instante en que ella lo toma), bill=índice de billete)].
    Devuelve (lean, posiciones) y pone vendedora, clientes, billetes, sándwiches y la caja de plata."""
    xp, V0, yV, C, Bp, Sp, BOX, MV = V["xp"], V["V0"], V["yV"], V["C"], V["Bp"], V["Sp"], V["BOX"], V["MV"]
    rest_md = MV @ v3(-0.26, 0.10, 0.92)
    rest_mi = MV @ v3(0.26, 0.10, 0.92)
    kmd = list(vmd_pre) or [(0.0, dict(w=rest_md, d=MV.to_3x3() @ v3(0, 1, -0.4), p=MV.to_3x3() @ v3(0, 0.3, 1), c=0.25, po=(-0.5, -0.6, -0.5)))]
    kmi = list(vmi_pre) or [(0.0, dict(w=rest_mi, d=MV.to_3x3() @ v3(0, 1, -0.4), p=MV.to_3x3() @ v3(0, 0.3, 1), c=0.25, po=(0.5, -0.6, -0.5)))]
    n_bill = 3
    for vt in ventas:
        s = vt["s"]
        pos_san, t_san = vt["san_t"]
        gr = pos_san + v3(0, 0, 0.13)
        kmd += [(s + 0.12, dict(w=rest_md)), (s + 0.52, dict(w=Bp + v3(0.04, 0.12, 0.0), d=(-0.2, -1, 0), p=(0, 0, 1), c=0.1)),
                (s + 0.82, dict(w=Bp + v3(0.04, 0.12, 0.0), c=0.7)), (s + 1.18, dict(w=BOX + v3(0, 0, 0.30), d=(0, -1, -0.3))),
                (s + 1.32, dict(w=BOX + v3(0, 0, 0.30), c=0.1)), (s + 1.70, dict(w=rest_md, c=0.25))]
        kmi += [(t_san - 0.55, dict(w=rest_mi)), (t_san - 0.05, dict(w=gr, d=(0, -1, -0.3), p=(0, 0, 1), c=0.1)),
                (t_san + 0.10, dict(w=gr, c=0.6)), (t_san + 0.45, dict(w=Sp + v3(0.02, 0.0, 0.03), d=(-0.2, -1, 0), c=0.6)),
                (t_san + 0.70, dict(w=Sp + v3(0.02, 0.0, 0.03), c=0.1)), (t_san + 1.05, dict(w=rest_mi, c=0.25))]
    md = mano(tau, [(a, {**b}) for a, b in sorted(kmd, key=lambda k: k[0])])
    mi = mano(tau, [(a, {**b}) for a, b in sorted(kmi, key=lambda k: k[0])])
    lean = lean_para(V0, [md["w"], mi["w"]], base=0.52, rango=0.32)
    # ---- clientes y objetos
    cab_v = (0, 0, 0)
    foco = None
    for i, vt in enumerate(ventas):
        s = vt["s"]
        nm = vt["n"]
        ca, cs = cliente_xy(V, s)
        t_arr = 2.6
        t_sal = s + 1.95
        E.mostrar(nm)
        E.PJ[nm].calzado("plano")
        bill = EX["bill"][vt["bill"]]
        hold_mi_l = (-0.18, 0.26, 0.96)
        if tau < t_sal:
            d = perfil(tau, s - t_arr, t_arr, ca.L, ta=0.4, td=0.65)
            pos, yaw, kw = marcha(ca, d, S=0.80, brazos=0.22, ini=False, fin=True)
            yaw = -math.pi / 2 + (math.pi / 2) * eio(seg(tau, s - 0.55, s - 0.02))
            if tau < s:
                md_c = None
                mi_c = dict(p=hold_mi_l, dedos=(0, 1, 0.2), palma=(0.3, 0.2, 1), curl=0.5, polo=(-0.5, -0.4, -0.6))
            else:
                u = tau - s
                Cw = lambda x, y, z: C + v3(x, y, z)
                mi_c = mano(u, [(0.0, dict(w=Cw(*hold_mi_l), d=(0, 1, 0.2), p=(0.3, 0.2, 1), c=0.5, po=(-0.5, -0.4, -0.6))),
                                (0.30, dict(w=Bp + v3(-0.03, -0.10, 0.0), d=(0.3, 1, 0.1), c=0.5)), (0.62, dict(w=Bp + v3(-0.03, -0.10, 0.0), c=0.5)),
                                (0.50, dict(c=0.12)), (0.95, dict(w=Cw(-0.26, 0.04, 0.86), d=(0, 0, -1), p=(1, 0.2, 0), c=0.28))])
                md_c = mano(u, [(0.0, dict(w=Cw(0.26, 0.04, 0.86), d=(0, 0, -1), p=(-1, 0.2, 0), c=0.28, po=(0.5, -1, -0.2))),
                                (1.10, dict(w=Cw(0.26, 0.04, 0.86))), (1.50, dict(w=Sp + v3(0.0, -0.08, -0.02), d=(0, 1, 0.1), p=(0, 0, 1), c=0.15)),
                                (1.68, dict(w=Sp + v3(0.0, -0.08, -0.02), c=0.15)), (1.90, dict(w=Cw(0.16, 0.30, 1.10), d=(0, 1, 0), p=(0, 0, 1), c=0.5))])
            ln = lean_para(pos, [(mi_c["w"] if "w" in mi_c else pos), (md_c["w"] if md_c else pos)], base=0.50, rango=0.35) if tau >= s else 0.0
            P(nm, pos, yaw, tau, base=kw, md=md_c, mi=mi_c, lean=ln, cab=(0, 0, 0), ph=1.0 + i)
        else:
            d = perfil(tau, t_sal, 3.2, cs.L, ta=0.30, td=0.5)
            pos, yaw, kw = marcha(cs, d, S=0.80, brazos=0.20, ini=True, fin=False)
            yaw = yaw if d > 0.4 else (-math.pi / 2) * eio(seg(tau, t_sal - 0.2, t_sal + 0.3))
            carry = dict(p=(0.16, 0.28, 1.08), dedos=(0, 1, 0), palma=(0, 0, 1), curl=0.5, polo=(0.4, -0.3, -1))
            P(nm, pos, yaw, tau, base=kw, md=carry, cab=(0, 0, 0), ph=1.0 + i)
            if pos.x > xp + 4.8:
                E.PJ[nm].ocultar(True)
        # billete: mano izquierda del cliente -> mano derecha de la vendedora -> caja
        if tau >= s - t_arr:
            en_c = lambda tx, nm=nm: en_mano(nm, "i", off=(0, 0.01, 0.11), yaw=0.2, tilt=-1.0, esc=0.62)
            en_v = lambda tx: en_mano("ambar", "d", off=(0, 0.01, 0.11), yaw=0.2, tilt=-1.0, esc=0.62)
            en_x = lambda tx: fijo(BOX + v3(0, 0, 0.19), math.radians(-8), 0.0, 0.62)
            if tau < s + 1.26:
                llevar(bill, tau, [(0.0, en_c), (s + 0.60, en_v), (s + 1.15, en_x)], bl=0.20)
        if tau >= s + 1.28:
            n_bill += 4
        # sándwich: bandeja/tablero -> mano izquierda de la vendedora -> mano derecha del cliente
        san = vt["san"]
        pos_san, t_san = vt["san_t"]
        sc = vt.get("san_esc", 1.0)
        mk_static = lambda tx, p=pos_san, sc=sc: fijo(p, 0.0, 0.0, sc)
        mk_v = lambda tx, sc=sc: en_mano("ambar", "i", off=(0, 0.07, 0.05), yaw=0.0, esc=sc)
        mk_c = lambda tx, nm=nm, sc=sc: en_mano(nm, "d", off=(0, 0.07, 0.05), yaw=0.0, esc=sc)
        llevar(san, tau, [(-99.0, mk_static), (t_san, mk_v), (t_san + 0.62, mk_c)], bl=0.24)
    # ---- vendedora
    cercano = None
    for vt in ventas:
        if vt["s"] - 0.3 <= tau <= vt["s"] + 2.2:
            cercano = vt
    foco_p = V["C"] + v3(0, 0, 1.6)
    P("ambar", V0, yV, tau, md=md, mi=mi, lean=lean, cab=(0.10 * lean, 0, mirar(V0, yV, foco_p, k=0.8)), ph=0.5)
    caja_llena(V, n_bill)
    return lean


# =============================================================================== 5 · puesto en grande (19–27 s)
def m5(t):
    tau = t - 19.0
    V = puesto_vars()
    xp = V["xp"]
    E.mostrar("ambar")
    E.PJ["ambar"].calzado("plano")
    E.vis(E.SETS["puesto"], True)
    ventas = []
    for i, (nm, s) in enumerate((("rosa", 0.9), ("coral", 3.5), ("blanco", 6.1))):
        san = E.SETS["bandeja"][i]
        ventas.append(dict(n=nm, s=s, san=san, san_t=(v3(xp - 0.40, 2.40 - 0.15 * i, 1.02), s + 1.0), bill=i, san_esc=0.86))
    servicio(tau, V, ventas)
    cp = v3(xp, -1.2 + 0.5 * tau / 8.0, 1.75)
    ob = v3(xp - 0.1 - 0.15 * tau / 8.0, 2.0, 1.55)
    E.plan([cam_vista(cp, ob, 24, f=3.5)], [cartel(tau, 0.1, "LA HIZO CRECER", AMBAR, 0.095, 112),
                                           cartel(tau, 0.65, "VENDE SÁNGUCHES", AMBAR, 0.145, 46, vel=22.0, kind="rotulo")])
    E.ilumina(cp, "ambar", "rosa", "coral", "blanco")


# =============================================================================== 3 · celular POV (10–16 s)
MENSAJES = [(0.9, 0), (1.9, 1), (3.0, 2), (4.2, 3)]       # (instante en que aparece, pantalla)
TOQUES = (0.66, 2.78, 3.94)                                # el pulgar toca el teclado


def m3(t):
    from bpy_extras.object_utils import world_to_camera_view
    tau = t - 10.0
    x0 = E.X_PLAZA
    E.mostrar("amigo")
    G = E.PJ["amigo"]
    ph = E.SETS["celular"]
    E.vis(ph.raiz, True)
    if "cel_base" not in EX:
        EX["cel_base"] = {o.name: o.location.copy() for g in ph.grupos for o in g}
    # qué pantalla se ve y cuánto lleva apareciendo (los mensajes entran subiendo con un golpe)
    vis_i, t_ap = -1, 0.0
    for ta, i in MENSAJES:
        if tau >= ta:
            vis_i, t_ap = i, ta
    ph.mostrar(vis_i)
    if vis_i >= 0:
        u = eo(seg(tau, t_ap, t_ap + 0.20))
        for o in ph.grupos[vis_i]:
            b = EX["cel_base"][o.name]
            o.location = Vector((b.x, b.y - 0.045 * (1 - u), b.z))
    for o in E.SETS["bokeh"]:
        o.hide_render = False
    ojos = v3(x0 + 0.02, 0.22, 1.80)
    centro = v3(x0 + 0.05, 0.58, 1.56)
    palma = (ojos - centro).normalized()
    dedos = v3(1.0, 0.0, 0.0)
    Rm = mat_rot(dedos, palma)
    sube = 0.55 * (1 - eo(seg(tau, 0.0, 0.50)))                       # la mano sube desde abajo
    temblor = 0.004 * math.sin(2 * math.pi * 8.0 * tau) * seg(tau, 4.2, 4.6)
    centro_t = centro + v3(0.0, 0.0, -sube + temblor) + v3(0.0, -0.06 * sube, 0)
    muneca = centro_t - Rm @ v3(0.0, 0.062 * HM, 0.05)
    # pulgar: toca la pantalla (hacia la palma), con un par de teclas distintas
    tq = 0.0
    for tt in TOQUES:
        tq = max(tq, math.exp(-((tau - tt) / 0.07) ** 2))
    pul = (-0.165 + 0.03 * math.sin(tau * 7.0) * tq, 0.086 - 0.050 * tq, 0.06 + 0.02 * math.sin(tau * 5.0) * tq)
    P("amigo", v3(x0, 0.0, 0.0), 0.0, t, md=dict(w=muneca, dedos_w=dedos, palma_w=palma, curl=((0.55, 0.3),) * 4, pulgar=pul, polo=(1.0, -0.2, -0.6)),
      mi=dict(p=(-0.26, 0.03, 0.84), curl=0.3), cab=(0.5, 0, 0), torso_rot=(0.10, 0, 0))
    for o in bpy.data.objects:                              # la otra mano no entra en el POV
        if o.name.startswith("amigo_i_") or o.name in ("amigo_bri", "amigo_ani"):
            o.hide_render = True
    E.vis(G.cabeza, False)
    E.adjuntar(ph.raiz, G.brazo["d"]["mano"], (0.0, 0.062 * HM, 0.05), E.R_PLANO_PALMA)
    ojos = ojos + v3(0.006 * math.sin(tau * 1.3), 0.0, 0.006 * math.sin(tau * 0.9))
    ojos = ojos + (centro - ojos) * (0.10 * seg(tau, 0.0, 6.0))      # avance lento hacia el celular
    N.ESCALA_LUZ[0] = 0.55
    bpy.context.view_layer.update()
    cen = ph.raiz.matrix_world.translation.copy()
    E.plan([cam_vista(ojos, cen, 40, dof=((cen - ojos).length, 2.2))], [cartel(tau, 1.9, "VISTO", AZUL, 0.095, 150, vel=12.0, osc=0.8)])
    # las luces lejanas no tapan las letras del cartel: se sacan de esa franja (y de la zona de la caja de texto)
    sc = bpy.context.scene
    for o in E.SETS["bokeh"]:
        c = world_to_camera_view(sc, E.CAM, o.matrix_world.translation)
        if (1.0 - c.y) < 0.27:
            o.hide_render = True
    E.N.luces_a(G, ojos)
    f, r = N.LUCES_PJ["amigo"]
    f.location = ojos + v3(0.0, -0.1, 0.25)
    r.location = ojos + v3(0.5, 0.5, 0.2)
    N.apuntar(r, cen)


# =============================================================================== 2 · pantalla dividida (3–10 s)
def ensamblar(tau, V, hands):
    """Arma el sándwich sobre la tabla: cada ingrediente sale de su montoncito, viaja en arco en la mano de la vendedora y
    cae en su lugar. Devuelve las teclas de mano (md, mi) y desplaza las partes del sándwich."""
    xp = V["xp"]
    board = v3(xp - 0.45, 2.12, 1.01)
    R = fijo(board)
    pasos = [  # nombre, partes, centro final local, centro en el montoncito (mundo), mano, instante de inicio
        ("l1", ["san_m_l1"], v3(0, -0.045, 0.098), v3(xp - 0.85, 2.36, 1.022), "d", 0.25),
        ("j", ["san_m_j1", "san_m_j2"], v3(-0.01, -0.051, 0.12), v3(xp - 0.62, 2.36, 1.022), "i", 0.70),
        ("q", ["san_m_q"], v3(0, -0.045, 0.142), v3(xp - 0.38, 2.36, 1.022), "d", 1.15),
        ("t", ["san_m_t0", "san_m_t1", "san_m_t2"], v3(0, -0.04, 0.153), v3(xp - 0.12, 2.36, 1.022), "i", 1.60),
        ("pt", ["san_m_pt"] + [f"san_m_cor{k}" for k in range(4)], v3(0, 0, 0.185), v3(xp + 0.33, 2.33, 1.07), "i", 2.20),
    ]
    keys = dict(d=[], i=[])
    for nom, partes, loc_f, st, mh, T0 in pasos:
        F = board + loc_f
        D = st - F
        ta, tb, tc = T0, T0 + 0.12, T0 + 0.38
        u = eio(seg(tau, tb, tc))
        disp = D * (1 - u) + v3(0, 0, 0.12 * math.sin(math.pi * u))
        for p in partes:
            o = bpy.data.objects[p]
            o.matrix_world = Matrix.Translation(disp) @ R @ EX["san_base"][p]
        up = v3(0, 0, 0.10)
        kk = keys[mh]
        kk.append((ta, dict(w=st + up, d=(0, -1, -0.2), p=(0, 0.2, -1), c=0.15)))
        kk.append((tb, dict(w=st + v3(0, 0, 0.06), c=0.55)))
        for k in range(1, 5):
            tt = tb + (tc - tb) * k / 4
            uu = eio((tt - tb) / (tc - tb))
            dd = D * (1 - uu) + v3(0, 0, 0.12 * math.sin(math.pi * uu))
            kk.append((tt, dict(w=F + dd + v3(0, 0, 0.07))))
        kk.append((tc + 0.10, dict(w=F + v3(0, 0, 0.16), c=0.15)))
    return keys["d"], keys["i"]


def m2(t):
    tau = t - 3.0
    V = puesto_vars()
    xp, xt = V["xp"], E.X_TIENDA
    # ======== mitad de arriba: el puesto
    E.mostrar("ambar", "blanco", "rosa")
    for n in ("ambar", "blanco", "rosa"):
        E.PJ[n].calzado("plano")
    E.vis(E.SETS["puesto"], True)
    board = v3(xp - 0.45, 2.12, 1.01)
    MV = V["MV"]
    rest_md = MV @ v3(-0.26, 0.10, 0.92)
    rest_mi = MV @ v3(0.26, 0.10, 0.92)
    base_d = dict(d=MV.to_3x3() @ v3(0, 1, -0.4), p=MV.to_3x3() @ v3(0, 0.3, 1), c=0.25, po=(-0.5, -0.6, -0.5))
    base_i = dict(d=MV.to_3x3() @ v3(0, 1, -0.4), p=MV.to_3x3() @ v3(0, 0.3, 1), c=0.25, po=(0.5, -0.6, -0.5))
    kd, ki = ensamblar(tau, V, None)
    pre_d = [(0.0, dict(w=rest_md, **base_d))] + kd + [(1.03, dict(w=rest_md, c=0.25))]
    pre_i = [(0.0, dict(w=rest_mi, **base_i))] + ki
    ready = E.SETS["bandeja"][0]
    ventas = [dict(n="blanco", s=2.75, san=E.SETS["san_m"], san_t=(board, 3.75), bill=0, san_esc=1.0),
              dict(n="rosa", s=6.3, san=ready, san_t=(v3(xp + 0.40, 2.12, 1.01), 7.3), bill=1, san_esc=0.86)]
    # el segundo sale de la lista de rest: las teclas de ensamblado van primero, así que se ordenan dentro de servicio
    servicio(tau, V, ventas, vmd_pre=pre_d, vmi_pre=pre_i)
    if tau > 2.6:                                           # ya armado: las partes quedan en su sitio
        pass
    # ======== mitad de abajo: la tienda
    E.mostrar("azul", "violeta")
    A, Vd = E.PJ["azul"], E.PJ["violeta"]
    A.calzado("zapa"); Vd.calzado("plano")
    E.vis(E.SETS["zapa_m"], True)
    if EX["shoe_grey"] is not None:
        E.vis(EX["shoe_grey"], False)
    shelf_pos = v3(xt - 0.55, 1.85, 0)
    ys = 0.35
    c1 = Camino([(xt - 2.2, 1.85), (xt - 1.4, 1.85), (shelf_pos.x, shelf_pos.y)])
    c2 = Camino([(shelf_pos.x, shelf_pos.y), (xt - 0.10, 1.55), (xt + 0.38, 1.25)])
    c3 = Camino([(xt + 0.38, 1.25), (xt - 0.3, 1.1), (xt - 2.6, 1.0)])
    yD = c2.en(c2.L)[1]
    pos_D = v3(xt + 0.38, 1.25, 0)
    MD = Matrix.Translation(pos_D) @ Matrix.Rotation(yD, 4, 'Z')
    Ms = Matrix.Translation(shelf_pos) @ Matrix.Rotation(ys, 4, 'Z')
    hold_l = (-0.20, 0.30, 1.0)
    carry_i = dict(p=hold_l, dedos=(0, 1, 0), palma=(0, 0, 1), curl=0.5, polo=(-0.5, -0.3, -1))
    az_pos, az_yaw = None, 0.0
    if tau < 1.0 + 0.0:                                     # A: entra caminando hasta el estante
        d = perfil(tau, 0.0, 1.15, c1.L, ta=0.35, td=0.5)
        pos, yaw, kw = marcha(c1, d, S=0.80, brazos=0.26, ini=False, fin=True)
        yaw = -math.pi / 2 + (math.pi / 2 + ys) * eio(seg(tau, 0.65, 1.15))
        P("azul", pos, yaw, tau, base=kw)
        az_yaw = yaw
    elif tau < 2.05:                                        # B: toma la zapatilla roja del estante
        u = tau
        shoe_c = v3(xt - 0.90, 2.30, 0.93)
        mi_ = mano(u, [(1.0, dict(w=Ms @ v3(-0.26, 0.04, 0.86), d=Ms.to_3x3() @ v3(0, 0, -1), p=Ms.to_3x3() @ v3(1, 0.2, 0), c=0.28, po=(-0.5, -1, -0.2))),
                       (1.12, dict(w=Ms @ v3(-0.22, 0.10, 0.92))),                                   # anticipación: junta la mano
                       (1.42, dict(w=shoe_c + v3(0.05, -0.02, 0.10), d=(-0.3, 1, -0.4), p=(0, 0.4, -1), c=0.15)),
                       (1.52, dict(w=shoe_c + v3(0.05, -0.02, 0.10), c=0.7)),
                       (1.90, dict(w=Ms @ v3(*hold_l), d=Ms.to_3x3() @ v3(0, 1, 0), p=Ms.to_3x3() @ v3(0, 0, 1), c=0.5))])
        ln = 0.9 * eio(seg(u, 1.0, 1.35)) * (1 - eio(seg(u, 1.6, 1.95)))
        P("azul", shelf_pos, ys, tau, mi=mi_, lean=ln, cab=(0, 0, 0))
        az_yaw = ys
    elif tau < 3.1:                                         # C: camina al mostrador con la zapatilla
        d = perfil(tau, 2.05, 1.05, c2.L, ta=0.30, td=0.45)
        pos, yaw, kw = marcha(c2, d, S=0.78, brazos=0.22, ini=True, fin=True)
        y0 = c2.en(0)[1]
        yaw = yaw + ang(ys - y0) * (1 - eio(seg(tau, 2.05, 2.5)))
        P("azul", pos, yaw, tau, base=kw, mi=carry_i)
        az_yaw = yaw
    elif tau < 4.9:                                         # D: paga
        u = tau
        pk = MD @ v3(0.24, 0.07, 0.92)
        Bz = v3(xt + 1.00, 1.15, 1.27)
        md_ = mano(u, [(3.1, dict(w=MD @ v3(0.26, 0.04, 0.86), d=MD.to_3x3() @ v3(0, 0, -1), p=MD.to_3x3() @ v3(-1, 0.2, 0), c=0.28, po=(0.5, -1, -0.2))),
                       (3.18, dict(w=MD @ v3(0.26, 0.04, 0.86))),
                       (3.45, dict(w=pk, d=MD.to_3x3() @ v3(0, 0.3, -1), c=0.4)),
                       (3.58, dict(w=pk, c=0.3)),
                       (3.95, dict(w=Bz, d=(1, 0.2, 0), p=(0, 0, 1), c=0.3)),
                       (4.35, dict(w=Bz)),
                       (4.75, dict(w=MD @ v3(0.26, 0.04, 0.86), d=MD.to_3x3() @ v3(0, 0, -1), p=MD.to_3x3() @ v3(-1, 0.2, 0), c=0.28))])
        mi_ = dict(w=MD @ v3(*hold_l), dedos_w=MD.to_3x3() @ v3(0, 1, 0), palma_w=MD.to_3x3() @ v3(0, 0, 1), curl=0.5, polo=(-0.5, -0.3, -1))
        ln = 0.7 * eio(seg(u, 3.7, 4.0)) * (1 - eio(seg(u, 4.3, 4.7)))
        P("azul", pos_D, yD, tau, md=md_, mi=mi_, lean=ln, cab=(0, 0, 0))
        az_yaw = yD
    else:                                                   # E: se va con la zapatilla
        d = perfil(tau, 4.9, 2.1, c3.L, ta=0.5, td=0.3)
        pos, yaw, kw = marcha(c3, d, S=0.80, brazos=0.24, ini=True, fin=False)
        y0 = c3.en(0)[1]
        yaw = yaw + ang(yD - y0) * (1 - eio(seg(tau, 4.9, 5.45)))
        P("azul", pos, yaw, tau, base=kw, mi=carry_i)
        az_yaw = yaw
    # zapatilla: estante -> mano izquierda del azul
    shelf_M = fijo(v3(xt - 0.90, 2.40, 0.83), math.radians(166), 0.0, 1.0)
    en_az = lambda tx: en_mano("azul", "i", off=(0, 0.02, 0.08), yaw=az_yaw, esc=1.0) @ Matrix.Translation((0, 0, -0.15))
    llevar(E.SETS["zapa_m"], tau, [(-99.0, lambda tx: shelf_M), (1.45, en_az)], bl=0.22)
    # vendedor (violeta): recibe el billete, lo apoya junto a la caja y teclea
    pv = v3(xt + 1.72, 1.25, 0)
    yv = math.pi / 2 + 0.45
    MVd = Matrix.Translation(pv) @ Matrix.Rotation(yv, 4, 'Z')
    restv = lambda sg: MVd @ v3(sg * 0.26, 0.04, 0.86)
    Bv = v3(xt + 1.06, 1.17, 1.27)
    drop = v3(xt + 1.12, 0.74, 1.20)
    rg = v3(xt + 1.05, 0.86, 1.30)
    mi_v = mano(tau, [(0.0, dict(w=restv(-1), d=MVd.to_3x3() @ v3(0, 0, -1), p=MVd.to_3x3() @ v3(1, 0.2, 0), c=0.28, po=(-0.5, -1, -0.2))),
                      (3.55, dict(w=restv(-1))),
                      (3.95, dict(w=Bv, d=(-1, 0.1, 0), p=(0, 0, 1), c=0.15)),
                      (4.12, dict(w=Bv, c=0.7)),
                      (4.55, dict(w=drop, d=(-1, 0, -0.3))),
                      (4.72, dict(w=drop, c=0.15)),
                      (5.1, dict(w=restv(-1), d=MVd.to_3x3() @ v3(0, 0, -1), p=MVd.to_3x3() @ v3(1, 0.2, 0), c=0.28))])
    md_v = mano(tau, [(0.0, dict(w=restv(1), d=MVd.to_3x3() @ v3(0, 0, -1), p=MVd.to_3x3() @ v3(-1, 0.2, 0), c=0.28, po=(0.5, -1, -0.2))),
                      (4.7, dict(w=restv(1))),
                      (4.95, dict(w=rg + v3(0, 0, 0.07), d=(-1, 0, -0.5), c=0.5)),
                      (5.05, dict(w=rg, c=0.5)), (5.15, dict(w=rg + v3(0, 0, 0.07))), (5.28, dict(w=rg)), (5.40, dict(w=rg + v3(0, 0, 0.07))),
                      (5.9, dict(w=restv(1), d=MVd.to_3x3() @ v3(0, 0, -1), p=MVd.to_3x3() @ v3(-1, 0.2, 0), c=0.28))])
    lnv = lean_para(pv, [mi_v["w"], md_v["w"]], base=0.52, rango=0.32)
    P("violeta", pv, yv, tau, md=md_v, mi=mi_v, lean=lnv, cab=(0, 0, 0.0), ph=1.0)
    # billete del azul: bolsillo -> vendedor -> apoyado junto a la caja (queda a la vista)
    bill = EX["bill"][4]
    en_a = lambda tx: en_mano("azul", "d", off=(0, 0.01, 0.11), yaw=1.0, tilt=-1.0, esc=0.62)
    en_vv = lambda tx: en_mano("violeta", "i", off=(0, 0.01, 0.11), yaw=1.0, tilt=-1.0, esc=0.62)
    reposo = lambda tx: fijo(v3(xt + 1.15, 0.70, 1.025), 0.3, 0.0, 0.62)
    llevar(bill, tau, [(3.46, en_a), (4.12, en_vv), (4.70, reposo)], bl=0.20)
    # ---- cámaras, carteles, luces
    cam1 = v3(xp + 0.55, -1.9 + 0.30 * tau / 7.0, 3.0)
    cam2 = v3(xt + 0.30, -1.4 + 0.25 * tau / 7.0, 1.65)
    mitad = (1080, 960)
    v_top = cam_vista(cam1, v3(xp - 0.62, 2.2, 1.45), 42, tam=mitad, orig=(0, 0), f=3.0)
    v_bot = cam_vista(cam2, v3(xt + 0.30, 1.25, 1.36), 28, tam=mitad, orig=(0, 960), f=4.0)
    E.plan([v_top, v_bot], [cartel(tau, 0.05, "LA HIZO CRECER", AMBAR, 0.060, 84, vel=18.0),
                            cartel(tau, 0.55, "VENDE SÁNGUCHES", AMBAR, 0.095, 38, vel=26.0, kind="rotulo"),
                            cartel(tau, 0.25, "SE LA GASTÓ", AZUL, 0.563, 84, vel=18.0),
                            cartel(tau, 0.75, "COMPRA ZAPATILLAS", AZUL, 0.598, 38, vel=26.0, kind="rotulo")], linea=960)
    for n in ("ambar", "blanco", "rosa"):
        N.luces_a(E.PJ[n], cam1)
    for n in ("azul", "violeta"):
        N.luces_a(E.PJ[n], cam2)


# =============================================================================== aplicar
def aplicar(t, escena):
    global E
    E = escena
    preparar()
    t = t % E.DURACION
    del FALTAS[:]
    E.ocultar_todos()
    ocultar_extras()
    if t < 3.0:
        m1(t)
    elif t >= 33.0:
        m7(t)
    elif t >= 27.0:
        m6(t)
    elif t >= 19.0:
        m5(t)
    elif t >= 10.0 and t < 16.0:
        m3(t)
    elif t >= 3.0 and t < 10.0:
        m2(t)
    elif t >= 16.0:
        m4(t)
    else:
        m1(t % 3.0)       # provisional
    bpy.context.view_layer.update()
