# render-blender

Escenas 3D hechas por código (Blender 4.2, `bpy`) y un workflow que las renderiza en varias compus de GitHub a la vez.

- `escenas/<nombre>/escena.py`: toda la escena y la animación salen de ese archivo (sin keyframes: `aplicar(t)`).
- `.github/workflows/render.yml`: reparte los cuadros en hasta 20 tramos en paralelo, arma el mp4 (H.264) y lo deja
  como artifact `video`.

```
gh workflow run render.yml -f escena=07-billetera -f muestras=24
```

Cada `escena.py` acepta: `--anim --start A --end B --samples N --escala E --carpeta frames` y escribe `f_0000.png`…
