import csv
import os
import sqlite3
from datetime import date, timedelta


BASE_DIR = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(BASE_DIR, "database", "retail_store.db")
CSV_PATH = os.path.join(BASE_DIR, "data", "retail_sales.csv")


def get_connection(path=DATABASE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path=DATABASE_PATH):
    with get_connection(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL CHECK (price > 0),
                stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
                reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0)
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                sale_date TEXT NOT NULL,
                total_amount REAL NOT NULL CHECK (total_amount >= 0),
                customer_id TEXT,
                location TEXT,
                discount_applied TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
            );
            """
        )
        # Additive migration for existing local databases; historical rows are
        # preserved and the new metadata remains NULL until entered on a sale.
        existing_sales_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(sales)").fetchall()
        }
        for column in ("customer_id", "location", "discount_applied"):
            if column not in existing_sales_columns:
                connection.execute(f"ALTER TABLE sales ADD COLUMN {column} TEXT")
        product_count = connection.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
        if product_count == 0:
            seed_products(connection)
            seed_sales(connection)
        export_csv(connection)


def seed_products(connection):
    products = [
        ("Wireless Mouse", "Accessories", 799.0, 18, 8),
        ("Mechanical Keyboard", "Accessories", 2499.0, 7, 5),
        ("USB-C Hub", "Accessories", 1299.0, 12, 6),
        ("Laptop Stand", "Workspace", 1899.0, 5, 5),
        ("Notebook Set", "Stationery", 299.0, 34, 10),
        ("Gel Pen Pack", "Stationery", 149.0, 42, 12),
        ("Desk Lamp", "Workspace", 1599.0, 9, 5),
        ("Water Bottle", "Lifestyle", 699.0, 16, 6),
        ("Backpack", "Lifestyle", 2199.0, 8, 5),
        ("Power Bank", "Electronics", 1799.0, 11, 5),
        ("Bluetooth Speaker", "Electronics", 2299.0, 6, 4),
        ("Phone Tripod", "Electronics", 999.0, 14, 6),
    ]
    connection.executemany(
        """
        INSERT INTO products
        (product_name, category, price, stock_quantity, reorder_level)
        VALUES (?, ?, ?, ?, ?)
        """,
        products,
    )


def seed_sales(connection):
    quantities = [
        (1, 2), (5, 4), (2, 1), (8, 3), (10, 2), (6, 5),
        (3, 2), (1, 1), (7, 2), (9, 1), (4, 1), (12, 3),
        (11, 2), (5, 6), (2, 2), (10, 1), (8, 2), (6, 4),
        (3, 3), (1, 2), (7, 1), (9, 2), (12, 2), (11, 1),
        (5, 5), (2, 1), (10, 2), (8, 1), (6, 3), (3, 2),
        (1, 1), (7, 2), (9, 1), (12, 1), (11, 2), (4, 2),
    ]
    start = date.today() - timedelta(days=155)
    rows = []
    for index, (product_id, quantity) in enumerate(quantities):
        product = connection.execute("SELECT price FROM products WHERE id = ?", (product_id,)).fetchone()
        sale_day = start + timedelta(days=index * 4 + (index % 3))
        rows.append((product_id, quantity, sale_day.isoformat(), product["price"] * quantity))
    connection.executemany(
        "INSERT INTO sales (product_id, quantity, sale_date, total_amount) VALUES (?, ?, ?, ?)",
        rows,
    )


def export_csv(connection):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    rows = connection.execute(
        """
        SELECT s.id AS sale_id, p.product_name, p.category, p.price,
               s.quantity, s.total_amount, s.sale_date, s.customer_id,
               s.location, s.discount_applied
        FROM sales s JOIN products p ON p.id = s.product_id
        ORDER BY s.sale_date
        """
    ).fetchall()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "sale_id",
                "product_name",
                "category",
                "price",
                "quantity",
                "total_amount",
                "sale_date",
                "customer_id",
                "location",
                "discount_applied",
            ]
        )
        writer.writerows([tuple(row) for row in rows])


def get_user_by_email(email):
    if not email:
        return None
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    if not user_id:
        return None
    with get_connection() as connection:
        row = connection.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_products(search=""):
    with get_connection() as connection:
        if search:
            rows = connection.execute(
                """
                SELECT * FROM products
                WHERE product_name LIKE ? OR category LIKE ?
                ORDER BY product_name
                """,
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM products ORDER BY product_name").fetchall()
        return [dict(row) for row in rows]


def get_product(product_id):
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def add_product(product):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO products
            (product_name, category, price, stock_quantity, reorder_level)
            VALUES (:product_name, :category, :price, :stock_quantity, :reorder_level)
            """,
            product,
        )
        export_csv(connection)


