import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd

# 建立/連線資料庫
conn = sqlite3.connect("overtime.db", check_same_thread=False)
c = conn.cursor()

# 建立使用者資料表
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        account TEXT UNIQUE,
        password TEXT
    )
''')
conn.commit()

# 建立加班紀錄資料表
c.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_date TEXT,
        start_time TEXT,
        end_time TEXT,
        total_hours REAL,
        overtime_hours REAL,
        rest_minutes INTEGER,
        account TEXT
    )
''')
conn.commit()

# Admin帳密
ADMIN_USER = st.secrets["admin"]["username"]
ADMIN_PWD = st.secrets["admin"]["password"]

# Session初始化
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "role" not in st.session_state:
    st.session_state["role"] = None
if "account" not in st.session_state:
    st.session_state["account"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None

# 登入畫面
if not st.session_state["logged_in"]:
    st.title("登入")
    acc = st.text_input("帳號")
    pwd = st.text_input("密碼", type="password")

    if st.button("登入"):
        # Admin
        if acc == ADMIN_USER and pwd == ADMIN_PWD:
            st.session_state["logged_in"] = True
            st.session_state["role"] = "admin"
            st.session_state["account"] = "admin"
            st.session_state["username"] = "Admin"
            st.experimental_rerun()
        else:
            # User
            c.execute("SELECT username FROM users WHERE account=? AND password=?", (acc, pwd))
            res = c.fetchone()
            if res:
                st.session_state["logged_in"] = True
                st.session_state["role"] = "user"
                st.session_state["account"] = acc
                st.session_state["username"] = res[0]
                st.experimental_rerun()
            else:
                st.error("帳號或密碼錯誤")

else:
    # 登出
    if st.sidebar.button("登出"):
        for k in ["logged_in", "role", "account", "username"]:
            st.session_state[k] = None
        st.experimental_rerun()

    st.sidebar.success(f"登入身份：{st.session_state['username']}")

    # 選單
    page = st.sidebar.radio("選擇功能", ["查看紀錄", "新增紀錄", "編輯/刪除紀錄"] + (["使用者管理"] if st.session_state["role"] == "admin" else []))

    if page == "查看紀錄":
        st.title("查看紀錄")
        selected_year = st.selectbox("年份", range(2022, datetime.now().year + 1), index=datetime.now().year - 2022)
        selected_month = st.selectbox("月份", range(1, 13), index=datetime.now().month -1)

        start_month = date(selected_year, selected_month, 1)
        if selected_month == 12:
            end_month = date(selected_year+1,1,1)
        else:
            end_month = date(selected_year, selected_month+1,1)

        if st.session_state["role"] == "admin":
            c.execute('''
                SELECT work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes, account
                FROM records
                WHERE work_date >= ? AND work_date < ?
                ORDER BY work_date
            ''',(start_month.isoformat(), end_month.isoformat()))
        else:
            c.execute('''
                SELECT work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes
                FROM records
                WHERE work_date >= ? AND work_date < ? AND account=?
                ORDER BY work_date
            ''',(start_month.isoformat(), end_month.isoformat(), st.session_state["account"]))

        rows = c.fetchall()
        if rows:
            if st.session_state["role"] == "admin":
                df = pd.DataFrame(rows, columns=["日期","上班","下班","總工時","加班","休息(分)","帳號"])
            else:
                df = pd.DataFrame(rows, columns=["日期","上班","下班","總工時","加班","休息(分)"])
            st.dataframe(df)
        else:
            st.info("此月份無資料")

    elif page == "新增紀錄":
        st.title("新增紀錄")
        work_date = st.date_input("日期")
        start_time = st.time_input("上班時間")
        end_time = st.time_input("下班時間")
        rest_minutes = st.number_input("休息分鐘",0,300,0)

        if st.button("儲存"):
            start_dt = datetime.combine(work_date, start_time)
            end_dt = datetime.combine(work_date, end_time)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            total_hours = round((end_dt-start_dt - timedelta(minutes=rest_minutes)).total_seconds()/3600,2)
            overtime_hours = max(0,total_hours -8)
            c.execute('''
                INSERT INTO records (work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes, account)
                VALUES (?,?,?,?,?,?,?)
            ''',(work_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), total_hours, overtime_hours, rest_minutes, st.session_state["account"]))
            conn.commit()
            st.success("已新增")
            st.experimental_rerun()

    elif page == "編輯/刪除紀錄":
        st.title("編輯或刪除紀錄")
        if st.session_state["role"] == "admin":
            c.execute('SELECT id, work_date, start_time, end_time, account FROM records ORDER BY work_date DESC')
        else:
            c.execute('SELECT id, work_date, start_time, end_time FROM records WHERE account=? ORDER BY work_date DESC',(st.session_state["account"],))
        rows = c.fetchall()
        if rows:
            if st.session_state["role"] == "admin":
                options = [f"{r[1]} {r[2]}-{r[3]} (帳號:{r[4]}) (ID:{r[0]})" for r in rows]
            else:
                options = [f"{r[1]} {r[2]}-{r[3]} (ID:{r[0]})" for r in rows]
            selected = st.selectbox("選擇紀錄", options)
            selected_id = int(selected.split("ID:")[1].strip(")"))

            action = st.radio("動作",["編輯","刪除"])

            if action=="編輯":
                c.execute('SELECT work_date, start_time, end_time, rest_minutes FROM records WHERE id=?',(selected_id,))
                rec = c.fetchone()
                new_date = st.date_input("日期", datetime.strptime(rec[0],"%Y-%m-%d").date())
                new_start = st.time_input("上班", datetime.strptime(rec[1],"%H:%M").time())
                new_end = st.time_input("下班", datetime.strptime(rec[2],"%H:%M").time())
                new_rest = st.number_input("休息分鐘",0,300,rec[3])
                if st.button("更新"):
                    start_dt = datetime.combine(new_date, new_start)
                    end_dt = datetime.combine(new_date, new_end)
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    total_hours = round((end_dt-start_dt - timedelta(minutes=new_rest)).total_seconds()/3600,2)
                    overtime_hours = max(0,total_hours -8)
                    c.execute('''
                        UPDATE records SET work_date=?, start_time=?, end_time=?, rest_minutes=?, total_hours=?, overtime_hours=? WHERE id=?
                    ''',(new_date.isoformat(), new_start.strftime("%H:%M"), new_end.strftime("%H:%M"), new_rest, total_hours, overtime_hours, selected_id))
                    conn.commit()
                    st.success("已更新")
                    st.experimental_rerun()
            else:
                if st.button("刪除確認"):
                    c.execute('DELETE FROM records WHERE id=?',(selected_id,))
                    conn.commit()
                    st.success("已刪除")
                    st.experimental_rerun()
        else:
            st.info("無資料")

    elif page == "使用者管理":
        st.title("使用者管理")
        st.subheader("新增使用者")
        uname = st.text_input("使用者名稱")
        uacc = st.text_input("帳號")
        upwd = st.text_input("密碼")
        if st.button("新增使用者"):
            try:
                c.execute("INSERT INTO users (username, account, password) VALUES (?,?,?)",(uname,uacc,upwd))
                conn.commit()
                st.success("已新增")
            except sqlite3.IntegrityError:
                st.error("帳號已存在")
        st.subheader("所有使用者")
        c.execute('SELECT id, username, account FROM users')
        ulist = c.fetchall()
        for u in ulist:
            st.write(f"ID:{u[0]} 名稱:{u[1]} 帳號:{u[2]}")

