import streamlit as st
import pandas as pd
import random
import itertools

# =======================
# 設定與 CSS 優化
# =======================
st.set_page_config(page_title="互動式循環賽系統", layout="wide", page_icon="🏸")

# 讓表格置中與美化的 CSS
st.markdown("""
<style>
    .stDataFrame { margin: 0 auto; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# =======================
# 1. 核心邏輯區
# =======================

def generate_schedule(players):
    """產生單循環賽程的初始資料結構"""
    matches = []
    # 產生所有對戰組合 (Combinations)
    for p1, p2 in itertools.combinations(players, 2):
        matches.append({
            "隊伍 A": p1,
            "隊伍 B": p2,
            "A 得分": None, # 預設留空
            "B 得分": None
        })
    return pd.DataFrame(matches)

def calculate_rankings(df_matches, players):
    """根據輸入的成績，計算積分與排名"""
    stats = {p: {"勝": 0, "敗": 0, "得失分": 0, "總得分": 0} for p in players}
    
    # 遍歷每一場比賽
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        # 只有當雙方都有輸入分數時才計算
        if pd.notna(s1) and pd.notna(s2):
            stats[p1]["總得分"] += s1
            stats[p2]["總得分"] += s2
            stats[p1]["得失分"] += (s1 - s2)
            stats[p2]["得失分"] += (s2 - s1)
            
            if s1 > s2:
                stats[p1]["勝"] += 1
                stats[p2]["敗"] += 1
            elif s2 > s1:
                stats[p2]["勝"] += 1
                stats[p1]["敗"] += 1
            # 平手通常不計勝敗，或可自行定義規則

    # 轉成 DataFrame 並排序
    df_rank = pd.DataFrame.from_dict(stats, orient='index')
    df_rank.index.name = "隊伍"
    df_rank.reset_index(inplace=True)
    # 排序邏輯：勝場 > 得失分 > 總得分
    df_rank = df_rank.sort_values(by=["勝", "得失分", "總得分"], ascending=False)
    df_rank.reset_index(drop=True, inplace=True)
    df_rank.index += 1 # 排名從 1 開始
    return df_rank

def create_cross_table(df_matches, players):
    """產生交叉勝敗表 (四角形/五角形表格)"""
    # 建立一個 N x N 的空表格
    cross_df = pd.DataFrame("-", index=players, columns=players)
    
    # 對角線填滿灰色或 X
    for p in players:
        cross_df.at[p, p] = "❌"

    # 填入比分
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2):
            # 填入 P1 vs P2 的格子
            cross_df.at[p1, p2] = f"{int(s1)}:{int(s2)}"
            # 填入 P2 vs P1 的格子 (反轉)
            cross_df.at[p2, p1] = f"{int(s2)}:{int(s1)}"
        else:
            # 還沒打
            cross_df.at[p1, p2] = "未賽"
            cross_df.at[p2, p1] = "未賽"
            
    return cross_df

# =======================
# 2. 網頁介面區 (UI)
# =======================

st.title("🏸 循環賽：即時比分輸入系統")

# --- 側邊欄：設定與重置 ---
with st.sidebar:
    st.header("⚙️ 比賽設定")
    default_players = "張三/李四\n王五/趙六\nTeam A\nTeam B\nTeam C"
    raw_text = st.text_area("參賽名單 (一行一隊)", default_players, height=150)
    players_list = [p.strip() for p in raw_text.split('\n') if p.strip()]
    
    st.warning("⚠️ 注意：若重新整理網頁，輸入的成績會清空！(除非連結資料庫)")
    
    # 重置按鈕 logic
    if st.button("🔄 重新產生賽程 (清空比分)"):
        st.session_state.clear()

# --- 初始化 Session State (讓資料不會跑掉) ---
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = generate_schedule(players_list)

# 檢查名單是否有變動，若有則重置
if set(st.session_state.schedule_df["隊伍 A"].unique()).union(set(st.session_state.schedule_df["隊伍 B"].unique())) != set(players_list):
     st.session_state.schedule_df = generate_schedule(players_list)


# --- 主畫面 ---

if len(players_list) < 2:
    st.error("請輸入至少兩隊！")
else:
    # 1. 輸入區：互動式表格
    st.subheader("1️⃣ 輸入比分 (請直接修改表格)")
    st.caption("👇 在「A 得分」與「B 得分」欄位點兩下即可輸入數字")
    
    # 這是最關鍵的一行：st.data_editor
    edited_df = st.data_editor(
        st.session_state.schedule_df,
        column_config={
            "A 得分": st.column_config.NumberColumn(min_value=0, max_value=100, step=1),
            "B 得分": st.column_config.NumberColumn(min_value=0, max_value=100, step=1),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed" # 禁止使用者新增刪除列，只能改分數
    )

    # 2. 運算區：即時計算
    rank_df = calculate_rankings(edited_df, players_list)
    cross_df = create_cross_table(edited_df, players_list)

    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.subheader("2️⃣ 即時排名 (Rank)")
        # 標示前兩名
        def highlight_top2(s):
            return ['background-color: #d1e7dd' if s.name < 2 else '' for _ in s]
        
        st.dataframe(rank_df.style.apply(highlight_top2, axis=1), use_container_width=True)

    with col2:
        st.subheader("3️⃣ 交叉勝敗表 (Cross Table)")
        st.caption("這就是您說的四角/五角形賽制表")
        st.dataframe(cross_df, use_container_width=True)
