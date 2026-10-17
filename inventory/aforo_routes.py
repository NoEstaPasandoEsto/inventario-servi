from flask import Blueprint, flash, redirect, render_template, request, url_for

from inventory.aforo import (
    create_container,
    get_aforo_date,
    list_clients,
    list_containers,
    recent_aforo_records,
    save_aforo_record,
    set_client_active,
    set_aforo_date,
)

aforo_blueprint = Blueprint("aforos_module", __name__)


@aforo_blueprint.get("/aforos")
def aforos():
    return render_template(
        "aforos.html",
        aforo_date=get_aforo_date(),
        clients=list_clients(),
        active_clients=list_clients(active_only=True),
        containers=list_containers(),
        records=recent_aforo_records(),
    )


@aforo_blueprint.post("/aforos/fecha")
def change_aforo_date():
    try:
        set_aforo_date(request.form.get("record_date", ""))
        flash("La fecha quedó fijada para los próximos aforos.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("aforos_module.aforos"))


@aforo_blueprint.post("/aforos/recipientes")
def add_container():
    try:
        created = create_container(request.form.get("name", ""))
        flash(
            "Recipiente agregado al catálogo."
            if created
            else "Ese recipiente ya existe en el catálogo."
        )
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("aforos_module.aforos"))


@aforo_blueprint.post("/aforos/usuarios/<int:client_id>/estado")
def change_client_status(client_id):
    active_value = request.form.get("active")
    try:
        if active_value not in {"0", "1"}:
            raise ValueError("El estado del usuario no es válido.")
        active = active_value == "1"
        set_client_active(client_id, active)
        flash(
            "Usuario activado."
            if active
            else "Usuario desactivado; se conserva su historial."
        )
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("aforos_module.aforos"))


@aforo_blueprint.post("/aforos")
def create_aforo():
    container_names = request.form.getlist("container[]")
    quantities = request.form.getlist("quantity[]")
    observations = request.form.getlist("observation[]")
    items = []

    try:
        if not (len(container_names) == len(quantities) == len(observations)):
            raise ValueError("Revise las filas de recipientes antes de guardar.")
        for container_name, raw_quantity, observation in zip(
            container_names, quantities, observations
        ):
            container_name = container_name.strip()
            raw_quantity = raw_quantity.strip()
            observation = observation.strip()
            if not container_name and not raw_quantity and not observation:
                continue
            if not container_name or not raw_quantity:
                raise ValueError(
                    "Complete recipiente y cantidad en cada fila que quiera registrar."
                )
            try:
                quantity = int(raw_quantity)
            except ValueError as exc:
                raise ValueError("La cantidad debe ser un número entero.") from exc
            items.append((container_name, quantity, observation))

        save_aforo_record(
            request.form.get("client_name", ""),
            request.form.get("aforo_number", ""),
            items,
        )
        flash("Aforo guardado con su usuario, fecha y detalle.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("aforos_module.aforos"))


def register_aforo_routes(app):
    app.register_blueprint(aforo_blueprint)
