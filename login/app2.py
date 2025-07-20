from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from datetime import datetime
# from flask import Blueprint, render_template

# app3_blueprint = Blueprint('app2', __name__)

# @app3_blueprint.route('/')
# def productivity():
#     return "Productivity Page"

# Add other routes of app3 here

app = Flask(__name__)

# MySQL config
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Megha@22",
    database="order_data"
)
cursor = db.cursor()

# Month table creation logic
def create_table_if_not_exists(table_name):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_type VARCHAR(50),
            tdc VARCHAR(50),
            thickness FLOAT,
            width FLOAT,
            zinc_coating VARCHAR(50),
            quantity INT,
            booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

def get_month_table():
    now = datetime.now()
    month_year = now.strftime('%B_%Y').lower()
    create_table_if_not_exists(month_year)
    return month_year

@app.route('/', methods=['GET', 'POST'])
def index():
    table = get_month_table()

    # Constants
    total_hours = 744
    shutdown = 24
    setup = 12
    utilization = 98
    available_time = round((total_hours - shutdown - setup) * (utilization / 100), 2)

    if request.method == 'POST':
        form = request.form

        # Extract data from form
        product_type = form['product_type']
        tdc = form['tdc']
        thickness = float(form['thickness'])
        width = float(form['width'])
        zinc_coating = form['zinc_coating']
        quantity = int(form['quantity'])

        productivity = 1.0  # default fixed
        required_time = round(quantity / productivity, 2)

        # Get already booked time
        cursor.execute(f"SELECT SUM(quantity / 1.0) FROM `{table}`")
        result = cursor.fetchone()[0] or 0
        remaining = round(available_time - result, 2)

        if required_time <= remaining:
            cursor.execute(f"""
                INSERT INTO `{table}` 
                (product_type, tdc, thickness, width, zinc_coating, quantity)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                product_type,
                tdc,
                thickness,
                width,
                zinc_coating,
                quantity
            ))
            db.commit()
        else:
            return render_template("order_punch.html",
                                   error="Operation time booked. Not enough available time.",
                                   show_form=True,
                                   records=[],
                                   available_time=available_time,
                                   booked_time=result,
                                   left_time=remaining,
                                   table=table)

        return redirect(url_for('index'))

    # Fetch records
    cursor.execute(f"SELECT * FROM `{table}` ORDER BY id DESC")
    records = cursor.fetchall()

    # Booked Time
    cursor.execute(f"SELECT SUM(quantity / 1.0) FROM `{table}`")
    booked_time = cursor.fetchone()[0] or 0
    left_time = round(available_time - booked_time, 2)

    return render_template("order_punch.html",
                           records=records,
                           available_time=available_time,
                           booked_time=booked_time,
                           left_time=left_time,
                           table=table,
                           error=None,
                           show_form=False)

@app.route('/delete/<int:id>')
def delete_order(id):
    table = get_month_table()
    cursor.execute(f"DELETE FROM `{table}` WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_order(id):
    table = get_month_table()
    if request.method == 'POST':
        form = request.form
        cursor.execute(f"""
            UPDATE `{table}` SET
            product_type=%s, tdc=%s, thickness=%s, width=%s,
            zinc_coating=%s, quantity=%s
            WHERE id=%s
        """, (
            form['product_type'], form['tdc'], form['thickness'],
            form['width'], form['zinc_coating'], form['quantity'], id
        ))
        db.commit()
        return redirect(url_for('index'))

    cursor.execute(f"SELECT * FROM `{table}` WHERE id = %s", (id,))
    order = cursor.fetchone()
    return render_template("edit.html", order=order)

@app.route('/show_form')
def show_form():
    table = get_month_table()
    cursor.execute(f"SELECT SUM(quantity / 1.0) FROM `{table}`")
    booked_time = cursor.fetchone()[0] or 0

    total_hours = 744
    shutdown = 24
    setup = 12
    utilization = 98
    available_time = round((total_hours - shutdown - setup) * (utilization / 100), 2)
    left_time = round(available_time - booked_time, 2)

    return render_template("order_punch.html",
                           records=[],
                           available_time=available_time,
                           booked_time=booked_time,
                           left_time=left_time,
                           table=table,
                           error=None,
                           show_form=True)

if __name__ == '__main__':
    app.run(debug=True)