import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
from fpdf import FPDF
import hashlib
from sklearn.linear_model import LinearRegression
import numpy as np
import cv2
from PIL import Image

# ---------------------- Admin Credentials ----------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("12345".encode()).hexdigest()

# ---------------------- Session Login ----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_type" not in st.session_state:
    st.session_state.user_type = None

# ---------------------- Database Setup ----------------------
conn = sqlite3.connect('medical_inventory.db', check_same_thread=False)
c = conn.cursor()

# SQL table creation
c.execute("""CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT,
    category TEXT,
    quantity INTEGER,
    unit TEXT,
    expiry_date TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    item_type TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT
)""")
conn.commit()

# ---------------------- Helper Functions ----------------------
def add_inventory_item(item_name, category, quantity, unit, expiry_date):
    c.execute("INSERT INTO inventory (item_name, category, quantity, unit, expiry_date) VALUES (?, ?, ?, ?, ?)",
              (item_name, category, quantity, unit, expiry_date))
    conn.commit()

def remove_inventory_item(item_id):
    c.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()

def view_inventory():
    c.execute("SELECT * FROM inventory")
    return c.fetchall()

def add_supplier(name, email, phone, item_type):
    c.execute("INSERT INTO suppliers (name, email, phone, item_type) VALUES (?, ?, ?, ?)",
              (name, email, phone, item_type))
    conn.commit()

def view_suppliers():
    c.execute("SELECT * FROM suppliers")
    return c.fetchall()

