import streamlit as st
import pandas as pd
import random

# =======================
# 1. 核心邏輯區 (Logic)
# =======================
def generate_schedule(players):
    """產生單循環賽程"""
    random.shuffle(players)
    schedule = []
    n = len(players)
    if n < 2: return []
    
    # 簡單的循環賽演算法
    for i in range(n):
        for j in range(i + 1, n):
            schedule.append({
                "隊伍1": players[i],
                "隊伍2": players[j],
                "比分": " vs " # 預留欄位
            })
    return schedule

def simulate_rankings(players):
    """(測試用) 隨機模擬排名"""
    data = []
    for p in players:
        wins = random.randint(0, len(players)-1)
        diff = random.randint(-20, 50)
        data.append({"隊伍": p, "勝場": wins, "得失分": diff})
    
    # 排序：先比勝場，再比得失分
    df = pd.DataFrame(data)
    df = df.sort_values(by=["勝場", "得失分"], ascending=[False, False])
    df.reset_index(drop=True, inplace=True)
    df.index += 1 # 排名從 1 開始
    return df

# =======================
# 2. 網頁介面區 (UI)
# =======================
st.set_page_config(page_title="循環賽產生器", page_icon="🏆")

st.title("🏆 羽球/網球 循環賽排程系統")
st.markdown("輸入名單後，自動產生對戰表與 Excel/HTML 下載。")

# --- 側邊欄：輸入設定 ---
st.sidebar.header("⚙️ 比賽設定")
level_name = st.sidebar.text_input("輸入組別名稱", "公開組 (Level A)")
qualify_num = st.sidebar.number_input("錄取前幾名?", min_value=1, value=2)

st.sidebar.subheader("📝 參賽名單")
default_players = "張三/李四\n王五/趙六\n陳七/林八\nTeam A/Team B\nTeam C/Team D"
raw_text = st.sidebar.text_area("一行一隊 (雙打請用斜線隔開)", default_players, height=200)

# 處理輸入名單
players_list = [p.strip() for p in raw_text.split('\n') if p.strip()]

# --- 主畫面：操作與顯示 ---
if len(players_list) < 2:
    st.warning("👈 請在左側輸入至少 2 隊參賽隊伍")
else:
    st.info(f"目前參賽隊伍數：{len(players_list)} 隊")

    # 按鈕區
    col1, col2 = st.columns(2)
    with col1:
        run_btn = st.button("🚀 產生賽程表", type="primary")
    with col2:
        sim_btn = st.button("🎲 模擬排名結果 (測試邏輯)")

    st.divider()

    # 顯示 1: 賽程表
    if run_btn:
        st.subheader(f"📅 {level_name} - 對戰賽程表")
        matches = generate_schedule(players_list)
        df_schedule = pd.DataFrame(matches)
        
        # 顯示美觀的表格
        st.table(df_schedule)
        
        # 提供下載按鈕 (CSV)
        csv = df_schedule.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載賽程表 (Excel/CSV)",
            data=csv,
            file_name=f'{level_name}_schedule.csv',
            mime='text/csv',
        )

    # 顯示 2: 排名模擬
    if sim_btn:
        st.subheader("📊 排名邏輯預覽 (勝場 > 得失分)")
        df_rank = simulate_rankings(players_list)
        
        # 標示晉級者 (Highlight)
        def highlight_qualified(s):
            is_qualified = s.name <= qualify_num
            return ['background-color: #d4edda' if is_qualified else '' for _ in s]

        st.dataframe(df_rank.style.apply(highlight_qualified, axis=1))
        st.caption(f"綠色底色表示前 {qualify_num} 名晉級")
