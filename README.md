# Sistema de inventario por municipio y asesor

Aplicación web sencilla para controlar stock por municipio y por asesor, con registro de ingresos, salidas y trazabilidad de movimientos.

## Funcionalidades

- Registro de productos
- Registro de municipios
- Registro de asesores por municipio
- Ingreso de stock con distribución automática o manual
- Control de salidas por asesor
- Consulta del stock disponible por asesor y municipio
- Historial de movimientos con cantidad, fecha y observación
- Registro de aforos con cliente, fecha fija, número de factura y detalle por recipiente

## Estructura del proyecto

- `app.py`: punto de entrada de Flask y compatibilidad con las funciones públicas existentes.
- `inventory/database.py`: conexión, inicialización, persistencia y consultas.
- `inventory/stock.py`: reglas de distribución de ingresos y registro de salidas.
- `inventory/routes.py`: rutas HTTP y comunicación con las plantillas.
- `inventory/aforo.py` y `inventory/aforo_routes.py`: datos y rutas del módulo de aforos.
- `templates/aforos.html`: registro y consulta de aforos.
- `templates/` y `static/`: vistas HTML y estilos.

## Módulo de aforos

Desde la sección **Aforos** se puede mantener una fecha activa que se conserva al recargar
la aplicación, ingresar un cliente (los nombres nuevos se agregan al catálogo) y guardar un
aforo/factura con varias filas de recipiente, cantidad entera y observación. Los recipientes
se administran desde el catálogo del mismo módulo y se sugieren al escribir. Los usuarios
pueden activarse o desactivarse desde su catálogo; solo los activos aparecen en las sugerencias
y los inactivos no pueden asociarse a nuevos aforos, aunque se conserva su historial.
El autocompletado de recipientes y usuarios busca también dentro del nombre (por ejemplo, `55`
encuentra `Caneca 55 gl`); `Tab` selecciona la coincidencia y las flechas permiten elegir otra.
En la tabla, `Tab` desde Observación agrega una fila nueva; `Tab` desde un recipiente vacío
lleva al botón de guardado, y `Enter` desde cualquier campo de la tabla intenta guardar el aforo.
Solo usuario y número de aforo son obligatorios; se puede guardar sin detalle. Si se completa
parcialmente una fila de detalle, el formulario pide recipiente y cantidad para evitar descartar datos.

## Requisitos

- Python 3.12+
- Flask

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar la aplicación

```bash
python app.py
```

Luego abrir http://localhost:5000

## Datos por defecto

La primera ejecución crea un municipio de ejemplo llamado "Yumbo" con tres asesores:

- Asesor A
- Asesor B
- Asesor C

## Lógica de inventario

- Si la distribución es automática, el sistema reparte la cantidad entre los asesores del municipio en forma equitativa.
- Si no se divide exactamente, el sobrante queda como stock sin asignar.
- Si la distribución es manual, se puede definir la cantidad exacta por asesor y el sobrante queda sin asignar.
- Las salidas validan que el asesor tenga disponibilidad suficiente antes de descontar stock.

## Ejecutar pruebas

```bash
python -m unittest test_app.py
```
