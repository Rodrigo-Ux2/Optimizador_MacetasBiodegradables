# Sistema Productivo de Macetas Biodegradables

Proyecto en Python 3.11 para dimensionar equipos por fase y optimizar la produccion de macetas biodegradables (cascaras de huevo + alginato).

**Modos**
1. `maximize_Q`: maximiza la produccion con tiempo fijo `T`.
2. `minimize_time`: minimiza el tiempo requerido para `Q_obj`. Si no es posible dentro de `T`, devuelve la produccion maxima alcanzable en `T`.

**Estructura**
1. `src/model.py`: dataclasses y validacion.
2. `src/optimizer.py`: enumeracion discreta.
3. `src/bottleneck.py`: deteccion de cuello de botella.
4. `src/simulate.py`: simulacion por eventos discretos (opcional).
5. `src/main.py`: CLI.
6. `configs/`: ejemplos.

## Requisitos
Python 3.11, solo standard library.

## Uso
```bash
python main.py --config configs/ejemplo_1.json
```

## Interfaz grafica
```bash
python gui.py
```

La interfaz permite editar parametros, cargar un JSON y ejecutar el modelo con el boton "Calcular".

Salida en consola y un JSON con resultados. El archivo se define con `output_path` en el config.

## Configuracion (campos principales)
1. `mode`: `maximize_Q` o `minimize_time`.
2. `T`: tiempo disponible (min). En `minimize_time` puede usarse `T_max`.
3. `P`: personas disponibles.
4. `M`: materia prima disponible (g).
5. `a`: gramos por maceta (default 155).
6. `t_p`, `t_m`, `t_c`: tiempos promedio (min).
7. Limites de equipos:
   - `L_p_min`, `L_p_max`: minimo y maximo de balanzas.
   - `L_m_min`, `L_m_max`: minimo y maximo de bowls.
   - `L_o_min`, `L_o_max`: minimo y maximo de moldes.
   - (Compatibilidad) `L_p`, `L_m`, `L_o` se interpretan como maximos.
8. `Q_obj`: cantidad objetivo (solo en `minimize_time`).
9. El acoplamiento fue desactivado en esta version porque puede generar resultados inconsistentes.
10. `simulation_on`: activar simulacion.
11. `simulation_save_schedule`: incluir cronograma detallado (puede ser grande).

## Salida (resumen)
1. Equipos optimos por fase.
2. Produccion maxima o tiempo requerido.
3. Cuello de botella.
4. Verificacion de restricciones.
5. (Opcional) metricas de simulacion: utilizacion y colas.

## Ejemplos
```bash
python main.py --config configs/ejemplo_1.json
python main.py --config configs/ejemplo_2.json
```
