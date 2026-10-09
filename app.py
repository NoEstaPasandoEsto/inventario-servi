import os
import sqlite3
from typing import Iterable

from flask import Flask, flash, redirect, render_template, request, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("INVENTORY_DB_PATH", os.path.join(BASE_DIR, "inventory.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = "inventory-demo-secret"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as file:
        schema = file.read()
    conn = get_db()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    ensure_seed_data()


def ensure_seed_data():
    conn = get_db()
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if product_count == 0:
        conn.execute(
            "INSERT INTO products (name, sku, unit) VALUES (?, ?, ?)",
            ("Producto base", "P-001", "unidad"),
        )

    municipality_count = conn.execute("SELECT COUNT(*) FROM municipalities").fetchone()[0]
    if municipality_count == 0:
        conn.execute("INSERT INTO municipalities (name) VALUES (?)", ("Yumbo",))
        municipality_id = conn.execute("SELECT id FROM municipalities WHERE name = ?", ("Yumbo",)).fetchone()[0]
        advisors = ["Asesor A", "Asesor B", "Asesor C"]
        for name in advisors:
            conn.execute(
                "INSERT INTO advisors (name, municipality_id) VALUES (?, ?)",
                (name, municipality_id),
            )

    conn.commit()
    conn.close()


def list_products():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_municipalities():
    conn = get_db()
    rows = conn.execute("SELECT * FROM municipalities ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_advisors():
    conn = get_db()
    rows = conn.execute(
        "SELECT a.*, m.name AS municipality_name FROM advisors a JOIN municipalities m ON m.id = a.municipality_id ORDER BY m.name, a.name"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_advisors_by_municipality():
    data = {}
    for advisor in list_advisors():
        data.setdefault(advisor["municipality_id"], []).append({
            "id": advisor["id"],
            "name": advisor["name"],
        })
    return data


def get_stock_row(product_id, municipality_id, advisor_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM stock WHERE product_id = ? AND municipality_id = ? AND advisor_id IS ?",
        (product_id, municipality_id, advisor_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_stock(product_id, municipality_id, advisor_id, quantity):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM stock WHERE product_id = ? AND municipality_id = ? AND advisor_id IS ?",
        (product_id, municipality_id, advisor_id),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO stock (product_id, municipality_id, advisor_id, quantity, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (product_id, municipality_id, advisor_id, quantity),
        )
    else:
        conn.execute(
            "UPDATE stock SET quantity = quantity + ?, updated_at = datetime('now') WHERE id = ?",
            (quantity, row["id"]),
        )
    conn.commit()
    conn.close()


def record_movement(product_id, municipality_id, advisor_id, movement_type, quantity, note=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO movements (product_id, municipality_id, advisor_id, type, quantity, note) VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, municipality_id, advisor_id, movement_type, quantity, note),
    )
    conn.commit()
    conn.close()


def recent_movements(limit=20):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT m.*, p.name AS product_name, mu.name AS municipality_name, a.name AS advisor_name
        FROM movements m
        JOIN products p ON p.id = m.product_id
        JOIN municipalities mu ON mu.id = m.municipality_id
        LEFT JOIN advisors a ON a.id = m.advisor_id
        ORDER BY m.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def stock_summary():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT p.id AS product_id,
               p.name AS product_name,
               mu.id AS municipality_id,
               mu.name AS municipality_name,
               a.id AS advisor_id,
               a.name AS advisor_name,
               COALESCE(s.quantity, 0) AS quantity
        FROM products p
        CROSS JOIN municipalities mu
        LEFT JOIN advisors a ON a.municipality_id = mu.id
        LEFT JOIN stock s ON s.product_id = p.id AND s.municipality_id = mu.id AND s.advisor_id = a.id
        ORDER BY p.name, mu.name, a.name
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def municipality_product_totals():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT p.id AS product_id,
               p.name AS product_name,
               mu.id AS municipality_id,
               mu.name AS municipality_name,
               COALESCE(SUM(s.quantity), 0) AS total_quantity
        FROM products p
        CROSS JOIN municipalities mu
        LEFT JOIN stock s ON s.product_id = p.id AND s.municipality_id = mu.id
        GROUP BY p.id, p.name, mu.id, mu.name
        ORDER BY p.name, mu.name
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def municipality_report_data():
    conn = get_db()
    municipalities = conn.execute("SELECT * FROM municipalities ORDER BY name ASC").fetchall()
    report = []

    for municipality in municipalities:
        advisor_rows = conn.execute(
            """
            SELECT a.name AS advisor_name,
                   COALESCE(SUM(s.quantity), 0) AS total_quantity
            FROM advisors a
            LEFT JOIN stock s ON s.advisor_id = a.id AND s.municipality_id = a.municipality_id
            WHERE a.municipality_id = ?
            GROUP BY a.id, a.name
            ORDER BY a.name
            """,
            (municipality["id"],),
        ).fetchall()

        product_rows = conn.execute(
            """
            SELECT p.name AS product_name,
                   COALESCE(SUM(s.quantity), 0) AS total_quantity
            FROM products p
            LEFT JOIN stock s ON s.product_id = p.id AND s.municipality_id = ?
            GROUP BY p.id, p.name
            ORDER BY p.name
            """,
            (municipality["id"],),
        ).fetchall()

        movement_rows = conn.execute(
            """
            SELECT m.created_at,
                   p.name AS product_name,
                   a.name AS advisor_name,
                   m.type,
                   m.quantity,
                   m.note
            FROM movements m
            JOIN products p ON p.id = m.product_id
            LEFT JOIN advisors a ON a.id = m.advisor_id
            WHERE m.municipality_id = ?
            ORDER BY m.id DESC
            LIMIT 8
            """,
            (municipality["id"],),
        ).fetchall()

        totals = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'entry' THEN quantity ELSE 0 END), 0) AS total_entries,
                COALESCE(SUM(CASE WHEN type = 'output' THEN quantity ELSE 0 END), 0) AS total_outputs,
                COALESCE(SUM(CASE WHEN type = 'entry' THEN quantity ELSE 0 END) - SUM(CASE WHEN type = 'output' THEN quantity ELSE 0 END), 0) AS net_balance
            FROM movements
            WHERE municipality_id = ?
            """,
            (municipality["id"],),
        ).fetchone()

        report.append({
            "municipality": dict(municipality),
            "advisors": [dict(row) for row in advisor_rows],
            "products": [dict(row) for row in product_rows],
            "movements": [dict(row) for row in movement_rows],
            "totals": dict(totals),
        })

    conn.close()
    return report


def apply_entry(product_id, municipality_id, quantity, mode, notes, allocations):
    if quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    if mode == "auto":
        advisors = [a for a in list_advisors() if a["municipality_id"] == municipality_id]
        if not advisors:
            upsert_stock(product_id, municipality_id, None, quantity)
            record_movement(product_id, municipality_id, None, "entry", quantity, notes or "Ingreso automático sin asesores")
            return

        base = quantity // len(advisors)
        remainder = quantity % len(advisors)
        for index, advisor in enumerate(advisors):
            assigned = base + (1 if index < remainder else 0)
            if assigned > 0:
                upsert_stock(product_id, municipality_id, advisor["id"], assigned)
                record_movement(product_id, municipality_id, advisor["id"], "entry", assigned, notes or "Ingreso automático")
        return

    total_allocated = sum(int(value) for value in allocations.values() if int(value) > 0)
    if total_allocated > quantity:
        raise ValueError("La suma asignada no puede superar la cantidad del ingreso.")

    remaining = quantity - total_allocated
    if remaining > 0:
        upsert_stock(product_id, municipality_id, None, remaining)
        record_movement(product_id, municipality_id, None, "entry", remaining, notes or "Ingreso sin asignar")

    for advisor_id, value in allocations.items():
        amount = int(value)
        if amount > 0:
            upsert_stock(product_id, municipality_id, int(advisor_id), amount)
            record_movement(product_id, municipality_id, int(advisor_id), "entry", amount, notes or "Ingreso manual")


def apply_output(product_id, municipality_id, advisor_id, quantity, note):
    if quantity <= 0:
        raise ValueError("La cantidad de salida debe ser mayor que cero.")

    current = get_stock_row(product_id, municipality_id, advisor_id)
    current_quantity = current["quantity"] if current else 0
    if current_quantity < quantity:
        raise ValueError("No hay disponibilidad suficiente para el asesor seleccionado.")

    conn = get_db()
    conn.execute(
        "UPDATE stock SET quantity = quantity - ?, updated_at = datetime('now') WHERE product_id = ? AND municipality_id = ? AND advisor_id IS ?",
        (quantity, product_id, municipality_id, advisor_id),
    )
    conn.commit()
    conn.close()
    record_movement(product_id, municipality_id, advisor_id, "output", quantity, note or "Salida de inventario")


@app.route("/")
def index():
    summary = municipality_product_totals()
    stocks = stock_summary()
    products = list_products()
    municipalities = list_municipalities()
    advisors = list_advisors()
    advisor_map = list_advisors_by_municipality()
    movements = recent_movements(15)
    return render_template(
        "index.html",
        summary=summary,
        stocks=stocks,
        products=products,
        municipalities=municipalities,
        advisors=advisors,
        advisor_map=advisor_map,
        movements=movements,
    )


@app.route("/reporte")
def report_view():
    return render_template("report.html", municipality_reports=municipality_report_data())


@app.route("/producto", methods=["POST"])
def create_product():
    name = request.form.get("name", "").strip()
    sku = request.form.get("sku", "").strip()
    unit = request.form.get("unit", "unidad").strip() or "unidad"
    if not name:
        flash("Debe ingresar un nombre para el producto.")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, sku, unit) VALUES (?, ?, ?)",
        (name, sku or None, unit),
    )
    conn.commit()
    conn.close()
    flash("Producto registrado con éxito.")
    return redirect(url_for("index"))


@app.route("/municipio", methods=["POST"])
def create_municipality():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Debe ingresar el nombre del municipio.")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute("INSERT INTO municipalities (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    flash("Municipio registrado con éxito.")
    return redirect(url_for("index"))


@app.route("/asesor", methods=["POST"])
def create_advisor():
    name = request.form.get("name", "").strip()
    municipality_id = request.form.get("municipality_id")
    if not name or not municipality_id:
        flash("Debe completar nombre y municipio.")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute(
        "INSERT INTO advisors (name, municipality_id) VALUES (?, ?)",
        (name, municipality_id),
    )
    conn.commit()
    conn.close()
    flash("Asesor registrado con éxito.")
    return redirect(url_for("index"))


@app.route("/ingreso", methods=["POST"])
def create_entry():
    product_id = request.form.get("product_id")
    municipality_id = request.form.get("municipality_id")
    quantity = request.form.get("quantity", "0")
    mode = request.form.get("distribution_mode", "auto")
    note = request.form.get("note", "").strip()

    if not product_id or not municipality_id or not quantity:
        flash("Debe completar producto, municipio y cantidad.")
        return redirect(url_for("index"))

    try:
        quantity = int(quantity)
        if mode == "manual":
            allocations = {}
            for advisor in [a for a in list_advisors() if a["municipality_id"] == int(municipality_id)]:
                raw_value = request.form.get(f"alloc_{advisor['id']}", "0")
                allocations[str(advisor["id"])] = int(raw_value)
            apply_entry(int(product_id), int(municipality_id), quantity, mode, note, allocations)
        else:
            apply_entry(int(product_id), int(municipality_id), quantity, mode, note, {})
        flash("Ingreso registrado correctamente.")
    except ValueError as exc:
        flash(str(exc))

    return redirect(url_for("index"))


@app.route("/salida", methods=["POST"])
def create_output():
    product_id = request.form.get("product_id")
    municipality_id = request.form.get("municipality_id")
    advisor_id = request.form.get("advisor_id")
    quantity = request.form.get("quantity", "0")
    note = request.form.get("note", "").strip()

    if not product_id or not municipality_id or not advisor_id or not quantity:
        flash("Debe completar producto, municipio, asesor y cantidad.")
        return redirect(url_for("index"))

    try:
        apply_output(int(product_id), int(municipality_id), int(advisor_id), int(quantity), note)
        flash("Salida registrada correctamente.")
    except ValueError as exc:
        flash(str(exc))

    return redirect(url_for("index"))


init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
