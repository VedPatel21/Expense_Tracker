from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from cs50 import SQL
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
import requests, sqlite3
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = '7743d712adb8c3636ba6358a6c4cc4dc'

# API Key and Base URL for Exchange Rate API
load_dotenv()  # Load environment variables from the .env file
API_KEY = os.getenv('API_KEY')  # Fetch the API key
BASE_URL = 'https://v6.exchangerate-api.com/v6/'

# Function to get exchange rates
def get_exchange_rates(base_currency='USD'):
    url = f"{BASE_URL}{API_KEY}/latest/{base_currency}"
    response = requests.get(url)
    if response.status_code == 200:
        rates = response.json().get('conversion_rates', {})
        return rates
    else:
        return {}

# Initialize the database using CS50 library
db = SQL("sqlite:///expense_tracker.db")

# Create the users table if it doesn't exist
db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    );
""")

# Function to connect to the database using sqlite3
def get_db_connection():
    conn = sqlite3.connect('expense_tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

# Authentication Routes

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration. It allows new users to register by providing a username and password.
    It hashes the password and stores the user information in the database.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Both username and password are required.')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                         (username, hashed_password))
            conn.commit()
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login. It checks the provided username and password against the database.
    If the credentials are valid, the user is logged in and redirected to the dashboard.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.')
    
    return render_template('login.html')

# Dashboard Route

@app.route('/dashboard')
def dashboard():
    """
    Displays the user's dashboard. It shows the user's total income, total expenses,
    recent expenses, and notifications.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    expenses = conn.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 3", (user_id,)).fetchall()
    notifications = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)).fetchall()

    # Calculate total income
    total_income = conn.execute("SELECT SUM(amount) AS total_income FROM income WHERE user_id = ?", (user_id,)).fetchone()['total_income'] or 0
    total_income = float(total_income)  # Convert to float

    # Calculate total expenses
    total_expenses = conn.execute("SELECT SUM(amount) AS total_expenses FROM expenses WHERE user_id = ?", (user_id,)).fetchone()['total_expenses'] or 0
    total_expenses = float(total_expenses)  # Convert to float

    # Check if budget is exceeded and add a flash message
    budget_exceeded = session.get('budget_exceeded', False)
    if budget_exceeded:
        flash("Budget exceeded!", "warning")

    # Get user's preferred currency or default to 'USD'
    currency = session.get('currency', 'USD')
    rates = get_exchange_rates('USD')  # Fetch exchange rates based on USD

    # Convert total income and expenses to the selected currency
    conversion_rate = rates.get(currency, 1)
    converted_total_income = total_income * conversion_rate
    converted_total_expenses = total_expenses * conversion_rate

    # Convert each expense amount to the selected currency
    converted_expenses = []
    for expense in expenses:
        converted_amount = expense['amount'] * conversion_rate
        converted_expenses.append({
            'id': expense['id'],
            'title': expense['title'],
            'amount': f"{converted_amount:.2f}",
            'date': expense['date'],
            'category': expense['category']
        })

    if user:
        return render_template(
            'dashboard.html',
            user=user,
            expenses=converted_expenses,
            notifications=notifications,
            total_income=f"{converted_total_income:.2f}",
            total_expenses=f"{converted_total_expenses:.2f}",
            currency=currency
        )
    else:
        flash("User not found.")
        return redirect(url_for('login'))

#Settings Route

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """
    Displays the settings page for the user. Handles updates to the user's preferred currency.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if user:
        # Fetch the current settings from session or database if needed
        currency = session.get('currency', 'USD')
        theme = session.get('theme', 'light')  # Default to light theme

        return render_template('settings.html', user=user, currency=currency, theme=theme)
    else:
        flash("User not found.")
        return redirect(url_for('login'))

# Expense Routes

def get_conversion_rate(from_currency, to_currency):
    """
    Returns the conversion rate from one currency to another.
    """
    rates = get_exchange_rates(from_currency)
    return rates.get(to_currency, 1)

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    if request.method == 'POST':
        user_id = session['user_id']
        title = request.form.get('title')
        amount = float(request.form.get('amount'))
        date = request.form.get('date')
        new_category = request.form.get('new_category')
        selected_category = request.form.get('category')
        category = new_category if new_category else selected_category
        currency = request.form.get('currency')  # Currency of the input amount
        recurring = 'recurring' in request.form
        frequency = request.form.get('frequency') if recurring else None

        # Validation
        if not title or not amount or not date or not category or amount <= 0:
            flash("All fields are required and the amount must be greater than 0.")
            return redirect(url_for('add_expense'))

        # Fetch user's default currency
        default_currency = session.get('currency', 'USD')

        # Convert the amount to the default currency
        conversion_rate = get_conversion_rate(currency, default_currency)
        converted_amount = amount * conversion_rate

        # Insert expense into the appropriate table
        try:
            conn = get_db_connection()
            if recurring:
                conn.execute("""
                    INSERT INTO recurring_expenses (user_id, title, amount, category, start_date, frequency)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, title, converted_amount, category, date, frequency))
            else:
                conn.execute("""
                    INSERT INTO expenses (user_id, title, amount, date, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, title, converted_amount, date, category))
            conn.commit()

            # Check if budget is exceeded
            current_month = date[:7]  # Extracting YYYY-MM format
            total_expenses = conn.execute("""
                SELECT SUM(amount) as total 
                FROM expenses 
                WHERE user_id = ? 
                AND category = ? 
                AND strftime('%Y-%m', date) = ?
            """, (user_id, category, current_month)).fetchone()['total'] or 0.0

            budget = conn.execute("SELECT monthly_budget FROM budget WHERE user_id = ? AND category = ?", 
                                  (user_id, category)).fetchone()

            if budget and total_expenses > float(budget['monthly_budget']):
                flash(f"Budget for {category} exceeded! Monthly budget: {budget['monthly_budget']}, Current expenses: {total_expenses}")
                # Generate Notification
                message = f"Your budget for {category} has been exceeded. Monthly budget: {budget['monthly_budget']}, Current expenses: {total_expenses}"
                conn.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (user_id, message))
                conn.commit()

            conn.close()
            flash('Expense added successfully!')
        except Exception as e:
            flash(f'Error adding expense: {e}')
            return redirect(url_for('add_expense'))

        return redirect(url_for('view_expenses'))

    # Fetch existing categories from the database
    conn = get_db_connection()
    categories = conn.execute("SELECT DISTINCT category FROM expenses WHERE user_id = ?", (session['user_id'],)).fetchall()
    conn.close()

    return render_template('add_expense.html', categories=[row['category'] for row in categories], selected_currency=session.get('currency', 'USD'))

@app.route('/view_expenses', methods=['GET', 'POST'])
def view_expenses():
    """
    Displays the user's expenses. Allows filtering by category, start date, end date, and sorting by different fields.
    Converts the expense amounts to the user's preferred currency.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    query = "SELECT * FROM expenses WHERE user_id = ?"
    params = [user_id]

    if request.method == 'POST':
        category = request.form.get('category', 'All')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        sort_by = request.form.get('sort_by', 'date')

        if category != 'All':
            query += " AND category = ?"
            params.append(category)
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += f" ORDER BY {sort_by} DESC"

    expenses = conn.execute(query, params).fetchall()

    # Fetch recurring expenses
    recurring_expenses_query = "SELECT * FROM recurring_expenses WHERE user_id = ?"
    recurring_expenses = conn.execute(recurring_expenses_query, [user_id]).fetchall()

    # Get user's preferred currency or default to 'USD'
    currency = session.get('currency', 'USD')
    rates = get_exchange_rates('USD')  # Fetch exchange rates based on USD
    
    # Convert each regular expense amount
    conversion_rate = rates.get(currency, 1)
    combined_expenses = []

    for expense in expenses:
        converted_amount = expense['amount'] * conversion_rate
        combined_expenses.append({
            'id': expense['id'],
            'title': expense['title'],
            'converted_amount': f"{converted_amount:.2f}",
            'date': expense['date'],
            'category': expense['category'],
            'is_recurring': "Not Recurring"
        })

    # Convert each recurring expense amount
    for expense in recurring_expenses:
        converted_amount = expense['amount'] * conversion_rate
        combined_expenses.append({
            'id': expense['id'],
            'title': expense['title'],
            'converted_amount': f"{converted_amount:.2f}",
            'date': expense['start_date'],
            'category': expense['category'],
            'is_recurring': "Recurring"
        })

    # Sort combined expenses by date
    combined_expenses.sort(key=lambda x: x['date'], reverse=True)

    return render_template('view_expenses.html', expenses=combined_expenses, selected_currency=currency)

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    """
    Deletes a specific expense. It ensures that the expense belongs to the logged-in user before deleting it.
    If the expense is successfully deleted, a success message is shown.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']

    try:
        with get_db_connection() as conn:
            # Check if the expense is a regular expense
            expense = conn.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id)).fetchone()

            if expense:
                # Delete the regular expense
                conn.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
            else:
                # Check if the expense is a recurring expense
                recurring_expense = conn.execute("SELECT * FROM recurring_expenses WHERE id = ? AND user_id = ?", (expense_id, user_id)).fetchone()
                
                if recurring_expense:
                    # Delete the recurring expense
                    conn.execute("DELETE FROM recurring_expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
                else:
                    flash("Expense not found or you do not have permission to delete it.", "danger")
                    return redirect(url_for('view_expenses'))
            
            conn.commit()
        
        flash("Expense deleted successfully.", "success")
    except Exception as e:
        print(f"Error deleting expense: {e}")
        flash(f"Error deleting expense: {e}", "danger")

    return redirect(url_for('view_expenses'))

# Budget Routes

@app.route('/set_budget', methods=['GET', 'POST'])
def set_budget():
    """
    Allows the user to set a monthly budget for different categories. If a budget already exists for a category, it updates it.
    Otherwise, it creates a new budget entry.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user_id = session['user_id']
    conn = get_db_connection()
    categories = conn.execute("SELECT category_name FROM categories WHERE user_id = ?", (user_id,)).fetchall()

    if request.method == 'POST':
        new_category = request.form.get('new_category', '').strip()
        selected_category = request.form.get('category')
        monthly_budget = request.form['monthly_budget']

        if not new_category and not selected_category:
            flash("Please either type a new category or select an existing one.", "danger")
            return redirect(url_for('set_budget'))

        category = new_category if new_category else selected_category

        if new_category:
            existing_category = conn.execute("SELECT * FROM categories WHERE user_id = ? AND category_name = ?", 
                                             (user_id, new_category)).fetchone()
            if not existing_category:
                conn.execute("INSERT INTO categories (user_id, category_name) VALUES (?, ?)", 
                             (user_id, new_category))
        
        existing_budget = conn.execute("SELECT * FROM budget WHERE user_id = ? AND category = ?", 
                                       (user_id, category)).fetchone()
        if existing_budget:
            conn.execute("UPDATE budget SET monthly_budget = ? WHERE user_id = ? AND category = ?", 
                         (monthly_budget, user_id, category))
        else:
            conn.execute("INSERT INTO budget (user_id, category, monthly_budget) VALUES (?, ?, ?)", 
                         (user_id, category, monthly_budget))
        conn.commit()

        flash("Budget set successfully!")
        return redirect(url_for('view_budgets'))

    conn.close()
    return render_template('set_budget.html', categories=categories)

@app.route('/view_budgets')
def view_budgets():
    """
    Displays the user's budgets. It retrieves and shows all budgets set by the user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    budgets = db.execute("SELECT * FROM budget WHERE user_id = ?", user_id)
    
    return render_template('view_budget.html', budgets=budgets)

@app.route('/delete_budget/<int:budget_id>', methods=['POST'])
def delete_budget(budget_id):
    """
    Deletes a specific budget. It ensures that the budget belongs to the logged-in user before deleting it.
    If the budget is successfully deleted, a success message is shown.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    db.execute("DELETE FROM budget WHERE id = ? AND user_id = ?", budget_id, user_id)
    flash("Budget deleted successfully!")

    return redirect(url_for('view_budgets'))

# Recurring Expenses Routes

@app.route('/add_recurring_expense', methods=['GET', 'POST'])
def add_recurring_expense():
    """
    Allows the user to add a recurring expense. The user provides details such as title, amount, category,
    start date, and frequency. The expense is then added to the database.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    if request.method == 'POST':
        user_id = session['user_id']
        title = request.form['title']
        amount = float(request.form['amount'])  # Convert to float for precise arithmetic
        category = request.form['category']
        start_date = request.form['start_date']
        frequency = request.form['frequency']

        # Validation
        if not title or amount <= 0 or not category or not start_date or not frequency:
            flash("All fields are required and the amount must be greater than 0.")
            return redirect(url_for('add_recurring_expense'))

        # Insert recurring expense into the database
        db.execute("""
            INSERT INTO recurring_expenses (user_id, title, amount, category, start_date, frequency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, user_id, title, amount, category, start_date, frequency)

        flash('Recurring expense added successfully!')
        return redirect(url_for('dashboard'))

    return render_template('add_recurring_expense.html')

@app.route('/view_recurring_expenses')
def view_recurring_expenses():
    """
    Displays the user's recurring expenses. It retrieves and shows all recurring expenses for the user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    recurring_expenses = db.execute("SELECT * FROM recurring_expenses WHERE user_id = ?", user_id)
    
    return render_template('view_recurring_expenses.html', recurring_expenses=recurring_expenses)

@app.route('/delete_recurring_expense/<int:expense_id>', methods=['POST'])
def delete_recurring_expense(expense_id):
    """
    Deletes a specific recurring expense. It ensures that the expense belongs to the logged-in user before deleting it.
    If the recurring expense is successfully deleted, a success message is shown.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    db.execute("DELETE FROM recurring_expenses WHERE id = ?", expense_id)
    flash('Recurring expense deleted successfully!')
    return redirect(url_for('view_recurring_expenses'))

# Income Routes

@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    """
    Allows the user to add an income entry. The user provides details such as amount, source, date,
    and category. The income is then added to the database.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user_id = session['user_id']
    with get_db_connection() as conn:
        categories = conn.execute("SELECT category_name FROM categories WHERE user_id = ?", (user_id,)).fetchall()

    if request.method == 'POST':
        amount = float(request.form['amount'])
        source = request.form['source']
        date = request.form['date']
        input_currency = request.form['currency']
        new_category = request.form.get('new_category').strip()
        selected_category = request.form.get('category')

        if not new_category and not selected_category:
            flash("Please either type a new category or select an existing one.", "danger")
            return redirect(url_for('add_income'))

        category = new_category if new_category else selected_category

        # Get the selected dashboard currency and fetch exchange rates
        selected_currency = session.get('currency', 'USD')
        rates = get_exchange_rates(input_currency)

        # Convert the amount to the selected dashboard currency before storing
        if input_currency != selected_currency:
            amount_in_selected_currency = amount / rates[input_currency] * rates[selected_currency]
        else:
            amount_in_selected_currency = amount

        with get_db_connection() as conn:
            if new_category:
                existing_category = conn.execute("SELECT * FROM categories WHERE user_id = ? AND category_name = ?", 
                                                 (user_id, new_category)).fetchone()
                if not existing_category:
                    conn.execute("INSERT INTO categories (user_id, category_name) VALUES (?, ?)", 
                                 (user_id, new_category))
                    conn.commit()
            
            conn.execute("INSERT INTO income (user_id, amount, source, date, category) VALUES (?, ?, ?, ?, ?)",
                         (user_id, amount_in_selected_currency, source, date, category))
            conn.commit()

        flash('Income added successfully!')
        return redirect(url_for('view_income'))

    return render_template('add_income.html', selected_currency=session.get('currency', 'USD'), categories=categories)

@app.route('/view_income', methods=['GET', 'POST'])
def view_income():
    """
    Displays the user's income entries. It retrieves and shows all income entries for the user,
    converting the amounts to the user's preferred currency.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    selected_currency = session.get('currency', 'USD')

    income_entries = db.execute("SELECT * FROM income WHERE user_id = ? ORDER BY date DESC", user_id)
    
    # Fetch exchange rates
    rates = get_exchange_rates('USD')
    conversion_rate = rates.get(selected_currency, 1)

    # Convert income to selected currency
    converted_income_entries = []
    for entry in income_entries:
        converted_entry = dict(entry)
        converted_entry['converted_amount'] = entry['amount'] * conversion_rate
        converted_income_entries.append(converted_entry)
    
    return render_template('view_income.html', income_entries=converted_income_entries, selected_currency=selected_currency)

@app.route('/delete_income/<int:income_id>', methods=['POST'])
def delete_income(income_id):
    """
    Deletes a specific income entry. It ensures that the income entry belongs to the logged-in user before deleting it.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    db.execute("DELETE FROM income WHERE id = ?", income_id)
    return redirect(url_for('view_income'))

# Category Routes

@app.route('/add_category', methods=['POST'])
def add_category():
    """
    Adds a new category to the user's list of categories.
    If the category already exists, it is not added again.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user_id = session['user_id']
    category_name = request.form['category']

    # Insert new category into the database
    with get_db_connection() as conn:
        existing_category = conn.execute("SELECT * FROM categories WHERE user_id = ? AND category_name = ?", 
                                         (user_id, category_name)).fetchone()
        if not existing_category:
            conn.execute("INSERT INTO categories (user_id, category_name) VALUES (?, ?)", 
                         (user_id, category_name))
            conn.commit()

    return redirect(request.referrer)

# Notifications Routes

@app.route('/notifications')
def notifications():
    """
    Displays the user's notifications. It retrieves and shows all notifications for the user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    notifications = db.execute("SELECT * FROM notifications WHERE user_id = ?", user_id)

    return render_template('notifications.html', notifications=notifications)

@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    """
    Deletes a specific notification. It ensures that the notification belongs to the logged-in user before deleting it.
    If the notification is successfully deleted, a success message is shown.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    db.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", notification_id, user_id)
    flash("Notification deleted successfully!")

    return redirect(url_for('notifications'))

# Reporting Routes

@app.route('/generate_report', methods=['GET', 'POST'])
def generate_report():
    """
    Generates a report of the user's expenses. It can generate reports in PDF or Excel format,
    converting expense amounts to the selected currency.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()

    # Fetch both regular and recurring expenses
    expenses = conn.execute("""
        SELECT title, amount, date, category 
        FROM expenses 
        WHERE user_id = ? 
        UNION ALL
        SELECT title, amount, start_date, category 
        FROM recurring_expenses 
        WHERE user_id = ?
        ORDER BY date DESC
    """, (user_id, user_id)).fetchall()

    if request.method == 'POST':
        report_type = request.form.get('report_type')
        report_currency = request.form.get('report_currency', 'USD')

        # Get exchange rates
        exchange_rates = get_exchange_rates(base_currency='USD')  # Assuming 'USD' as base for simplicity
        rate = exchange_rates.get(report_currency, 1)

        # Convert amounts
        converted_expenses = []
        for expense in expenses:
            expense_dict = dict(expense)
            expense_dict['converted_amount'] = round(expense_dict['amount'] * rate, 2)
            converted_expenses.append(expense_dict)

        if report_type == 'pdf':
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('Title', parent=styles['Title'], spaceAfter=14)
            title = Paragraph("Expense Report", title_style)
            elements.append(title)
            
            subtitle_style = ParagraphStyle('Normal', parent=styles['Normal'], spaceAfter=14)
            subtitle = Paragraph(f"Username: {user['username']}", subtitle_style)
            elements.append(subtitle)
            subtitle_currency = Paragraph(f"Report Currency: {report_currency}", subtitle_style)
            elements.append(subtitle_currency)

            if converted_expenses:
                data = [['ID', 'Title', 'Amount (USD)', f'Amount ({report_currency})', 'Date', 'Category']]
                for idx, expense in enumerate(converted_expenses, start=1):
                    data.append([idx, expense['title'], f"${expense['amount']}", f"{expense['converted_amount']} {report_currency}", expense['date'], expense['category']])

                table = Table(data, hAlign='LEFT')
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ]))

                elements.append(table)
            else:
                no_expenses_message = Paragraph("No expenses found.", styles['Normal'])
                elements.append(no_expenses_message)

            doc.build(elements)
            buffer.seek(0)

            return send_file(buffer, as_attachment=True, download_name='expense_report.pdf', mimetype='application/pdf')

        elif report_type == 'excel':
            df = pd.DataFrame(converted_expenses)
            df.insert(0, 'ID', range(1, 1 + len(df)))  # Insert a new ID column starting from 1
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            return send_file(buffer, as_attachment=True, download_name='expense_report.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    conn.close()
    return render_template('generate_report.html')

# Add route to generate graphical reports
@app.route('/generate_graphical_report')
def generate_graphical_report():
    """
    Displays the graphical reports page where users can view their expenses and other data in visual formats.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    return render_template('graphical_reports.html')

# Import Expenses
@app.route('/import_expenses', methods=['GET', 'POST'])
def import_expenses():
    """
    Allows the user to import expenses from a CSV file. The user uploads a CSV file containing expense data,
    which is then inserted into the database.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    if request.method == 'POST':
        user_id = session['user_id']
        file = request.files['file']

        if file and file.filename.endswith('.csv'):
            df = pd.read_csv(file)
            conn = get_db_connection()
            for index, row in df.iterrows():
                recurring_status = row.get('recurring', 'not recurring').lower()
                is_recurring = recurring_status == 'recurring'

                if is_recurring:
                    frequency = row.get('frequency', 'monthly')  # Provide a default value for frequency
                    conn.execute("""
                        INSERT INTO recurring_expenses (user_id, title, amount, start_date, category, frequency)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, row['title'], row['amount'], row['date'], row['category'], frequency))
                else:
                    conn.execute("""
                        INSERT INTO expenses (user_id, title, amount, date, category)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, row['title'], row['amount'], row['date'], row['category']))
            conn.commit()
            conn.close()
            flash('Expenses imported successfully!')
            return redirect(url_for('view_expenses'))
        else:
            flash('Please upload a valid CSV file.')

    return render_template('import_expenses.html')

# Export Expenses
@app.route('/export_expenses')
def export_expenses():
    """
    Allows the user to export their expenses to a CSV file. The expenses are retrieved from the database
    and written to a CSV file, which is then sent to the user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    expenses = conn.execute("""
        SELECT id, amount, title, date, category, 'Not recurring' as recurring FROM expenses WHERE user_id = ?
        UNION ALL
        SELECT id, amount, title, start_date AS date, category, 'Recurring' as recurring FROM recurring_expenses WHERE user_id = ?
    """, (user_id, user_id)).fetchall()
    conn.close()

    # Convert expenses to a list of dictionaries for DataFrame
    expense_list = []
    for expense in expenses:
        expense_dict = dict(expense)
        expense_list.append(expense_dict)

    df = pd.DataFrame(expense_list)
    buffer = BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='expenses.csv', mimetype='text/csv')

# Sharing Expense Routes

@app.route('/share_expense/<int:expense_id>', methods=['GET', 'POST'])
def share_expense(expense_id):
    """
    Allows the user to share an expense with another user. The user provides the username of the person
    they want to share the expense with. A notification is sent to the shared user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()  # Ensure the connection is established correctly
    if request.method == 'POST':
        shared_with_username = request.form.get('shared_with')
        shared_with_user = conn.execute("SELECT id FROM users WHERE username = ?", (shared_with_username,)).fetchone()

        if not shared_with_user:
            flash('User not found.')
            return redirect(url_for('view_expenses'))

        shared_with_id = shared_with_user['id']
        owner_id = session['user_id']

        # Insert into shared_expenses table
        conn.execute("INSERT INTO shared_expenses (owner_id, shared_with_id, expense_id) VALUES (?, ?, ?)", 
                      (owner_id, shared_with_id, expense_id))
        conn.commit()

        # Create a notification for the shared user
        owner_username = conn.execute("SELECT username FROM users WHERE id = ?", (owner_id,)).fetchone()['username']
        message = f"Expense shared by {owner_username}. Check your shared expenses."
        conn.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (shared_with_id, message))
        conn.commit()

        flash('Expense shared successfully!')
        return redirect(url_for('view_expenses'))

    return render_template('share_expense.html', expense_id=expense_id)

@app.route('/view_shared_expenses')
def view_shared_expenses():
    """
    Displays the shared expenses for the logged-in user.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    shared_expenses = conn.execute("""
        SELECT e.*, u.username AS owner_username 
        FROM expenses e
        JOIN shared_expenses se ON e.id = se.expense_id
        JOIN users u ON se.owner_id = u.id
        WHERE se.shared_with_id = ?
        ORDER BY e.date DESC
    """, (user_id,)).fetchall()

    return render_template('view_shared_expenses.html', shared_expenses=shared_expenses)

