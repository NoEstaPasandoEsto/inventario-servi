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
