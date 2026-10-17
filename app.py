import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, date

DB_FILE = "bike_shop.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            notes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bike_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_model_name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bikes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            brand_model TEXT NOT NULL,
            wheel_size TEXT,
            color TEXT,
            frame_serial TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    """)

    cursor.execute("PRAGMA table_info(bikes)")
    columns = [col[1] for col in cursor.fetchall()]
    if "wheel_size" not in columns:
        cursor.execute("ALTER TABLE bikes ADD COLUMN wheel_size TEXT")
    if "color" not in columns:
        cursor.execute("ALTER TABLE bikes ADD COLUMN color TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bike_id INTEGER NOT NULL,
            intake_date TEXT,
            completed_date TEXT,
            status TEXT DEFAULT 'בטיפול',
            issue_description TEXT,
            work_done TEXT,
            estimated_price REAL DEFAULT 0.0,
            final_price REAL DEFAULT 0.0,
            FOREIGN KEY (bike_id) REFERENCES bikes (id)
        )
    """)

    cursor.execute("PRAGMA table_info(work_orders)")
    wo_columns = [col[1] for col in cursor.fetchall()]
    if "work_done" not in wo_columns:
        cursor.execute("ALTER TABLE work_orders ADD COLUMN work_done TEXT")
    if "final_price" not in wo_columns:
        cursor.execute("ALTER TABLE work_orders ADD COLUMN final_price REAL DEFAULT 0.0")
    if "estimated_price" not in wo_columns:
        cursor.execute("ALTER TABLE work_orders ADD COLUMN estimated_price REAL DEFAULT 0.0")
    if "completed_date" not in wo_columns:
        cursor.execute("ALTER TABLE work_orders ADD COLUMN completed_date TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_name TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'פתוח',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    default_brands = [
        "קנונדייל (Cannondale)",
        "טרק (Trek)",
        "ספשלייזד (Specialized)",
        "ג'איינט (Giant)",
        "סקוט (Scott)",
        "סנטה קרוז (Santa Cruz)",
        "מרידה (Merida)",
        "קונה (Kona)",
        "אורבאה (Orbea)",
        "יטי (Yeti)",
        "נורקו (Norco)",
        "ברומפטון (Brompton)",
        "ביאנקי (Bianchi)",
        "סרבלו (Cervélo)",
        "פינארלו (Pinarello)",
        "קיוב (Cube)",
        "קניון (Canyon)",
        "פוקוס (Focus)"
    ]

    for brand in default_brands:
        cursor.execute(
            "INSERT OR IGNORE INTO bike_models (brand_model_name) VALUES (?)",
            (brand,)
        )

    conn.commit()
    conn.close()


init_db()

st.set_page_config(page_title="ניהול חנות אופניים", layout="wide")

st.sidebar.title("🚲 סדנת אופניים")
menu = [
    "🏠 דף ראשי - תיקונים פתוחים",
    "➕ קבלת תיקון / לקוח חדש",
    "👤 ניהול לקוחות והיסטוריה",
    "💬 צ'אט עובדים פנימי"
]
choice = st.sidebar.radio("תפריט ניווט", menu)


