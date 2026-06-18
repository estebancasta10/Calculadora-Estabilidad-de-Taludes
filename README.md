# Herramienta de estabilidad de taludes

Aplicacion de escritorio en Python para estimar el factor de seguridad de un talud con superficie circular de falla.

## Como ejecutar en escritorio

```powershell
python slope_stability_tool.py
```

Si Python no esta en el `PATH`, abre el archivo `slope_stability_tool.py` con tu instalacion de Python 3.

## Como ejecutar en Streamlit o web

```powershell
streamlit run streamlit_app.py
```

Para Streamlit Cloud usa `streamlit_app.py` como archivo principal. No uses `slope_stability_tool.py` en Streamlit Cloud porque esa version usa `tkinter`, y Streamlit Cloud no incluye interfaz grafica de escritorio.

## Calculadora CBR en Streamlit

La herramienta de CBR esta en `cbr_tool.py` y se ejecuta asi:

```powershell
streamlit run cbr_tool.py
```

Para Streamlit Cloud o GitHub, selecciona `cbr_tool.py` como archivo principal si quieres publicar directamente la calculadora CBR.

La calculadora permite:

- Agregar mas datos en una tabla editable.
- Cambiar unidades de penetracion entre `mm` y `pulgadas`.
- Cambiar unidades de carga entre `kN`, `kgf` y `lbf`.
- Graficar la curva carga-penetracion y las rectas de tendencia.
- Calcular CBR a `2.5 mm` y `5.0 mm`.
- Separar graficos cuando hay varios grupos con dispersion alta.

## Que calcula

- Dibuja el talud, el circulo de falla y el numero de dovelas indicado.
- Muestra cotas y magnitudes sobre el dibujo: altura, base horizontal, corona, radio, centro, ancho de dovela, peso y angulo de base.
- Puede buscar automaticamente un circulo critico aproximado, probando centros sobre y detras del talud.
- Considera nivel freatico horizontal, peso unitario sobre NAF, peso saturado y presion de poros `uL`.
- Permite trabajar en `SI (kPa, kN/m3)` o en `Toneladas metricas (t/m2, t/m3)`.
- Calcula tabla por dovela: area, peso, angulo de base, longitud de arco, normal y fuerza actuante.
- Reporta el factor de seguridad por:
  - Fellenius u ordinario de dovelas.
  - Bishop simplificado, con iteracion automatica.

## Datos principales

- `c' cohesion (kPa)`
- `Angulo phi (grados)`
- `Gamma sobre NAF (kN/m3)`
- `Gamma saturado (kN/m3)`
- `Gamma agua (kN/m3)`
- `Nivel freatico Y (m)`
- `Altura H (m)`
- `Angulo del talud beta (grados)`
- `Centro X`, `Centro Y` y `Radio R` del circulo de falla
- `Numero de dovelas`

El circulo debe cortar el terreno en dos puntos para que el calculo sea valido.

La casilla `Buscar circulo critico automaticamente` prueba una malla de centros posibles y adopta el circulo que produce el menor F.S. de Bishop simplificado. Si quieres probar una superficie de falla especifica, desmarca esa casilla y escribe `Centro X`, `Centro Y` y `Radio R`.

La casilla `Numero de dovelas automatico` ajusta la discretizacion a la geometria de la masa deslizante. Usa entre 8 y 30 dovelas, buscando un ancho aproximado de `H/6`; si necesitas reproducir un ejercicio exacto, desmarca la casilla y escribe el numero de dovelas manualmente.

El nivel freatico se modela como una linea horizontal de cota `Y`. Por debajo de esa linea se usa `Gamma saturado`; por encima se usa `Gamma sobre NAF`. En la resistencia se resta la presion de poros de la normal efectiva.
