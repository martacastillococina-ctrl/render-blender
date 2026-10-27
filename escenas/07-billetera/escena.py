"""
Dos Mentes 07 — INGRESOS / GASTOS, hecho en Blender por código (bpy, sin interfaz).

Toda la escena y toda la animación salen de este archivo: no hay keyframes, hay una función
`aplicar(t)` que coloca cada hormiga, cada paloma y cada chispa para el segundo t. Así el bucle
es perfecto por construcción: aplicar(t) == aplicar(t + T).

Uso (con Blender 4.2 o con el paquete pip `bpy==4.2.0`; es el mismo motor):
    blender -b -P escena.py -- --still 3.7 --out prueba/cuadro-3.png
    python escena.py --frame 120                    # un cuadro (n.º de cuadro, 30 fps)
    python escena.py --anim --start 0 --end 329     # cuadros a salida/frames/f_0000.png ...
Opciones: --samples N  --escala 0.5 (resolución)  --out ruta.png  --carpeta salida/frames
"""
import bpy, bmesh, math, sys, os, time, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

# ----------------------------------------------------------------------------- argumentos
def leer_args():
    a = sys.argv
    a = a[a.index("--") + 1:] if "--" in a else a[1:]
    o = {"still": None, "frame": None, "anim": False, "start": 0, "end": None, "samples": 48,
         "escala": 1.0, "out": None, "carpeta": None}
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--anim": o["anim"] = True
        elif k in ("--still", "--frame", "--start", "--end", "--samples", "--escala", "--out", "--carpeta"):
            i += 1
            v = a[i]
            kk = k[2:]
            o[kk] = v if kk in ("out", "carpeta") else float(v)
        i += 1
    return o

ARGS = leer_args()
AQUI = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------- constantes
FPS = 30
T = 11.0                    # período del bucle (s) -> 330 cuadros
NCUADROS = int(round(T * FPS))
ANCHO, ALTO = 1080, 1920

N_PALOMAS = 13              # 13 en 11 s = 1,18 por segundo
VIDA_PALOMA = 3.0           # segundos que una paloma está en pantalla
ESPACIO_PAL = T / N_PALOMAS
N_CHISPAS = 9

SEMILLA = 7
random.seed(SEMILLA)

# ----------------------------------------------------------------------------- utilidades
def limpiar():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def mat_principled(nombre, color, rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n = m.node_tree.nodes
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k, v in kw.items():
        b.inputs[k.replace("_", " ")].default_value = v
    return m

def mat_emision(nombre, color, fuerza):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    n = m.node_tree.nodes
    n.clear()
    e = n.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = fuerza
    o = n.new("ShaderNodeOutputMaterial")
    m.node_tree.links.new(e.outputs[0], o.inputs[0])
    return m

def objeto(nombre, malla, mat=None, padre=None, suave=True):
    o = bpy.data.objects.new(nombre, malla)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for mm in mat: malla.materials.append(mm)
        else:
            malla.materials.append(mat)
    if suave:
        for p in malla.polygons: p.use_smooth = True
    if padre is not None:
        o.parent = padre
    return o

def bm_a_malla(bm, nombre):
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    return me

def caja_redonda(nombre, tam, bisel=0.05, seg=3):
    """Caja de esquinas redondeadas centrada en el origen."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= tam[0]; v.co.y *= tam[1]; v.co.z *= tam[2]
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bisel, segments=seg, profile=0.6, affect='EDGES')
    return bm_a_malla(bm, nombre)

def esfera(radio=1.0, esc=(1, 1, 1), loc=(0, 0, 0), seg=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(8, seg // 2), radius=radio)
    for v in bm.verts:
        v.co = Vector((v.co.x * esc[0], v.co.y * esc[1], v.co.z * esc[2])) + Vector(loc)
    return bm

def fusionar(bms):
    """Une varios bmesh en uno."""
    tot = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("tmp")
        b.to_mesh(me)
        b.free()
        tot.from_mesh(me)
        bpy.data.meshes.remove(me)
    return tot

def cilindro_unitario():
    """Cilindro de radio 1 y largo 1 a lo largo de Z, con la base en z=0 (para patas)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=1.0, radius2=0.8, depth=1.0)
    for v in bm.verts: v.co.z += 0.5
    return bm_a_malla(bm, "cil")

def suavizar(s, a, b):
    x = min(1.0, max(0.0, (s - a) / (b - a)))
    return x * x * (3 - 2 * x)

# ----------------------------------------------------------------------------- texturas
def textura_billete():
    """Billete verde procedural (512x256) generado con numpy: marco, guilloché, óvalo y números."""
    W, H = 512, 256
    rng = np.random.default_rng(SEMILLA)
    u, v = np.meshgrid(np.linspace(0, 1, W), np.linspace(0, 1, H))
    base = np.array([0.40, 0.66, 0.40])
    img = np.ones((H, W, 3)) * base
    g = 0.5 + 0.5 * np.sin(150 * u + 9 * np.sin(38 * v) + 5 * np.sin(23 * u))
    g2 = 0.5 + 0.5 * np.sin(95 * v + 7 * np.sin(31 * u))
    img *= (1 - 0.20 * g - 0.12 * g2)[..., None]
    # óvalo central con anillos concéntricos
    r = np.sqrt(((u - 0.5) / 0.16) ** 2 + ((v - 0.5) / 0.36) ** 2)
    ov = r < 1
    anillos = 0.5 + 0.5 * np.sin(r * 55)
    img[ov] = (np.array([0.78, 0.88, 0.70]) * (0.78 + 0.22 * anillos[..., None]))[ov]
    img[(r > 0.93) & (r < 1.0)] = np.array([0.18, 0.36, 0.20])
    # marco
    d = np.minimum(np.minimum(u, 1 - u) * 2, np.minimum(v, 1 - v) * 2.0 * 2)
    img[d < 0.05] = np.array([0.17, 0.33, 0.19])
    img[(d >= 0.05) & (d < 0.065)] = np.array([0.80, 0.90, 0.76])
    img[(d >= 0.065) & (d < 0.09)] *= 0.8
    # números "100" con una fuente de bloques 3x5
    glifos = {"1": ["010", "110", "010", "010", "111"], "0": ["111", "101", "101", "101", "111"]}
    def numeros(x0, y0, bloque):
        for k, ch in enumerate("100"):
            for j, fila in enumerate(glifos[ch]):
                for i, c in enumerate(fila):
                    if c == "1":
                        xs = x0 + (k * 4 + i) * bloque
                        ys = y0 + j * bloque
                        img[ys:ys + bloque, xs:xs + bloque] = np.array([0.10, 0.25, 0.14])
    numeros(30, 30, 8)
    numeros(W - 30 - 12 * 8 + 4, H - 30 - 5 * 8, 8)
    img += rng.normal(0, 0.012, img.shape)
    img = np.clip(img, 0, 1)
    rgba = np.concatenate([img, np.ones((H, W, 1))], axis=2)[::-1]   # Blender: fila 0 = abajo
    im = bpy.data.images.new("billete", W, H)
    im.pixels.foreach_set(rgba.astype(np.float32).ravel())
    im.pack()
    return im

# ----------------------------------------------------------------------------- materiales
HX = -0.48                  # centro de la entrada de las hormigas (x)
YB_FRENTE = -0.37           # frente de la tapa a ras de piso (y)
def entrada_sombra(m):
    """Lo que está detrás de la boca de la billetera se va a negro (la hormiga se mete en la sombra del túnel):
    mezcla con negro según la y del mundo. Así el túnel oscuro y la hormiga se funden sin atravesar nada."""
    nt = m.node_tree; N = nt.nodes; L = nt.links
    out = next(n for n in N if n.type == 'OUTPUT_MATERIAL')
    src = out.inputs["Surface"].links[0].from_socket
    g = N.new("ShaderNodeNewGeometry"); sep = N.new("ShaderNodeSeparateXYZ")
    L.new(g.outputs["Position"], sep.inputs[0])
    mr = N.new("ShaderNodeMapRange"); mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs["From Min"].default_value = YB_FRENTE - 0.08; mr.inputs["From Max"].default_value = YB_FRENTE + 0.25
    L.new(sep.outputs["Y"], mr.inputs["Value"])
    # solo vale en la boca del túnel: máscara en x alrededor de HX (el resto de la fila no se toca)
    rx = N.new("ShaderNodeMath"); rx.operation = 'SUBTRACT'; rx.inputs[1].default_value = HX
    L.new(sep.outputs["X"], rx.inputs[0])
    ax = N.new("ShaderNodeMath"); ax.operation = 'ABSOLUTE'; L.new(rx.outputs[0], ax.inputs[0])
    mx = N.new("ShaderNodeMapRange"); mx.interpolation_type = 'SMOOTHSTEP'
    mx.inputs["From Min"].default_value = 0.45; mx.inputs["From Max"].default_value = 0.8
    mx.inputs["To Min"].default_value = 1.0; mx.inputs["To Max"].default_value = 0.0
    L.new(ax.outputs[0], mx.inputs["Value"])
    prod = N.new("ShaderNodeMath"); prod.operation = 'MULTIPLY'
    L.new(mr.outputs["Result"], prod.inputs[0]); L.new(mx.outputs["Result"], prod.inputs[1])
    negro = N.new("ShaderNodeBsdfDiffuse"); negro.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = N.new("ShaderNodeMixShader")
    L.new(prod.outputs[0], mix.inputs[0]); L.new(src, mix.inputs[1]); L.new(negro.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])

