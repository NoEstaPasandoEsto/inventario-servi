from inventory.database import (
    get_db,
    get_stock_row,
    list_advisors,
    record_movement,
    upsert_stock,
)


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
