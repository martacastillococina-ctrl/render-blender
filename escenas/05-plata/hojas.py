"""
Celdas de las hojas de aprobación (personajes, poses, objetos). Se renderiza cada celda por separado en el "estudio"
oscuro (piso mojado, luz de noche) y `armar_hojas.py` las une con rótulos. Se llama desde `escena.py --hoja NOMBRE`.
Cámara libre: `E.libre()` apaga los carteles y `E.renderizar` le pone a cada personaje visible su luz de rol (azul / ámbar / blanca).
"""
import bpy, math, os
from mathutils import Vector, Matrix
from motor import *
import objetos as O
from objetos import C


def v3(*a):
    return Vector(a)


def hacer(nombre, carpeta, solo, E):
    X = E.X_ESTUDIO
    fn = {"personajes": personajes, "poses": poses, "objetos": objetos}[nombre]
    E.libre()
    fn(carpeta, solo, E, X)


def _quiere(solo, clave):
    return (not solo) or clave in solo.split(",")


def _borrar(raices):
    for r in raices:
        for h in list(r.children_recursive):
            bpy.data.objects.remove(h)
        bpy.data.objects.remove(r)


def _cam_estudio(E, xc, d=4.0, z=1.15, lente=60, alto_ojo=None):
    E.camara((xc, -d, alto_ojo if alto_ojo is not None else z), (xc, 0.0, z), lente)


def _luz_obj(E, cam, objetivo, energia=260.0, color="#CFE0FF"):
    """Luz de relleno para las celdas de objetos (sin personajes): sale de la cámara, desde arriba y al costado."""
    k = E.SETS.get("luz_obj")
    if k is None:
        k = E.SETS["luz_obj"] = E.N.luz("luz_obj", 'POINT', (0, 0, 0), color, energia, radio=0.6)
        k2 = E.SETS["luz_obj2"] = E.N.luz("luz_obj2", 'POINT', (0, 0, 0), "#FFB36B", energia * 0.7, radio=0.6)
    k.data.energy = energia
    d = (Vector(cam) - Vector(objetivo))
    d.z = 0
    d = d.normalized()
    lado = Vector((-d.y, d.x, 0))
    k.location = Vector(objetivo) + d * 1.4 + lado * 1.1 + Vector((0, 0, 1.6))
    E.SETS["luz_obj2"].location = Vector(objetivo) - d * 0.8 - lado * 1.3 + Vector((0, 0, 1.4))


# ----------------------------------------------------------------------------- personajes
ORDEN = ["azul", "ambar", "amigo", "rosa", "coral"]


def personajes(carpeta, solo, E, X):
    E.resolucion(640, 860)
    E.ocultar_todos()
    for nom in ORDEN:
        if not _quiere(solo, nom):
            continue
        E.ocultar_todos()
        E.PJ[nom].ocultar(False)
        for tag, yaw in (("frente", math.pi), ("tres_cuartos", math.pi - 0.8)):
            E.PJ[nom].poner(pos=v3(X, 0, 0.0), yaw=yaw, **E.parado(
                cabeza_rot=(0, 0, 0.0), md=dict(p=(0.30, 0.04, 0.80), curl=0.12), mi=dict(p=(-0.30, 0.04, 0.80), curl=0.12)))
            _cam_estudio(E, X, d=3.5, z=1.2, lente=50)
            E.renderizar(os.path.join(carpeta, f"pj_{nom}_{tag}.png"))


# ----------------------------------------------------------------------------- poses
FASES = [0.0, 0.12, 0.30, 0.52]