def crear_materiales():
    M = {}
    # cuero marrón gastado: grano (voronoi) + manchas claras por desgaste + rugosidad variable
    m = bpy.data.materials.new("cuero")
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    ruido_g = N.new("ShaderNodeTexNoise"); ruido_g.inputs["Scale"].default_value = 4.0
    ruido_g.inputs["Detail"].default_value = 8
    vor = N.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 55
    vor.feature = 'DISTANCE_TO_EDGE'
    L.new(tc.outputs["Object"], ruido_g.inputs["Vector"]); L.new(tc.outputs["Object"], vor.inputs["Vector"])
    rampa = N.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].position = 0.38; rampa.color_ramp.elements[1].position = 0.68
    rampa.color_ramp.elements[0].color = (0.10, 0.045, 0.018, 1)   # marrón oscuro
    rampa.color_ramp.elements[1].color = (0.36, 0.17, 0.07, 1)     # cuero gastado claro
    L.new(ruido_g.outputs["Fac"], rampa.inputs["Fac"])
    L.new(rampa.outputs["Color"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.5; bump.inputs["Distance"].default_value = 0.02
    L.new(vor.outputs["Distance"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    rug = N.new("ShaderNodeMapRange"); rug.inputs["To Min"].default_value = 0.38; rug.inputs["To Max"].default_value = 0.75
    L.new(ruido_g.outputs["Fac"], rug.inputs["Value"])
    L.new(rug.outputs["Result"], b.inputs["Roughness"])
    b.inputs["Coat Weight"].default_value = 0.25
    b.inputs["Coat Roughness"].default_value = 0.35
    # desgaste: los bordes redondeados se aclaran (Bevel node vs normal geométrica)
    bev = N.new("ShaderNodeBevel"); bev.inputs["Radius"].default_value = 0.035
    geo = N.new("ShaderNodeNewGeometry")
    dot = N.new("ShaderNodeVectorMath"); dot.operation = 'DOT_PRODUCT'
    L.new(bev.outputs["Normal"], dot.inputs[0]); L.new(geo.outputs["Normal"], dot.inputs[1])
    rd = N.new("ShaderNodeValToRGB")
    rd.color_ramp.elements[0].position = 0.80; rd.color_ramp.elements[0].color = (1, 1, 1, 1)
    rd.color_ramp.elements[1].position = 0.97; rd.color_ramp.elements[1].color = (0, 0, 0, 1)
    L.new(dot.outputs["Value"], rd.inputs["Fac"])
    mezcla = N.new("ShaderNodeMix"); mezcla.data_type = 'RGBA'
    L.new(rd.outputs["Color"], mezcla.inputs["Factor"])
    L.new(rampa.outputs["Color"], mezcla.inputs["A"])
    mezcla.inputs["B"].default_value = (0.55, 0.32, 0.15, 1)
    L.new(mezcla.outputs["Result"], b.inputs["Base Color"])
    M["cuero"] = m
    M["cuero_oscuro"] = mat_principled("cuero_oscuro", (0.06, 0.028, 0.012), 0.5)
    M["hilo"] = mat_principled("hilo", (0.80, 0.68, 0.45), 0.7)
    M["hueco"] = mat_principled("hueco", (0.004, 0.004, 0.004), 1.0)
    M["interior"] = mat_emision("interior", (0.10, 0.8, 0.25), 0.10)
    M["latón"] = mat_principled("laton", (0.95, 0.65, 0.22), 0.28, 1.0)
    M["oro"] = mat_principled("oro", (1.0, 0.70, 0.16), 0.22, 1.0)
    # hormiga verde con brillo (laca esmeralda)
    M["hormiga"] = mat_principled("hormiga", (0.025, 0.30, 0.05), 0.16, 0.25, Coat_Weight=1.0, Coat_Roughness=0.05)
    M["pata"] = mat_principled("pata", (0.02, 0.22, 0.05), 0.25, 0.1, Coat_Weight=0.6)
    # suelo oscuro con algo de reflejo
    M["suelo"] = mat_principled("suelo", (0.022, 0.018, 0.015), 0.62)
    # billete: textura sobre papel con un poco de brillo propio para que se lea en la sombra
    im = textura_billete()
    m = bpy.data.materials.new("billete")
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]
    tx = N.new("ShaderNodeTexImage"); tx.image = im; tx.extension = 'REPEAT'; tx.interpolation = 'Linear'
    L.new(tx.outputs["Color"], b.inputs["Base Color"])
    L.new(tx.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.22
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Specular IOR Level"].default_value = 0.6
    b.inputs["Sheen Weight"].default_value = 0.4
    M["billete"] = m
    # chispa: la fuerza sale del color del objeto (R) para poder apagarla suave sin esconder nada de golpe
    m = bpy.data.materials.new("chispa"); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; N.clear()
    e = N.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (0.10, 1.0, 0.12, 1)
    oi = N.new("ShaderNodeObjectInfo"); sp = N.new("ShaderNodeSeparateColor")
    mu = N.new("ShaderNodeMath"); mu.operation = 'MULTIPLY'; mu.inputs[1].default_value = 5.0
    L.new(oi.outputs["Color"], sp.inputs[0]); L.new(sp.outputs["Red"], mu.inputs[0]); L.new(mu.outputs[0], e.inputs["Strength"])
    o = N.new("ShaderNodeOutputMaterial"); L.new(e.outputs[0], o.inputs[0])
    M["chispa"] = m
    # tarjetas
    M["tarj_negra"] = mat_principled("tarj_negra", (0.006, 0.006, 0.008), 0.38, 0.0, Coat_Weight=0.25, Coat_Roughness=0.25)
    M["tarj_dorada"] = mat_principled("tarj_dorada", (0.85, 0.50, 0.08), 0.34, 0.9)
    M["tarj_azul"] = mat_principled("tarj_azul", (0.025, 0.10, 0.50), 0.28, 0.0, Coat_Weight=0.7, Coat_Roughness=0.1)
    M["tarj_plata"] = mat_principled("tarj_plata", (0.72, 0.74, 0.78), 0.28, 0.9)
    M["relieve_oro"] = mat_principled("relieve_oro", (1.0, 0.78, 0.30), 0.25, 1.0)
    M["relieve_plata"] = mat_principled("relieve_plata", (0.85, 0.88, 0.92), 0.25, 1.0)
    M["chip_linea"] = mat_principled("chip_linea", (0.30, 0.17, 0.04), 0.4, 0.8)
    for k in ("hormiga", "pata", "oro"):
        entrada_sombra(M[k])
    M["texto"] = mat_emision("texto", (1.0, 1.0, 1.0), 1.0)
    return M

# ----------------------------------------------------------------------------- billetera
AN, PR, AL = 2.0, 0.55, 1.45                # ancho, profundidad, alto del cuerpo
GR, ALT_TAPA, LEAN = 0.09, 1.30, 6.0         # grosor de la tapa, alto de la tapa, inclinación (grados)
TW, TPARED = 0.38, 0.50                      # túnel de las hormigas: medio ancho y alto de la pared recta (arriba, semicírculo)
Y_FONDO = 0.20                               # fondo del túnel (y)

def prisma_arco(nombre, cx, y0, y1, zmin=-0.2):
    """Cortador en forma de arco (sección en XZ) extruido a lo largo de y."""
    pts = [(cx - TW, zmin), (cx - TW, TPARED)]
    pts += [(cx - TW * math.cos(math.pi * k / 16), TPARED + TW * math.sin(math.pi * k / 16)) for k in range(1, 16)]
    pts += [(cx + TW, TPARED), (cx + TW, zmin)]
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for x, z in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=(0, y1 - y0, 0), verts=[v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm_a_malla(bm, nombre)

def caja_cortador(nombre, x0, x1, y0, y1, z0, z1):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
    return bm_a_malla(bm, nombre)

def restar(o, cortadores, padre=None):
    """Boolean exacto de varios cortadores contra el objeto o (se aplica: queda malla fija)."""
    cs = []
    for k, me in enumerate(cortadores):
        c = bpy.data.objects.new(f"corte{k}", me); bpy.context.scene.collection.objects.link(c)
        if padre is not None: c.parent = padre
        md = o.modifiers.new(f"b{k}", 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = c
        cs.append(c)
    bpy.context.view_layer.update()
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    nueva = bpy.data.meshes.new_from_object(ev)
    for md in list(o.modifiers): o.modifiers.remove(md)
    viejo = o.data; o.data = nueva
    for c in cs: bpy.data.objects.remove(c)
    bpy.data.meshes.remove(viejo)
    return nueva

def marcar_hueco(me, M, caja, filtro=None):
    """Las caras dentro de `caja` (x0,x1,y0,y1,z0,z1) pasan al material oscuro del hueco."""
    me.materials.append(M["hueco"]); ih = len(me.materials) - 1
    x0, x1, y0, y1, z0, z1 = caja
    for p in me.polygons:
        c = p.center
        if x0 <= c.x <= x1 and y0 <= c.y <= y1 and z0 <= c.z <= z1 and (filtro is None or filtro(p)):
            p.material_index = ih

def rect_redondo(nombre, w, h, r, grosor, seg=6):
    """Placa de esquinas redondeadas en el plano XZ, con el grosor a lo largo de y (centrada)."""
    pts = []
    for (cx, cz, a0) in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new((x, -grosor / 2, z)) for x, z in pts])
    rr = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=(0, grosor, 0), verts=[v for v in rr["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm_a_malla(bm, nombre)

def texto_malla(cuerpo, size, extrude, ruta_fuente="LiberationSerif-Bold.ttf", espacio=1.0):
    """Texto en relieve mirando a -y (hacia la cámara), con el centro en el origen."""
    cur = bpy.data.curves.new("txt", 'FONT'); cur.body = cuerpo; cur.size = size; cur.extrude = extrude
    cur.align_x = 'CENTER'; cur.align_y = 'CENTER'; cur.space_character = espacio
    cur.font = bpy.data.fonts.load(os.path.join(AQUI, "fuentes", ruta_fuente))
    o = bpy.data.objects.new("txt", cur); bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(o)
    bpy.data.objects.remove(o)
    me.transform(Matrix.Rotation(math.radians(90), 4, 'X'))
    return me

CARTAS = []          # (objeto, caja_mundo) para las pruebas de colisión

def construir_tarjeta(M, i, mat, mat_relieve, x, y, zbase, yaw, lean, numero):
    W, H, G = 0.70, 0.50, 0.020
    raiz = bpy.data.objects.new(f"tarjeta{i}", None); bpy.context.scene.collection.objects.link(raiz)
    raiz.location = (x, y, zbase + H / 2)
    raiz.rotation_euler = (math.radians(lean), 0, math.radians(yaw))
    base = objeto(f"tarj{i}_base", rect_redondo("tarj", W, H, 0.045, G), mat, padre=raiz)
    top = H / 2
    fy = -G / 2
    # chip dorado con rayitas, arriba a la izquierda (es lo que asoma por encima de la billetera)
    chip = objeto(f"tarj{i}_chip", rect_redondo("chip", 0.115, 0.085, 0.018, 0.006, 4), M["relieve_oro"], padre=raiz)
    chip.location = (-W / 2 + 0.115, fy - 0.002, top - 0.075)
    for dx, dz, sx, sz in ((0, 0, 0.115, 0.004), (0, 0.027, 0.115, 0.004), (0, -0.027, 0.115, 0.004), (0, 0, 0.004, 0.085)):
        ln = objeto(f"tarj{i}_ln", caja_cortador("ln", -sx / 2, sx / 2, -0.001, 0.001, -sz / 2, sz / 2), M["chip_linea"], padre=raiz, suave=False)
        ln.location = (-W / 2 + 0.115 + dx, fy - 0.0055, top - 0.075 + dz)
    # número en relieve a la derecha del chip
    mt = texto_malla(numero, 0.052, 0.003, espacio=1.25)
    t = objeto(f"tarj{i}_num", mt, mat_relieve, padre=raiz)
    t.location = (0.07, fy - 0.0035, top - 0.075)
    # contorno que se pueda leer cuando asoma solo la franja de arriba: línea fina en relieve
    return raiz

def construir_billete_asomando(M, i, x, y, zbase, alto, ancho, yaw, lean):
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in ((-ancho / 2, 0, 0), (ancho / 2, 0, 0), (ancho / 2, 0, alto), (-ancho / 2, 0, alto))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UV")
    for l, (u, v) in zip(f.loops, ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0))):
        l[uv].uv = (u, v)
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    # un poquito de curva (el billete no es una plancha)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=6, use_grid_fill=True)
    for v in bm.verts: v.co.y += 0.035 * math.sin(math.pi * (v.co.z / alto)) * (v.co.x / ancho)
    me = bm_a_malla(bm, "billete_asoma"); me.materials.append(M["billete"])
    o = objeto(f"billete_asoma{i}", me, padre=None)
    for p in me.polygons: p.use_smooth = True
    o.location = (x, y, zbase); o.rotation_euler = (math.radians(lean), 0, math.radians(yaw))
    # doble cara: el material no tiene backface culling, así que alcanza
    return o

def construir_billetera(M):
    """Billetera de cuero: cuerpo con boca de bolsillo arriba (tarjetas y billetes asoman), tapa delantera algo abierta,
    y en la base, abajo a la izquierda, un túnel oscuro por donde entran las hormigas."""
    # ---- cuerpo: caja biselada, con el túnel y el bolsillo restados, + subdivisión
    me = caja_redonda("cuerpo", (AN, PR, AL), 0.10, 6)
    me.transform(Matrix.Translation((0, 0, AL / 2)))
    cuerpo = objeto("billetera_cuerpo", me, M["cuero"], suave=False)
    me = restar(cuerpo, [prisma_arco("tunel", HX, -1.2, Y_FONDO), caja_cortador("bolsillo", -0.94, 0.94, -0.20, 0.08, 0.95, 1.7)])
    marcar_hueco(me, M, (HX - TW - 0.02, HX + TW + 0.02, -1.2, Y_FONDO + 0.02, -0.3, TPARED + TW + 0.02), lambda p: abs(p.normal.y) < 0.75 or p.center.y > 0.0)
    marcar_hueco(me, M, (-0.96, 0.96, -0.22, 0.10, 0.93, AL - 0.03), None)
    for p in me.polygons: p.use_smooth = True
    # ---- tapa: bisagra abajo, inclinada hacia la cámara
    bis = bpy.data.objects.new("bisagra", None); bpy.context.scene.collection.objects.link(bis)
    bis.location = (0, -PR / 2, 0.0); bis.rotation_euler = (math.radians(LEAN), 0, 0)
    me = caja_redonda("tapa", (AN, GR, ALT_TAPA), 0.04, 5)
    me.transform(Matrix.Translation((0, -GR / 2, ALT_TAPA / 2)))
    tapa = objeto("billetera_tapa", me, M["cuero"], padre=bis, suave=False)
    me = restar(tapa, [prisma_arco("tunel_t", HX, -0.5, 0.2)], padre=bis)
    marcar_hueco(me, M, (HX - TW - 0.02, HX + TW + 0.02, -0.5, 0.2, -0.3, TPARED + TW + 0.02), lambda p: abs(p.normal.y) < 0.75)
    for p in me.polygons: p.use_smooth = True
    FY = -GR - 0.002                            # cara delantera de la tapa (coordenadas de la bisagra)
    # piso oscuro del túnel (sombra): una plaquita negra a ras de suelo
    bm = bmesh.new()
    y0p, y1p = YB_FRENTE + 0.03, Y_FONDO - 0.01
    for x, y in ((HX - TW, y0p), (HX + TW, y0p), (HX + TW, y1p), (HX - TW, y1p)):
        bm.verts.new((x, y, 0.003))
    bm.faces.new(list(bm.verts)); bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    objeto("piso_tunel", bm_a_malla(bm, "piso"), M["hueco"], suave=False)
    # broche lateral
    correa = objeto("correa", caja_redonda("correa", (0.22, 0.03, 0.80), 0.012, 2), M["cuero_oscuro"], padre=bis)
    correa.location = (0.80, FY - 0.012, 0.78)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=0.085, radius2=0.07, depth=0.05)
    bro = objeto("broche", bm_a_malla(bm, "broche"), M["latón"], padre=bis)
    bro.rotation_euler = (math.radians(90), 0, 0)
    bro.location = (0.80, FY - 0.045, 0.62)
    # costuras (rayitas crema) en el borde de la tapa y alrededor del arco
    mh = caja_redonda("punto", (0.075, 0.018, 0.016), 0.006, 1)
    def punto(x, z, giro):
        o = objeto("punto", mh, M["hilo"], padre=bis, suave=False)
        o.location = (x, FY - 0.002, z); o.rotation_euler = (0, math.radians(giro), 0)
    for k in range(18):
        x = -0.87 + k * 0.102
        punto(x, ALT_TAPA - 0.14, 0)
        if abs(x - HX) > TW + 0.16: punto(x, 0.14, 0)
    for k in range(11):
        z = 0.20 + k * 0.095
        if z > 1.0: punto(-0.90, z, 90)
        punto(0.90, z, 90)
    RR = TW + 0.08
    for k in range(0, 17):
        a = math.pi * k / 16
        punto(HX - RR * math.cos(a), TPARED + RR * math.sin(a), 90 - math.degrees(a) + 0.0)
    for z in (0.10, 0.24, 0.38):
        punto(HX - RR, z, 90); punto(HX + RR, z, 90)
    # ---- tarjetas (de atrás hacia adelante, las de atrás asoman más), y billetes
    spec = [(M["tarj_plata"], M["relieve_plata"], -0.58, -0.005, 1.48, 2.5, -5, "7712 3094"),
            (M["tarj_azul"], M["relieve_plata"], -0.60, -0.050, 1.34, -2.0, -5, "4519 8830"),
            (M["tarj_negra"], M["relieve_oro"], -0.59, -0.095, 1.20, 2.0, -5, "5301 7764"),
            (M["tarj_dorada"], M["relieve_oro"], -0.61, -0.140, 1.06, -1.5, -5, "6011 2285")]
    for i, (a, b, x, y, zb, yaw, lean, num) in enumerate(spec):
        CARTAS.append(construir_tarjeta(M, i, a, b, x, y, zb, yaw, lean, num))
    CARTAS.append(construir_billete_asomando(M, 0, 0.70, -0.015, 1.18, 0.62, 0.42, 6, -6))
    CARTAS.append(construir_billete_asomando(M, 1, 0.78, 0.04, 1.12, 0.62, 0.40, -5, -4))
    return bis

def _cono():
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.07, radius2=0.05, depth=0.05)
    return bm

# ----------------------------------------------------------------------------- moneda con $
def construir_moneda(M):
    R, G = 0.135, 0.026
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=R, radius2=R, depth=G)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=0.004, segments=2, affect='EDGES')
    partes = [bm]
    # aro en relieve
    for lado in (1, -1):
        b2 = bmesh.new()
        bmesh.ops.create_cone(b2, cap_ends=True, segments=48, radius1=R * 0.93, radius2=R * 0.93, depth=0.006)
        for v in b2.verts: v.co.z += lado * (G / 2)
        partes.append(b2)
        b3 = bmesh.new()
        bmesh.ops.create_cone(b3, cap_ends=True, segments=48, radius1=R * 0.84, radius2=R * 0.84, depth=0.004)
        for v in b3.verts: v.co.z += lado * (G / 2 - 0.004)
        # hueco hundido: lo dejamos plano y más oscuro por la geometría del $
        partes.append(b3)
    # el "$" en relieve, en ambas caras
    cur = bpy.data.curves.new("signo", 'FONT')
    cur.body = "$"
    cur.size = 0.24
    cur.extrude = 0.010
    cur.align_x = 'CENTER'; cur.align_y = 'CENTER'
    cur.font = bpy.data.fonts.load(os.path.join(AQUI, "fuentes", "LiberationSerif-Bold.ttf"))
    tmpo = bpy.data.objects.new("signo", cur)
    bpy.context.scene.collection.objects.link(tmpo)
    bpy.context.view_layer.update()
    me_s = bpy.data.meshes.new_from_object(tmpo)
    bpy.data.objects.remove(tmpo)
    for lado in (1, -1):
        b4 = bmesh.new(); b4.from_mesh(me_s)
        for v in b4.verts:
            v.co.z += lado * (G / 2 + 0.002)
            if lado == -1: v.co.x *= -1
        if lado == -1: bmesh.ops.reverse_faces(b4, faces=list(b4.faces))
        partes.append(b4)
    tot = fusionar(partes)
    # la moneda queda de canto: eje del disco a lo largo de X (la cara mira de costado)
    for v in tot.verts:
        v.co = Vector((v.co.x, -v.co.z, v.co.y))      # disco de canto, cara hacia adelante/atrás de la hormiga
    for f in tot.faces: f.smooth = True
    me = bm_a_malla(tot, "moneda")
    me.materials.append(M["oro"])
    return me