# ==========================================
# 1. דף ראשי - תיקונים פתוחים
# ==========================================
if choice == "🏠 דף ראשי - תיקונים פתוחים":
    st.title("📋 לוח תיקונים פעילים בסדנה")
    st.caption("מציג את כל התיקונים הדורשים טיפול")

    conn = get_connection()

    df_raw = pd.read_sql_query("""
        SELECT 
            wo.id AS מס_כרטיס,
            c.name AS שם_לקוח,
            c.phone AS טלפון,
            b.brand_model AS דגם_אופניים,
            b.wheel_size AS גודל_גלגל,
            b.color AS צבע,
            wo.status AS raw_status,
            wo.issue_description AS raw_issue,
            wo.work_done AS raw_work_done,
            wo.estimated_price AS מחיר_משוער,
            wo.final_price AS מחיר_סופי,
            wo.intake_date AS תאריך_קבלה,
            wo.completed_date AS תאריך_סיום
        FROM work_orders wo
        JOIN bikes b ON wo.bike_id = b.id
        JOIN customers c ON b.customer_id = c.id
        WHERE wo.status IN ('בטיפול', 'ממתין לחלקים', 'מוכן לאיסוף')
        ORDER BY wo.id DESC
    """, conn)

    in_service_count = len(df_raw[df_raw['raw_status'] == 'בטיפול'])
    waiting_parts_count = len(df_raw[df_raw['raw_status'] == 'ממתין לחלקים'])
    ready_count = len(df_raw[df_raw['raw_status'] == 'מוכן לאיסוף'])

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🔧 בטיפול פעיל", in_service_count)
    col_m2.metric("📦 ממתין לחלקים", waiting_parts_count)
    col_m3.metric("✅ מוכן לאיסוף", ready_count)

    st.markdown("---")

    if not df_raw.empty:
        st.subheader("🛠️ כרטיסי תיקון פעילים")

        for _, row in df_raw.iterrows():
            details_str = f"{row['דגם_אופניים']}"
            if row['צבע']:
                details_str += f" | צבע: {row['צבע']}"
            if row['גודל_גלגל']:
                details_str += f" | גלגל: {row['גודל_גלגל']}"

            title_str = f"🔧 כרטיס #{row['מס_כרטיס']} | {row['שם_לקוח']} ({row['טלפון']}) - {details_str} | סטטוס: {row['raw_status']}"
            with st.expander(title_str):
                col_info, col_status = st.columns([2, 1])

                with col_info:
                    st.write(f"🛠️ **תקלה מדווחת (מהלקוח):** {row['raw_issue']}")
                    st.write(f"⚙️ **טיפול שנעשה בפועל:** {row['raw_work_done'] or 'טרם הוזן'}")
                    st.write(f"💰 **מחיר משוער בקבלה:** ₪{row['מחיר_משוער'] or 0}")

                with col_status:
                    st.markdown("**עדכון פרטי הטיפול, תאריכים וסטטוס:**")
                    status_options = ["בטיפול", "ממתין לחלקים", "מוכן לאיסוף", "הושלם ונאסף", "בוטל"]
                    current_idx = status_options.index(row['raw_status']) if row['raw_status'] in status_options else 0

                    new_status = st.selectbox(
                        "סטטוס:",
                        status_options,
                        index=current_idx,
                        key=f"status_select_{row['מס_כרטיס']}"
                    )

                    try:
                        parsed_intake = datetime.strptime(str(row['תאריך_קבלה'])[:10], "%Y-%m-%d").date()
                    except Exception:
                        parsed_intake = date.today()

                    new_intake_date = st.date_input(
                        "📅 תאריך פתיחת טיפול:",
                        value=parsed_intake,
                        key=f"intake_date_{row['מס_כרטיס']}"
                    )

                    parsed_completed = None
                    if row['תאריך_סיום']:
                        try:
                            parsed_completed = datetime.strptime(str(row['תאריך_סיום'])[:10], "%Y-%m-%d").date()
                        except Exception:
                            parsed_completed = None

                    has_completed_date = st.checkbox(
                        "הזן תאריך סיום טיפול",
                        value=True if parsed_completed else False,
                        key=f"has_comp_{row['מס_כרטיס']}"
                    )

                    new_completed_date_str = None
                    if has_completed_date:
                        comp_val = parsed_completed if parsed_completed else date.today()
                        new_comp_date = st.date_input(
                            "🏁 תאריך סיום טיפול:",
                            value=comp_val,
                            key=f"completed_date_{row['מס_כרטיס']}"
                        )
                        new_completed_date_str = str(new_comp_date)

                    new_work_done = st.text_area(
                        "טיפול שנעשה בפועל:",
                        value=row['raw_work_done'] or "",
                        key=f"work_done_input_{row['מס_כרטיס']}",
                        placeholder="רשום אילו חלקים הוחלפו / איזה תיקון בוצע..."
                    )

                    current_final_price = float(row['מחיר_סופי'] or 0.0)
                    if current_final_price == 0.0 and row['מחיר_משוער']:
                        current_final_price = float(row['מחיר_משוער'])

                    new_final_price = st.number_input(
                        "מחיר סופי (₪):",
                        min_value=0.0,
                        value=current_final_price,
                        step=10.0,
                        key=f"price_input_{row['מס_כרטיס']}"
                    )

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 שמור שינויים", key=f"btn_update_{row['מס_כרטיס']}"):
                            cursor = conn.cursor()
                            
                            final_completed_str = new_completed_date_str
                            if new_status == "הושלם ונאסף" and not final_completed_str:
                                final_completed_str = str(date.today())

                            cursor.execute(
                                "UPDATE work_orders SET status = ?, intake_date = ?, completed_date = ?, work_done = ?, final_price = ? WHERE id = ?",
                                (new_status, str(new_intake_date), final_completed_str, new_work_done.strip(), new_final_price, row['מס_כרטיס'])
                            )
                            conn.commit()
                            st.success(f"כרטיס #{row['מס_כרטיס']} עודכן בהצלחה!")
                            st.rerun()

                    with btn_col2:
                        if st.button("🗑️ מחק תיקון", key=f"btn_delete_wo_{row['מס_כרטיס']}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM work_orders WHERE id = ?", (row['מס_כרטיס'],))
                            conn.commit()
                            st.warning(f"כרטיס תיקון #{row['מס_כרטיס']} נמחק!")
                            st.rerun()
    else:
        st.info("אין תיקונים פתוחים כרגע. 🎉")

    conn.close()


