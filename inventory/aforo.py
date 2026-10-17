from datetime import date

from inventory.database import get_db


def get_aforo_date():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'aforo_date'"
        ).fetchone()
        if row is None:
            return date.today().isoformat()
        return row["value"]
    finally:
        conn.close()


def set_aforo_date(value):
    try:
        selected_date = date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("Seleccione una fecha válida.") from exc

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('aforo_date', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (selected_date,),
        )
        conn.commit()
    finally:
        conn.close()


def list_clients(active_only=False):
    conn = get_db()
    try:
        query = "SELECT id, name, active FROM clients"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name COLLATE NOCASE"
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def set_client_active(client_id, active):
    if not isinstance(active, bool):
        raise ValueError("El estado del usuario no es válido.")
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE clients SET active = ? WHERE id = ?",
            (int(active), client_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError("No se encontró el usuario.")
    finally:
        conn.close()


def list_containers():
    conn = get_db()
    try:
        rows = conn.execute("SELECT name FROM containers ORDER BY name COLLATE NOCASE").fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()


def create_container(name):
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Debe ingresar el nombre del recipiente.")

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO containers (name) VALUES (?)",
            (normalized_name,),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def save_aforo_record(client_name, aforo_number, items):
    client_name = client_name.strip()
    aforo_number = aforo_number.strip()
    if not client_name:
        raise ValueError("Debe ingresar el nombre del usuario o cliente.")
    if not aforo_number:
        raise ValueError("Debe ingresar el número de aforo o factura.")

    normalized_items = []
    for container_name, quantity, observation in items:
        container_name = container_name.strip()
        if not container_name:
            raise ValueError("Seleccione un recipiente para cada fila.")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("La cantidad de cada recipiente debe ser un entero mayor que cero.")
        normalized_items.append((container_name, quantity, observation.strip()))

    conn = get_db()
    try:
        with conn:
            containers = {}
            for container_name, _, _ in normalized_items:
                row = conn.execute(
                    "SELECT id FROM containers WHERE name = ? COLLATE NOCASE",
                    (container_name,),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        f"El recipiente «{container_name}» no existe en el catálogo."
                    )
                containers[container_name.casefold()] = row["id"]

            client = conn.execute(
                "SELECT id, active FROM clients WHERE name = ? COLLATE NOCASE",
                (client_name,),
            ).fetchone()
            if client is not None and not client["active"]:
                raise ValueError(
                    "Este usuario está inactivo. Active el usuario para registrar un aforo."
                )
            if client is None:
                cursor = conn.execute(
                    "INSERT INTO clients (name) VALUES (?)",
                    (client_name,),
                )
                client_id = cursor.lastrowid
            else:
                client_id = client["id"]
            record_date = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'aforo_date'"
            ).fetchone()["value"]
            cursor = conn.execute(
                """
                INSERT INTO aforo_records (client_id, aforo_number, record_date)
                VALUES (?, ?, ?)
                """,
                (client_id, aforo_number, record_date),
            )
            record_id = cursor.lastrowid
            conn.executemany(
                """
                INSERT INTO aforo_items (record_id, container_id, quantity, observation)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        record_id,
                        containers[container_name.casefold()],
                        quantity,
                        observation,
                    )
                    for container_name, quantity, observation in normalized_items
                ],
            )
    finally:
        conn.close()


def recent_aforo_records(limit=30):
    conn = get_db()
    try:
        records = conn.execute(
            """
            SELECT r.id, r.aforo_number, r.record_date, r.created_at, c.name AS client_name
            FROM aforo_records r
            JOIN clients c ON c.id = r.client_id
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        result = []
        for record in records:
            record_data = dict(record)
            record_data["aforo_items"] = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT c.name AS container_name, i.quantity, i.observation
                    FROM aforo_items i
                    JOIN containers c ON c.id = i.container_id
                    WHERE i.record_id = ?
                    ORDER BY i.id
                    """,
                    (record["id"],),
                ).fetchall()
            ]
            result.append(record_data)
        return result
    finally:
        conn.close()