# ----------------------------------------------------------------------------- hormiga
ESC_HORMIGA = 1.6
LH = 0.12      # muslo
LS = 0.15      # tibia
ALT_CUERPO = 0.105

def construir_hormiga_modelo(M):
    """Devuelve las mallas compartidas que usa cada hormiga."""
    partes = [esfera(1, (0.075, 0.115, 0.075), (0, -0.19, 0.0), 24),      # abdomen
              esfera(1, (0.050, 0.075, 0.05), (0, -0.03, 0.01), 20),     # tórax
              esfera(1, (0.055, 0.060, 0.050), (0, 0.095, 0.015), 20)]   # cabeza
    tot = fusionar(partes)
    me = bm_a_malla(tot, "hormiga_cuerpo"); me.materials.append(M["hormiga"])
    for p in me.polygons: p.use_smooth = True
    return me

class Hormiga:
    def __init__(self, idx, M, me_cuerpo, me_cil, me_moneda):
        self.raiz = bpy.data.objects.new(f"hormiga{idx}", None)
        bpy.context.scene.collection.objects.link(self.raiz)
        self.cuerpo = objeto(f"h{idx}_cuerpo", me_cuerpo, padre=self.raiz)
        self.moneda = objeto(f"h{idx}_moneda", me_moneda, padre=self.raiz)
        self.moneda.location = (0, -0.05, 0.225)
        self.moneda.rotation_euler = (math.radians(-8), 0, math.radians(10))
        # antenas
        self.antenas = []
        for lado in (-1, 1):
            a = objeto(f"h{idx}_ant", me_cil, M["pata"], padre=self.raiz, suave=False)
            self.antenas.append((a, lado))
        # patas: 3 pares, 2 segmentos
        self.patas = []
        for lado in (-1, 1):
            for k, yk in enumerate((0.04, -0.025, -0.09)):
                s1 = objeto(f"h{idx}_p1", me_cil, M["pata"], padre=self.raiz, suave=False)
                s2 = objeto(f"h{idx}_p2", me_cil, M["pata"], padre=self.raiz, suave=False)
                fase = (0.0 if (k % 2 == 0) == (lado == 1) else 0.5)
                self.patas.append((s1, s2, lado, yk, fase))

