from flask import Flask, render_template, request, redirect
import sqlite3
from collections import defaultdict
import matplotlib.pyplot as plt
from flask import send_file
import io
import google.generativeai as genai
import csv
from reportlab.pdfgen import canvas

genai.configure(api_key="")

model = genai.GenerativeModel(
    "gemini-3.6-flash"
)

app = Flask(__name__)

# Database Setup
def init_db():
    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        amount REAL,
        type TEXT,
        category TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

@app.route("/chart")
def chart():

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT category, SUM(amount)
    FROM transactions
    WHERE type='Expense'
    GROUP BY category
    """)

    data = cur.fetchall()
    conn.close()

    plt.figure(figsize=(5, 5))

    if len(data) == 0:
        plt.text(
            0.5,
            0.5,
            "No Expense Data",
            ha="center",
            va="center",
            fontsize=16
        )
        plt.axis("off")

    else:
        labels = [row[0] for row in data]
        values = [row[1] for row in data]

        plt.pie(
            values,
            labels=labels,
            autopct="%1.1f%%"
        )

    img = io.BytesIO()

    plt.savefig(
        img,
        format="png",
        bbox_inches="tight"
    )

    plt.close()

    img.seek(0)

    return send_file(
        img,
        mimetype="image/png"
    )

@app.route("/")
def home():

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions ORDER BY id DESC")
    transactions = cur.fetchall()

    cur.execute(
        "SELECT SUM(amount) FROM transactions WHERE type='Income'"
    )
    income = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT SUM(amount) FROM transactions WHERE type='Expense'"
    )
    expense = cur.fetchone()[0] or 0

    balance = income - expense

    category_data = defaultdict(float)

    for t in transactions:
        if t[3] == "Expense":
            category_data[t[4]] += t[2]

    highest_category = "No Expenses Yet"

    if category_data:
        highest_category = max(
            category_data,
            key=category_data.get
        )

    ai_advice = "Add some expenses to get AI advice."

    if expense > 0:

        prompt = f"""
        Income: {income}

        Expense: {expense}

        Highest Expense Category:
        {highest_category}

        Give 3 short money-saving tips.
        """

        try:

            response = model.generate_content(
                prompt
            )

            ai_advice = response.text

        except Exception as e:

            ai_advice = f"AI advice unavailable: {str(e)}"

    conn.close()

    return render_template(
        "index.html",
        transactions=transactions,
        income=income,
        expense=expense,
        balance=balance,
        highest_category=highest_category,
        ai_advice=ai_advice
    )

@app.route("/add", methods=["POST"])
def add():

    title = request.form["title"]
    amount = float(request.form["amount"])
    trans_type = request.form["type"]
    category = request.form["category"]

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO transactions
    (title, amount, type, category)
    VALUES (?, ?, ?, ?)
    """,
    (title, amount, trans_type, category))

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/delete/<int:id>")
def delete(id):

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM transactions WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/export_csv")
def export_csv():

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions")

    rows = cur.fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Title",
        "Amount",
        "Type",
        "Category"
    ])

    writer.writerows(rows)

    mem = io.BytesIO()

    mem.write(
        output.getvalue().encode("utf-8")
    )

    mem.seek(0)

    return send_file(
        mem,
        as_attachment=True,
        download_name="expenses.csv",
        mimetype="text/csv"
    )

@app.route("/export_pdf")
def export_pdf():

    conn = sqlite3.connect("expense.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions")

    rows = cur.fetchall()

    conn.close()

    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer)

    y = 800

    pdf.drawString(
        50,
        y,
        "AI Expense Tracker Report"
    )

    y -= 40

    for row in rows:

        pdf.drawString(
            50,
            y,
            str(row)
        )

        y -= 20

        if y < 40:
            pdf.showPage()
            y = 800

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="expense_report.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)