# ==========================================
# 2. קבלת תיקון / לקוח חדש
# ==========================================
elif choice == "➕ קבלת תיקון / לקוח חדש":
    st.title("📝 טופס קבלת אופניים ותיקון חדש")
    st.caption("הזן את כל הפרטים במקום אחד - הלקוח, האופניים והבעיה")

    if "success_msg" in st.session_state:
        st.success(st.session_state["success_msg"])
        del st.session_state["success_msg"]

    conn = get_connection()

    saved_models = pd.read_sql_query("SELECT brand_model_name FROM bike_models ORDER BY brand_model_name ASC", conn)["brand_model_name"].tolist()
    brands_dropdown = ["➕ להקליד חברה/דגם חדשים שלא ברשימה"] + saved_models

    existing_customers = pd.read_sql_query("SELECT id, name, phone FROM customers ORDER BY name ASC", conn)

    is_existing = st.checkbox("👤 הלקוח כבר רשום במערכת?")

    customer_id = None
    c_name = ""
    c_phone = ""

    if is_existing and not existing_customers.empty:
        cust_options = {f"{r['name']} ({r['phone']})": r['id'] for _, r in existing_customers.iterrows()}
        selected_cust_label = st.selectbox("בחר לקוח קיים מהרשימה:", list(cust_options.keys()))
        customer_id = cust_options[selected_cust_label]

        df_cust_bikes = pd.read_sql_query(
            "SELECT id, brand_model, wheel_size, color FROM bikes WHERE customer_id = ?",
            conn,
            params=(customer_id,)
        )

        bike_choice_options = ["➕ הוסף זוג אופניים חדש ללקוח זה"]
        bike_map = {}
        for _, b_row in df_cust_bikes.iterrows():
            label = f"{b_row['brand_model']}"
            if b_row['color']:
                label += f" ({b_row['color']})"
            if b_row['wheel_size']:
                label += f" - {b_row['wheel_size']}"
            bike_choice_options.append(label)
            bike_map[label] = b_row['id']

        selected_existing_bike = st.selectbox("🚲 בחר אופניים שמורים של הלקוח:", bike_choice_options)
    else:
        selected_existing_bike = "➕ הוסף זוג אופניים חדש ללקוח זה"

    with st.form("quick_intake_form", clear_on_submit=True):
        if not is_existing:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                c_name = st.text_input("שם מלא של הלקוח *")
            with col_c2:
                c_phone = st.text_input("מספר טלפון *")

        st.markdown("---")
        
        if is_existing and selected_existing_bike != "➕ הוסף זוג אופניים חדש ללקוח זה":
            st.info(f"נבחרו האופניים השמורים: **{selected_existing_bike}**")
            selected_brand = None
            new_brand_model_input = ""
            wheel_size_select = None
            color_input = ""
            frame_serial = ""
        else:
            st.subheader("🚲 פרטי האופניים החדשים")
            selected_brand = st.selectbox("חברה / דגם מתוך הרשימה הקיימת:", brands_dropdown)

            new_brand_model_input = st.text_input(
                "הקלד חברה/דגם חדשים (או תוספת דגם):",
                placeholder="למשל: Yeti SB140 / Cannondale Topstone 1"
            )

            col_spec1, col_spec2, col_spec3 = st.columns(3)
            with col_spec1:
                wheel_size_options = ['29"', '27.5"', '26"', "700c", '24"', '20"', '16"', "אחר"]
                wheel_size_select = st.selectbox("גודל גלגל:", wheel_size_options)
            with col_spec2:
                color_input = st.text_input("צבע האופניים:", placeholder="למשל: שחור מט / אדום")
            with col_spec3:
                frame_serial = st.text_input("מספר שלדה (אופציונלי):")

        st.markdown("---")
        st.subheader("🛠️ הבעיה והטיפול")
        
        intake_date_input = st.date_input("📅 תאריך פתיחת טיפול:", value=date.today())
        
        issue_desc = st.text_area("תקלה מדווחת (על מה הלקוח מתלונן?) *", placeholder="למשל: רעשים מהפדלים, שרשרת קופצת...")
        work_done_initial = st.text_area("טיפול שנעשה בפועל (אופציונלי):", placeholder="הערות טכניות / עבודה שבוצעה...")
        est_price = st.number_input("הערכת מחיר ראשונית ב-₪:", min_value=0.0, step=10.0)

        submit_intake = st.form_submit_button("🚀 שמור ופתח כרטיס תיקון")

        if submit_intake:
            if not is_existing and (not c_name.strip() or not c_phone.strip()):
                st.error("חובה להזין שם לקוח ומספר טלפון!")
            elif not issue_desc.strip():
                st.error("חובה להזין את תיאור התקלה!")
            else:
                cursor = conn.cursor()

                if not is_existing:
                    cursor.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (c_name.strip(), c_phone.strip()))
                    customer_id = cursor.lastrowid

                if is_existing and selected_existing_bike != "➕ הוסף זוג אופניים חדש ללקוח זה":
                    bike_id = bike_map[selected_existing_bike]
                    final_bike_name = selected_existing_bike
                else:
                    final_bike_name = ""
                    if selected_brand == "➕ להקליד חברה/דגם חדשים שלא ברשימה":
                        final_bike_name = new_brand_model_input.strip() or "אופניים כלליים"
                    else:
                        if new_brand_model_input.strip():
                            final_bike_name = f"{selected_brand} {new_brand_model_input.strip()}"
                        else:
                            final_bike_name = selected_brand

                    cursor.execute(
                        "INSERT INTO bikes (customer_id, brand_model, wheel_size, color, frame_serial) VALUES (?, ?, ?, ?, ?)",
                        (customer_id, final_bike_name, wheel_size_select, color_input.strip(), frame_serial.strip())
                    )
                    bike_id = cursor.lastrowid

                    if final_bike_name and final_bike_name != "אופניים כלליים":
                        cursor.execute("INSERT OR IGNORE INTO bike_models (brand_model_name) VALUES (?)", (final_bike_name,))

                cursor.execute(
                    "INSERT INTO work_orders (bike_id, intake_date, issue_description, work_done, estimated_price, final_price, status) VALUES (?, ?, ?, ?, ?, ?, 'בטיפול')",
                    (bike_id, str(intake_date_input), issue_desc.strip(), work_done_initial.strip(), est_price, est_price)
                )

                conn.commit()
                st.session_state["success_msg"] = f"🎉 כרטיס נפתח בהצלחה עבור '{final_bike_name}'! הטופס מוכן ללקוח הבא."
                st.rerun()

    conn.close()