def poner_cilindro(o, a, b, radio):
    d = b - a
    L = d.length
    if L < 1e-6: L = 1e-6
    q = d.to_track_quat('Z', 'Y')
    o.matrix_basis = Matrix.Translation(a) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((radio, radio, L, 1.0))

CICLOS_POR_PASO = 4                # ciclos de pata por cada lugar de la fila: entero, así el bucle empalma en la pose
def amp_paso():
    """Mitad del recorrido del pie en el cuerpo. Apoyo = la mitad del ciclo: el pie retrocede 2·amp mientras el cuerpo
    avanza PASO/(CICLOS·2) -> para que el pie NO patine: 2·amp = PASO/(CICLOS·2·ESC)  =>  amp = PASO/(4·CICLOS·ESC)."""
    return PASO_HORMIGAS / (4.0 * CICLOS_POR_PASO * ESC_HORMIGA)

def pie_y_paso(fase_t, yk, lado, amp):
    """Posición local del pie de una pata (fase_t en ciclos). Apoyo (mitad del ciclo): el pie queda fijo en el suelo, o sea
    retrocede en el cuerpo a la velocidad del cuerpo; vuelo: sube, avanza y apoya adelante (arco suave)."""
    ph = fase_t % 1.0
    if ph < 0.5:                       # apoyo
        u = ph / 0.5
        dy = amp * (1 - 2 * u); lev = 0.0
    else:                              # vuelo, con ease para que no frene de golpe
        u = (ph - 0.5) / 0.5
        e = u * u * (3 - 2 * u)
        dy = amp * (-1 + 2 * e); lev = math.sin(math.pi * u) ** 1.3 * 0.05
    return Vector((lado * 0.19, yk + dy, -ALT_CUERPO + 0.01 + lev))

def animar_hormiga(h, s, pos, tang):
    """Coloca la hormiga en el punto s del camino; las patas caminan según s (no según el tiempo): sin patinar."""
    yaw = math.atan2(-tang[0], tang[1])             # adelante = +Y local = tangente del camino
    ciclo = CICLOS_POR_PASO * s / PASO_HORMIGAS
    bob = 0.004 * math.sin(4 * math.pi * ciclo)    # el cuerpo sube y baja dos veces por ciclo (un apoyo por grupo)
    h.raiz.matrix_basis = (Matrix.Translation(Vector((pos[0], pos[1], (ALT_CUERPO + bob) * ESC_HORMIGA)))
                           @ Euler((0, 0, yaw)).to_matrix().to_4x4() @ Matrix.Scale(ESC_HORMIGA, 4))
    # la moneda siempre mira a la cámara (nunca de canto): se contrarresta el giro de la hormiga
    h.moneda.rotation_euler = (math.radians(-8), 0, math.radians(10) - yaw)
    # leve vaivén del cuerpo
    h.cuerpo.rotation_euler = (0, 0.03 * math.sin(2 * math.pi * ciclo), 0.02 * math.sin(2 * math.pi * ciclo))
    for a, lado in h.antenas:
        base = Vector((lado * 0.02, 0.15, 0.04))
        punta = base + Vector((lado * 0.07, 0.13, 0.10 + 0.012 * math.sin(2 * math.pi * (ciclo + 0.25 * lado))))
        poner_cilindro(a, base, punta, 0.006)
    amp = amp_paso()
    for s1, s2, lado, yk, fase in h.patas:
        cadera = Vector((lado * 0.04, yk, 0.0))
        pie = pie_y_paso(ciclo + fase, yk, lado, amp)
        d = pie - cadera
        dist = min(d.length, LH + LS - 1e-3)
        dirn = d.normalized()
        a = (LH * LH - LS * LS + dist * dist) / (2 * dist)
        hh = math.sqrt(max(LH * LH - a * a, 0.0))
        arriba = Vector((lado * 0.55, 0.0, 1.0))
        perp = (arriba - dirn * arriba.dot(dirn)).normalized()
        rodilla = cadera + dirn * a + perp * hh
        poner_cilindro(s1, cadera, rodilla, 0.012)
        poner_cilindro(s2, rodilla, cadera + dirn * dist if dist < d.length else pie, 0.009)

