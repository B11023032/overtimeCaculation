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
    overtime_hours REAL,
    rest_minutes INTEGER
)
''')
conn.commit()
try:
    c.execute("ALTER TABLE records ADD COLUMN rest_minutes INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    # 欄位已存在就略過
    pass

# 加班費計算
def calculate_overtime_pay(hourly_rate, overtime_hours, is_rest_day, work_time):
    pay = 0
    if overtime_hours <= 0 and not is_rest_day:
        return 0
    if is_rest_day:
        if work_time <= 2:
            pay = work_time * hourly_rate * 1.3333
        elif work_time <= 8:
            pay = (2 * hourly_rate * 1.3333) + (work_time - 2) * hourly_rate * 1.6666
        else:
            pay = (2 * hourly_rate * 1.3333) + (6 * hourly_rate * 1.6666) + (work_time - 8) * hourly_rate * 2.6666
    else:
        if overtime_hours <= 2:
            pay = overtime_hours * hourly_rate * 1.3333
        elif overtime_hours <= 4:
            pay = 2 * hourly_rate * 1.3333 + (overtime_hours - 2) * hourly_rate * 1.6666
        else:
            pay = 2 * hourly_rate * 1.3333 + 2 * hourly_rate * 1.6666 + (overtime_hours - 4) * hourly_rate * 2
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
    selected_end = st.selectbox("選擇下班時間", time_options, index=time_options.index("20:20"))
    end_time = datetime.strptime(selected_end,"%H:%M").time()
    rest_minutes_options = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120]
    rest_minutes = st.selectbox("選擇休息時間(分鐘)", rest_minutes_options, index=rest_minutes_options.index(80))


    # 計算總工時
    dt_start = datetime.combine(work_date, start_time)
    dt_end = datetime.combine(work_date, end_time)
    if dt_end < dt_start:
        dt_end += timedelta(days=1)
    duration = dt_end - dt_start - timedelta(minutes=rest_minutes)  # 扣除休息時間
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
            c.execute(
                "INSERT INTO records (work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    work_date.isoformat(),
                    start_time.strftime("%H:%M"),
                    end_time.strftime("%H:%M"),
                    total_hours,
                    overtime_hours,
                    rest_minutes
                )
            )
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

        # 查詢當月範圍
        start_month = date(selected_year, selected_month, 1)
        if selected_month == 12:
            end_month = date(selected_year+1, 1, 1)
        else:
            end_month = date(selected_year, selected_month+1, 1)

        # 查詢所有資料（先依日期排序）
        c.execute('''
            SELECT work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes
            FROM records
            ORDER BY work_date
        ''')
        all_rows = c.fetchall()

        # 將所有紀錄轉成日期+標記用
        all_dates = []
        for r in all_rows:
            all_dates.append(datetime.strptime(r[0], "%Y-%m-%d").date())

        # 建立每個日期的是否休息日映射
        streak = 0
        last_date = None
        date_rest_map = {}
        for d in all_dates:
            if last_date and (d - last_date).days == 1:
                streak += 1
            else:
                streak = 1
            date_rest_map[d] = (streak >= 6)
            last_date = d

        # 查詢本月資料
        c.execute('''
            SELECT work_date, start_time, end_time, total_hours, overtime_hours, rest_minutes
            FROM records
            WHERE work_date >= ? AND work_date < ?
            ORDER BY work_date
        ''', (start_month.isoformat(), end_month.isoformat()))
        rows = c.fetchall()

        if rows:
            df = pd.DataFrame(rows, columns=["日期", "上班時間", "下班時間", "總工時", "加班時數", "休息時間(分鐘)"])

            total_overtime = 0
            total_pay = 0
            pay_list = []
            rest_day_flags = []

            for r in rows:
                this_date = datetime.strptime(r[0], "%Y-%m-%d").date()
                is_rest = date_rest_map.get(this_date, False)
                rest_day_flags.append(is_rest)                

                start_dt = datetime.strptime(r[1], "%H:%M")
                end_dt = datetime.strptime(r[2], "%H:%M")
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                duration = end_dt - start_dt - timedelta(minutes=r[5])
                work_hours = round(duration.total_seconds()/3600, 2)

                overtime = r[4]
                pay = calculate_overtime_pay(hourly_rate, overtime, is_rest, work_hours)
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
    c.execute('''
        CREATE TABLE records_temp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date TEXT,
            start_time TEXT,
            end_time TEXT,
            rest_minutes INTEGER,
            total_hours REAL,
            overtime_hours REAL
        )
        ''')

    c.execute('''
        INSERT INTO records_temp (work_date, start_time, end_time, rest_minutes, total_hours, overtime_hours)
        SELECT work_date, start_time, end_time, rest_minutes, total_hours, overtime_hours FROM records
    ''')

    c.execute('DROP TABLE records')
    c.execute('ALTER TABLE records_temp RENAME TO records')
    conn.commit()

    c.execute('SELECT id, work_date, start_time, end_time FROM records ORDER BY work_date DESC')
    rows = c.fetchall()
    if rows:
        options = [f"{r[1]} {r[2]}-{r[3]} (ID:{r[0]})" for r in rows]
        selected_idx = st.selectbox("選擇要編輯或刪除的紀錄", range(len(options)), format_func=lambda i: options[i])
        selected_id = rows[selected_idx][0]

        action = st.radio("動作", ["編輯", "刪除"])
        if action == "編輯":
            # 重新查詢這筆ID
            c.execute('SELECT work_date, start_time, end_time, rest_minutes FROM records WHERE id=?', (selected_id,))
            record = c.fetchone()

            new_date = st.date_input("日期", datetime.strptime(record[0], "%Y-%m-%d").date())
            new_start = st.selectbox("上班時間", time_options, index=time_options.index(record[1]))
            new_end = st.selectbox("下班時間", time_options, index=time_options.index(record[2]))
            rest_minutes_options = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120]
            new_rest = st.selectbox("休息時間(分鐘)", rest_minutes_options, index=rest_minutes_options.index(record[3]))


            if st.button("更新"):
                # 把字串轉成 datetime
                dt_start = datetime.combine(new_date, datetime.strptime(new_start, "%H:%M").time())
                dt_end = datetime.combine(new_date, datetime.strptime(new_end, "%H:%M").time())
                if dt_end < dt_start:
                    dt_end += timedelta(days=1)
                duration = dt_end - dt_start - timedelta(minutes=new_rest)
                total_hours = round(duration.total_seconds() / 3600, 2)
                overtime_hours = max(0, total_hours - 8)

                c.execute(
                    "UPDATE records SET work_date=?, start_time=?, end_time=?, rest_minutes=?, total_hours=?, overtime_hours=? WHERE id=?",
                    (
                        new_date.isoformat(),
                        new_start,
                        new_end,
                        new_rest,
                        total_hours,
                        overtime_hours,
                        selected_id
                    )
                )
                conn.commit()
                st.toast("更新完成")
                st.rerun()
        else:
            if st.button("刪除"):
                c.execute("DELETE FROM records WHERE id=?", (selected_id,))
                conn.commit()
                st.toast("已刪除")
                st.rerun()
    else:
        st.info("無任何紀錄")


#git add .
#git commit -m "Update overtime app"
#git push origin main

