import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date, time
import pandas as pd

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

# 加班費計算
def calculate_overtime_pay(hourly_rate, overtime_hours, is_rest_day):
    pay = 0
    if overtime_hours <= 0:
        return 0
    if is_rest_day:
        if overtime_hours <= 2:
            pay = 2 * hourly_rate * 1.34
        elif overtime_hours <= 4:
            pay = overtime_hours * hourly_rate * 1.34
        elif overtime_hours <= 8:
            pay = overtime_hours * hourly_rate * 1.67
        else:
            pay = 8 * hourly_rate * 1.67 + (overtime_hours - 8) * hourly_rate * 2
    else:
        if overtime_hours <= 2:
            pay = overtime_hours * hourly_rate * 1.34
        elif overtime_hours <= 4:
            pay = 2 * hourly_rate * 1.34 + (overtime_hours - 2) * hourly_rate * 1.67
        else:
            pay = 2 * hourly_rate * 1.34 + 2 * hourly_rate * 1.67 + (overtime_hours - 4) * hourly_rate * 2
    return round(pay, 0)

# 頁面選單
page = st.sidebar.selectbox("選擇頁面", ["新增上班紀錄", "查看每月統計", "編輯/刪除紀錄"])

# 時間選單
time_options = []
for h in range(0,24):
    for m in range(0,60,1):
        time_options.append(f"{h:02d}:{m:02d}")

# 1️⃣ 新增上班紀錄
if page == "新增上班紀錄":
    st.title("新增上班紀錄")

    work_date = st.date_input("選擇上班日期", date.today())
    selected_start = st.selectbox("選擇上班時間", time_options, index=time_options.index("11:00"))
    start_time = datetime.strptime(selected_start,"%H:%M").time()
    selected_end = st.selectbox("選擇下班時間", time_options, index=time_options.index("20:30"))
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

    # 防止時間重疊
    c.execute('''
        SELECT * FROM records WHERE work_date = ? AND (
            (? BETWEEN start_time AND end_time) OR
            (? BETWEEN start_time AND end_time)
        )
    ''', (
        work_date.isoformat(),
        start_time.strftime("%H:%M"),
        end_time.strftime("%H:%M")
    ))
    overlap = c.fetchone()

    if st.button("新增紀錄"):
        if overlap:
            st.warning("此日期已有重疊時間，請確認後再新增。")
        else:
            c.execute("INSERT INTO records (work_date, start_time, end_time, total_hours, overtime_hours) VALUES (?, ?, ?, ?, ?)",
                (work_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), total_hours, overtime_hours))
            conn.commit()
            st.toast("已新增紀錄！")

# 2️⃣ 查看每月統計
elif page == "查看每月統計":
    st.title("每月加班統計")

    year_options = list(range(2000, 2101))
    month_options = list(range(1, 13))
    selected_year = st.selectbox("選擇年份", year_options, index=year_options.index(date.today().year))
    selected_month = st.selectbox("選擇月份", month_options, index=month_options.index(date.today().month))
    base_salary_text = st.text_input("輸入底薪 (月薪)")

    if st.button("查詢"):
        try:
            base_salary = float(base_salary_text)
            hourly_rate = round(base_salary / (30 * 8), 2)
        except:
            st.error("請輸入正確數字")
            st.stop()

        # 查詢資料
        start_month = date(selected_year, selected_month, 1)
        if selected_month == 12:
            end_month = date(selected_year+1, 1, 1)
        else:
            end_month = date(selected_year, selected_month+1, 1)

        c.execute('''
            SELECT work_date, start_time, end_time, total_hours, overtime_hours
            FROM records
            WHERE work_date >= ? AND work_date < ?
            ORDER BY work_date
        ''', (start_month.isoformat(), end_month.isoformat()))
        rows = c.fetchall()

        if rows:
            df = pd.DataFrame(rows, columns=["日期", "上班時間", "下班時間", "總工時", "加班時數"])
            # 判斷是否休息日
            dates = [r[0] for r in rows]
            dates_dt = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
            rest_day_flags = []

            # 依日期排序
            dates_dt.sort()
            streak = 0
            last_date = None
            for d in dates_dt:
                if last_date and (d - last_date).days == 1:
                    streak += 1
                else:
                    streak = 1
                is_rest = streak >=5
                rest_day_flags.append(is_rest)
                last_date = d

            total_overtime = 0
            total_pay = 0
            pay_list = []

            for i, r in enumerate(rows):
                overtime = r[4]
                is_rest = rest_day_flags[i]
                pay = calculate_overtime_pay(hourly_rate, overtime, is_rest)
                pay_list.append(pay)
                total_overtime += overtime
                total_pay += pay

            df["是否休息日"] = ["是" if x else "否" for x in rest_day_flags]
            df["加班費"] = pay_list

            st.dataframe(df)
            st.write(f"本月加班總時數：**{total_overtime} 小時**")
            st.write(f"本月加班費總額：**{total_pay} 元**")
        else:
            st.info("本月份尚無紀錄")

# 3️⃣ 編輯/刪除紀錄
elif page == "編輯/刪除紀錄":
    st.title("編輯或刪除紀錄")
    c.execute('SELECT id, work_date, start_time, end_time FROM records ORDER BY work_date DESC')
    rows = c.fetchall()
    if rows:
        options = [f"{r[1]} {r[2]}-{r[3]} (ID:{r[0]})" for r in rows]
        selected = st.selectbox("選擇要編輯或刪除的紀錄", options)
        selected_id = int(selected.split("ID:")[1][:-1])

        action = st.radio("動作", ["編輯", "刪除"])
        if action == "編輯":
            new_date = st.date_input("日期", datetime.strptime(rows[0][1], "%Y-%m-%d").date())
            new_start = st.selectbox("上班時間", time_options, index=time_options.index(rows[0][2]))
            new_end = st.selectbox("下班時間", time_options, index=time_options.index(rows[0][3]))
            if st.button("更新"):
                c.execute("UPDATE records SET work_date=?, start_time=?, end_time=? WHERE id=?",
                    (new_date.isoformat(), new_start, new_end, selected_id))
                conn.commit()
                st.toast("更新完成")
        else:
            if st.button("刪除"):
                c.execute("DELETE FROM records WHERE id=?", (selected_id,))
                conn.commit()
                st.toast("已刪除")
    else:
        st.info("無任何紀錄")