# ----------------------------------------------------------------------------- camino de las hormigas
def construir_camino():
    """Fila en S: baja en curvas y termina de frente al arco de la base: los últimos 1,5 son una recta hacia el túnel."""
    ctrl = np.array([(-3.6, 10.5), (-2.9, 8.4), (-1.9, 6.4), (-2.6, 4.4), (-2.1, 2.6), (-1.6, 0.9), (-2.3, -0.8),
                     (-1.9, -2.2), (-1.0, -2.6), (HX, -1.9), (HX, -1.1), (HX, -0.4), (HX, 0.45)], float)
    # Catmull-Rom denso
    P = np.vstack([ctrl[0] * 2 - ctrl[1], ctrl, ctrl[-1] * 2 - ctrl[-2]])
    pts = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, 60, endpoint=False):
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    pts.append(ctrl[-1])
    pts = np.array(pts)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    return pts, s

CAM_PTS, CAM_S = construir_camino()
LARGO_CAMINO = CAM_S[-1]
N_HORMIGAS = int(LARGO_CAMINO // 1.15)
K_AVANCE = 2                                  # lugares que avanza la fila por período (la marcha se ve natural)
PASO_HORMIGAS = LARGO_CAMINO / N_HORMIGAS     # separación; la fila avanza exactamente K lugares por período

def punto_camino(s):
    s = min(max(s, 0.0), LARGO_CAMINO)
    x = np.interp(s, CAM_S, CAM_PTS[:, 0]); y = np.interp(s, CAM_S, CAM_PTS[:, 1])
    e = 0.02
    s2 = min(s + e, LARGO_CAMINO); s1 = max(s - e, 0.0)
    dx = np.interp(s2, CAM_S, CAM_PTS[:, 0]) - np.interp(s1, CAM_S, CAM_PTS[:, 0])
    dy = np.interp(s2, CAM_S, CAM_PTS[:, 1]) - np.interp(s1, CAM_S, CAM_PTS[:, 1])
    n = math.hypot(dx, dy) or 1.0
    return (x, y), (dx / n, dy / n)

# ----------------------------------------------------------------------------- paloma de origami
def construir_paloma(M):
    """Dos mallas: cuerpo (con cabeza y cola) y ala derecha; la izquierda es el espejo. Adelante = +Y."""
    def uvs(me, pts_por_cara, rng):
        uv = me.uv_layers.new(name="UV")
        for p in me.polygons:
            ou, ov = rng.random(), rng.random()
            for li in p.loop_indices:
                v = me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv = (0.5 + v.x * 0.9 + ou, 0.5 + v.y * 1.4 + v.z * 0.6 + ov)
    rng = random.Random(3)
    # cuerpo: huso de 4 aristas + cuello + cola en abanico
    V = {
        "nariz": (0, 0.36, 0.015), "cabT": (0, 0.24, 0.085), "cabL": (-0.045, 0.23, 0.03), "cabR": (0.045, 0.23, 0.03),
        "cabB": (0, 0.24, -0.02),
        "pecT": (0, 0.06, 0.10), "pecL": (-0.095, 0.05, 0.0), "pecR": (0.095, 0.05, 0.0), "pecB": (0, 0.08, -0.095),
        "lomoT": (0, -0.14, 0.07), "lomoL": (-0.06, -0.13, 0.0), "lomoR": (0.06, -0.13, 0.0), "lomoB": (0, -0.12, -0.06),
        "colaP": (0, -0.34, 0.015),
        "cola1": (-0.17, -0.46, 0.05), "cola2": (0.17, -0.46, 0.05), "cola3": (0, -0.50, 0.075),
    }
    nom = list(V); idx = {k: i for i, k in enumerate(nom)}
    F = [("nariz", "cabL", "cabT"), ("nariz", "cabT", "cabR"), ("nariz", "cabR", "cabB"), ("nariz", "cabB", "cabL"),
         ("cabT", "cabL", "pecL"), ("cabT", "pecL", "pecT"), ("cabT", "pecT", "pecR"), ("cabT", "pecR", "cabR"),
         ("cabB", "pecL", "cabL"), ("cabB", "pecB", "pecL"), ("cabB", "pecR", "pecB"), ("cabB", "cabR", "pecR"),
         ("pecT", "pecL", "lomoL"), ("pecT", "lomoL", "lomoT"), ("pecT", "lomoT", "lomoR"), ("pecT", "lomoR", "pecR"),
         ("pecB", "lomoL", "pecL"), ("pecB", "lomoB", "lomoL"), ("pecB", "lomoR", "lomoB"), ("pecB", "pecR", "lomoR"),
         ("lomoT", "lomoL", "colaP"), ("lomoL", "lomoB", "colaP"), ("lomoB", "lomoR", "colaP"), ("lomoR", "lomoT", "colaP"),
         ("colaP", "cola1", "cola3"), ("colaP", "cola3", "cola2"), ("colaP", "cola2", "cola1")]
    me = bpy.data.meshes.new("paloma_cuerpo")
    me.from_pydata([V[k] for k in nom], [], [tuple(idx[k] for k in f) for f in F])
    me.update(); uvs(me, None, rng); me.materials.append(M["billete"])
    # ala derecha: dos paneles plegados + pluma
    def ala(signo):
        s = signo
        W = [(0, 0.15, 0.0), (0, -0.14, 0.0), (0.30 * s, -0.17, 0.07), (0.30 * s, 0.11, 0.05),
             (0.66 * s, -0.33, 0.14), (0.58 * s, 0.00, 0.11), (0.88 * s, -0.46, 0.17)]
        caras = [(0, 1, 2), (0, 2, 3), (3, 2, 4), (3, 4, 5), (5, 4, 6)]
        if s < 0: caras = [tuple(reversed(c)) for c in caras]
        m2 = bpy.data.meshes.new("paloma_ala")
        m2.from_pydata(W, [], caras); m2.update(); uvs(m2, None, random.Random(11 if s > 0 else 12))
        m2.materials.append(M["billete"])
        for p in m2.polygons: p.use_smooth = False
        return m2
    for p in me.polygons: p.use_smooth = False
    return me, ala(1), ala(-1)

class Paloma:
    def __init__(self, i, M, me_c, me_d, me_i, me_chispa):
        self.i = i
        self.raiz = bpy.data.objects.new(f"paloma{i}", None)
        bpy.context.scene.collection.objects.link(self.raiz)
        self.cuerpo = objeto(f"p{i}_cuerpo", me_c, padre=self.raiz, suave=False)
        self.ad = objeto(f"p{i}_alaD", me_d, padre=self.raiz, suave=False)
        self.ai = objeto(f"p{i}_alaI", me_i, padre=self.raiz, suave=False)
        self.ad.location = (0.04, 0.0, 0.05); self.ai.location = (-0.04, 0.0, 0.05)
        self.chispas = [objeto(f"p{i}_ch{j}", me_chispa, M["chispa"], suave=True) for j in range(N_CHISPAS)]
        rg = random.Random(100 + i)
        self.desv = [Vector((rg.uniform(-0.25, 0.25), rg.uniform(-0.25, 0.25), rg.uniform(-0.25, 0.25))) for _ in range(N_CHISPAS)]
        self.fase_ala = rg.random()
        for o in [self.cuerpo, self.ad, self.ai] + self.chispas:
            o.hide_render = True; o.hide_viewport = True

ORIGEN_PAL = Vector((0.16, -0.07, 1.22))               # dentro del bolsillo, entre las tarjetas y los billetes
DIR_PAL = Vector((0.55, 0.40, 0.78)).normalized()      # arriba y a la derecha en pantalla
ARRANQUE = 0.35                                         # anticipación: se agacha un poquito antes de salir
VMAX = 3.1                                              # u/s al final de la aceleración
ESC_PAL = 1.1

def _tabla_trayectoria():
    """Integra la trayectoria una vez: arranca vertical (sale de la ranura) y la curva se abre hacia arriba-derecha."""
    dt = 1.0 / 240
    e = 0.0; p = Vector(ORIGEN_PAL); es = [0.0]; ps = [Vector(p)]
    V0 = Vector((0.0, 0.03, 1.0))
    while e < VIDA_PALOMA + 0.05:
        x = max(0.0, e - ARRANQUE)
        v = VMAX * (0.30 + 0.70 * suavizar(x, 0.0, 1.5))
        w = suavizar(x, 0.0, 1.9)
        d = (V0 * (1 - w) + DIR_PAL * w).normalized()
        p = p + d * v * dt; e += dt
        es.append(e); ps.append(Vector(p))
    return np.array(es), np.array([[q.x, q.y, q.z] for q in ps])

TAB_E, TAB_P = _tabla_trayectoria()

def pos_paloma(a, fase):
    """Posición en el mundo de una paloma de edad a (segundos): trayectoria curva suave + un poco de vaivén lateral."""
    a = min(max(a, 0.0), TAB_E[-1])
    p = Vector([float(np.interp(a, TAB_E, TAB_P[:, k])) for k in range(3)])
    x = max(0.0, a - ARRANQUE)
    lat = Vector((0.7, -0.55, 0.0)).normalized()
    onda = 0.10 * math.sin(2 * math.pi * 0.9 * x + fase * 6.28) * suavizar(x, 0.2, 1.2)
    hundir = -0.05 * math.sin(math.pi * min(a / ARRANQUE, 1.0)) if a < ARRANQUE else 0.0   # anticipación (se agacha)
    return p + lat * onda + Vector((0, 0, hundir))

def escala_paloma(edad):
    """Nace casi puntito dentro del bolsillo y crece con la altura: a la altura de las tarjetas todavía es chica,
    así no roza nada; con un pequeño rebote ya libre."""
    z = pos_paloma(edad, 0.0).z
    crece = 0.25 * suavizar(z, ORIGEN_PAL.z + 0.05, ORIGEN_PAL.z + 0.7) + 0.70 * suavizar(z, 2.0, 3.4)
    rebote = 1.0 + 0.06 * math.sin(math.pi * suavizar(z, 2.6, 3.8))
    return ESC_PAL * (0.05 + crece) * rebote

def matriz_paloma(adel, edad, fase):
    """Orientación: adelante = velocidad; arriba = hacia la cámara al salir y luego hacia el cielo. Sin volteos."""
    f = adel.normalized()
    w = suavizar(edad, 0.0, 1.4)
    ref = (Vector((0, -1, 0)) * (1 - w) + Vector((0, 0, 1)) * w).normalized()
    der = f.cross(ref).normalized()
    arr = der.cross(f)
    m = Matrix(((der.x, f.x, arr.x), (der.y, f.y, arr.y), (der.z, f.z, arr.z)))
    roll = 0.30 * math.sin(2 * math.pi * 0.8 * edad + fase * 6.28) * suavizar(edad, 0.4, 1.2)
    return m.to_quaternion() @ Quaternion((0, 1, 0), roll)

def angulo_ala(edad, fase):
    """Aleteo con ease: bajada más lenta que la subida, y arranca con las alas plegadas hacia arriba."""
    plegada = math.radians(10 + 60 * suavizar(edad, 0.0, ARRANQUE))
    x = edad - ARRANQUE
    ph = (x * 2.4) % 1.0
    # onda asimétrica con ease: sube rápido (0..0.4) y baja más lento (0.4..1)
    if ph < 0.4: u = suavizar(ph, 0.0, 0.4); v = u
    else: u = suavizar(ph, 0.4, 1.0); v = 1 - u
    libre = math.radians(-42 + 90 * v)
    k = suavizar(edad, ARRANQUE, ARRANQUE + 0.5)
    return plegada * (1 - k) + libre * k

def animar_paloma(p, t, M):
    edad = (t - p.i * ESPACIO_PAL) % T
    vis = edad < VIDA_PALOMA
    for o in [p.cuerpo, p.ad, p.ai]:
        o.hide_render = not vis; o.hide_viewport = not vis
    if not vis:
        for c in p.chispas: c.hide_render = True; c.hide_viewport = True
        return
    pos = pos_paloma(edad, p.fase_ala)
    adel = pos_paloma(edad + 0.02, p.fase_ala) - pos_paloma(max(edad - 0.02, 0.0), p.fase_ala)
    if adel.length < 1e-4: adel = Vector((0, 0.03, 1.0))
    p.raiz.rotation_mode = 'QUATERNION'
    p.raiz.rotation_quaternion = matriz_paloma(adel, edad, p.fase_ala)
    sc = escala_paloma(edad)
    p.raiz.scale = (sc, sc, sc)
    p.raiz.location = pos
    ang = angulo_ala(edad, p.fase_ala)
    p.ad.rotation_euler = (0, -ang, 0)
    p.ai.rotation_euler = (0, ang, 0)
    # chispas: cola de puntitos que se apagan de a poco (la fuerza de la emisión sale del color del objeto)
    for j, c in enumerate(p.chispas):
        e2 = edad - (j + 1) * 0.055
        f = suavizar(e2, 0.25, 0.8) * (1 - j / (N_CHISPAS + 1.0)) ** 1.6
        ok = f > 0.01
        c.hide_render = not ok; c.hide_viewport = not ok
        if ok:
            c.location = pos_paloma(e2, p.fase_ala) + p.desv[j] * (0.3 + 0.12 * j)
            esc = 0.050 * (0.6 + 0.4 * math.sin(edad * 30 + j * 2.1) ** 2) * (0.5 + 0.5 * f)
            c.scale = (esc, esc, esc)
            c.color = (f, f, f, 1.0)

# ----------------------------------------------------------------------------- escena
CAM = None
HORMIGAS = []
PALOMAS = []

def construir_escena():
    global CAM
    limpiar()
    sc = bpy.context.scene
    M = crear_materiales()
    # suelo infinito
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    objeto("suelo", bm_a_malla(bm, "suelo"), M["suelo"], suave=False)
    construir_billetera(M)
    me_c = construir_hormiga_modelo(M)
    me_cil = cilindro_unitario(); me_cil.materials.append(M["pata"])
    me_m = construir_moneda(M)
    for i in range(N_HORMIGAS + K_AVANCE + 1):
        HORMIGAS.append(Hormiga(i, M, me_c, me_cil, me_m))
    me_pc, me_pd, me_pi = construir_paloma(M)
    bm = esfera(1, (1, 1, 1), (0, 0, 0), 8); me_ch = bm_a_malla(bm, "chispa")
    for i in range(N_PALOMAS):
        PALOMAS.append(Paloma(i, M, me_pc, me_pd, me_pi, me_ch))
    # cámara fija: picado leve, lente largo (look diorama)
    cam = bpy.data.cameras.new("cam")
    cam.lens = 85; cam.sensor_width = 36; cam.sensor_fit = 'HORIZONTAL'
    cam.dof.use_dof = True; cam.dof.aperture_fstop = 9.0
    obj = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(obj)
    objetivo = Vector((-0.45, 0.2, 0.95)); dist = 11.5; elev = math.radians(27)
    obj.location = objetivo + Vector((0, -dist * math.cos(elev), dist * math.sin(elev)))
    obj.rotation_euler = (objetivo - obj.location).to_track_quat('-Z', 'Y').to_euler()
    cam.dof.focus_distance = (objetivo - obj.location).length
    sc.camera = obj; CAM = obj
    # textos fijos pegados a la cámara y a la misma distancia del foco
    fd = 6.0            # más cerca que el piso (si no, el piso tapa el texto); a esa distancia el desenfoque es de ~2 px
    ancho_vis = 2 * fd * (18.0 / 85.0)
    for txt, xrel in (("INGRESOS", -0.235), ("GASTOS", 0.235)):
        cur = bpy.data.curves.new("t_" + txt, 'FONT')
        cur.body = txt
        cur.font = bpy.data.fonts.load(os.path.join(AQUI, "fuentes", "LiberationSerif-Regular.ttf"))
        cur.size = ancho_vis * 0.052
        cur.space_character = 1.55
        cur.align_x = 'CENTER'; cur.align_y = 'CENTER'
        o = bpy.data.objects.new("t_" + txt, cur)
        sc.collection.objects.link(o)
        cur.materials.append(M["texto"])
        o.parent = obj
        alto_vis = ancho_vis * (ALTO / ANCHO)
        o.location = (xrel * ancho_vis, -0.345 * alto_vis, -fd)
        o.visible_shadow = False; o.visible_glossy = False; o.visible_transmission = False
        o.visible_diffuse = False
    # luces
    mundo = bpy.data.worlds.new("mundo"); sc.world = mundo
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.004, 0.005, 1)
    mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    foco = bpy.data.lights.new("foco", 'SPOT')
    foco.energy = 8000; foco.color = (1.0, 0.70, 0.42)
    foco.spot_size = math.radians(40); foco.spot_blend = 1.0; foco.shadow_soft_size = 0.5
    o = bpy.data.objects.new("foco", foco); sc.collection.objects.link(o)
    o.location = (-0.9, -1.4, 8.5)
    o.rotation_euler = (math.radians(4), 0, 0)
    # relleno suave para que los metales tengan algo que reflejar
    for nombre, loc, pot, col, tam in (("sb1", (-5, -6, 5), 120, (1.0, 0.75, 0.5), 3.0),
                                       ("sb2", (6, -4, 6), 90, (0.7, 0.85, 1.0), 3.0)):
        l = bpy.data.lights.new(nombre, 'AREA'); l.energy = pot; l.color = col; l.size = tam
        ob = bpy.data.objects.new(nombre, l); sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, 0.5)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        ob.visible_camera = False if hasattr(ob, "visible_camera") else None
    # brillo verde saliendo de la billetera
    l = bpy.data.lights.new("verde", 'POINT'); l.energy = 70; l.color = (0.2, 1.0, 0.35); l.shadow_soft_size = 0.5
    ob = bpy.data.objects.new("verde", l); sc.collection.objects.link(ob); ob.location = (0.3, -0.15, 1.7)
    configurar_render(sc)