# ==========================================
# 3. ניהול לקוחות והיסטוריה
# ==========================================
elif choice == "👤 ניהול לקוחות והיסטוריה":
    st.title("👤 ניהול לקוחות והיסטוריית טיפולים")

    conn = get_connection()
    df_customers = pd.read_sql_query("SELECT * FROM customers", conn)

    if df_customers.empty:
        st.info("אין לקוחות במערכת עדיין.")
    else:
        customer_options = {f"{row['name']} | {row['phone']}": row['id'] for _, row in df_customers.iterrows()}
        selected_cust_label = st.selectbox("🔎 חפש / בחר לקוח:", list(customer_options.keys()))
        selected_cust_id = customer_options[selected_cust_label]

        cust_info = df_customers[df_customers['id'] == selected_cust_id].iloc[0]

        st.subheader(f"📄 כרטיס לקוח: {cust_info['name']}")
        col_c1, col_c2, col_del = st.columns([2, 2, 1])
        col_c1.write(f"📞 **טלפון:** {cust_info['phone']}")
        col_c2.write(f"📧 **אימייל:** {cust_info['email'] or 'לא הוזן'}")

        with col_del:
            if st.button("🗑️ מחק לקוח זה", key=f"del_cust_{selected_cust_id}"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM work_orders WHERE bike_id IN (SELECT id FROM bikes WHERE customer_id = ?)", (selected_cust_id,))
                cursor.execute("DELETE FROM bikes WHERE customer_id = ?", (selected_cust_id,))
                cursor.execute("DELETE FROM customers WHERE id = ?", (selected_cust_id,))
                conn.commit()
                st.warning(f"הלקוח {cust_info['name']} וכל הנתונים המשויכים נמחקו בהצלחה!")
                st.rerun()

        st.markdown("---")
        st.subheader(f"🚲 אופניים הרשומים על שם {cust_info['name']}")
        df_cust_bikes_all = pd.read_sql_query(
            "SELECT brand_model AS דגם, wheel_size AS גודל_גלגל, color AS צבע, frame_serial AS מספר_שלדה FROM bikes WHERE customer_id = ?",
            conn,
            params=(selected_cust_id,)
        )
        if not df_cust_bikes_all.empty:
            st.dataframe(df_cust_bikes_all, use_container_width=True)
        else:
            st.info("אין אופניים רשומים ללקוח זה.")

        st.markdown("---")
        st.subheader(f"📜 היסטוריית תיקונים עבור {cust_info['name']}")

        df_history = pd.read_sql_query("""
            SELECT 
                wo.id AS מס_כרטיס,
                wo.intake_date AS תאריך_פתיחת_טיפול,
                wo.completed_date AS תאריך_סיום_טיפול,
                b.brand_model AS אופניים,
                b.wheel_size AS גודל_גלגל,
                b.color AS צבע,
                b.frame_serial AS מספר_שלדה,
                wo.issue_description AS תקלה_מדווחת,
                wo.work_done AS טיפול_שנעשה,
                wo.status AS סטטוס,
                wo.estimated_price AS מחיר_משוער,
                wo.final_price AS מחיר_סופי
            FROM work_orders wo
            JOIN bikes b ON wo.bike_id = b.id
            WHERE b.customer_id = ?
            ORDER BY wo.id DESC
        """, conn, params=(selected_cust_id,))

        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("ללקוח זה אין היסטוריית תיקונים עדיין.")

    conn.close()


# ==========================================
# 4. צ'אט עובדים פנימי
# ==========================================
elif choice == "💬 צ'אט עובדים פנימי":
    st.title("💬 לוח הודעות ותקשורת צוות")

    conn = get_connection()

    col_chat1, col_chat2 = st.columns([1, 2])

    with col_chat1:
        st.subheader("✍️ כתיבת הודעה חדשה")
        with st.form("staff_msg_form"):
            sender = st.text_input("שם העובד/שולח")
            message = st.text_area("תוכן ההודעה")
            send_btn = st.form_submit_button("שלח הודעה")

            if send_btn and sender and message:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO staff_messages (sender_name, message, status) VALUES (?, ?, 'פתוח')", (sender, message))
                conn.commit()
                st.success("ההודעה נשלחה בהצלחה!")
                st.rerun()

    with col_chat2:
        st.subheader("📢 מעקב הודעות צוות")

        show_filter = st.radio("סינון הודעות:", ["הצג הודעות פתוחות בלבד", "הצג את כל ההודעות (כולל שטופלו)"], horizontal=True)

        if show_filter == "הצג הודעות פתוחות בלבד":
            df_msgs = pd.read_sql_query("SELECT id, sender_name, message, status, created_at FROM staff_messages WHERE status = 'פתוח' ORDER BY id DESC", conn)
        else:
            df_msgs = pd.read_sql_query("SELECT id, sender_name, message, status, created_at FROM staff_messages ORDER BY id DESC", conn)

        if not df_msgs.empty:
            for _, r in df_msgs.iterrows():
                status_icon = "🟢" if r['status'] == 'טופל' else "🔴"
                msg_title = f"{status_icon} הודעה #{r['id']} מאת {r['sender_name']}"

                with st.expander(msg_title):
                    st.write(f"**תאריך:** {r['created_at']}")
                    st.write(f"**תוכן:** {r['message']}")

                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if r['status'] == 'פתוח' and st.button("✅ סמן כטופל", key=f"resolve_{r['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE staff_messages SET status = 'טופל' WHERE id = ?", (r['id'],))
                            conn.commit()
                            st.rerun()
                    with c_btn2:
                        if r['status'] == 'טופל' and st.button("🔄 פתח מחדש", key=f"reopen_{r['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE staff_messages SET status = 'פתוח' WHERE id = ?", (r['id'],))
                            conn.commit()
                            st.rerun()
        else:
            st.info("אין הודעות להצגה כרגע.")

    conn.close()
