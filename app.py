from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)



@app.route("/")
def home():
    return render_template("index.html")

@app.route("/paiement")
def paiement():
    # On récupère le nom et le prix du produit depuis l'URL
    produit = request.args.get('produit', 'Fleur')
    prix = request.args.get('prix', '0')
    return render_template("paiement.html", produit=produit, prix=prix)

if __name__ == "__main__":
    app.run(debug=True)