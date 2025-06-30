import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date, time

# 建立/連接資料庫
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
    is_rest_day TEXT
)
''')
conn.commit()

# 加班費計算
def calculate_overtime_pay(hourly_rate, overtime_hours, is_rest_day):
    pay = 0
    if overtime_hours <=0:
        return 0
    if is_rest_day=="是":
        if overtime_hours <=2:
            pay = 2*hourly_rate*1.34
        elif overtime_hours<=4:
            pay = overtime_hours*hourly_rate*1.34
        elif overtime_hours<=8:
            pay = overtime_hours*hourly_rate*1.67
        else:
            pay = 8*hourly_rate*1.67 + (overtime_hours-8)*hourly_rate*2
    else:
        if overtime_hours<=2:
            pay = overtime_hours*hourly_rate*1.34
        elif overtime_hours<=4:
            pay = 2*hourly_rate*1.34 + (overtime_hours-2)*hourly_rate*1.67
        else:
            pay = 2*hourly_rate*1.34 +2*hourly_rate*1.67 +(overtime_hours-4)*hourly_rate*2
    return round(pay,0)

# 休息日判斷
def is_rest_day(work_date):
    work_dt = datetime.strptime(work_date, "%Y-%m-%d").date()
    weekday = work_dt.weekday()
    # 平日
    if weekday<5:
        return "否"
    # 若連續工作5天
    c.execute("SELECT work_date FROM records WHERE work_date < ? ORDER BY work_date DESC LIMIT 7", (work_date,))
    rows = c.fetchall()
    dates = [datetime.strptime(r[0],"%Y-%m-%d").date() for r in rows]
    dates_set = set(dates)
    count = 0
    for i in range(1,8):
        d = work_dt - timedelta(days=i)
        if d in dates_set:
            count+=1
        else:
            break
    if count>=5:
        return "是"
    return "是" if weekday>=5 else "否"

# 左側展開頁面
st.sidebar.title("功能選單")
show_add = st.sidebar.checkbox("➕ 新增上班紀錄", value=True)
show_summary = st.sidebar.checkbox("📊 查看統計報表", value=True)

# 新增紀錄
if show_add:
    with st.expander("➕ 新增上班紀錄", expanded=True):
        work_date = st.date_input("上班日期", date.today())
        start_time = st.time_input("上班時間", time(9,0))
        end_time = st.time_input("下班時間", time(18,0))
        
        # 計算工時
        dt_start = datetime.combine(work_date, start_time)
        dt_end = datetime.combine(work_date, end_time)
        if dt_end < dt_start:
            dt_end += timedelta(days=1)
        total_hours = round((dt_end - dt_start).total_seconds()/3600,2)
        overtime_hours = max(0,total_hours-8)
        
        # 判斷休息日
        rest_flag = is_rest_day(work_date.isoformat())
        st.write(f"總工時：{total_hours} 小時")
        st.write(f"加班時數：{overtime_hours} 小時")
        st.write(f"休息日：{'✅' if rest_flag=='是' else '❌'}")
        
        # 檢查是否重複
        c.execute("SELECT start_time,end_time FROM records WHERE work_date=?",(work_date.isoformat(),))
        rows = c.fetchall()
        overlap = False
        for r in rows:
            s1 = datetime.combine(work_date, datetime.strptime(r[0],"%H:%M").time())
            e1 = datetime.combine(work_date, datetime.strptime(r[1],"%H:%M").time())
            if e1<s1:
                e1+=timedelta(days=1)
            if not (dt_end<=s1 or dt_start>=e1):
                overlap = True
                break
        
        if overlap:
            st.error("⚠️ 時間與現有紀錄重疊，請檢查！")
        elif st.button("新增紀錄"):
            c.execute("INSERT INTO records (work_date,start_time,end_time,total_hours,overtime_hours,is_rest_day) VALUES(?,?,?,?,?,?)",
                (work_date.isoformat(),start_time.strftime("%H:%M"),end_time.strftime("%H:%M"),total_hours,overtime_hours,rest_flag))
            conn.commit()
            st.success("✅ 已新增紀錄")

# 統計報表
if show_summary:
    with st.expander("📊 查看統計報表", expanded=True):
        year = st.number_input("年份", min_value=2000, max_value=2100, value=date.today().year)
        month = st.number_input("月份", min_value=1, max_value=12, value=date.today().month)
        hourly_rate = st.number_input("每小時薪資", min_value=0,value=200)
        
        start_month = date(year,month,1).strftime("%Y-%m-%d")
        end_month = (date(year+1,1,1) if month==12 else date(year,month+1,1)).strftime("%Y-%m-%d")

        
        c.execute("""SELECT id, work_date, start_time, end_time, total_hours, overtime_hours, is_rest_day
        FROM records WHERE work_date >= ? AND work_date < ? ORDER BY work_date
        """, (start_month, end_month))
        rows = c.fetchall()
        
        if rows:
            df = pd.DataFrame(rows, columns=["ID","日期","上班","下班","工時","加班","休息日"])
            st.dataframe(df)
            total_ot = df["加班"].sum()
            total_pay = df.apply(lambda r: calculate_overtime_pay(hourly_rate,r["加班"],r["休息日"]),axis=1).sum()
            st.write(f"本月加班總時數：{total_ot} 小時")
            st.write(f"本月加班費：{total_pay} 元")
            
            # 匯出Excel
            if st.button("匯出Excel"):
                filename = f"加班統計_{year}_{month}.xlsx"
                df.to_excel(filename,index=False)
                st.success(f"已匯出：{filename}")
            
            # 刪除
            del_id = st.number_input("輸入要刪除的ID",min_value=1,step=1)
            if st.button("刪除此筆資料"):
                c.execute("DELETE FROM records WHERE id=?",(del_id,))
                conn.commit()
                st.success("已刪除資料")
        else:
            st.info("本月份尚無紀錄")
