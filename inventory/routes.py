from flask import flash, redirect, render_template, request, url_for

from inventory.database import (
    get_db,
    list_advisors,
    list_advisors_by_municipality,
    list_municipalities,
    list_products,
    municipality_product_totals,
    municipality_report_data,
    recent_movements,
    stock_summary,
)
from inventory.stock import apply_entry, apply_output
from inventory.aforo_routes import register_aforo_routes


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


def report_view():
    return render_template("report.html", municipality_reports=municipality_report_data())


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


def register_routes(app):
    app.add_url_rule("/", endpoint="index", view_func=index)
    app.add_url_rule("/reporte", endpoint="report_view", view_func=report_view)
    app.add_url_rule("/producto", endpoint="create_product", view_func=create_product, methods=["POST"])
    app.add_url_rule("/municipio", endpoint="create_municipality", view_func=create_municipality, methods=["POST"])
    app.add_url_rule("/asesor", endpoint="create_advisor", view_func=create_advisor, methods=["POST"])
    app.add_url_rule("/ingreso", endpoint="create_entry", view_func=create_entry, methods=["POST"])
    app.add_url_rule("/salida", endpoint="create_output", view_func=create_output, methods=["POST"])
    register_aforo_routes(app)
