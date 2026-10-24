import os
import math
from datetime import date, datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from analysis import (
    calculate_summary,
    generate_charts,
    get_category_analysis,
    get_category_location_pivot,
    get_category_month_pivot,
    get_category_sales,
    get_low_stock_products,
    get_monthly_analysis,
    get_monthly_sales,
    get_product_sales,
    get_top_products,
    get_year_over_year_growth,
    load_csv_sales_data,
    load_sales_data,
)
from database import (
    add_product,
    create_sale,
    delete_product,
    get_categories,
    get_connection,
    get_dashboard_data,
    get_product,
    get_products,
    get_sales_history,
    get_user_by_email,
    get_user_by_id,
    initialize_database,
    update_product,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "retail-store-local-development-secret")
app.config["DATABASE_PATH"] = os.path.join(os.path.dirname(__file__), "database", "retail_store.db")


def current_user():
    user_id = session.get("user_id")
    return get_user_by_id(user_id) if user_id else None


@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "current_year": datetime.now().year}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def valid_product_form(form):
    name = form.get("product_name", "").strip()
    category = form.get("category", "").strip()
    try:
        price = float(form.get("price", ""))
        stock = int(form.get("stock_quantity", ""))
        reorder = int(form.get("reorder_level", ""))
    except (TypeError, ValueError):
        return None, "Enter valid numbers for price, stock and reorder level."
    if not name or not category:
        return None, "Product name and category are required."
    if not math.isfinite(price) or price <= 0:
        return None, "Price must be greater than zero."
    if stock < 0 or reorder < 0:
        return None, "Stock and reorder level cannot be negative."
    return {
        "product_name": name,
        "category": category,
        "price": price,
        "stock_quantity": stock,
        "reorder_level": reorder,
    }, None


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not name or not email or not password:
            flash("All fields are required.", "error")
        elif "@" not in email or "." not in email:
            flash("Enter a valid email address.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif get_user_by_email(email):
            flash("An account with that email already exists.", "error")
        else:
            with get_connection() as connection:
                connection.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}.", "success")
            destination = request.args.get("next")
            return redirect(destination if destination and destination.startswith("/") else url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    frame = load_sales_data()
    summary = calculate_summary(frame)
    dashboard_data = get_dashboard_data()
    summary.update(
        {
            "total_sales": dashboard_data["total_sales"],
            "products": dashboard_data["total_products"],
            "items_sold": dashboard_data["items_sold"],
            "current_stock": dashboard_data["current_stock"],
            "low_stock": dashboard_data["low_stock"],
            "categories": dashboard_data["categories"],
        }
    )
    generate_charts(frame)
    return render_template(
        "dashboard.html",
        summary=summary,
        recent_sales=dashboard_data["recent_sales"],
        low_stock=get_low_stock_products(),
        top_products=get_top_products().head(5).to_dict("records"),
        categories=get_categories(),
    )


@app.route("/products")
@login_required
def products():
    search = request.args.get("q", "").strip()
    return render_template("products.html", products=get_products(search), search=search)


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product_page():
    if request.method == "POST":
        product, error = valid_product_form(request.form)
        if error:
            flash(error, "error")
        else:
            add_product(product)
            flash("Product added successfully.", "success")
            return redirect(url_for("products"))
    return render_template("add_product.html")


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product_page(product_id):
    product = get_product(product_id)
    if not product:
        return render_template("error.html", code=404, message="Product not found."), 404
    if request.method == "POST":
        values, error = valid_product_form(request.form)
        if error:
            flash(error, "error")
        else:
            update_product(product_id, values)
            flash("Product updated successfully.", "success")
            return redirect(url_for("products"))
    return render_template("edit_product.html", product=product)


@app.post("/products/<int:product_id>/delete")
@login_required
def delete_product_page(product_id):
    if not get_product(product_id):
        flash("Product not found.", "error")
    else:
        try:
            delete_product(product_id)
            flash("Product deleted.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return redirect(url_for("products"))


@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    products_list = get_products()
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", ""))
        except (TypeError, ValueError):
            product_id, quantity = 0, 0
        sale_date = request.form.get("sale_date", "").strip()
        customer_id = request.form.get("customer_id", "").strip() or None
        location = request.form.get("location", "").strip() or None
        discount_value = request.form.get("discount_applied", "").strip().casefold()
        product = get_product(product_id)
        if not product:
            flash("Select a valid product.", "error")
        elif quantity <= 0:
            flash("Quantity must be greater than zero.", "error")
        elif quantity > product["stock_quantity"]:
            flash(f"Only {product['stock_quantity']} units of {product['product_name']} are in stock.", "error")
        elif not sale_date:
            flash("Sale date is required.", "error")
        elif len(customer_id or "") > 80 or len(location or "") > 100:
            flash("Customer ID must be 80 characters or fewer and location 100 characters or fewer.", "error")
        elif discount_value not in {"", "yes", "no"}:
            flash("Choose Yes or No for discount applied.", "error")
        else:
            try:
                datetime.strptime(sale_date, "%Y-%m-%d")
                discount_applied = {"yes": "Yes", "no": "No"}.get(discount_value)
                create_sale(product_id, quantity, sale_date, customer_id, location, discount_applied)
                flash("Sale recorded and stock updated.", "success")
                return redirect(url_for("sales_history"))
            except ValueError as exc:
                flash(str(exc), "error")
    return render_template("sales.html", products=products_list, today=date.today().isoformat())


@app.route("/sales-history")
@login_required
def sales_history():
    filters = {
        "q": request.args.get("q", "").strip(),
        "from_date": request.args.get("from_date", "").strip(),
        "to_date": request.args.get("to_date", "").strip(),
        "sort": request.args.get("sort", "newest"),
    }
    return render_template("sales_history.html", sales=get_sales_history(filters), filters=filters)


@app.route("/analysis")
@login_required
def analysis_page():
    # The CSV is a fresh analysis snapshot exported from the live SQLite data.
    # Clean it with Pandas before building summaries and charts.
    frame = load_csv_sales_data()
    generate_charts(frame)
    return render_template(
        "analysis.html",
        summary=calculate_summary(frame),
        product_sales=get_product_sales(frame).to_dict("records"),
        category_sales=get_category_analysis(frame).to_dict("records"),
        monthly_sales=get_monthly_analysis(frame).to_dict("records"),
        year_over_year=get_year_over_year_growth(frame),
        category_month_pivot=get_category_month_pivot(frame),
        category_location_pivot=get_category_location_pivot(frame),
        low_stock=get_low_stock_products(),
        csv_rows=len(frame),
    )


@app.route("/documentation")
@login_required
def documentation():
    return render_template("documentation.html")


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="The page you requested could not be found."), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


initialize_database(app.config["DATABASE_PATH"])

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )