import io
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection
import pandas as pd
import plotly.express as px
import plotly.utils
import json
from datetime import datetime
from prophet import Prophet
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import base64
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secret_key"

def get_business_report_data():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # total sales
    cursor.execute("SELECT SUM(amount) as total_sales FROM manual_sales")
    total_sales = float(cursor.fetchone()['total_sales'] or 0)

    # total profit (FIXED)
    cursor.execute("SELECT SUM(profit) as total_profit FROM manual_sales")
    total_profit = float(cursor.fetchone()['total_profit'] or 0)

    # best product
    cursor.execute("""
        SELECT product, SUM(quantity) as total_qty
        FROM manual_sales
        GROUP BY product
        ORDER BY total_qty DESC
        LIMIT 1
    """)
    best_product = cursor.fetchone()

    # growth rate
    growth_rate = round((total_profit / total_sales) * 100, 2) if total_sales else 0

    # expected profit
    expected_profit = round(total_profit * 1.1, 2)
    # ================= INSIGHTS =================

    if total_profit > 0:
        performance = "Business is profitable 📈"
    else:
        performance = "Business is running at a loss ⚠️"

    if growth_rate > 10:
        growth_msg = "Strong growth observed 🚀"
    elif growth_rate > 0:
        growth_msg = "Moderate growth 👍"
    else:
        growth_msg = "Negative growth, needs attention ⚠️"

    if best_product:
        product_msg = f"Top performing product is {best_product['product']} 🏆"
    else:
        product_msg = "No product insights available"

    # recommendation
    if total_profit < 0:
        recommendation = "Reduce costs or improve pricing strategy"
    elif growth_rate < 5:
        recommendation = "Focus on marketing and scaling best products"
    else:
        recommendation = "Business is performing well, consider expansion"

    cursor.close()
    conn.close()

    return {
        "total_sales": total_sales,
        "total_profit": total_profit,
        "growth_rate": growth_rate,
        "best_product": best_product['product'] if best_product else "N/A",
        "expected_profit": expected_profit,
         "performance": performance,
    "growth_msg": growth_msg,
    "product_msg": product_msg,
    "recommendation": recommendation
    }

# ================= HOME, REGISTER, LOGIN =================
@app.route('/')
def home():
    return render_template('home.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password_raw = request.form.get('password')
        confirm_password = request.form.get('confirm_password') 
        if not name or not email or not password_raw:
            return render_template('register.html', message="Please fill in all fields")
        if password_raw != confirm_password:
            return render_template('register.html', message="Passwords do not match")
        password_hashed = generate_password_hash(password_raw)
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password_hashed))
                conn.commit()
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
            except Exception:
                return render_template('register.html', message="Registration failed: Email already exists")
    return render_template('register.html')

from datetime import datetime

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            # ✅ Store session
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']   # ⭐ IMPORTANT (needed for logout)

            # ✅ Update activity
            
            # 🔥 FIXED UPDATE
            cursor.execute("""
                UPDATE users 
                SET last_login=NOW(), is_active=1 
                WHERE email=%s
            """, (email,))

            conn.commit()

            cursor.close()
            conn.close()

            return redirect('/home_dashboard')

        cursor.close()
        conn.close()

        return render_template('login.html', message="Invalid credentials")

    return render_template('login.html')
#===================================================
@app.route('/home_dashboard')
def home_dashboard():
        if 'user_id' not in session:
             return redirect('/login')

        return render_template('home_dashboard.html', name=session['user_name'])

#======================welcome==================================== 
@app.route('/welcome')
def welcome():
    return """
<div style="font-family: 'Segoe UI', sans-serif; 
            background-color: #f8fafc; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: center; 
            height: 100vh; 
            margin: 0;">

    <div style="background: white; 
                padding: 60px; 
                border-radius: 24px; 
                box-shadow: 0 20px 50px rgba(15, 23, 42, 0.1); 
                border-left: 10px solid #0f172a; 
                max-width: 650px; 
                text-align: center;">

        <h1 style="color: #0f172a; 
                   font-size: 3.2em; 
                   margin-bottom: 15px; 
                   font-weight: 800;">
            Business 
            <span style="color: #38bdf8;">Analyzer</span>
        </h1>

        <p style="font-size: 1.2em; 
                  color: #475569; 
                  line-height: 1.7; 
                  margin-bottom: 35px;">
            Your professional toolkit for tracking sales, 
            inventory movement, and profit margins across all platforms.
        </p>

    </div>
</div>
"""


# ================= DASHBOARD =================
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    # ================= INIT =================
    bar_json = pie_json = line_json = None
    forecast_json = expense_sunburst_json = None
    daily_total = 0
    all_revenues = []
# ================= 1. HANDLE CSV UPLOAD FIRST =================
    if request.method == 'POST':

        form_type = request.form.get("form_type")

        if form_type == "sales":

            file = request.files.get("sales_file")

            if file and file.filename != "":
                try:
                    df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
                    df.columns = [c.strip().lower() for c in df.columns]

                    col_sales = next((c for c in df.columns if any(x in c for x in ['sale','revenue','selling','amount'])), None)
                    col_prod = next((c for c in df.columns if any(x in c for x in ['product','item','name'])), None)
                    col_date = next((c for c in df.columns if 'date' in c), None)

                    if col_sales and col_prod:

                        conn = get_connection()
                        cursor = conn.cursor()

                        cursor.execute("DELETE FROM manual_sales")

                        curr_date = datetime.now().strftime('%Y-%m-%d')

                        for _, row in df.iterrows():

                            val = float(row[col_sales])
                            product = str(row[col_prod])

                            sale_date = (
                                pd.to_datetime(row[col_date]).strftime('%Y-%m-%d')
                                if col_date else curr_date
                            )

                            cost = 0
                            profit = 0

                            cursor.execute("""
                                INSERT INTO manual_sales
                                (product, quantity, amount, cost_price, profit, sale_date)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (product, 1, val, cost, profit, sale_date))

                        conn.commit()
                        cursor.close()
                        conn.close()

                        flash("CSV uploaded & saved successfully!")
                        return redirect(url_for('dashboard'))

                    else:
                        flash("Invalid CSV format!")

                except Exception as e:
                    flash(f"Upload Error: {e}")

    # ================= 2. FETCH DATA FROM DB =================

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            SUM(amount * quantity) as sales
            
        FROM manual_sales
    """)


    row = cursor.fetchone()

    sales = float(row['sales'] or 0)

    # ✅ GET EXPENSE FROM EXPENSE TABLE
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_expense
        FROM expenses
    """)

    expense_row = cursor.fetchone()
    total_expense = float(expense_row['total_expense'] or 0)

    # ✅ FINAL SUMMARY
    summary = {
        "sales": sales,
        "expenses": total_expense,
        "profit": sales - total_expense
}




    
    cursor.execute("""
    SELECT product, quantity, amount, profit, sale_date
    FROM manual_sales
""")
   

    db_rows = cursor.fetchall()

    today = datetime.now().date()
    product_sales = {}

    for t in db_rows:
        amt = float(t['amount'] or 0)
        qty = int(t['quantity'] or 1)
        profit = float(t['profit'] or 0)

        all_revenues.append(amt * qty)

        product_sales[t['product']] = product_sales.get(t['product'], 0) + qty

        if pd.to_datetime(t['sale_date']).date() == today:
            daily_total += profit

    best_product = max(product_sales, key=product_sales.get) if product_sales else None

    profit_margin = round((summary["profit"] / summary["sales"]) * 100, 2) if summary["sales"] > 0 else 0

    # ================= 3. CHARTS =================
    if db_rows:
        df = pd.DataFrame(db_rows)

        # 🔥 IMPORTANT FIX
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

        # ---------- PRODUCT ----------
        df_prod = df.groupby('product')['amount'].sum().reset_index()

        fig_bar = px.bar(df_prod, x='product', y='amount', title="Sales per Product")
        bar_json = json.dumps(fig_bar, cls=plotly.utils.PlotlyJSONEncoder)

        fig_pie = px.pie(df_prod, names='product', values='amount')
        pie_json = json.dumps(fig_pie, cls=plotly.utils.PlotlyJSONEncoder)

       # ---------- DATE ----------
       # ---------- DATE ----------
        df['sale_date'] = pd.to_datetime(df['sale_date'])

        df_trend = df.groupby('sale_date')['amount'].sum().reset_index()
        df_trend.rename(columns={'sale_date': 'date', 'amount': 'sales'}, inplace=True)

        # ---------- EXPENSE DATA ----------
        cursor.execute("""
            SELECT expense_date as date, SUM(amount) as expense
            FROM expenses
            GROUP BY expense_date
        """)

        expense_rows = cursor.fetchall()

        df_exp = pd.DataFrame(expense_rows)

        # ---------- FIX TYPES ----------
        df_trend['date'] = pd.to_datetime(df_trend['date']).dt.date

        if not df_exp.empty:
            df_exp['date'] = pd.to_datetime(df_exp['date']).dt.date
            df_exp['expense'] = pd.to_numeric(df_exp['expense'], errors='coerce')

            df_trend = pd.merge(df_trend, df_exp, on='date', how='left')
        else:
            df_trend['expense'] = 0

        df_trend['expense'] = df_trend['expense'].fillna(0)

        # ---------- FINAL CALCULATION ----------
        df_trend['profit'] = df_trend['sales'] - df_trend['expense']

        # ================= GRAPH =================
        import plotly.graph_objects as go

        fig_line = go.Figure()

        # 🔵 SALES (LEFT AXIS)
        fig_line.add_trace(go.Scatter(
            x=df_trend['date'],
            y=df_trend['sales'],
            name='Sales',
            mode='lines+markers',
            line=dict(color='blue', width=3)
        ))

        # 🔴 EXPENSE (RIGHT AXIS)
        fig_line.add_trace(go.Scatter(
            x=df_trend['date'],
            y=df_trend['expense'],
            name='Expense',
            mode='lines+markers',
            line=dict(color='red', width=3, dash='dash'),
            yaxis='y2'
        ))

        # 🟢 PROFIT (RIGHT AXIS)
        fig_line.add_trace(go.Scatter(
            x=df_trend['date'],
            y=df_trend['profit'],
            name='Profit',
            mode='lines+markers',
            line=dict(color='green', width=3, dash='dot'),
            yaxis='y2'
        ))

        # 🎯 LAYOUT (VERY IMPORTANT)
        fig_line.update_layout(
            title="Sales vs Expenses vs Profit",
            xaxis=dict(title="Date"),

            # LEFT AXIS
            yaxis=dict(
                title="Sales",
                showgrid=True
            ),

            # RIGHT AXIS
            yaxis2=dict(
                title="Expense & Profit",
                overlaying='y',
                side='right',
                showgrid=False
            ),

            hovermode='x unified',
            legend_title="Metrics"
        )

        line_json = json.dumps(fig_line, cls=plotly.utils.PlotlyJSONEncoder)
       
        

    # ================= 4. EXPENSE CHART =================

    cursor.execute("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        GROUP BY category
    """)

    exp_rows = cursor.fetchall()

    if exp_rows:
        df_exp = pd.DataFrame(exp_rows)
        fig_exp = px.sunburst(df_exp, path=['category'], values='total')
        expense_sunburst_json = json.dumps(fig_exp, cls=plotly.utils.PlotlyJSONEncoder)

    cursor.close()
    conn.close()

    # ================= 5. FINAL STATS =================

    stats = {
        'avg_sale': round(sum(all_revenues) / len(all_revenues), 2) if all_revenues else 0,
        'max_sale': round(max(all_revenues), 2) if all_revenues else 0,
        'count': len(all_revenues)
    }

    # ================= FINAL RENDER =================

    return render_template(
        'dashboard.html',
        name=session.get('user_name'),
        summary=summary,
        stats=stats,
        daily_total=round(daily_total, 2),
        bar_json=bar_json,
        pie_json=pie_json,
        line_json=line_json,
        forecast_json=forecast_json,
        expense_json=expense_sunburst_json,
        profit_margin=profit_margin,
        best_product=best_product
    )
# ================= MANUAL ENTRY & RESET =================
@app.route('/add_sale', methods=['POST'])
def add_sale():
    product = request.form.get('product')
    qty = int(request.form.get('quantity') or 1)
    s_price = float(request.form.get('selling_price') or 0)
    c_price = float(request.form.get('cost_price') or 0)
    total_profit = (s_price - c_price) * qty
    
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO manual_sales (product, quantity, amount, cost_price, profit, sale_date) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (product, qty, s_price, c_price, total_profit, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/reset_inventory', methods=['POST'])
def reset_inventory():
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM manual_sales")
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/download_analysis')
def download_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product, quantity, amount, cost_price, profit, sale_date FROM manual_sales")
        combined_data = cursor.fetchall()
        cursor.close()
        conn.close()
        df_combined = pd.DataFrame(combined_data) if combined_data else pd.DataFrame(columns=['product', 'quantity', 'amount', 'cost_price', 'profit', 'sale_date'])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_combined.to_excel(writer, index=False, sheet_name='Sales_Report')
        output.seek(0)
        return send_file(output, download_name="Business_Analysis_Report.xlsx", as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return redirect(url_for('dashboard'))
@app.route('/reset_warehouse', methods=['POST'])
def reset_warehouse():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # This clears your warehouse stock levels
        cursor.execute("DELETE FROM inventory")
        conn.commit()
        cursor.close()
        conn.close()
        flash("Warehouse inventory has been reset.")
    return redirect(url_for('dashboard'))
# ============== INVENTORY ==============
@app.route('/inventory', methods=['GET','POST'])
def inventory():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # ================= TOP SELLING PRODUCTS =================
    cursor.execute("""
        SELECT product, SUM(quantity) AS total_sold
        FROM manual_sales
        GROUP BY product
        ORDER BY total_sold DESC
        LIMIT 5
    """)

    top_products = cursor.fetchall()

    # ================= HANDLE FORM SUBMISSION =================
    if request.method == "POST":

        product = request.form.get("product_name")
        quantity = request.form.get("quantity")

        if product and quantity:
            quantity = int(quantity)

            cursor.execute("""
                INSERT INTO inventory (product_name, current_stock)
                VALUES (%s,%s)
                ON DUPLICATE KEY UPDATE
                current_stock = current_stock + VALUES(current_stock)
            """,(product, quantity))

            conn.commit()
            flash("Stock updated successfully!")

        # ---------- CSV Upload ----------
        file = request.files.get("inventory_file")

        if file and file.filename != "":
            try:

                df = pd.read_csv(file) if file.filename.endswith(".csv") else pd.read_excel(file)

                df.columns = [c.strip().lower() for c in df.columns]

                col_prod = next((c for c in df.columns if 'product' in c or 'item' in c or 'name' in c), None)
                col_stock = next((c for c in df.columns if 'stock' in c or 'qty' in c or 'quantity' in c), None)

                if col_prod and col_stock:

                    for _, row in df.iterrows():

                        product = str(row[col_prod])
                        stock = int(row[col_stock])

                        cursor.execute("""
                            INSERT INTO inventory (product_name, current_stock)
                            VALUES (%s,%s)
                            ON DUPLICATE KEY UPDATE
                            current_stock = VALUES(current_stock)
                        """,(product, stock))

                    conn.commit()
                    flash("Warehouse file uploaded successfully!")

            except Exception as e:
                flash(f"File Upload Error: {e}")

    # ================= FETCH INVENTORY DATA =================
    cursor.execute("""
        SELECT product_name AS product,
               current_stock AS warehouse_stock
        FROM inventory
    """)

    inventory_data = cursor.fetchall()

    total_products = len(inventory_data)
    total_stock = sum(item['warehouse_stock'] for item in inventory_data)
    low_stock = sum(1 for item in inventory_data if item['warehouse_stock'] < 5)

    # ================= INVENTORY CHART =================
    inventory_chart_json = None

    if inventory_data:

        df_inv = pd.DataFrame(inventory_data)

        fig_inv = px.bar(
            df_inv,
            x="product",
            y="warehouse_stock",
            title="Inventory Stock Levels",
            labels={
                "product":"Product",
                "warehouse_stock":"Stock Quantity"
            },
            color="warehouse_stock"
        )

        fig_inv.update_layout(
            template="plotly_white",
            height=400
        )

        inventory_chart_json = json.dumps(
            fig_inv,
            cls=plotly.utils.PlotlyJSONEncoder
        )

    cursor.close()
    conn.close()

    return render_template(
        "inventory.html",
        inventory_data=inventory_data,
        total_products=total_products,
        total_stock=total_stock,
        low_stock=low_stock,
        inventory_chart_json=inventory_chart_json,
        top_products=top_products
    )
    
#=============FORECAST===============
#============= FORECAST =============
@app.route('/forecast')
def forecast():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # ===== 1. FETCH SALES DATA =====
    cursor.execute("SELECT sale_date as ds, amount as y FROM manual_sales")
    sales_records = cursor.fetchall()

    if len(sales_records) < 2:
        cursor.close()
        conn.close()
        return render_template('forecast.html', forecast_json=None)

    # ===== 2. PREPARE DATA =====
    df = pd.DataFrame(sales_records)
    df['ds'] = pd.to_datetime(df['ds'])
    df_daily = df.groupby('ds')['y'].sum().reset_index()

    # ===== 3. PROPHET MODEL =====
    m = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False
    )
    m.fit(df_daily)

    future = m.make_future_dataframe(periods=30)
    forecast_results = m.predict(future)

    # ===== 4. GRAPH (WITH CONFIDENCE INTERVAL) =====
    fig_ai = px.line(df_daily, x='ds', y='y', title="Revenue Trend")

    # Prediction line
    fig_ai.add_scatter(
        x=forecast_results.tail(30)['ds'],
        y=forecast_results.tail(30)['yhat'],
        name="AI Prediction",
        mode='lines+markers'
    )

    # Upper bound
    fig_ai.add_scatter(
        x=forecast_results.tail(30)['ds'],
        y=forecast_results.tail(30)['yhat_upper'],
        mode='lines',
        line=dict(width=0),
        showlegend=False
    )

    # Lower bound (filled)
    fig_ai.add_scatter(
        x=forecast_results.tail(30)['ds'],
        y=forecast_results.tail(30)['yhat_lower'],
        fill='tonexty',
        fillcolor='rgba(0,123,255,0.2)',
        line=dict(width=0),
        name='Confidence Interval'
    )

    forecast_graph_json = json.dumps(fig_ai, cls=plotly.utils.PlotlyJSONEncoder)

    # ===== 5. METRICS =====
    next_day_val = forecast_results.iloc[-30]['yhat']
    total_30_day = forecast_results.tail(30)['yhat'].sum()

    weekly_res = forecast_results.tail(7)
    total_week_pred = weekly_res['yhat'].sum()

    daily_avg = forecast_results['yhat'].mean()

    # ===== 6. TREND =====
    first_val = forecast_results['yhat'].iloc[0]
    last_val = forecast_results['yhat'].iloc[-1]

    trend_percent = ((last_val - first_val) / first_val) * 100

    if trend_percent > 10:
        trend_text = "📈 Strong Growth"
    elif trend_percent < -10:
        trend_text = "📉 Decline"
    else:
        trend_text = "⚖ Stable"

    # ===== 7. AI INSIGHTS =====
    if trend_percent > 10:
        insight = "Revenue is expected to increase significantly."
    elif trend_percent < -10:
        insight = "Revenue may decline, monitor business closely."
    else:
        insight = "Revenue is expected to remain stable."

    # ===== 8. WEEKLY TABLE DATA =====
    table_data = []
    for _, row in weekly_res.iterrows():
        table_data.append({
            'date': row['ds'].strftime('%Y-%m-%d'),
            'day': row['ds'].strftime('%A'),
            'revenue': round(row['yhat'], 2)
        })

    # ===== 9. TRENDING PRODUCTS (ML BASED) =====

   

    cursor.execute("""
        SELECT product, sale_date, amount
        FROM manual_sales
        ORDER BY product, sale_date
    """)

    sales_data = cursor.fetchall()

    trending_products = []

    if sales_data:

        df = pd.DataFrame(sales_data)
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        df['amount'] = df['amount'].astype(float)   # 🔥 IMPORTANT FIX

        # Group data per product
        for product, group in df.groupby('product'):

            group = group.sort_values('sale_date')

            # Need minimum data
            
            if len(group) < 2:
                current = float(group['amount'].iloc[-1])
                predicted = current   # no ML, fallback

                trending_products.append({
                    "name": product,
                    "current": round(current, 2),
                    "predicted": round(predicted, 2),
                    "growth": 0
                })
                continue
                

            # Time index
            group['t'] = np.arange(len(group))

            X = group[['t']]
            y = group['amount']

            # Train ML model
            model = LinearRegression()
            model.fit(X, y)

            # Predict next value
            next_t = np.array([[len(group)]])
            predicted = model.predict(next_t)[0]

            current = y.iloc[-1]

            # Avoid division error
            if current != 0:
                growth = ((predicted - current) / current) * 100
            else:
                growth = 0

            trending_products.append({
                "name": product,
                "current": round(current, 2),
                "predicted": round(predicted, 2),
                "growth": round(growth, 2)
            })

    # Sort by highest growth
    trending_products = sorted(trending_products, key=lambda x: x['growth'], reverse=True)

    # Take top 5
    trending_products = trending_products[:5]

    cursor.close()
    conn.close()

    # ===== 10. RETURN =====
    return render_template(
        'forecast.html',
        next_pred=round(next_day_val, 2),
        total_month_pred=round(total_30_day, 2),
        total_week_pred=round(total_week_pred, 2),
        daily_avg=round(daily_avg, 2),

        trend_text=trend_text,
        insight=insight,

        weekly_forecast=table_data,
        trending_products=trending_products,

        forecast_json=forecast_graph_json
    )
#================Expenses=================
@app.route('/expense', methods=['GET','POST'])
def expense():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(amount) as total FROM expenses")
    total_expense = cursor.fetchone()["total"] or 0

    cursor.execute("""
    SELECT category, SUM(amount) as total
    FROM expenses
    GROUP BY category
    ORDER BY total DESC
    LIMIT 1
    """)

    top_expense = cursor.fetchone()

    cursor.execute("""
    SELECT id, category, amount
    FROM expenses
    ORDER BY id DESC
    LIMIT 10
    """)

    expense_list = cursor.fetchall()

    # -------- SAVE NEW EXPENSE --------
    if request.method == 'POST':

        category = request.form.get("category")
        amount = request.form.get("amount")

        # If user selected "Other"
        if category == "Other":
            category = request.form.get("other_category")

        cursor.execute("""
            INSERT INTO expenses (category, amount)
            VALUES (%s,%s)
        """, (category, amount))

        conn.commit()
        flash("Expense saved successfully!")

     



    # -------- GENERATE EXPENSE CHART --------
    expense_json = None

    cursor.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        GROUP BY category
    """)

    expense_data = cursor.fetchall()
    if expense_data:

        df_exp = pd.DataFrame(expense_data)
        fig_exp = px.pie(
                df_exp,
                names='category',
                values='total',
                hole=0.45,
                title=None
            )

        fig_exp.update_traces(
                textinfo="percent+label",
                pull=[0.05 if i == df_exp['total'].idxmax() else 0 for i in range(len(df_exp))]
            )

        fig_exp.update_layout(
                template="plotly_white",
                legend_title="Category",
                margin=dict(t=10,b=10,l=10,r=10)
            )

            

        expense_json = json.dumps(
                fig_exp,
                cls=plotly.utils.PlotlyJSONEncoder
            )

    cursor.close()
    conn.close()

    # -------- MONTHLY EXPENSE TREND --------
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT DATE_FORMAT(expense_date,'%Y-%m') as month,
    SUM(amount) as total
    FROM expenses
    GROUP BY month
    ORDER BY month
    """)

    monthly_data = cursor.fetchall()

    monthly_expense_json = None

    if monthly_data:

        df_month = pd.DataFrame(monthly_data)

        # Convert month format to nicer label
        df_month['month'] = pd.to_datetime(df_month['month']).dt.strftime('%b %Y')

        fig_month = px.line(
            df_month,
            x="month",
            y="total",
            markers=True,
            labels={
                "month": "Month",
                "total": "Expenses (₹)"
            }
        )

        fig_month.update_layout(
            template="plotly_white",
            height=400
        )

        monthly_expense_json = json.dumps(
            fig_month,
            cls=plotly.utils.PlotlyJSONEncoder
        )
        cursor.close()
        conn.close()

    return render_template(
        'expense.html',
        expense_json=expense_json,
         monthly_expense_json= monthly_expense_json,
        total_expense=total_expense,
        top_expense=top_expense,
        expense_list=expense_list
    )

@app.route('/upload_expense_csv', methods=['POST'])
def upload_expense_csv():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('file')

    if not file:
        flash("No file selected!")
        return redirect(url_for('expense'))

    try:
        df = pd.read_csv(file)

        conn = get_connection()
        cursor = conn.cursor()

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO expenses (category, amount, expense_date)
                VALUES (%s, %s, %s)
            """, (
                row['category'],
                float(row['amount']),   # 🔥 IMPORTANT FIX
                row['expense_date']
            ))

        conn.commit()
        cursor.close()
        conn.close()

        flash("✅ Expense CSV uploaded successfully!")

    except Exception as e:
        flash(f"❌ Error: {str(e)}")

    return redirect(url_for('expense'))    

@app.route("/delete_expense/<int:id>")
def delete_expense(id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE id=%s",(id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Expense deleted successfully!")

    return redirect(url_for("expense"))


@app.route('/save_expense', methods=['POST'])
def save_expense():
    category = request.form.get('category')
    amount = float(request.form.get('amount') or 0)
    
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # "expenses" table ka use kar rahe hain jo aapne naya banaya hai
        cursor.execute("INSERT INTO expenses (category, amount, expense_date) VALUES (%s, %s, %s)", 
                       (category, amount, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
    return redirect(url_for('expense'))
#===============ADMIN===============
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM admin WHERE username=%s", (username,))
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin and check_password_hash(admin['password'], password):
            session['admin'] = True
            return redirect('/admin_dashboard')
        else:
            return render_template('admin_login.html', error="Invalid admin credentials")

    return render_template('admin_login.html')
#===================ADMIN============
@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin_login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # All users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    # Total users
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']

    # Active users
    cursor.execute("SELECT COUNT(*) as active FROM users WHERE is_active=1")
    active_users = cursor.fetchone()['active']

    return render_template(
        'admin_dashboard.html',
        users=users,
        total_users=total_users,
        active_users=active_users
    )

@app.route('/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin_dashboard')


@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin_login')



@app.route('/admin_change_password', methods=['POST'])
def admin_change_password():
    if not session.get('admin'):
        return redirect('/admin_login')

    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # ✅ check confirm password
    if new_password != confirm_password:
        flash("Passwords do not match", "error")
        return redirect('/admin_dashboard')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admin WHERE username=%s", ('admin',))
    admin = cursor.fetchone()

    # ✅ check old password
    if admin and check_password_hash(admin['password'], old_password):

        new_hashed = generate_password_hash(new_password)

        cursor.execute("""
            UPDATE admin 
            SET password=%s 
            WHERE username=%s
        """, (new_hashed, 'admin'))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Password updated successfully", "success")
        return redirect('/admin_dashboard')

    # ❌ wrong old password case
    cursor.close()
    conn.close()

    flash("Old password incorrect", "error")
    return redirect('/admin_dashboard')


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    email = session.get('user_email')

    if email:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users 
            SET is_active=0 
            WHERE email=%s
        """, (email,))

        conn.commit()
        cursor.close()
        conn.close()

    session.clear()
    return redirect(url_for('home'))
#=============Report=========
@app.route('/download_csv')
def download_csv():
    if 'user_id' not in session:
        return redirect('/login')

    import pandas as pd

    data = get_business_report_data()

    df = pd.DataFrame([data])

    file_path = "business_report.csv"
    df.to_csv(file_path, index=False)

    return send_file(file_path, as_attachment=True)

@app.route('/download_excel')
def download_excel():
    if 'user_id' not in session:
        return redirect('/login')

    import pandas as pd

    data = get_business_report_data()

    df = pd.DataFrame([data])

    file_path = "business_report.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)



@app.route('/download_pdf')
def download_pdf():
    if 'user_id' not in session:
        return redirect('/login')

    data = get_business_report_data()

    file_path = "business_report.pdf"
    doc = SimpleDocTemplate(file_path)

    styles = getSampleStyleSheet()

    content = []

    # ===== TITLE =====
    content.append(Paragraph("Business Analysis Report", styles['Title']))
    content.append(Spacer(1, 20))

    # ===== METRICS =====
    content.append(Paragraph(f"Total Sales: ₹{data['total_sales']}", styles['Normal']))
    content.append(Paragraph(f"Total Profit: ₹{data['total_profit']}", styles['Normal']))
    content.append(Paragraph(f"Growth Rate: {data['growth_rate']}%", styles['Normal']))
    content.append(Paragraph(f"Best Product: {data['best_product']}", styles['Normal']))
    content.append(Paragraph(f"Expected Next Profit: ₹{data['expected_profit']}", styles['Normal']))

    content.append(Spacer(1, 20))

    # ===== INSIGHTS SECTION (THIS WAS MISSING) =====
    content.append(Paragraph("Insights & Analysis", styles['Heading2']))
    content.append(Spacer(1, 10))

    content.append(Paragraph(data.get('performance', ''), styles['Normal']))
    content.append(Paragraph(data.get('growth_msg', ''), styles['Normal']))
    content.append(Paragraph(data.get('product_msg', ''), styles['Normal']))

    content.append(Spacer(1, 10))

    content.append(Paragraph("Recommendation:", styles['Heading3']))
    content.append(Paragraph(data.get('recommendation', ''), styles['Normal']))

    # ===== BUILD PDF =====
    doc.build(content)

    return send_file(file_path, as_attachment=True)


# ================= MAIN =================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    


