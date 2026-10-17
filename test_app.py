import os
import sqlite3
import tempfile
import unittest

os.environ["INVENTORY_DB_PATH"] = os.path.join(tempfile.gettempdir(), "inventory_test.db")

import app as inventory_app
import inventory.database as inventory_database
from inventory.aforo import create_container, list_clients


class InventoryAppTests(unittest.TestCase):
    def setUp(self):
        if os.path.exists(os.environ["INVENTORY_DB_PATH"]):
            os.remove(os.environ["INVENTORY_DB_PATH"])
        inventory_app.init_db()
        self.client = inventory_app.app.test_client()

    def test_auto_distribution_even_split(self):
        product = inventory_app.list_products()[0]
        municipality = inventory_app.list_municipalities()[0]
        advisors = [a for a in inventory_app.list_advisors() if a["municipality_id"] == municipality["id"]]

        inventory_app.apply_entry(product["id"], municipality["id"], 9, "auto", "test", {})

        for advisor in advisors:
            row = inventory_app.get_stock_row(product["id"], municipality["id"], advisor["id"])
            self.assertEqual(row["quantity"], 3)

    def test_output_rejects_unsufficient_stock(self):
        product = inventory_app.list_products()[0]
        municipality = inventory_app.list_municipalities()[0]
        advisor = [a for a in inventory_app.list_advisors() if a["municipality_id"] == municipality["id"]][0]

        inventory_app.apply_entry(product["id"], municipality["id"], 2, "auto", "test", {})

        with self.assertRaises(ValueError):
            inventory_app.apply_output(product["id"], municipality["id"], advisor["id"], 3, "fallido")

    def test_manual_distribution_keeps_unassigned_leftover(self):
        product = inventory_app.list_products()[0]
        municipality = inventory_app.list_municipalities()[0]
        advisors = [a for a in inventory_app.list_advisors() if a["municipality_id"] == municipality["id"]]
        allocations = {str(advisors[0]["id"]): 2, str(advisors[1]["id"]): 1}

        inventory_app.apply_entry(product["id"], municipality["id"], 5, "manual", "manual", allocations)

        self.assertEqual(inventory_app.get_stock_row(product["id"], municipality["id"], advisors[0]["id"])["quantity"], 2)
        self.assertEqual(inventory_app.get_stock_row(product["id"], municipality["id"], advisors[1]["id"])["quantity"], 1)
        self.assertEqual(inventory_app.get_stock_row(product["id"], municipality["id"], None)["quantity"], 2)

    def test_aforo_saves_header_and_multiple_items_with_fixed_date(self):
        self.client.post(
            "/aforos/fecha",
            data={"record_date": "2026-10-12"},
        )
        self.client.post(
            "/aforos/recipientes",
            data={"name": "Canastilla"},
        )
        self.client.post(
            "/aforos/recipientes",
            data={"name": "Tambor"},
        )

        response = self.client.post(
            "/aforos",
            data={
                "client_name": "Cliente de prueba",
                "aforo_number": "FAC-0042",
                "container[]": ["Canastilla", "Tambor"],
                "quantity[]": ["4", "2"],
                "observation[]": ["Llenas", "Con tapa"],
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = inventory_app.get_db()
        try:
            record = conn.execute(
                """
                SELECT r.aforo_number, r.record_date, c.name AS client_name
                FROM aforo_records r JOIN clients c ON c.id = r.client_id
                """
            ).fetchone()
            items = conn.execute(
                """
                SELECT c.name AS container_name, i.quantity, i.observation
                FROM aforo_items i JOIN containers c ON c.id = i.container_id
                ORDER BY i.id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(record["aforo_number"], "FAC-0042")
        self.assertEqual(record["record_date"], "2026-10-12")
        self.assertEqual(record["client_name"], "Cliente de prueba")
        self.assertEqual(
            [(item["container_name"], item["quantity"], item["observation"]) for item in items],
            [("Canastilla", 4, "Llenas"), ("Tambor", 2, "Con tapa")],
        )
        history_response = self.client.get("/aforos")
        self.assertEqual(history_response.status_code, 200)
        self.assertIn("Canastilla", history_response.get_data(as_text=True))

        self.client.post(
            "/aforos",
            data={
                "client_name": "Otro cliente",
                "aforo_number": "FAC-0043",
                "container[]": ["Tambor"],
                "quantity[]": ["1"],
                "observation[]": [""],
            },
        )
        conn = inventory_app.get_db()
        try:
            fixed_date = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'aforo_date'"
            ).fetchone()["value"]
        finally:
            conn.close()
        self.assertEqual(fixed_date, "2026-10-12")

    def test_aforo_rejects_unknown_container_without_saving_record(self):
        self.client.post(
            "/aforos",
            data={
                "client_name": "No debe guardarse",
                "aforo_number": "FAC-0001",
                "container[]": ["Recipiente inexistente"],
                "quantity[]": ["1"],
                "observation[]": [""],
            },
        )
        conn = inventory_app.get_db()
        try:
            record_count = conn.execute("SELECT COUNT(*) FROM aforo_records").fetchone()[0]
            client_count = conn.execute(
                "SELECT COUNT(*) FROM clients WHERE name = ?",
                ("No debe guardarse",),
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(record_count, 0)
        self.assertEqual(client_count, 0)

    def test_aforo_page_is_available(self):
        response = self.client.get("/aforos")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Registro de aforos", page)
        self.assertNotIn('id="add-aforo-line"', page)
        self.assertIn("input[name=\"observation[]\"]", page)
        self.assertNotIn('name="container[]" list="container-options" autocomplete="on" placeholder="Escriba para buscar" required', page)
        self.assertNotIn('name="quantity[]" min="1" step="1" inputmode="numeric" required', page)

    def test_aforo_can_be_saved_without_container_details(self):
        response = self.client.post(
            "/aforos",
            data={
                "client_name": "Cliente sin recipiente",
                "aforo_number": "FAC-0050",
                "container[]": [""],
                "quantity[]": [""],
                "observation[]": [""],
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = inventory_app.get_db()
        try:
            record_count = conn.execute(
                "SELECT COUNT(*) FROM aforo_records WHERE aforo_number = ?",
                ("FAC-0050",),
            ).fetchone()[0]
            item_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM aforo_items i
                JOIN aforo_records r ON r.id = i.record_id
                WHERE r.aforo_number = ?
                """,
                ("FAC-0050",),
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(record_count, 1)
        self.assertEqual(item_count, 0)

        page_response = self.client.get("/aforos")
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("FAC-0050", page_response.get_data(as_text=True))
        self.assertIn(
            "Aforo guardado sin detalle de recipientes.",
            page_response.get_data(as_text=True),
        )

    def test_container_autocomplete_supports_partial_catalog_matches(self):
        create_container("Caneca 55 gl")

        response = self.client.get("/aforos")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Caneca 55 gl", page)
        self.assertIn(".toLocaleLowerCase().includes(query)", page)

    def test_user_autocomplete_only_suggests_active_users(self):
        self.client.post(
            "/aforos",
            data={
                "client_name": "Cliente activo 55",
                "aforo_number": "FAC-0060",
            },
        )
        conn = inventory_app.get_db()
        try:
            client_id = conn.execute(
                "SELECT id FROM clients WHERE name = ?",
                ("Cliente activo 55",),
            ).fetchone()["id"]
        finally:
            conn.close()

        active_page = self.client.get("/aforos").get_data(as_text=True)
        self.assertIn('const clientOptions = ["Cliente activo 55"]', active_page)
        self.assertIn(".toLocaleLowerCase().includes(query)", active_page)

        self.client.post(
            f"/aforos/usuarios/{client_id}/estado",
            data={"active": "0"},
        )
        inactive_page = self.client.get("/aforos").get_data(as_text=True)
        self.assertIn("Cliente activo 55", inactive_page)
        self.assertIn("const clientOptions = []", inactive_page)

        self.client.post(
            "/aforos",
            data={
                "client_name": "Cliente activo 55",
                "aforo_number": "FAC-0061",
            },
        )
        conn = inventory_app.get_db()
        try:
            record_count = conn.execute(
                "SELECT COUNT(*) FROM aforo_records WHERE aforo_number = ?",
                ("FAC-0061",),
            ).fetchone()[0]
            active_status = conn.execute(
                "SELECT active FROM clients WHERE id = ?",
                (client_id,),
            ).fetchone()["active"]
        finally:
            conn.close()
        self.assertEqual(record_count, 0)
        self.assertEqual(active_status, 0)

        self.client.post(
            f"/aforos/usuarios/{client_id}/estado",
            data={"active": "1"},
        )
        self.client.post(
            "/aforos",
            data={
                "client_name": "Cliente activo 55",
                "aforo_number": "FAC-0062",
            },
        )
        conn = inventory_app.get_db()
        try:
            reactivated_count = conn.execute(
                "SELECT COUNT(*) FROM aforo_records WHERE aforo_number = ?",
                ("FAC-0062",),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(reactivated_count, 1)

    def test_legacy_client_table_migrates_existing_users_as_active(self):
        original_db_path = inventory_database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            inventory_database.DB_PATH = os.path.join(temp_dir, "legacy.db")
            try:
                conn = sqlite3.connect(inventory_database.DB_PATH)
                conn.execute(
                    """
                    CREATE TABLE clients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute("INSERT INTO clients (name) VALUES (?)", ("Usuario antiguo",))
                conn.commit()
                conn.close()

                inventory_app.init_db()

                clients = list_clients()
                self.assertEqual(
                    [(client["name"], client["active"]) for client in clients],
                    [("Usuario antiguo", 1)],
                )
            finally:
                inventory_database.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
