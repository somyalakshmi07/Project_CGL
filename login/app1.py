from flask import Flask, request, render_template, send_file, redirect, url_for, jsonify
import mysql.connector
import pandas as pd
import io 
from io import BytesIO
import os
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

db = mysql.connector.connect(
    host="metro.proxy.rlwy.net",
    user="root",
    password="mnNvxgJvxSNRSDmHSbZdUxZIkPYASNub@metro",
    database="railway"
)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_filtered_data', methods=['POST'])
def get_filtered_data():
    data = request.json
    cgl = data.get('cgl')
    fy = data.get('fy')
    product = data.get('product')

    print(f"Received: CGL={cgl}, FY={fy}, Product={product}")  # Debug

    if cgl != "CGL-2" or not fy or not product:
        return jsonify({"error": "Missing or invalid inputs"}), 400

    table = f"{fy}datacsv"
    print(f"Querying table: {table}")  # Debug

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Ensure Area column exists
        # Check and add 'Area' column if it doesn't exist
        cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE 'Area';")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `Area` DOUBLE;")

        # Check and add 'Zinc' column if it doesn't exist
        cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE 'Zinc';")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `Zinc` DOUBLE;")


        # Update Area and Zinc values
        cursor.execute(f"""
            UPDATE `{table}` 
            SET `Area` = ROUND((`Ip Width` * `Total Length`) / 1000, 4),
                `Zinc` = ROUND((`Ip Width` * `Total Length` * `Total Zn/AlZn Coating`) / 1000000000, 3);
        """)

        conn.commit()
        cursor.close()

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query = f"""
        SELECT 
            `Op Batch No`,
            `Actual Product`, 
            `Actual Tdc`,
            CASE 
                WHEN LEFT(`Actual Tdc`, 3) = 'ZAP' THEN 'Appliance'
                WHEN LEFT(`Actual Tdc`, 3) = 'ZST' THEN 'Retail'
                WHEN LEFT(`Actual Tdc`, 3) = 'ZGN' THEN 'Retail'
                WHEN LEFT(`Actual Tdc`, 3) = 'ZTU' THEN 'P&T'
                WHEN LEFT(`Actual Tdc`, 3) = 'ZPL' THEN 'Panel'
                WHEN LEFT(`Actual Tdc`, 3) = 'ZEX' THEN 'export'
                ELSE 'Other'
            END AS segment,
            `Prop Ip Wt`,
            `O/P Wt`,
            `Total Length`,
            `Area`,
            `Zinc`,
            ROUND(`Process Duration(in min)`, 0) AS `Process Duration(in min)`,
            ROUND((`Prop Ip Wt` * 1000) / (7.850 * (`Ip Width` * `Total Length`) / 1000), 3) AS `CRFH thickness`,
            ROUND((`Total Zn/AlZn Coating` / 
                CASE 
                    WHEN `Actual Product` = 'GI' THEN 7140
                    WHEN `Actual Product` IN ('GL', 'PPGL') THEN 3750
                    WHEN `Actual Product` = 'ZM' THEN 6850
                    ELSE NULL
                END
            ) + ROUND((`Prop Ip Wt` * 1000) / (7.850 * (`Ip Width` * `Total Length`) / 1000), 3), 4) AS `GP thickness`,
            `Total Zn/AlZn Coating`,
            `Op Width`,
            ROUND((`Total Length`/`Process Duration(in min)`),3) as speed,
            ROUND((`O/P Wt`/`Process Duration(in min)`)*60,3) as productivity

        FROM `{table}`
        WHERE `Actual Product` = %s
        """

        cursor.execute(query, (product,))
        rows = cursor.fetchall()
        return jsonify(rows)

    except Exception as e:
        print(f"Error: {e}")  # Debug
        return jsonify({"error": str(e)}), 500
    