def generate_pdf_report(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Medical Inventory Report", ln=1, align="C")
    pdf.ln(10)
    for row in data:
        line = f"ID: {row[0]} | Name: {row[1]} | Category: {row[2]} | Qty: {row[3]} {row[4]} | Exp: {row[5]}"
        pdf.cell(200, 10, txt=line, ln=1)
    pdf.output("inventory_report.pdf")

def predict_demand():
    c.execute("SELECT quantity FROM inventory")
    quantities = [q[0] for q in c.fetchall()]
    if len(quantities) < 2:
        return 0, [], []
    days = np.array(range(1, len(quantities) + 1)).reshape(-1, 1)
    q_arr = np.array(quantities)
    model = LinearRegression()
    model.fit(days, q_arr)
    future_day = np.array([[len(quantities) + 1]])
    predicted_qty = model.predict(future_day)[0]
    return round(predicted_qty, 2), days.flatten(), q_arr

def decode_barcode(img):
    detector = cv2.QRCodeDetector()
    img = np.array(img.convert('RGB'))
    val, points, _ = detector.detectAndDecode(img)
    return val if val else None

def add_staff(username, password):
    hashed_pass = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO staff (username, password_hash) VALUES (?, ?)", (username, hashed_pass))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def view_staff():
    c.execute("SELECT id, username FROM staff")
    return c.fetchall()

def remove_staff(staff_id):
    c.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    conn.commit()
    return True

# ---------------------- Login Page ----------------------
def login_page():
    st.title("🔐 Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        hashed_input = hashlib.sha256(password.encode()).hexdigest()
        c.execute("SELECT * FROM admins WHERE username = ? AND password_hash = ?", (username, hashed_input))
        admin = c.fetchone()
        if admin:
            st.session_state.logged_in = True
            st.session_state.user_type = "admin"
            st.success("Admin login successful!")
        else:
            c.execute("SELECT * FROM staff WHERE username = ? AND password_hash = ?", (username, hashed_input))
            staff = c.fetchone()
            if staff:
                st.session_state.logged_in = True
                st.session_state.user_type = "staff"
                st.success("Staff login successful!")
            else:
                st.error("Invalid username or password.")

    st.markdown("---")
    st.markdown("### Or Create a New Admin Account")
    new_username = st.text_input("New Admin Username")
    new_password = st.text_input("New Admin Password", type="password")
    confirm_password = st.text_input("Confirm Admin Password", type="password")
    if st.button("Sign Up as Admin"):
        if new_password != confirm_password:
            st.error("Passwords do not match!")
        elif len(new_username.strip()) == 0 or len(new_password.strip()) == 0:
            st.error("Username and password cannot be empty.")
        else:
            hashed_pass = hashlib.sha256(new_password.encode()).hexdigest()
            try:
                c.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", (new_username, hashed_pass))
                conn.commit()
                st.success("Admin account created successfully! You can now log in.")
            except sqlite3.IntegrityError:
                st.error("Username already exists. Try another one.")

if not st.session_state.logged_in:
    login_page()
    st.stop()

# ---------------------- Streamlit UI ----------------------
st.set_page_config(page_title="Medical Inventory", layout="wide")
st.sidebar.title("Navigation")
menu = ["Home", "Inventory", "Suppliers", "Reports", "Demand Prediction", "QR Scanner"]
if st.session_state.user_type == "admin":
    menu.append("Staff Management")
menu.append("Logout")
choice = st.sidebar.selectbox("Go to", menu)

# --- UI Improvements ---
st.markdown(
    """
    <style>
    .st-subheader {
        color: #007bff; /* Primary blue color */
    }
    .st-info {
        background-color: #f0f8ff; /* Light cyan background */
        border-left: 5px solid #007bff;
        padding: 10px;
        margin-bottom: 10px;
    }
    .st-warning {
        background-color: #fff3cd; /* Light yellow background */
        border-left: 5px solid #ffc107; /* Warning yellow color */
        padding: 10px;
        margin-bottom: 10px;
    }
    .st-success {
        background-color: #d4edda; /* Light green background */
        border-left: 5px solid #28a745; /* Success green color */
        padding: 10px;
        margin-bottom: 10px;
    }
    .st-error {
        background-color: #f8d7da; /* Light red background */
        border-left: 5px solid #dc3545; /* Error red color */
        padding: 10px;
        margin-bottom: 10px;
    }
    .dataframe {
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 5px;
        padding: 10px 20px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if choice == "Home":
    st.title("🏥 Medical Inventory Management System")
    st.markdown("### Welcome!")
    st.info("Use the sidebar to navigate through different sections of the application.")
    st.image("Unknown.png", width=600)

elif choice == "Inventory":
    st.subheader("📦 Inventory Management")
    inv_menu = ["View Inventory", "Add Item", "Remove Item", "Manage Expiry Dates"]
    inv_choice = st.selectbox("Select Action", inv_menu)

    if inv_choice == "View Inventory":
        st.subheader("Current Inventory")
        items = view_inventory()
        df = pd.DataFrame(items, columns=["ID", "Item Name", "Category", "Quantity", "Unit", "Expiry Date"])

        # Convert Expiry Date to datetime objects for comparison
        df['Expiry Date'] = pd.to_datetime(df['Expiry Date'])
        today = pd.to_datetime(date.today())
        expiry_threshold = today + pd.Timedelta(days=30)  # Highlight items expiring within 30 days

        # Highlight rows based on expiry date
        def highlight_expiry(row):
            if row['Expiry Date'] < today:
                return ['background-color: #f8d7da'] * len(row)  # Light red for expired
            elif row['Expiry Date'] < expiry_threshold:
                return ['background-color: #fff3cd'] * len(row)  # Light yellow for near expiry
            return [''] * len(row)

        styled_df = df.style.apply(highlight_expiry, axis=1)
        st.dataframe(styled_df)

        low_stock = df[df["Quantity"] < 10]
        if not low_stock.empty:
            st.warning("⚠️ Low Stock Items:")
            st.dataframe(low_stock)

        expired_items = df[df['Expiry Date'] < today]
        if not expired_items.empty:
            st.error("🚨 Expired Items:")
            st.dataframe(expired_items)

        near_expiry_items = df[(df['Expiry Date'] >= today) & (df['Expiry Date'] < expiry_threshold)]
        if not near_expiry_items.empty:
            st.warning("⏳ Items Expiring Soon (within 30 days):")
            st.dataframe(near_expiry_items)

    elif inv_choice == "Add Item":
        st.subheader("➕ Add New Inventory Item")
        with st.form(key='inv_form'):
            col1, col2 = st.columns(2)
            name = col1.text_input("Item Name")
            category = col1.text_input("Category")
            quantity = col1.number_input("Quantity", min_value=1)
            unit = col2.text_input("Unit (e.g., ml, tablets)")
            expiry = col2.date_input("Expiry Date")
            submit = st.form_submit_button("Add Item")

        if submit:
            add_inventory_item(name, category, quantity, unit, str(expiry))
            st.success(f"✅ Item '{name}' added successfully!")

    elif inv_choice == "Remove Item":
        st.subheader("❌ Remove Inventory Item")
        items = view_inventory()
        df = pd.DataFrame(items, columns=["ID", "Item Name", "Category", "Quantity", "Unit", "Expiry Date"])
        if not df.empty:
            item_id = st.selectbox("Select Item ID to Remove", df["ID"])
            if st.button("Remove"):
                remove_inventory_item(item_id)
                st.success(f"Item with ID {item_id} removed.")
        else:
            st.info("Inventory is empty.")

    elif inv_choice == "Manage Expiry Dates":
        st.subheader("📅 Manage Expiry Dates")
        items = view_inventory()
        df = pd.DataFrame(items, columns=["ID", "Item Name", "Category", "Quantity", "Unit", "Expiry Date"])
        if not df.empty:
            item_id_to_update = st.selectbox("Select Item ID to Update Expiry Date", df["ID"])
            current_expiry = df[df['ID'] == item_id_to_update]['Expiry Date'].iloc[0]
            new_expiry_date = st.date_input("New Expiry Date", value=pd.to_datetime(current_expiry))

            if st.button("Update Expiry Date"):
                c.execute("UPDATE inventory SET expiry_date = ? WHERE id = ?", (str(new_expiry_date), item_id_to_update))
                conn.commit()
                st.success(f"Expiry date for Item ID {item_id_to_update} updated to {new_expiry_date}.")
        else:
            st.info("Inventory is empty.")

elif choice == "Suppliers":
    st.subheader("📇 Supplier Management")
    sup_menu = ["View Suppliers", "Add Supplier"]
    sup_choice = st.selectbox("Select Action", sup_menu)

    if sup_choice == "View Suppliers":
        st.subheader("Current Suppliers")
        data = view_suppliers()
        df_sup = pd.DataFrame(data, columns=["ID", "Name", "Email", "Phone", "Supplies"])
        st.dataframe(df_sup)

    elif sup_choice == "Add Supplier":
        st.subheader("➕ Add New Supplier")
        with st.form(key='sup_form'):
            name = st.text_input("Supplier Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            item_type = st.text_input("Supplies (e.g., Medicines, Gloves)")
            add = st.form_submit_button("Add Supplier")

        if add:
            add_supplier(name, email, phone, item_type)
            st.success(f"✅ Supplier '{name}' added!")

elif choice == "Reports":
    st.subheader("📊 Inventory Reports")
    data = view_inventory()
    if data:
        df_report = pd.DataFrame(data, columns=["ID", "Item Name", "Category", "Quantity", "Unit", "Expiry Date"])
        st.dataframe(df_report)
        if st.button("Generate PDF Report"):
            generate_pdf_report(data)
            with open("inventory_report.pdf", "rb") as f:
                st.download_button("Download Report", f, file_name="inventory_report.pdf")
    else:
        st.info("No inventory data available to generate a report.")

elif choice == "Demand Prediction":
    st.subheader("📈 Demand Prediction")
    predicted_qty, days, qties = predict_demand()
    if len(qties) > 0:
        st.info(f"📅 Predicted quantity needed next cycle: **{predicted_qty:.2f} units**")
        df_predict = pd.DataFrame({
            "Day": days,
            "Quantity": qties
        })
        st.line_chart(df_predict.set_index("Day"), height=300)
    else:
        st.warning("⚠️ Not enough data to predict demand. Please add more inventory entries.")

elif choice == "QR Scanner":
    st.subheader("📱 QR Code Scanner")
    uploaded_img = st.file_uploader("Upload QR Image", type=["jpg", "png", "jpeg"])
    if uploaded_img:
        try:
            img = Image.open(uploaded_img).convert("RGB")
            barcode_val = decode_barcode(img)
            if barcode_val:
                st.success(f"✅ Detected QR Code: {barcode_val}")
            else:
                st.warning("⚠️ No QR code detected in the image.")
        except Exception as e:
            st.error(f"Error processing image: {e}")

elif choice == "Staff Management" and st.session_state.user_type == "admin":
    st.subheader("🧑‍⚕️ Staff Account Management")
    staff_menu = ["View Staff", "Add Staff", "Remove Staff"]
    staff_choice = st.selectbox("Manage Staff", staff_menu)

    if staff_choice == "View Staff":
        st.subheader("Current Staff Accounts")
        staff_list = view_staff()
        if staff_list:
            df_staff = pd.DataFrame(staff_list, columns=["ID", "Username"])
            st.dataframe(df_staff)
        else:
            st.info("No staff accounts created yet.")

    elif staff_choice == "Add Staff":
        st.subheader("➕ Add New Staff Account")
        with st.form(key='add_staff_form'):
            new_staff_username = st.text_input("New Staff Username")
            new_staff_password = st.text_input("New Staff Password", type="password")
            confirm_staff_password = st.text_input("Confirm Staff Password", type="password")
            add_staff_button = st.form_submit_button("Add Staff")

        if add_staff_button:
            if new_staff_password != confirm_staff_password:
                st.error("Passwords do not match!")
            elif len(new_staff_username.strip()) == 0 or len(new_staff_password.strip()) == 0:
                st.error("Username and password cannot be empty.")
            else:
                if add_staff(new_staff_username, new_staff_password):
                    st.success(f"✅ Staff account '{new_staff_username}' created successfully!")
                else:
                    st.error("Username already exists. Try another one.")

    elif staff_choice == "Remove Staff":
        st.subheader("❌ Remove Staff Account")
        staff_list = view_staff()
        if staff_list:
            df_staff = pd.DataFrame(staff_list, columns=["ID", "Username"])
            staff_id_to_remove = st.selectbox("Select Staff ID to Remove", df_staff["ID"])
            if st.button("Remove Staff Account"):
                if remove_staff(staff_id_to_remove):
                    st.success(f"Staff account with ID {staff_id_to_remove} removed.")
                else:
                    st.error("Failed to remove staff account.")
        else:
            st.info("No staff accounts to remove.")

elif choice == "Logout":
    st.session_state.logged_in = False
    if "user_type" in st.session_state:
        del st.session_state.user_type
    st.success("You have been logged out.")
    st.experimental_rerun()

# Close the database connection when the app is closed
conn.close()