import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date, time

# 建立/連線資料庫
conn = sqlite3.connect('overtime.db', check_same_thread=False)
c = conn.cursor()

# 建立表格（若不存在）
c.execute('''
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_date TEXT,
    start_time TEXT,
    end_time TEXT,
    total_hours REAL,
    overtime_hours REAL
)
''')
conn.commit()

# 加班費倍數 (平日加班)
def calculate_overtime_pay(hourly_rate, overtime_hours):
    pay = 0
    if overtime_hours <= 0:
        return 0
    if overtime_hours <= 2:
        pay = overtime_hours * hourly_rate * 1.34
    elif overtime_hours <= 4:
        pay = 2 * hourly_rate * 1.34 + (overtime_hours - 2) * hourly_rate * 1.67
    else:
        pay = 2 * hourly_rate * 1.34 + 2 * hourly_rate * 1.67 + (overtime_hours - 4) * hourly_rate * 2
    return round(pay, 0)

# 頁面選單
page = st.sidebar.selectbox("選擇頁面", ["新增上班紀錄", "查看每月統計"])

# 1️⃣ 新增上班紀錄
if page == "新增上班紀錄":
    st.title("新增上班紀錄")

    work_date = st.date_input("選擇上班日期", date.today())
    #start_time = st.time_input("上班時間", time(11,0))
    #end_time = st.time_input("下班時間", time(20,0))

    time_options = []
    for h in range(0,24):
        for m in range(0,60,1):  # 改成1分鐘
            time_options.append(f"{h:02d}:{m:02d}")

    selected_start = st.selectbox("選擇上班時間 (1分鐘間隔)", time_options, index=time_options.index("11:00"))
    start_time = datetime.strptime(selected_start,"%H:%M").time()
    selected_end = st.selectbox("選擇下班時間 (1分鐘間隔)", time_options, index=time_options.index("20:00"))
    end_time = datetime.strptime(selected_end,"%H:%M").time()


    # 計算總工時
    dt_start = datetime.combine(work_date, start_time)
    dt_end = datetime.combine(work_date, end_time)
    if dt_end < dt_start:
        dt_end += timedelta(days=1)
    duration = dt_end - dt_start
    total_hours = round(duration.total_seconds() / 3600, 2)
    overtime_hours = max(0, total_hours - 8)

    st.write(f"總工時：{total_hours} 小時")
    st.write(f"加班時數：{overtime_hours} 小時")

    if st.button("新增紀錄"):
        c.execute("INSERT INTO records (work_date, start_time, end_time, total_hours, overtime_hours) VALUES (?, ?, ?, ?, ?)",
                  (work_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), total_hours, overtime_hours))
        conn.commit()
        st.success("已新增紀錄！")

# 2️⃣ 查看每月統計
elif page == "查看每月統計":
    st.title("每月加班統計")

    year = st.number_input("年份", min_value=2000, max_value=2100, value=date.today().year)
    month = st.number_input("月份", min_value=1, max_value=12, value=date.today().month)
    hourly_rate = st.number_input("請輸入每小時薪資", min_value=0, value=200)

    # 查詢資料
    start_month = date(int(year), int(month), 1)
    if month == 12:
        end_month = date(int(year)+1, 1, 1)
    else:
        end_month = date(int(year), int(month)+1, 1)

    c.execute('''
        SELECT work_date, start_time, end_time, total_hours, overtime_hours
        FROM records
        WHERE work_date >= ? AND work_date < ?
        ORDER BY work_date
    ''', (start_month.isoformat(), end_month.isoformat()))
    rows = c.fetchall()

    if rows:
        # 顯示表格
        import pandas as pd
        df = pd.DataFrame(rows, columns=["日期", "上班時間", "下班時間", "總工時", "加班時數"])
        st.dataframe(df)

        # 統計總加班
        total_overtime = sum(r[4] for r in rows)
        total_pay = sum(calculate_overtime_pay(hourly_rate, r[4]) for r in rows)

        st.write(f"本月加班總時數：**{total_overtime} 小時**")
        st.write(f"本月加班費總額：**{total_pay} 元**")
    else:
        st.info("本月份尚無紀錄")

