from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
CORS(app)  # allows ANY frontend to call the API

import json

# Firebase init
cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
if cred_json:
    cred = credentials.Certificate(json.loads(cred_json))
else:
    cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def send_email(order):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receivers = os.getenv("EMAIL_RECEIVERS").split(",")  # splits into a list

    print("Email sender:", sender)
    print("Receivers:", receivers)
    print("Password length:", len(password) if password else "None")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🍗 New Order from {order['name']}!"
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)

    body = f"""
    <h2>New Chick Up Order</h2>
    <p><b>Customer:</b> {order['name']}</p>
    <p><b>Email:</b> {order.get('email', 'N/A')}</p>
    <p><b>Phone:</b> {order['phone']}</p>
    <p><b>Address:</b> {order['address']}</p>
    <p><b>Items:</b> {order['items']}</p>
    <p><b>Total:</b> ₱{order['total']}</p>
    <p><b>Time:</b> {order['timestamp']}</p>
    """
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())

@app.route("/api/order", methods=["POST"])
def place_order():
    data = request.get_json()
    print("Incoming order:", data)

    if not data:
        return jsonify({"error": "No JSON received"}), 400

    data["timestamp"] = datetime.now().isoformat()
    data["status"] = "pending"

    try:
        db.collection("orders").add(data)
        print("Order saved to Firestore")
        send_email(data)
        print("Email sent successfully")
    except Exception as e:
        print("Error while processing order:", e)
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Order placed successfully!"}), 201

@app.route("/api/orders", methods=["GET"])
def get_orders():
    orders_ref = db.collection("orders").order_by(
        "timestamp", direction=firestore.Query.DESCENDING
    ).stream()
    orders = []
    for doc in orders_ref:
        order = doc.to_dict()
        if order.get("status") == "delivered":
            continue
        order["id"] = doc.id
        orders.append(order)
    return jsonify(orders), 200

@app.route("/api/deliver/<order_id>", methods=["POST"])
def mark_delivered(order_id):
    data = request.get_json()
    customer_email = data.get("email")

    if not customer_email:
        return jsonify({"error": "Missing email"}), 400

    try:
        db.collection("orders").document(order_id).update({"status": "delivered"})
        
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Chick Up Order is on the way!"
        msg["From"] = sender
        msg["To"] = customer_email
        
        body = f"<h2>Chick Up</h2><p>Your order is on the way! Thank you for ordering!</p>"
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, [customer_email], msg.as_string())
            
        return jsonify({"message": "Order delivered and email sent!"}), 200
    except Exception as e:
        print("Error marking delivered:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/feedback", methods=["POST"])
def send_feedback():
    data = request.get_json()
    customer_email = data.get("email")
    message_text = data.get("message")
    order_id = data.get("order_id")

    if not customer_email or not message_text:
        return jsonify({"error": "Missing email or message"}), 400

    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Update on your Chick Up Order"
    msg["From"] = sender
    msg["To"] = customer_email

    body = f"""
    <h2>Chick Up</h2>
    <p>Hello,</p>
    <p>Here is an update regarding your order (ID: {order_id}):</p>
    <blockquote style="border-left: 4px solid #c8842a; padding-left: 10px; color: #555;">
        {message_text}
    </blockquote>
    <p>Thank you for choosing Chick Up!</p>
    """
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, [customer_email], msg.as_string())
        return jsonify({"message": "Feedback sent to customer!"}), 200
    except Exception as e:
        print("Error sending feedback email:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)