def update_product(product_id, product):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE products
            SET product_name = :product_name, category = :category, price = :price,
                stock_quantity = :stock_quantity, reorder_level = :reorder_level
            WHERE id = :id
            """,
            {**product, "id": product_id},
        )
        export_csv(connection)


def delete_product(product_id):
    with get_connection() as connection:
        sales_count = connection.execute("SELECT COUNT(*) AS count FROM sales WHERE product_id = ?", (product_id,)).fetchone()["count"]
        if sales_count:
            raise ValueError("This product has sales history and cannot be deleted.")
        connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
        export_csv(connection)


def create_sale(product_id, quantity, sale_date, customer_id=None, location=None, discount_applied=None):
    with get_connection() as connection:
        product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            raise ValueError("Product not found.")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if quantity > product["stock_quantity"]:
            raise ValueError("Insufficient stock.")
        connection.execute(
            """
            INSERT INTO sales
            (product_id, quantity, sale_date, total_amount, customer_id, location, discount_applied)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                quantity,
                sale_date,
                product["price"] * quantity,
                customer_id,
                location,
                discount_applied,
            ),
        )
        connection.execute(
            "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
            (quantity, product_id),
        )
        export_csv(connection)


def get_sales_history(filters=None):
    filters = filters or {}
    clauses, params = [], []
    if filters.get("q"):
        clauses.append("(p.product_name LIKE ? OR p.category LIKE ?)")
        params.extend([f"%{filters['q']}%", f"%{filters['q']}%"])
    if filters.get("from_date"):
        clauses.append("s.sale_date >= ?")
        params.append(filters["from_date"])
    if filters.get("to_date"):
        clauses.append("s.sale_date <= ?")
        params.append(filters["to_date"])
    order = "ASC" if filters.get("sort") == "oldest" else "DESC"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT s.id, p.product_name, p.category, p.price, s.quantity,
                   s.total_amount, s.sale_date, s.customer_id, s.location,
                   s.discount_applied
            FROM sales s JOIN products p ON p.id = s.product_id
            {where}
            ORDER BY s.sale_date {order}, s.id {order}
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_dashboard_data():
    with get_connection() as connection:
        recent = connection.execute(
            """
            SELECT s.id, p.product_name, p.category, s.quantity, s.total_amount, s.sale_date
            FROM sales s JOIN products p ON p.id = s.product_id
            ORDER BY s.sale_date DESC, s.id DESC LIMIT 6
            """
        ).fetchall()
        products_count = connection.execute("SELECT COUNT(*) AS value FROM products").fetchone()["value"]
        items_sold = connection.execute("SELECT COALESCE(SUM(quantity), 0) AS value FROM sales").fetchone()["value"]
        current_stock = connection.execute("SELECT COALESCE(SUM(stock_quantity), 0) AS value FROM products").fetchone()["value"]
        low_stock = connection.execute("SELECT COUNT(*) AS value FROM products WHERE stock_quantity <= reorder_level").fetchone()["value"]
        categories = connection.execute("SELECT COUNT(DISTINCT category) AS value FROM products").fetchone()["value"]
        total_sales = connection.execute("SELECT COALESCE(SUM(total_amount), 0) AS value FROM sales").fetchone()["value"]
        return {
            "total_sales": float(total_sales),
            "total_products": products_count,
            "items_sold": items_sold,
            "current_stock": current_stock,
            "low_stock": low_stock,
            "categories": categories,
            "recent_sales": [dict(row) for row in recent],
        }


def get_categories():
    with get_connection() as connection:
        return [row["category"] for row in connection.execute("SELECT DISTINCT category FROM products ORDER BY category")]