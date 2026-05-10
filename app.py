from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Daniel12349",
    database="site_fleurs"
)
cursor = conn.cursor(dictionary=True)

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)