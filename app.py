from flask import Flask

from inventory.database import (
    BASE_DIR,
    DB_PATH,
    ensure_seed_data,
    get_db,
    init_db,
    list_advisors,
    list_advisors_by_municipality,
    list_municipalities,
    list_products,
    municipality_product_totals,
    municipality_report_data,
    recent_movements,
    record_movement,
    stock_summary,
    upsert_stock,
    get_stock_row,
)
from inventory.stock import apply_entry, apply_output
from inventory.routes import register_routes

__all__ = [
    "BASE_DIR",
    "DB_PATH",
    "app",
    "apply_entry",
    "apply_output",
    "create_app",
    "ensure_seed_data",
    "get_db",
    "get_stock_row",
    "init_db",
    "list_advisors",
    "list_advisors_by_municipality",
    "list_municipalities",
    "list_products",
    "municipality_product_totals",
    "municipality_report_data",
    "recent_movements",
    "record_movement",
    "stock_summary",
    "upsert_stock",
]


def create_app():
    application = Flask(__name__)
    application.config["SECRET_KEY"] = "inventory-demo-secret"
    register_routes(application)
    return application


app = create_app()
init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
