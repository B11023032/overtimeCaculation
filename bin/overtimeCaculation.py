import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
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
    is_rest_day INTEGER
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
        elif overtime_hours <=4:
            pay = overtime_hours * hourly_rate *1.34
        elif overtime_hours <=8:
            pay = overtime_hours * hourly_rate *1.67
        else:
            pay = 8*hourly_rate*1.67 + (overtime_hours-8)*hourly_rate*2
    else:
        if overtime_hours <=2:
            pay = overtime_hours*hourly_rate*1.34
        elif overtime_hours <=4:
            pay = 2*hourly_rate*1.34 + (overtime_hours-2)*hourly_rate*1.67
        else:
            pay = 2*hourly_rate*1.34 + 2*hourly_rate*1.67 + (overtime_hours-4)*hourly_rate*2
    return round(pay,0)

# 自動判斷是否休息日
def is_rest_day(work_date):
    c.execute("SELECT DISTINCT work_date FROM records ORDER BY work_date")
    dates = [datetime.strptime(r[0], "%Y-%m-%d").date() for r in c.fetchall()]
    dates = sorted(set(dates + [work_date]))
    # 找到當天在列表的索引
    idx = dates.index(work_date)
    # 往前檢查5天
    count=0
    for i in range(idx-1, idx-6, -1):
        if i<0:
            break
        delta = (dates[i+1]-dates[i]).days
        if delta==1:
            count+=1
        else:
            break
    return count>=5

# Tab選單
tabs = st.tabs(["新增/編輯紀錄", "每月統計"])
page = st.sidebar.link_button("回首頁", "/")

with tabs[0]:
    st.header("新增或編輯上班紀錄")

    work_date = st.date_input("選擇上班日期", date.today())

    # 輸入時間(可手動)
    start_time_str = st.text_input("上班時間 (格式 HH:MM)", "09:00")
    end_time_str = st.text_input("下班時間 (格式 HH:MM)", "18:00")

    # 檢查格式
    def parse_time(s):
        try:
            return datetime.strptime(s.strip(), "%H:%M").time()
        except:
            return None

    t_start = parse_time(start_time_str)
    t_end = parse_time(end_time_str)

    if t_start and t_end:
        dt_start = datetime.combine(work_date, t_start)
        dt_end = datetime.combine(work_date, t_end)
        if dt_end < dt_start:
            dt_end += timedelta(days=1)
        total_hours = round((dt_end - dt_start).total_seconds()/3600,2)
        overtime_hours = max(0, total_hours-8)
        rest_flag = is_rest_day(work_date)
        st.write(f"總工時：{total_hours} 小時")
        st.write(f"加班時數：{overtime_hours} 小時")
        st.write(f"是否休息日：{'是' if rest_flag else '否'}")

        # 檢查時間重疊
        c.execute('''
            SELECT id, work_date, start_time, end_time FROM records WHERE work_date=?
        ''',(work_date.isoformat(),))
        overlaps=[]
        for r in c.fetchall():
            existing_start = datetime.combine(work_date, parse_time(r[2]))
            existing_end = datetime.combine(work_date, parse_time(r[3]))
            if existing_end < existing_start:
                existing_end+=timedelta(days=1)
            if not (dt_end<=existing_start or dt_start>=existing_end):
                overlaps.append(r)
        if overlaps:
            st.warning("⚠️ 時間區間與以下紀錄重疊：")
            for r in overlaps:
                st.caption(f"{r[2]} ~ {r[3]}")
        else:
            if st.button("新增紀錄"):
                c.execute('''
                    INSERT INTO records (work_date,start_time,end_time,total_hours,overtime_hours,is_rest_day)
                    VALUES (?,?,?,?,?,?)
                ''',(work_date.isoformat(),start_time_str,end_time_str,total_hours,overtime_hours,int(rest_flag)))
                conn.commit()
                st.toast("✅ 已新增")

    else:
        st.warning("請輸入正確的時間格式 (HH:MM)")

    st.divider()

    # 顯示本月所有紀錄供編輯刪除
    st.subheader("現有紀錄")
    this_month = date.today().strftime("%Y-%m")
    c.execute("SELECT * FROM records WHERE work_date LIKE ? ORDER BY work_date", (this_month+"%",))
    rows=c.fetchall()
    if rows:
        df=pd.DataFrame(rows,columns=["ID","日期","上班","下班","總工時","加班時數","休息日"])
        st.dataframe(df)
        edit_id = st.number_input("輸入要刪除的ID",min_value=1,step=1)
        if st.button("刪除指定ID"):
            c.execute("DELETE FROM records WHERE id=?",(edit_id,))
            conn.commit()
            st.toast("已刪除")
    else:
        st.info("本月尚無紀錄")

with tabs[1]:
    st.header("每月統計與加班費")

    year = st.number_input("年份", min_value=2000, max_value=2100, value=date.today().year)
    month = st.number_input("月份", min_value=1, max_value=12, value=date.today().month)
    hourly_rate = st.number_input("每小時薪資", min_value=0, value=200)

    start_month = date(int(year), int(month),1)
    if month==12:
        end_month = date(int(year)+1,1,1)
    else:
        end_month = date(int(year), int(month)+1,1)

    c.execute('''
        SELECT work_date,start_time,end_time,total_hours,overtime_hours,is_rest_day
        FROM records
        WHERE work_date>=? AND work_date<?
        ORDER BY work_date
    ''',(start_month.isoformat(),end_month.isoformat()))
    rows=c.fetchall()

    if rows:
        df=pd.DataFrame(rows,columns=["日期","上班","下班","總工時","加班時數","休息日"])
        st.dataframe(df)
        total_overtime=sum(r[4] for r in rows)
        total_pay=sum(calculate_overtime_pay(hourly_rate,r[4],r[5]) for r in rows)
        st.write(f"本月加班總時數：{total_overtime} 小時")
        st.write(f"本月加班費總額：{total_pay} 元")
    else:
        st.info("本月份尚無紀錄")