# Utility Routes

@app.route('/expense_data')
def expense_data():
    """
    Provides expense data in JSON format for generating graphical reports. This data can be used by
    JavaScript or other frontend frameworks to create visual representations of the user's expenses.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    conn = get_db_connection()
    expenses = conn.execute("""
        SELECT date, amount, category FROM expenses WHERE user_id = ?
        UNION ALL
        SELECT start_date AS date, amount, category FROM recurring_expenses WHERE user_id = ?
    """, (user_id, user_id)).fetchall()
    conn.close()
    
    expense_list = []
    for expense in expenses:
        expense_list.append({
            'date': expense['date'],
            'amount': expense['amount'],
            'category': expense['category']
        })

    return jsonify(expense_list)

@app.route('/set_currency', methods=['POST'])
def set_currency():
    """
    Sets the user's preferred currency for displaying income and expenses.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    currency = request.form['currency']
    session['currency'] = currency
    flash(f'Currency set to {currency}')
    return redirect(url_for('dashboard'))

@app.template_filter('format_currency')
def format_currency(amount, currency):
    """
    A template filter to format amounts with the appropriate currency symbol.
    """
    symbol_mapping = {
        'USD': '$',
        'EUR': '€',
        'JPY': '¥',
        'INR': '₹'
    }
    symbol = symbol_mapping.get(currency, '$')
    return f"{symbol}{amount:,.2f}"

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """
    Displays and allows the user to update their profile information, including username and password.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Both username and password are required.')
            return redirect(url_for('profile'))

        hashed_password = generate_password_hash(password)
        
        try:
            conn.execute("UPDATE users SET username = ?, password = ? WHERE id = ?",
                         (username, hashed_password, user_id))
            conn.commit()
            flash('Profile updated successfully!')
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.')
        finally:
            conn.close()
            return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    """
    Logs the user out by clearing the session and redirects to the index page.
    """
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('index'))

@app.route('/')
def index():
    """
    Displays the index page with login and register options. Redirects to the dashboard if the user is already logged in.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))  # Redirect to dashboard if already logged in
    return render_template('index.html')  # Show login and register options if not logged in

# Run the app
if __name__ == '__main__':
    app.run(debug=True)  # Run the Flask app in debug mode