def poses(carpeta, solo, E, X):
    E.ocultar_todos()
    # --- caminar en 4 fases, de perfil ---
    E.resolucion(560, 760)
    P = E.PJ["azul"]
    for i, fase in enumerate(FASES):
        if not _quiere(solo, f"caminar{i}"):
            continue
        E.ocultar_todos()
        P.ocultar(False)
        P.calzado("zapa")
        kw = E.caminata(fase)
        P.poner(pos=v3(X, 0, 0), yaw=-math.pi / 2, **kw)
        _cam_estudio(E, X, d=4.4, z=1.05, lente=55)
        E.renderizar(os.path.join(carpeta, f"po_caminar{i}.png"))
    # --- meñique: los dos con el meñique parado y enganchado en el aire (pulgar y resto en puño); plano y primer plano ---
    if _quiere(solo, "menique"):
        E.resolucion(900, 760)
        E.ocultar_todos()
        A, G = E.PJ["azul"], E.PJ["amigo"]
        A.ocultar(False); G.ocultar(False)
        A.calzado("plano")
        yp, zA = -0.20, 1.10
        puno_men = (1.0, 1.0, 1.0, (0.0, 0.95))             # puño con el meñique parado y doblado en gancho
        A.poner(pos=v3(X - 0.50, 0, 0), yaw=-math.pi / 2 + 0.35, **E.parado(cabeza_rot=(0, 0, 0.3)),
                md=dict(w=v3(X - 0.015, yp + 0.0525 * HM, zA), dedos_w=(0, 0, 1), palma_w=(1, 0, 0), curl=puno_men, pulgar=(0.0, 0.05, 0.12), polo=(0, -1, -0.5)),
                mi=dict(p=(-0.28, 0.02, 0.84), curl=0.3))
        G.poner(pos=v3(X + 0.50, 0, 0), yaw=math.pi / 2 - 0.35, **E.parado(cabeza_rot=(0, 0, -0.3)),
                md=dict(w=v3(X + 0.020, yp - 0.0525 * HM, zA - 0.028), dedos_w=(0, 0, 1), palma_w=(-1, 0, 0), curl=puno_men, pulgar=(0.0, 0.05, 0.12), polo=(0, -1, -0.5)),
                mi=dict(p=(-0.28, 0.02, 0.84), curl=0.3))
        E.camara((X, -2.4, 1.45), (X, 0.0, 1.20), 42)
        E.renderizar(os.path.join(carpeta, "po_menique.png"))
        E.N.ESCALA_LUZ[0] = 0.14
        E.camara((X + 0.03, -1.1, 1.40), (X, yp, 1.30), 85, dof=(0.9, 5.6))
        E.resolucion(700, 700)
        E.renderizar(os.path.join(carpeta, "po_menique_cerca.png"))
        E.N.ESCALA_LUZ[0] = 1.0
    # --- choque de puño ---
    if _quiere(solo, "choque"):
        E.ocultar_todos()
        E.m6_choque()
        E.libre()
        E.PJ["azul"].ocultar(True)
        E.resolucion(900, 760)
        x0 = E.X_PLAZA
        E.camara((x0, -3.0, 1.45), (x0, 0.0, 1.25), 36)
        E.renderizar(os.path.join(carpeta, "po_choque.png"))
        E.resolucion(700, 700)
        E.N.ESCALA_LUZ[0] = 0.3
        E.camara((x0, -1.05, 1.34), (x0, -0.05, 1.24), 50, dof=(1.05, 4.0))
        E.renderizar(os.path.join(carpeta, "po_choque_cerca.png"))
        E.N.ESCALA_LUZ[0] = 1.0
    # --- dar la plata (palma arriba con el fajo) ---
    if _quiere(solo, "dar"):
        E.ocultar_todos()
        E.m1_plaza()
        E.libre()
        E.resolucion(900, 760)
        x0 = E.X_PLAZA
        E.camara((x0 - 0.2, -3.0, 1.6), (x0 - 0.5, 0.0, 1.2), 40)
        E.renderizar(os.path.join(carpeta, "po_dar.png"))
    # --- celular en la mano, de cerca ---
    if _quiere(solo, "celular"):
        E.ocultar_todos()
        for i_, nom in ((1, "po_celular"), (3, "po_celular_a")):
            E.m3_celular(12.0)
            E.SETS["celular"].mostrar(i_)
            E.libre()
            E.resolucion(560, 860)
            E.renderizar(os.path.join(carpeta, nom + ".png"))


# ----------------------------------------------------------------------------- objetos
def _cel_pantallas(X):
    r = []
    from objetos import Celular
    for i in range(4):
        c = Celular(f"hc{i}")
        c.mostrar(i)
        c.raiz.location = (X + (i - 1.5) * 0.22, 0, 1.0)
        c.raiz.rotation_euler = (math.radians(90), 0, 0)
        r.append(c.raiz)
    return r


def objetos(carpeta, solo, E, X):
    E.ocultar_todos()
    E.resolucion(760, 760)

    def celda(clave, build, cam, lente=45, energia=260.0):
        if not _quiere(solo, clave):
            return
        raices = build()
        E.camara(cam[0], cam[1], lente)
        _luz_obj(E, cam[0], cam[1], energia)
        E.renderizar(os.path.join(carpeta, f"ob_{clave}.png"))
        _borrar(raices)

    def b_billetes():
        a = O.fajo("h_fajo", loc=(X - 0.38, 0.0, 0.0), rot=(0, 0, math.radians(18)))
        b = O.billete("h_bill", loc=(X + 0.10, -0.38, 0.003), rot=(0, 0, math.radians(-12)))
        c = O.abanico("h_aba", loc=(X + 0.02, 0.22, 0.0), rot=(0, 0, math.radians(-15)))
        return [a, b, c]
    celda("billetes", b_billetes, ((X, -1.2, 1.1), (X, 0.0, 0.0)), 45)

    def b_zapas():
        return [O.caja_zapatillas("h_caja", loc=(X - 0.2, 0.30, 0), rot=(0, 0, math.radians(-15)), abierta=True),
                O.zapatilla("h_z1", loc=(X + 0.45, -0.15, 0), rot=(0, 0, math.radians(200)), color="#E8332B", escala=1.2),
                O.zapatilla("h_z2", loc=(X + 0.05, -0.55, 0), rot=(0, 0, math.radians(165)), color="#E8332B", escala=1.2),
                O.caja_zapatillas("h_caja2", loc=(X - 0.62, -0.38, 0), rot=(0, 0, math.radians(12)), abierta=False)]
    celda("zapatillas", b_zapas, ((X, -1.5, 1.2), (X, 0.0, 0.1)), 45)

    def b_bolsa():
        return [O.bolsa("h_bolsa", loc=(X, 0, 0), rot=(0, 0, math.radians(-25)))]
    celda("bolsa", b_bolsa, ((X, -1.35, 0.7), (X, 0.0, 0.25)), 50)

    def b_puerta():
        return [O.puerta_tienda("h_pc", loc=(X - 1.5, 0, 0), angulo=0.0), O.puerta_tienda("h_pa", loc=(X + 1.1, 0, 0), angulo=-math.radians(75))]
    celda("puerta", b_puerta, ((X, -5.6, 1.7), (X, 0.0, 1.15)), 45, 420.0)

    def b_estante():
        return [O.estante_zapatillas("h_est", loc=(X, 0, 0), ancho=2.8, alto=2.3)]
    celda("estante", b_estante, ((X, -4.2, 1.5), (X, 0.0, 1.1)), 40, 420.0)

    def b_caja():
        return [O.mostrador("h_most", loc=(X, 0, 0), ancho=2.0), O.caja_zapatillas("h_cz", loc=(X - 0.5, 0.0, 0.98), abierta=False)]
    celda("caja_registradora", b_caja, ((X + 0.5, -3.0, 1.9), (X + 0.15, 0.0, 1.05)), 45, 380.0)

    def b_celular():
        return _cel_pantallas(X)
    celda("celular", b_celular, ((X, -1.2, 1.0), (X, 0.0, 1.0)), 40, 200.0)

    def b_comida():
        r = []
        r.append(caja("h_mesa", (2.1, 0.9, 0.06), material("mesa", C["madera_clara"], rough=0.7), loc=(X, 0, 0.03), bisel=0.01))
        r.append(O.pan_frances("h_pan", loc=(X - 0.55, -0.15, 0.1), rot=(0, 0, math.radians(15)), largo=0.5))
        r.append(O.feta("h_jam", C["jamon"], loc=(X - 0.08, -0.22, 0.075), rot=(0, 0, 0.3), tam=0.14))
        r.append(O.feta("h_jam2", C["jamon"], loc=(X + 0.05, -0.08, 0.087), rot=(0, 0, -0.4), tam=0.14))
        r.append(O.queso("h_que", loc=(X + 0.30, -0.25, 0.075), rot=(0, 0, math.radians(30)), tam=0.17))
        r.append(O.salame("h_sal", loc=(X - 0.40, 0.25, 0.115), rot=(0, 0, math.radians(8)), largo=0.42))
        r.append(O.lechuga("h_lec", loc=(X + 0.25, 0.14, 0.09), rot=(0, 0, 0.2)))
        for i in range(3):
            r.append(O.tomate_rodaja(f"h_tom{i}", loc=(X + 0.72, -0.22 + i * 0.14, 0.075)))
        return r
    celda("comida", b_comida, ((X, -1.7, 1.45), (X, 0.0, 0.08)), 45, 320.0)

    def b_sanguche():
        return [O.sanguche("h_san", loc=(X, 0, 0.0), rot=(0, 0, math.radians(-12)), largo=0.62)]
    celda("sanguche", b_sanguche, ((X, -1.15, 0.7), (X, 0.0, 0.14)), 50, 300.0)

    def b_puesto():
        r = [O.puesto("h_pue", loc=(X, 0, 0), rot=(0, 0, math.radians(-18)))]
        r.append(O.caja_plata("h_cp", loc=(X + 0.55, 0.0, 1.02), rot=(0, 0, math.radians(-18)), llena=1.0))
        for i in range(2):
            r.append(O.sanguche(f"h_ps{i}", loc=(X - 0.6 + i * 0.1, -0.05 + i * 0.1, 1.02), rot=(0, 0, math.radians(-18))))
        return r
    celda("puesto", b_puesto, ((X + 1.2, -5.4, 2.6), (X, 0.0, 1.35)), 36, 700.0)

    def b_caja_plata():
        return [O.caja_plata("h_c1", loc=(X - 0.35, 0, 0), rot=(0, 0, math.radians(15)), llena=0.1),
                O.caja_plata("h_c2", loc=(X + 0.40, -0.2, 0), rot=(0, 0, math.radians(-12)), llena=1.0)]
    celda("caja_plata", b_caja_plata, ((X, -1.9, 1.2), (X, 0.0, 0.1)), 40)

    def b_almacen():
        return [O.almacen_fondo("h_alm", loc=(X, 1.2, 0)), O.vitrina("h_vit", loc=(X + 0.5, -0.1, 0), ancho=1.8),
                O.canasta_pan("h_can", loc=(X - 1.35, -0.2, 0.0))]
    celda("almacen", b_almacen, ((X, -4.0, 2.1), (X, 0.5, 1.15)), 40, 520.0)