@app.route('/summary', methods=['GET'])
def summary():
    try:
        fy = request.args.get('fy')  # e.g., FY25
        actual_product = request.args.get('actual_product')  # e.g., GI, or All

        if not fy or not fy.startswith("FY"):
            return "Invalid FY value", 400

        if not actual_product:
            return "Missing actual_product filter", 400

        fy_number = fy[2:]  # FY25 → 25
        table_name = f"{fy_number}datacsv"

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Products to include when "All" is selected
        product_list = ['GI', 'GL', 'PPGL', 'ZM']

        # Build query
        if actual_product == "All":
            format_strings = ','.join(['%s'] * len(product_list))
            query = f"""
                SELECT 
                    `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` IN ({format_strings})
                GROUP BY `Actual Product`
                ORDER BY FIELD(`Actual Product`, {format_strings})
            """
            values = product_list * 2  # For both WHERE and ORDER BY FIELD
            cursor.execute(query, values)
            results = cursor.fetchall()

            # Grand total
            total_query = f"""
                SELECT 
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` IN ({format_strings})
            """
            cursor.execute(total_query, product_list)
            total = cursor.fetchone()
            total["Actual Product"] = "Grand Total"
            results.append(total)

        else:
            query = f"""
                SELECT 
                    `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` = %s
                GROUP BY `Actual Product`
            """
            cursor.execute(query, (actual_product,))
            results = cursor.fetchall()

            total_query = f"""
                SELECT 
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` = %s
            """
            cursor.execute(total_query, (actual_product,))
            total = cursor.fetchone()
            total["Actual Product"] = "Grand Total"
            results.append(total)

        return render_template("summary.html", data=results, fy=fy, actual_product=actual_product)


    except Exception as e:
        return f"Error occurred: {str(e)}"
from collections import defaultdict

# Track export counts per table in memory (resets when server restarts)
export_counts = defaultdict(int)


@app.route('/export-summary', methods=['POST'])
def export_summary():
    try:
        fy = request.form.get('fy')
        actual_product = request.form.get('actual_product')

        if not fy or not actual_product:
            return "Missing filters", 400

        table_name = f"{fy[-2:]}datacsv"
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        product_list = ['GI', 'GL', 'PPGL', 'ZM']

        if actual_product == "All":
            format_strings = ','.join(['%s'] * len(product_list))
            query = f"""
                SELECT 
                    `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` IN ({format_strings})
                GROUP BY `Actual Product`
                ORDER BY FIELD(`Actual Product`, {format_strings})
            """
            values = product_list * 2
            cursor.execute(query, values)
            rows = cursor.fetchall()

            # Grand Total
            total_query = f"""
                SELECT 
                    'Grand Total' AS `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2),
                    ROUND(SUM(`O/P Wt`), 2),
                    ROUND(SUM(`Total Length`), 2),
                    ROUND(SUM(`Area`), 2),
                    ROUND(SUM(`Zinc`), 2),
                    ROUND(SUM(`Process Duration(in min)`), 2)
                FROM {table_name}
                WHERE `Actual Product` IN ({format_strings})
            """
            cursor.execute(total_query, product_list)
            total = cursor.fetchone()
            rows.append(total)

        else:
            query = f"""
                SELECT 
                    `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2) AS `Prop IP Wt`,
                    ROUND(SUM(`O/P Wt`), 2) AS `O/P Wt`,
                    ROUND(SUM(`Total Length`), 2) AS `Total Length`,
                    ROUND(SUM(`Area`), 2) AS `Area`,
                    ROUND(SUM(`Zinc`), 2) AS `Zinc`,
                    ROUND(SUM(`Process Duration(in min)`), 2) AS `Process Duration(in min)`
                FROM {table_name}
                WHERE `Actual Product` = %s
                GROUP BY `Actual Product`
            """
            cursor.execute(query, (actual_product,))
            rows = cursor.fetchall()

            total_query = f"""
                SELECT 
                    'Grand Total' AS `Actual Product`,
                    ROUND(SUM(`Prop IP Wt`), 2),
                    ROUND(SUM(`O/P Wt`), 2),
                    ROUND(SUM(`Total Length`), 2),
                    ROUND(SUM(`Area`), 2),
                    ROUND(SUM(`Zinc`), 2),
                    ROUND(SUM(`Process Duration(in min)`), 2)
                FROM {table_name}
                WHERE `Actual Product` = %s
            """
            cursor.execute(total_query, (actual_product,))
            total = cursor.fetchone()
            rows.append(total)

        df = pd.DataFrame(rows)
        

        # Filename auto-increment
        export_counts[table_name] += 1
        filename = f"{table_name}({export_counts[table_name]})_{actual_product}_summary.xlsx"

        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name="Summary")
        writer.close()
        output.seek(0)

        return send_file(output, download_name=filename, as_attachment=True)

    except Exception as e:
        print("Export Error:", e)
        return f"An error occurred during export: {str(e)}"


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))   # ← use the env‑supplied port
    app.run(host="0.0.0.0", port=port)
