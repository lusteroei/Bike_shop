import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, date
import urllib.parse
import datetime as dt_module
import os
import shutil

DB_FILE = "bike_shop.db"
BACKUP_DIR = "backups"

# אתחול שעות הגיבוי בברירת מחדל במידה ולא הוגדרו עדיין ב-session_state
if "backup_hours" not in st.session_state:
    st.session_state["backup_hours"] = [12, 19]


def auto_backup_db():
    """יוצר גיבוי אוטומטי של מסד הנתונים בשעות שנבחרו על ידי המשתמש"""
    if os.path.exists(DB_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        now = datetime.now()
        current_hour = now.hour
        today_str = now.strftime("%Y-%m-%d")

        active_hours = st.session_state.get("backup_hours", [12, 19])

        for target_hour in active_hours:
            if current_hour >= target_hour:
                backup_label = f"{today_str}_{target_hour:02d}00"
                backup_filename = f"bike_shop_auto_{backup_label}.db"
                backup_path = os.path.join(BACKUP_DIR, backup_filename)

                if not os.path.exists(backup_path):
                    try:
                        shutil.copy(DB_FILE, backup_path)
                    except Exception:
                        pass


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    auto_backup_db()

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

    cursor.execute("PRAGMA table_info(customers)")
    cust_columns = [col[1] for col in cursor.fetchall()]
    if "email" not in cust_columns:
        cursor.execute("ALTER TABLE customers ADD COLUMN email TEXT")
    if "notes" not in cust_columns:
        cursor.execute("ALTER TABLE customers ADD COLUMN notes TEXT")

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
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_name TEXT NOT NULL,
            price REAL DEFAULT 0.0,
            notes TEXT
        )
    """)

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

conn_chk = get_connection()
try:
    unread_df = pd.read_sql_query("SELECT COUNT(*) AS cnt FROM staff_messages WHERE status = 'פתוח'", conn_chk)
    open_msgs_count = int(unread_df['cnt'].iloc[0]) if not unread_df.empty else 0
except Exception:
    open_msgs_count = 0
conn_chk.close()

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 חיפוש מהיר בסדנה")
search_query = st.sidebar.text_input("חפש לפי שם, טלפון או #כרטיס:", placeholder="הקלד לחיפוש מהיר...")

chat_menu_label = "💬 צ'אט עובדים פנימי"
if open_msgs_count > 0:
    chat_menu_label = f"💬 צ'אט עובדים פנימי 🔴 ({open_msgs_count})"

menu = [
    "🏠 דף ראשי - תיקונים פתוחים",
    "➕ קבלת תיקון / לקוח חדש",
    "👤 ניהול לקוחות והיסטוריה",
    "📦 מחירון חלפים ועבודות",
    chat_menu_label
]
choice = st.sidebar.radio("תפריט ניווט", menu)


# ==========================================
# 1. דף ראשי - תיקונים פתוחים
# ==========================================
if choice == "🏠 דף ראשי - תיקונים פתוחים":
    st.title("📋 לוח תיקונים פעילים בסדנה")
    st.caption("מציג את כל התיקונים הדורשים טיפול")

    conn = get_connection()

    df_parts_avail = pd.read_sql_query("SELECT id, part_name, price FROM inventory ORDER BY part_name ASC", conn)
    parts_dict = {}
    if not df_parts_avail.empty:
        for _, p_row in df_parts_avail.iterrows():
            parts_dict[f"{p_row['part_name']} (₪{p_row['price']})"] = p_row

    if search_query.strip():
        q_pattern = f"%{search_query.strip()}%"
        df_raw = pd.read_sql_query("""
            SELECT 
                wo.id AS ticket_id,
                c.id AS customer_id,
                c.name AS cust_name,
                c.phone AS cust_phone,
                b.id AS bike_id,
                b.brand_model AS bike_model,
                b.wheel_size AS wheel_size,
                b.color AS color,
                wo.status AS raw_status,
                wo.issue_description AS raw_issue,
                wo.work_done AS raw_work_done,
                wo.estimated_price AS est_price,
                wo.final_price AS final_price,
                wo.intake_date AS intake_date,
                wo.completed_date AS completed_date
            FROM work_orders wo
            JOIN bikes b ON wo.bike_id = b.id
            JOIN customers c ON b.customer_id = c.id
            WHERE c.name LIKE ? OR c.phone LIKE ? OR wo.id LIKE ? OR b.brand_model LIKE ?
            ORDER BY wo.id DESC
        """, conn, params=(q_pattern, q_pattern, q_pattern, q_pattern))
        st.info(f"תוצאות חיפוש עבור: '{search_query.strip()}'")
    else:
        df_raw = pd.read_sql_query("""
            SELECT 
                wo.id AS ticket_id,
                c.id AS customer_id,
                c.name AS cust_name,
                c.phone AS cust_phone,
                b.id AS bike_id,
                b.brand_model AS bike_model,
                b.wheel_size AS wheel_size,
                b.color AS color,
                wo.status AS raw_status,
                wo.issue_description AS raw_issue,
                wo.work_done AS raw_work_done,
                wo.estimated_price AS est_price,
                wo.final_price AS final_price,
                wo.intake_date AS intake_date,
                wo.completed_date AS completed_date
            FROM work_orders wo
            JOIN bikes b ON wo.bike_id = b.id
            JOIN customers c ON b.customer_id = c.id
            WHERE wo.status IN ('בטיפול', 'ממתין לחלקים', 'מוכן לאיסוף')
            ORDER BY wo.id DESC
        """, conn)

    in_service_count = len(df_raw[df_raw['raw_status'] == 'בטיפול']) if not df_raw.empty else 0
    waiting_parts_count = len(df_raw[df_raw['raw_status'] == 'ממתין לחלקים']) if not df_raw.empty else 0
    ready_count = len(df_raw[df_raw['raw_status'] == 'מוכן לאיסוף']) if not df_raw.empty else 0

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🔧 בטיפול פעיל", in_service_count)
    col_m2.metric("📦 ממתין לחלקים", waiting_parts_count)
    col_m3.metric("✅ מוכן לאיסוף", ready_count)

    st.markdown("---")

    filter_choice = st.radio(
        "🔎 סינון מהיר לפי סטטוס:",
        ["הצג הכל", "🔧 בטיפול פעיל בלבד", "📦 ממתין לחלקים בלבד", "✅ מוכן לאיסוף בלבד"],
        horizontal=True
    )

    if not df_raw.empty:
        if filter_choice == "🔧 בטיפול פעיל בלבד":
            df_raw = df_raw[df_raw['raw_status'] == 'בטיפול']
        elif filter_choice == "📦 ממתין לחלקים בלבד":
            df_raw = df_raw[df_raw['raw_status'] == 'ממתין לחלקים']
        elif filter_choice == "✅ מוכן לאיסוף בלבד":
            df_raw = df_raw[df_raw['raw_status'] == 'מוכן לאיסוף']

    st.markdown("---")

    if not df_raw.empty:
        st.subheader("🛠️ כרטיסי תיקון פעילים")

        for _, row in df_raw.iterrows():
            wo_id = row['ticket_id']
            details_str = f"{row['bike_model']}"
            if row['color']:
                details_str += f" | צבע: {row['color']}"
            if row['wheel_size']:
                details_str += f" | גלגל: {row['wheel_size']}"

            title_str = f"🔧 כרטיס #{wo_id} | {row['cust_name']} ({row['cust_phone']}) - {details_str} | סטטוס: {row['raw_status']}"
            with st.expander(title_str):
                col_info, col_status = st.columns([2, 1])

                with col_info:
                    st.write(f"🛠️ **תקלה מדווחת (מהלקוח):** {row['raw_issue']}")
                    st.write(f"⚙️ **טיפול שנעשה בפועל:** {row['raw_work_done'] or 'טרם הוזן'}")
                    st.write(f"💰 **מחיר משוער בקבלה:** ₪{row['est_price'] or 0}")

                    st.markdown("---")
                    st.markdown("📱 **שליחת הודעת וואטסאפ ללקוח:**")
                    
                    clean_phone = ''.join(filter(str.isdigit, str(row['cust_phone'])))
                    if clean_phone.startswith('0'):
                        clean_phone = '972' + clean_phone[1:]

                    wa_template = st.selectbox(
                        "בחר תבנית הודעה:",
                        [
                            "🎉 האופניים מוכנים לאיסוף",
                            "⚠️ דרוש אישור הצעת מחיר / חלק",
                            "📦 עדכון: ממתין לחלקים",
                            "💬 הודעה מותאמת אישית"
                        ],
                        key=f"wa_tpl_{wo_id}"
                    )

                    if wa_template == "🎉 האופניים מוכנים לאיסוף":
                        msg_text = f"שלום {row['cust_name']}, האופניים שלך ({row['bike_model']}) מוכנים בסדנה! מוזמן לבוא לאסוף. 🚲"
                    elif wa_template == "⚠️ דרוש אישור הצעת מחיר / חלק":
                        msg_text = f"שלום {row['cust_name']}, לגבי הטיפול באופניים ({row['bike_model']}): נדרשת עבודה / חלק נוסף. נשמח ליצור איתנו קשר לאישור הצעת המחיר. 🚲"
                    elif wa_template == "📦 עדכון: ממתין לחלקים":
                        msg_text = f"שלום {row['cust_name']}, עדכון קצר לגבי האופניים שלך ({row['bike_model']}): הטיפול התחיל ואנו ממתינים להגעת חלק רלוונטי. נעדכן ברגע שיהיה מוכן! 🚲"
                    else:
                        msg_text = st.text_input("הקלד הודעה מותאמת אישית:", value=f"שלום {row['cust_name']}, לגבי האופניים ({row['bike_model']}): ", key=f"custom_wa_{wo_id}")

                    encoded_msg = urllib.parse.quote(msg_text)
                    st.markdown(f"👉 [לחץ כאן לשליחת ההודעה בוואטסאפ](https://wa.me/{clean_phone}?text={encoded_msg})", unsafe_allow_html=True)

                    st.markdown("---")
                    
                    st.markdown("📦 **הוספת פריט מהמחירון לטיפול:**")
                    if parts_dict:
                        with st.form(key=f"add_part_form_{wo_id}"):
                            selected_part_label = st.selectbox("בחר חלק/עבודה מהמחירון:", ["-- בחר פריט --"] + list(parts_dict.keys()), key=f"part_select_{wo_id}")
                            btn_add_part = st.form_submit_button("➕ הוסף פריט לתיאור הטיפול")
                            
                            if btn_add_part:
                                if selected_part_label != "-- בחר פריט --":
                                    part_obj = parts_dict[selected_part_label]
                                    p_name = part_obj['part_name']
                                    p_price = part_obj['price']

                                    existing_work = row['raw_work_done'] or ""
                                    if existing_work.strip():
                                        new_work_text = f"{existing_work}\n• {p_name} (₪{p_price})"
                                    else:
                                        new_work_text = f"• {p_name} (₪{p_price})"

                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "UPDATE work_orders SET work_done = ? WHERE id = ?",
                                        (new_work_text.strip(), wo_id)
                                    )
                                    conn.commit()
                                    st.success("הפריט נוסף לתיאור הטיפול בהצלחה!")
                                    st.rerun()
                                else:
                                    st.warning("נא לבחור פריט תקין מהרשימה.")
                    else:
                        st.info("אין פריטים במחירון כרגע. הוסף פריטים דרך טאב 'מחירון חלפים ועבודות'.")

                    st.markdown("---")
                    with st.expander("✏️ ערוך פרטי לקוח / אופניים בכרטיס זה"):
                        with st.form(key=f"edit_cust_bike_{wo_id}"):
                            edit_name = st.text_input("שם לקוח:", value=str(row['cust_name']))
                            edit_phone = st.text_input("מספר טלפון:", value=str(row['cust_phone']))
                            edit_model = st.text_input("דגם אופניים:", value=str(row['bike_model']))
                            edit_color = st.text_input("צבע:", value=str(row['color'] or ''))
                            edit_wheel = st.text_input("גודל גלגל:", value=str(row['wheel_size'] or ''))
                            
                            btn_save_details = st.form_submit_button("💾 עדכן פרטים")
                            if btn_save_details:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE customers SET name = ?, phone = ? WHERE id = ?",
                                    (edit_name.strip(), edit_phone.strip(), row['customer_id'])
                                )
                                cursor.execute(
                                    "UPDATE bikes SET brand_model = ?, color = ?, wheel_size = ? WHERE id = ?",
                                    (edit_model.strip(), edit_color.strip(), edit_wheel.strip(), row['bike_id'])
                                )
                                conn.commit()
                                st.success("הפרטים עודכנו בהצלחה!")
                                st.rerun()

                with col_status:
                    st.markdown("**עדכון פרטי הטיפול, תאריכים וסטטוס:**")
                    
                    status_options = ["בטיפול", "ממתין לחלקים", "מוכן לאיסוף", "הושלם ונאסף", "בוטל"]
                    current_idx = status_options.index(row['raw_status']) if row['raw_status'] in status_options else 0

                    if f"status_{wo_id}" not in st.session_state:
                        st.session_state[f"status_{wo_id}"] = row['raw_status']
                    if f"work_done_{wo_id}" not in st.session_state:
                        st.session_state[f"work_done_{wo_id}"] = row['raw_work_done'] or ""
                    if f"price_{wo_id}" not in st.session_state:
                        init_price = float(row['final_price'] or 0.0)
                        if init_price == 0.0 and row['est_price']:
                            init_price = float(row['est_price'])
                        st.session_state[f"price_{wo_id}"] = init_price

                    new_status = st.selectbox(
                        "סטטוס:",
                        status_options,
                        index=current_idx,
                        key=f"status_{wo_id}"
                    )

                    try:
                        parsed_intake = datetime.strptime(str(row['intake_date'])[:10], "%Y-%m-%d").date()
                    except Exception:
                        parsed_intake = date.today()

                    new_intake_date = st.date_input(
                        "📅 תאריך פתיחת טיפול:",
                        value=parsed_intake,
                        key=f"intake_date_{wo_id}"
                    )

                    parsed_completed = None
                    if row['completed_date']:
                        try:
                            parsed_completed = datetime.strptime(str(row['completed_date'])[:10], "%Y-%m-%d").date()
                        except Exception:
                            parsed_completed = None

                    auto_comp_default = True if parsed_completed else (True if new_status in ["מוכן לאיסוף", "הושלם ונאסף"] else False)

                    has_completed_date = st.checkbox(
                        "הזן תאריך סיום טיפול",
                        value=auto_comp_default,
                        key=f"has_comp_{wo_id}"
                    )

                    new_completed_date_str = None
                    if has_completed_date:
                        comp_val = parsed_completed if parsed_completed else date.today()
                        new_comp_date = st.date_input(
                            "🏁 תאריך סיום טיפול:",
                            value=comp_val,
                            key=f"comp_date_{wo_id}"
                        )
                        new_completed_date_str = str(new_comp_date)

                    new_work_done = st.text_area(
                        "טיפול שנעשה בפועל:",
                        key=f"work_done_{wo_id}",
                        placeholder="רשום אילו חלקים הוחלפו / איזה תיקון בוצע..."
                    )

                    new_final_price = st.number_input(
                        "מחיר סופי (₪):",
                        min_value=0.0,
                        step=10.0,
                        key=f"price_{wo_id}"
                    )

                    st.markdown(" ")
                    btn_save = st.button("💾 שמור שינויים", key=f"btn_save_{wo_id}")
                    if btn_save:
                        cursor = conn.cursor()
                        
                        final_completed_str = new_completed_date_str
                        if new_status in ["מוכן לאיסוף", "הושלם ונאסף"] and not final_completed_str:
                            final_completed_str = str(date.today())

                        cursor.execute(
                            "UPDATE work_orders SET status = ?, intake_date = ?, completed_date = ?, work_done = ?, final_price = ? WHERE id = ?",
                            (new_status, str(new_intake_date), final_completed_str, new_work_done.strip(), new_final_price, wo_id)
                        )
                        conn.commit()
                        st.success(f"כרטיס #{wo_id} עודכן בהצלחה!")
                        st.rerun()

                    if st.button("🗑️ מחק תיקון", key=f"btn_delete_wo_{wo_id}"):
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM work_orders WHERE id = ?", (wo_id,))
                        conn.commit()
                        st.warning(f"כרטיס תיקון #{wo_id} נמחק!")
                        st.rerun()
    else:
        st.info("אין תיקונים תואמים להצגה לפי הסינון הנבחר. 🎉")

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
        
        with st.expander("✏️ ערוך פרטי לקוח (שם, טלפון, אימייל והערות)"):
            with st.form(key=f"edit_customer_profile_{selected_cust_id}"):
                up_name = st.text_input("שם מלא:", value=str(cust_info['name']))
                up_phone = st.text_input("טלפון:", value=str(cust_info['phone']))
                up_email = st.text_input("אימייל:", value=str(cust_info.get('email') or ''))
                up_notes = st.text_area("הערות על הלקוח:", value=str(cust_info.get('notes') or ''))

                if st.form_submit_button("💾 שמור שינויי לקוח"):
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE customers SET name = ?, phone = ?, email = ?, notes = ? WHERE id = ?",
                        (up_name.strip(), up_phone.strip(), up_email.strip(), up_notes.strip(), selected_cust_id)
                    )
                    conn.commit()
                    st.success("פרטי הלקוח עודכנו בהצלחה במערכת!")
                    st.rerun()

        col_c1, col_c2, col_del = st.columns([2, 2, 1])
        col_c1.write(f"📞 **טלפון:** {cust_info['phone']}")
        col_c2.write(f"📧 **אימייל:** {cust_info.get('email') or 'לא הוזן'}")

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
# 4. מחירון חלפים ועבודות
# ==========================================
elif choice == "📦 מחירון חלפים ועבודות":
    st.title("📦 מחירון חלפים ותעריפי עבודה")
    st.caption("ניהול רשימת החלקים והשירותים להוספה מהירה לכרטיסי התיקון")

    conn = get_connection()

    with st.expander("➕ הוסף חלק או שירות חדש למחירון"):
        with st.form("add_inventory_form", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                inv_name = st.text_input("שם החלק או העבודה *", placeholder="למשל: פנימית 29, כיוון הילוכים, שרשרת 12")
            with col_i2:
                inv_price = st.number_input("מחיר (₪) *", min_value=0.0, step=5.0)
            
            inv_notes = st.text_input("הערות (אופציונלי):", placeholder="יצרן, ספק או פרטים נוספים...")

            submit_inv = st.form_submit_button("שמור במחירון")
            if submit_inv:
                if not inv_name.strip():
                    st.error("חובה להזין את שם החלק או העבודה!")
                else:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO inventory (part_name, price, notes) VALUES (?, ?, ?)",
                        (inv_name.strip(), inv_price, inv_notes.strip())
                    )
                    conn.commit()
                    st.success(f"הפריט '{inv_name}' נוסף למחירון בהצלחה!")
                    st.rerun()

    st.markdown("---")

    df_inv = pd.read_sql_query("SELECT id, part_name AS שם_פריט, price AS מחיר, notes AS הערות FROM inventory ORDER BY part_name ASC", conn)

    if not df_inv.empty:
        st.subheader("📋 רשימת פריטים קיימים במחירון")

        for _, inv_row in df_inv.iterrows():
            i_id = inv_row['id']
            i_name = inv_row['שם_פריט']
            i_price = inv_row['מחיר']
            i_notes = inv_row['הערות']

            with st.expander(f"🔩 {i_name} — ₪{i_price}"):
                with st.form(key=f"edit_inv_{i_id}"):
                    e_name = st.text_input("שם הפריט:", value=str(i_name))
                    e_price = st.number_input("מחיר (₪):", min_value=0.0, value=float(i_price), step=5.0)
                    e_notes = st.text_input("הערות:", value=str(i_notes or ''))

                    if st.form_submit_button("💾 שמור שינויים במחירון"):
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE inventory SET part_name = ?, price = ?, notes = ? WHERE id = ?",
                            (e_name.strip(), e_price, e_notes.strip(), i_id)
                        )
                        conn.commit()
                        st.success("המחירון עודכן בהצלחה!")
                        st.rerun()

                if st.button("🗑️ מחק פריט מהמחירון", key=f"del_inv_{i_id}"):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM inventory WHERE id = ?", (i_id,))
                    conn.commit()
                    st.warning(f"הפריט '{i_name}' נמחק מהמחירון!")
                    st.rerun()
    else:
        st.info("אין עדיין פריטים במחירון. השתמש בטופס למעלה כדי להתחיל להוסיף.")

    conn.close()


# ==========================================
# 5. צ'אט עובדים פנימי
# ==========================================
elif choice.startswith("💬 צ'אט עובדים פנימי"):
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

# --- הגדרות וכפתורי גיבוי בתפריט הצד ---
st.sidebar.markdown("---")
st.sidebar.header("💾 גיבוי נתונים")

# תפריט מותאם אישית לבחירת שעות הגיבוי האוטומטי
with st.sidebar.expander("⚙️ הגדרות גיבוי אוטומטי"):
    hour_options = [f"{h:02d}:00" for h in range(24)]
    current_selected_hours = [f"{h:02d}:00" for h in st.session_state["backup_hours"]]

    selected_hour_strings = st.multiselect(
        "בחר שעות לגיבוי אוטומטי ביום:",
        options=hour_options,
        default=current_selected_hours
    )

    new_hours = sorted([int(h.split(":")[0]) for h in selected_hour_strings])
    if new_hours != st.session_state["backup_hours"]:
        st.session_state["backup_hours"] = new_hours
        st.success("שעות הגיבוי עודכנו!")

if os.path.exists(DB_FILE):
    with open(DB_FILE, "rb") as fp:
        now_str = dt_module.datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_name = f"bike_shop_backup_{now_str}.db"

        st.sidebar.download_button(
            label="📥 הורד גיבוי מסד נתונים ידני",
            data=fp,
            file_name=backup_name,
            mime="application/x-sqlite3",
            help="לחץ כאן כדי להוריד עותק גיבוי מעודכן של כל נתוני החנות",
        )
else:
    st.sidebar.warning("קובץ מסד הנתונים לא נמצא.")