def configurar_render(sc):
    sc.render.engine = 'CYCLES'
    c = sc.cycles
    c.device = 'CPU'
    c.samples = int(ARGS["samples"])
    c.use_adaptive_sampling = True; c.adaptive_threshold = 0.02
    c.use_denoising = True
    try: c.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    c.max_bounces = 5; c.diffuse_bounces = 3; c.glossy_bounces = 4; c.transmission_bounces = 2
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x = ANCHO; sc.render.resolution_y = ALTO
    sc.render.resolution_percentage = int(round(ARGS["escala"] * 100))
    sc.render.fps = FPS
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'Filmic' if 'Filmic' in [x.identifier for x in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Standard'
    try: sc.view_settings.look = 'Medium High Contrast'
    except Exception: pass
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = False

# ----------------------------------------------------------------------------- animación
def aplicar(t):
    """Coloca TODO para el segundo t (período T)."""
    t = t % T
    for i, h in enumerate(HORMIGAS):
        s = (i - K_AVANCE + K_AVANCE * t / T) * PASO_HORMIGAS
        ver = -1e-6 <= s <= LARGO_CAMINO + 1e-6      # fuera del camino: la punta está fuera de cuadro y el final, en negro
        h.raiz.hide_render = not ver
        for o in h.raiz.children_recursive: o.hide_render = not ver
        if not ver: continue
        pos, tan = punto_camino(s)
        animar_hormiga(h, s, pos, tan)
    for p in PALOMAS:
        animar_paloma(p, t, None)
    bpy.context.view_layer.update()

def renderizar(t, ruta):
    aplicar(t)
    bpy.context.scene.render.filepath = ruta
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0

def principal():
    construir_escena()
    if ARGS["still"] is not None or ARGS["frame"] is not None:
        t = ARGS["still"] if ARGS["still"] is not None else ARGS["frame"] / FPS
        ruta = ARGS["out"] or os.path.join(AQUI, "prueba", f"cuadro-{t:.2f}.png")
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        seg = renderizar(t, ruta)
        print(f"[escena] t={t:.2f}s -> {ruta} en {seg:.1f}s")
    elif ARGS["anim"]:
        carpeta = ARGS["carpeta"] or os.path.join(AQUI, "salida", "frames")
        os.makedirs(carpeta, exist_ok=True)
        fin = int(ARGS["end"]) if ARGS["end"] is not None else NCUADROS - 1
        for f in range(int(ARGS["start"]), fin + 1):
            ruta = os.path.join(carpeta, f"f_{f:04d}.png")
            if os.path.exists(ruta): continue          # se puede retomar
            seg = renderizar(f / FPS, ruta)
            print(f"[escena] cuadro {f}/{NCUADROS - 1}  {seg:.1f}s", flush=True)
    else:
        print("Falta --still T, --frame N o --anim")

if os.environ.get("ESCENA_SIN_PRINCIPAL") != "1":
    principal()
