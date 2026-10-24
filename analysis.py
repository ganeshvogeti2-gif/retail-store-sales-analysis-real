import os
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from database import CSV_PATH, DATABASE_PATH


BASE_DIR = os.path.dirname(__file__)
CHART_DIR = os.path.join(BASE_DIR, "static", "charts")
CLEANED_CSV_PATH = os.path.join(BASE_DIR, "data", "cleaned_retail_store_sales.csv")

COLUMN_ALIASES = {
    "transaction id": "sale_id",
    "transaction date": "sale_date",
    "item": "product_name",
    "price per unit": "price",
    "total spent": "total_amount",
    "customer id": "customer_id",
    "discount applied": "discount_applied",
}


def _normalize_columns(frame):
    rename = {}
    for column in frame.columns:
        normalized = str(column).strip().casefold()
        target = COLUMN_ALIASES.get(normalized, normalized.replace(" ", "_"))
        if target not in frame.columns or target == column:
            rename[column] = target
    return frame.rename(columns=rename)


def clean_sales_data(frame):
    """Clean sales rows while retaining the existing SQLite/CSV column names.

    The app's current schema has no customer, location, or discount fields.
    The cleaner accepts the names used in the attached sample code as aliases
    if those fields are supplied in a future CSV.
    """
    frame = _normalize_columns(frame.copy())
    required = {"sale_date", "product_name", "category", "price", "quantity", "total_amount"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Sales data is missing required columns: {', '.join(sorted(missing))}")

    frame = frame.drop_duplicates().copy()
    if frame.empty:
        frame["sale_date"] = pd.to_datetime(frame["sale_date"])
        frame["month"] = pd.Series(dtype="object")
        frame["year_month"] = pd.Series(dtype="object")
        frame["year"] = pd.Series(dtype="int64")
        return frame

    frame["sale_date"] = pd.to_datetime(frame["sale_date"], errors="coerce")
    for column in ("price", "quantity", "total_amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    known_prices = frame.dropna(subset=["product_name", "price"])

    def most_common_price(values):
        modes = values.mode(dropna=True)
        return modes.iloc[0] if not modes.empty else np.nan

    price_by_product = known_prices.groupby("product_name")["price"].agg(most_common_price)

    missing_price = frame["price"].isna()
    frame.loc[missing_price, "price"] = frame.loc[missing_price, "product_name"].map(price_by_product)

    # Fill an unknown unit price from known transaction total and quantity.
    missing_price = frame["price"].isna()
    can_derive_price = missing_price & frame["total_amount"].notna() & frame["quantity"].gt(0)
    frame.loc[can_derive_price, "price"] = (
        frame.loc[can_derive_price, "total_amount"] / frame.loc[can_derive_price, "quantity"]
    )

    # Match the attached cleaning approach for missing quantity and total.
    missing_quantity = frame["quantity"].isna()
    can_derive_quantity = missing_quantity & frame["total_amount"].notna() & frame["price"].gt(0)
    frame.loc[can_derive_quantity, "quantity"] = (
        frame.loc[can_derive_quantity, "total_amount"] / frame.loc[can_derive_quantity, "price"]
    ).round()

    missing_total = frame["total_amount"].isna()
    can_derive_total = missing_total & frame["price"].notna() & frame["quantity"].notna()
    frame.loc[can_derive_total, "total_amount"] = (
        frame.loc[can_derive_total, "price"] * frame.loc[can_derive_total, "quantity"]
    )

    frame = frame.dropna(
        subset=["sale_date", "product_name", "category", "price", "quantity", "total_amount"]
    ).copy()
    frame = frame[
        frame["price"].gt(0)
        & frame["quantity"].gt(0)
        & frame["total_amount"].ge(0)
        & np.isclose(frame["quantity"], frame["quantity"].round())
    ].copy()
    frame["quantity"] = frame["quantity"].astype(int)
    frame["month"] = frame["sale_date"].dt.strftime("%b")
    frame["year_month"] = frame["sale_date"].dt.to_period("M").astype(str)
    frame["year"] = frame["sale_date"].dt.year.astype(int)

    if "discount_applied" in frame.columns:
        def discount_label(value):
            if pd.isna(value):
                return "Unknown"
            if isinstance(value, (bool, np.bool_)):
                return "Yes" if value else "No"
            value = str(value).strip().casefold()
            if value in {"true", "yes"}:
                return "Yes"
            if value in {"false", "no"}:
                return "No"
            return "Unknown"

        frame["discount_applied"] = frame["discount_applied"].map(discount_label)

    return frame.sort_values(["sale_date", "sale_id"] if "sale_id" in frame.columns else ["sale_date"])


def save_cleaned_sales_data(frame, output_path=CLEANED_CSV_PATH):
    output_directory = os.path.dirname(output_path)
    if output_directory:
        os.makedirs(output_directory, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def load_sales_data(db_path=DATABASE_PATH):
    query = """
        SELECT s.id AS sale_id, p.product_name, p.category, p.price,
               s.quantity, s.total_amount, s.sale_date, s.customer_id,
               s.location, s.discount_applied
        FROM sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.sale_date
    """
    with sqlite3.connect(db_path) as connection:
        frame = pd.read_sql_query(query, connection)
    return clean_sales_data(frame)


def load_csv_sales_data(csv_path=CSV_PATH):
    """Load the exported CSV for the project's Pandas demonstration path.

    SQLite remains the live application source. The CSV is a portable analysis
    snapshot that is refreshed whenever the live database changes.
    """
    columns = ["sale_id", "product_name", "category", "price", "quantity", "total_amount", "sale_date"]
    if not os.path.exists(csv_path):
        empty_frame = clean_sales_data(pd.DataFrame(columns=columns))
        save_cleaned_sales_data(empty_frame)
        return empty_frame
    frame = clean_sales_data(pd.read_csv(csv_path))
    save_cleaned_sales_data(frame)
    return frame


def get_product_sales(frame=None):
    frame = frame if frame is not None else load_sales_data()
    return (
        frame.groupby("product_name", as_index=False)["total_amount"]
        .sum()
        .sort_values("total_amount", ascending=False)
        .rename(columns={"total_amount": "sales"})
    )


def get_category_sales(frame=None):
    frame = frame if frame is not None else load_sales_data()
    return (
        frame.groupby("category", as_index=False)["total_amount"]
        .sum()
        .sort_values("total_amount", ascending=False)
        .rename(columns={"total_amount": "sales"})
    )


def get_monthly_sales(frame=None):
    frame = frame if frame is not None else load_sales_data()
    return (
        frame.groupby("year_month", as_index=False)["total_amount"]
        .sum()
        .sort_values("year_month")
        .rename(columns={"total_amount": "sales"})
    )


def get_category_analysis(frame=None):
    frame = frame if frame is not None else load_sales_data()
    if frame.empty:
        return pd.DataFrame(columns=["category", "revenue", "units", "transactions", "average_value"])
    return (
        frame.groupby("category", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            units=("quantity", "sum"),
            transactions=("sale_id", "count") if "sale_id" in frame.columns else ("quantity", "count"),
            average_value=("total_amount", "mean"),
        )
        .sort_values("revenue", ascending=False)
        .round(2)
    )


def get_monthly_analysis(frame=None):
    frame = frame if frame is not None else load_sales_data()
    if frame.empty:
        return pd.DataFrame(columns=["year_month", "revenue", "transactions", "average_value"])
    transaction_column = "sale_id" if "sale_id" in frame.columns else "quantity"
    return (
        frame.groupby("year_month", as_index=False)
        .agg(
            revenue=("total_amount", "sum"),
            transactions=(transaction_column, "count"),
            average_value=("total_amount", "mean"),
        )
        .sort_values("year_month")
        .round(2)
    )


def get_year_over_year_growth(frame=None):
    frame = frame if frame is not None else load_sales_data()
    if frame.empty:
        return []
    yearly = frame.groupby("year")["total_amount"].sum().sort_index()
    revenues = yearly.to_numpy(dtype=float)
    if len(revenues) < 2:
        return []
    previous = revenues[:-1]
    growth = np.divide(
        np.diff(revenues) * 100,
        previous,
        out=np.full(len(previous), np.nan, dtype=float),
        where=previous != 0,
    )
    return [
        {
            "from_year": int(yearly.index[index]),
            "to_year": int(yearly.index[index + 1]),
            "revenue": float(revenues[index + 1]),
            "growth_percent": None if np.isnan(growth[index]) else float(np.round(growth[index], 1)),
        }
        for index in range(len(growth))
    ]


def get_category_month_pivot(frame=None):
    frame = frame if frame is not None else load_sales_data()
    if frame.empty:
        return {"months": [], "rows": []}
    pivot = frame.pivot_table(
        index="category",
        columns="year_month",
        values="total_amount",
        aggfunc="sum",
        fill_value=0,
    ).sort_index(axis=1)
    return {
        "months": [str(month) for month in pivot.columns],
        "rows": [
            {"category": str(category), "values": [float(value) for value in values]}
            for category, values in pivot.iterrows()
        ],
    }


def get_category_location_pivot(frame=None):
    """Return location comparison only for datasets that actually track location."""
    frame = frame if frame is not None else load_sales_data()
    if frame.empty or "location" not in frame.columns:
        return {"locations": [], "rows": []}
    pivot = frame.pivot_table(
        index="category",
        columns="location",
        values="total_amount",
        aggfunc="sum",
        fill_value=0,
    )
    return {
        "locations": [str(location) for location in pivot.columns],
        "rows": [
            {"category": str(category), "values": [float(value) for value in values]}
            for category, values in pivot.iterrows()
        ],
    }


def get_top_products(frame=None):
    frame = frame if frame is not None else load_sales_data()
    return (
        frame.groupby(["product_name", "category"], as_index=False)
        .agg(sales=("total_amount", "sum"), quantity=("quantity", "sum"))
        .sort_values("sales", ascending=False)
    )


def get_low_stock_products():
    with sqlite3.connect(DATABASE_PATH) as connection:
        frame = pd.read_sql_query(
            """
            SELECT product_name, category, stock_quantity, reorder_level
            FROM products
            WHERE stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC, product_name
            """,
            connection,
        )
    return frame.to_dict("records")


def calculate_summary(frame=None):
    frame = frame if frame is not None else load_sales_data()
    revenue = np.asarray(frame["total_amount"], dtype=float) if not frame.empty else np.array([])
    quantities = np.asarray(frame["quantity"], dtype=float) if not frame.empty else np.array([])
    return {
        "total_sales": float(revenue.sum()) if revenue.size else 0,
        "transactions": int(len(frame)),
        "items_sold": int(quantities.sum()) if quantities.size else 0,
        "average_sale": float(np.mean(revenue)) if revenue.size else 0,
        "highest_sale": float(np.max(revenue)) if revenue.size else 0,
        "lowest_sale": float(np.min(revenue)) if revenue.size else 0,
        "average_quantity": float(np.mean(quantities)) if quantities.size else 0,
        "products": int(frame["product_name"].nunique()) if not frame.empty else 0,
        "categories": int(frame["category"].nunique()) if not frame.empty else 0,
        "unique_customers": int(frame["customer_id"].nunique()) if "customer_id" in frame.columns else None,
    }


def _style_chart(ax, title):
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color="#16324f", pad=16)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#d7e0e8")
    ax.tick_params(colors="#60758a", labelsize=9)
    ax.grid(axis="y", color="#e7edf2", linewidth=0.8)
    ax.set_axisbelow(True)


def generate_charts(frame=None):
    frame = frame if frame is not None else load_sales_data()
    os.makedirs(CHART_DIR, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    accent = "#1e7a8a"
    secondary = "#f1a35b"

    product_sales = get_product_sales(frame).head(10)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    if not product_sales.empty:
        ax.barh(product_sales["product_name"][::-1], product_sales["sales"][::-1], color=accent)
        ax.set_xlabel("Revenue (₹)", color="#60758a")
    _style_chart(ax, "Sales by Product")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "sales_by_product.png"), dpi=150, transparent=False, facecolor="white")
    plt.close(fig)

    category_sales = get_category_sales(frame)
    fig, ax = plt.subplots(figsize=(7, 5))
    if not category_sales.empty:
        ax.pie(category_sales["sales"], labels=category_sales["category"], autopct="%1.0f%%", startangle=90, colors=[accent, secondary, "#7f9cc0", "#78b7a9", "#d67d7d"])
    ax.set_title("Sales by Category", loc="left", fontsize=14, fontweight="bold", color="#16324f", pad=16)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "sales_by_category.png"), dpi=150, facecolor="white")
    plt.close(fig)

    monthly_sales = get_monthly_sales(frame)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    if not monthly_sales.empty:
        ax.plot(monthly_sales["year_month"], monthly_sales["sales"], color=accent, marker="o", linewidth=2.5)
        ax.fill_between(range(len(monthly_sales)), monthly_sales["sales"], color=accent, alpha=0.10)
        ax.set_xticks(range(len(monthly_sales)))
        ax.set_xticklabels(monthly_sales["year_month"], rotation=35, ha="right")
        ax.set_ylabel("Revenue (₹)", color="#60758a")
    _style_chart(ax, "Monthly Sales Trend")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "monthly_sales.png"), dpi=150, facecolor="white")
    plt.close(fig)

    quantity_sales = frame.groupby("product_name", as_index=False)["quantity"].sum().sort_values("quantity", ascending=False).head(10) if not frame.empty else pd.DataFrame()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    if not quantity_sales.empty:
        ax.bar(quantity_sales["product_name"], quantity_sales["quantity"], color=secondary)
        ax.set_ylabel("Units sold", color="#60758a")
        ax.tick_params(axis="x", rotation=35)
    _style_chart(ax, "Quantity Sold by Product")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "quantity_by_product.png"), dpi=150, facecolor="white")
    plt.close(fig)

    category_month = get_category_month_pivot(frame)
    fig, ax = plt.subplots(figsize=(max(8, len(category_month["months"]) * 1.1), max(4, len(category_month["rows"]) * 0.65)))
    if category_month["rows"] and category_month["months"]:
        matrix = np.asarray([row["values"] for row in category_month["rows"]], dtype=float)
        image = ax.imshow(matrix, aspect="auto", cmap="YlGnBu")
        ax.set_xticks(range(len(category_month["months"])))
        ax.set_xticklabels(category_month["months"], rotation=35, ha="right")
        ax.set_yticks(range(len(category_month["rows"])))
        ax.set_yticklabels([row["category"] for row in category_month["rows"]])
        fig.colorbar(image, ax=ax, label="Revenue (₹)")
    ax.set_title("Revenue by Category and Month", loc="left", fontsize=14, fontweight="bold", color="#16324f", pad=16)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "category_month_heatmap.png"), dpi=150, facecolor="white")
    plt.close(fig)

    location_pivot = get_category_location_pivot(frame)
    location_chart_path = os.path.join(CHART_DIR, "category_location_comparison.png")
    if location_pivot["locations"]:
        location_frame = frame.pivot_table(
            index="category",
            columns="location",
            values="total_amount",
            aggfunc="sum",
            fill_value=0,
        )
        fig, ax = plt.subplots(figsize=(max(8, len(location_pivot["locations"]) * 1.2), 5))
        location_frame.plot(kind="bar", ax=ax, colormap="YlGnBu")
        _style_chart(ax, "Category Revenue by Location")
        ax.set_ylabel("Revenue (₹)", color="#60758a")
        ax.legend(title="Location", frameon=False)
        fig.tight_layout()
        fig.savefig(location_chart_path, dpi=150, facecolor="white")
        plt.close(fig)
    elif os.path.exists(location_chart_path):
        os.remove(location_chart_path)