import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("INVENTORY_DB_PATH", os.path.join(BASE_DIR, "inventory.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open(os.path.join(BASE_DIR, "schema.sql"), "r", encoding="utf-8") as file:
        schema = file.read()
    conn = get_db()
    conn.executescript(schema)
    client_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(clients)").fetchall()
    }
    if "active" not in client_columns:
        conn.execute(
            "ALTER TABLE clients ADD COLUMN active INTEGER NOT NULL DEFAULT 1 "
            "CHECK (active IN (0, 1))"
        )
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
