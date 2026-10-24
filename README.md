# Retail Store Sales Analysis

RetailIQ is a beginner-friendly retail store owner and manager system built for a BTech 2nd-year CSE college project. It manages products and stock, records sales, and turns live SQLite data into simple sales analysis and charts.

## Project objectives

- Maintain a small store's product and inventory records.
- Record sales without allowing insufficient stock.
- Detect products that need restocking.
- Analyze sales by product, category and month.
- Demonstrate a complete Python data flow: SQLite → Pandas → NumPy → Matplotlib → Flask → HTML/CSS/JavaScript.

## Features

- Home page with project introduction.
- Signup, login and logout using Flask sessions.
- Password hashing with Werkzeug.
- Product CRUD: view, search, add, edit and delete.
- Low-stock logic: `stock_quantity <= reorder_level`.
- Sales recording with automatic total preview.
- Automatic stock reduction after a successful sale.
- Sales history with product/category search, date filters and sorting.
- Dashboard KPIs loaded from the live SQLite database.
- Pandas summaries and grouped tables.
- Pandas data cleaning: remove exact duplicates, parse dates, coerce numeric values, infer derivable missing values and save a cleaned CSV.
- NumPy mean, maximum, minimum and quantity calculations.
- Four live Matplotlib charts:
  1. Sales by Product
  2. Sales by Category
  3. Monthly Sales
  4. Quantity Sold by Product
- Category-by-month revenue heatmap and yearly revenue growth when multiple years are present.
- Responsive, accessible and presentation-ready UI.
- In-app documentation and simple viva questions.

## Technology stack

Only the requested beginner-friendly stack is used:

- Python 3.11
- Flask
- SQLite
- Pandas
- NumPy
- Matplotlib
- HTML
- CSS
- JavaScript

There is no React, Node backend, MongoDB, Firebase, OAuth, AI/ML, payment system or cloud dependency.

## Project structure

```text
Retail-Store-Sales-Analysis/
├── app.py
├── database.py
├── analysis.py
├── requirements.txt
├── README.md
├── database/
│   └── retail_store.db           # created automatically on first run
├── data/
│   └── retail_sales.csv          # analysis/demo export
│   └── cleaned_retail_store_sales.csv  # generated Pandas-cleaned snapshot
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── products.html
│   ├── add_product.html
│   ├── edit_product.html
│   ├── sales.html
│   ├── sales_history.html
│   ├── analysis.html
│   ├── documentation.html
│   └── error.html
└── static/
    ├── css/style.css
    ├── js/script.js
    └── charts/                    # generated from live SQLite data
```

## Installation and run

### 1. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Start the application

```bash
python app.py
```

Open the local address printed by Flask, normally `http://127.0.0.1:5000`.

The database is initialized automatically. The first run creates:

- `users`, `products` and `sales` tables.
- 12 realistic sample products.
- 36 sample sales across several categories and dates.
- `data/retail_sales.csv`.
- `data/cleaned_retail_store_sales.csv` after the Analysis page is opened.
- Chart images inside `static/charts/`.

## Demo flow

1. Open the home page.
2. Create an account from **Create your workspace**.
3. Log in.
4. Review live dashboard KPIs.
5. Open **Products**, search the catalog, add a product, edit it, and review low-stock status.
6. Open **Record sale**, select a product and quantity, and verify the automatic total preview.
7. Save a sale and confirm that stock is reduced.
8. Open **Sales history** and try search, date filtering and sort order.
9. Open **Analysis** to view the cleaned CSV, Pandas tables, NumPy summary values and charts.
10. Open **Documentation** for architecture and viva preparation.
11. Log out.

## Database design

### `users`

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `name` | Store owner or manager name |
| `email` | Unique login email |
| `password` | Werkzeug password hash |

### `products`

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `product_name` | Name shown in catalog |
| `category` | Product category |
| `price` | Selling price |
| `stock_quantity` | Current available stock |
| `reorder_level` | Minimum desired stock level |

### `sales`

| Column | Meaning |
|---|---|
| `id` | Primary key |
| `product_id` | Related product |
| `quantity` | Units sold |
| `sale_date` | Date of sale |
| `total_amount` | Price multiplied by quantity |
| `customer_id` | Optional customer reference entered during sale recording |
| `location` | Optional store/branch location entered during sale recording |
| `discount_applied` | Optional Yes/No sale metadata; it does not change the stored price |

## Important calculations

- `total_amount = product.price × sale.quantity`
- `current_stock = current_stock − sale.quantity`
- A sale is rejected when `quantity <= 0`.
- A sale is rejected when `quantity > current_stock`.
- A product is low stock when `stock_quantity <= reorder_level`.
- Product sales use Pandas `groupby`, `sum` and descending sort.
- Category sales use Pandas grouping and revenue aggregation.
- Monthly sales convert dates to monthly periods before grouping.
- CSV cleanup drops exact duplicate records, parses sale dates, safely converts numeric values and derives missing price, quantity or total only when the other values allow it.
- Year-over-year growth is shown only when the data includes at least two calendar years.
- Customer and location metrics use optional values entered on new sales; older sample sales remain without fabricated metadata.
- Discounts are normalized to Yes/No/Unknown only when the source includes a discount field.
- The category-by-month pivot is rendered as a Matplotlib heatmap; no seaborn dependency is required.
- NumPy calculates average sale, highest sale, lowest sale and average quantity.

## Validation and error handling

The application checks required fields, valid email format, duplicate signup email, password confirmation, positive price, non-negative stock, non-negative reorder level, valid dates, valid products, positive sale quantity and available stock. Friendly flash messages are shown instead of raw error pages.

Deleting a product that already has sales history is intentionally blocked so historical data is not broken.

## Testing checklist

Run the repeatable data regression tests with `python -m unittest discover -s tests -v`. They use temporary SQLite and CSV files, leaving the development data untouched.

Manual end-to-end checks:

- Signup with valid values.
- Reject duplicate email.
- Reject mismatched passwords.
- Reject invalid login.
- Confirm protected pages redirect to login.
- Add, edit, search and delete a product.
- Confirm a product with sales history cannot be deleted.
- Record a valid sale and confirm stock reduction.
- Reject zero, negative and over-stock quantities.
- Filter and sort sales history.
- Confirm dashboard values change after a sale.
- Open all four charts and confirm they render.
- Open documentation and log out.
- Resize to a mobile viewport and confirm navigation opens with the menu button.

## Limitations and future scope

This is a local, single-store college project. It does not include multi-store permissions, cloud hosting, barcode scanning, supplier management, purchase orders, online payments or automated notifications. Year-over-year growth requires records from at least two calendar years. Customer IDs, locations and discount flags are optional sale metadata and are blank for the original sample history. A future version could add role-based access, supplier records, barcode support, scheduled reports and a production database.

## Conclusion

RetailIQ demonstrates a complete and understandable CRUD plus data-analysis workflow. The application keeps the core business logic in Python, the live records in SQLite and the analysis steps in a separate module, making it easy to inspect, explain and extend during a college demonstration.