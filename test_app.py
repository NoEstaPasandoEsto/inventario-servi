import os
import tempfile
import unittest

os.environ["INVENTORY_DB_PATH"] = os.path.join(tempfile.gettempdir(), "inventory_test.db")

import app as inventory_app


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


if __name__ == "__main__":
    unittest.main()
