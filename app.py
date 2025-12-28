import streamlit as st
import pandas as pd
import itertools
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# =======================
# 0. 設定與 CSS 美化 (解決畫面不清、對比度問題)
# =======================
st.set_page_config(page_title="專業循環賽系統", layout="wide", page_icon="🏸")

# 強制亮色高對比風格 + 手機優化 CSS
st.markdown("""
<style>
    /* 全局字體放大 */
    html, body, [class*="css"] {
        font-family: 'Helvetica', 'Arial', sans-serif;
        color: #000000; /* 極黑字體 */
    }
    
    /* 標題樣式 */
    h1, h2, h3 {
        color: #0d47a1 !important; /* 深藍色標題，專業感 */
        font-weight: 800 !important;
    }

    /* 輸入框優化：放大點擊區域，方便手指點按 */
    div[data-testid="stNumberInput"] input {
        font-size: 24px !important;
        height: 50px !important;
        background-color: #f0f2f6;
        border: 2px solid #ccc;
        border-radius: 10px;
        text-align: center;
    }
    div[data-testid="stNumberInput"] input:focus {
        border-color: #0d47a1;
        background-color: #ffffff;
        transform: scale(1.02); /* 點擊時微微放大 */
        transition: all 0.2s;
    }

    /* 表格優化：高對比、大字體 */
    .dataframe { 
        font-size: 18px !important; 
        text-align: center !important;
    }
    th {
        background-color: #0d47a1 !important;
        color: white !important;
        font-size: 20px !important;
        text-align: center !important;
    }
    
    /* 按鈕優化 */
    button[kind="primary"] {
        height: 60px;
        font-size: 20px !important;
        background-color: #00c853 !important; /* 鮮綠色儲存按鈕 */
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# =======================
# 1. Google Sheets 連線設定
# =======================
# ⚠️ 如果還沒設定 API，請把 USE_GOOGLE_SHEETS 改成 False 來測試介面
USE_GOOGLE_SHEETS = False 
SHEET_URL = "您的_GOOGLE_SHEET_網址" # 記得填入

def load_data_from_sheet():
    if not USE_GOOGLE_SHEETS:
        # 本機測試模式：如果沒有 Session 資料就初始化
        if 'matches_data' not in st.session_state:
             # 預設範例資料
            return pd.DataFrame([
                {"隊伍 A": "張三/李四", "隊伍 B": "王五/趙六", "A 得分": None, "B 得分": None},
                {"隊伍 A": "Team A", "隊伍 B": "Team B", "A 得分": None, "B 得分": None}
            ])
        return st.session_state.matches_data

    # 連線 Google Sheets (需要 secrets)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 這裡假設您把 json 內容放在 st.secrets 裡，或者直接讀取檔案
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data_to_sheet(df):
    if not USE_GOOGLE_SHEETS:
        st.session_state.matches_data = df
        st.success("✅ 資料已暫存 (本機模式)")
        return

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    # 將 DataFrame 寫回
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    st.toast("☁️ 資料已同步至 Google Sheets！", icon="✅")

# =======================
# 2. 邏輯運算 (排名計算)
# =======================
def calculate_rankings(df_matches):
    # 取得所有隊伍
    players = list(set(df_matches["隊伍 A"]).union(set(df_matches["隊伍 B"])))
    stats = {p: {"勝": 0, "敗": 0, "得失分": 0, "總得分": 0} for p in players}
    
    for index, row in df_matches.iterrows():
        # 確保數據是數字 (處理 Google Sheets 可能讀回來的字串)
        s1 = pd.to_numeric(row["A 得分"], errors='coerce')
        s2 = pd.to_numeric(row["B 得分"], errors='coerce')
        
        if pd.notna(s1) and pd.notna(s2):
            p1, p2 = row["隊伍 A"], row["隊伍 B"]
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

    df_rank = pd.DataFrame.from_dict(stats, orient='index')
    df_rank.index.name = "隊伍"
    df_rank.reset_index(inplace=True)
    # 排名邏輯：勝 > 得失分 > 總得分
    df_rank = df_rank.sort_values(by=["勝", "得失分", "總得分"], ascending=False)
    df_rank.reset_index(drop=True, inplace=True)
    df_rank.index += 1
    return df_rank

# =======================
# 3. 主介面設計
# =======================

# 讀取資料
df_schedule = load_data_from_sheet()
players_list = list(set(df_schedule["隊伍 A"]).union(set(df_schedule["隊伍 B"])))

# --- 標題區 ---
st.title("🏆 羽球循環賽計分板")

# --- 分頁設計 (手機版最好用 Tab 分流資訊) ---
tab1, tab2, tab3 = st.tabs(["📱 輸入成績", "📊 目前排名", "⚙️ 設定賽程"])

# --- Tab 1: 手機優化輸入介面 ---
with tab1:
    st.info("💡 點選下方場次，直接輸入比分")
    
    # 1. 選擇場次 (Dropdown 比表格好點)
    match_options = [f"{row['隊伍 A']} vs {row['隊伍 B']}" for i, row in df_schedule.iterrows()]
    selected_match_str = st.selectbox("選擇對戰組合", match_options)
    
    # 找出選到的那一列 index
    selected_index = match_options.index(selected_match_str)
    row_data = df_schedule.iloc[selected_index]

    # 2. 大卡片輸入區 (使用 Form 避免一直重整)
    with st.form("score_input_form"):
        col_a, col_vs, col_b = st.columns([2, 0.5, 2])
        
        with col_a:
            st.markdown(f"### {row_data['隊伍 A']}")
            # 預設值處理
            val_a = row_data['A 得分'] if pd.notna(row_data['A 得分']) else 0
            score_a = st.number_input("A 得分", min_value=0, max_value=100, value=int(val_a), key="input_a")
        
        with col_vs:
            st.markdown("<br><h2 style='text-align:center'>:</h2>", unsafe_allow_html=True)

        with col_b:
            st.markdown(f"### {row_data['隊伍 B']}")
            val_b = row_data['B 得分'] if pd.notna(row_data['B 得分']) else 0
            score_b = st.number_input("B 得分", min_value=0, max_value=100, value=int(val_b), key="input_b")

        submitted = st.form_submit_button("💾 儲存成績", type="primary", use_container_width=True)

        if submitted:
            # 更新 DataFrame
            df_schedule.at[selected_index, 'A 得分'] = score_a
            df_schedule.at[selected_index, 'B 得分'] = score_b
            # 存檔
            save_data_to_sheet(df_schedule)
            st.success(f"已更新：{row_data['隊伍 A']} {score_a} : {score_b} {row_data['隊伍 B']}")

# --- Tab 2: 高對比排名表 ---
with tab2:
    rank_df = calculate_rankings(df_schedule)
    
    # 特別標示前兩名 (金/銀色背景)
    def highlight_rank(s):
        if s.name == 0: # 第一名
            return ['background-color: #ffd700; color: black; font-weight: bold'] * len(s)
        elif s.name == 1: # 第二名
            return ['background-color: #c0c0c0; color: black; font-weight: bold'] * len(s)
        else:
            return ['background-color: white; color: black'] * len(s)

    st.markdown("### 🏅 即時戰績榜")
    st.dataframe(
        rank_df.style.apply(highlight_rank, axis=1).format(precision=0), 
        use_container_width=True,
        height=400 # 固定高度避免手機滑太久
    )

# --- Tab 3: 設定 (重新分組) ---
with tab3:
    with st.expander("重置賽程名單 (慎用)"):
        raw_text = st.text_area("輸入新名單 (一行一隊)", "張三/李四\n王五/趙六\nTeam A")
        if st.button("🔄 產生新賽程"):
            new_players = [p.strip() for p in raw_text.split('\n') if p.strip()]
            if len(new_players) < 2:
                st.error("至少兩隊")
            else:
                matches = []
                for p1, p2 in itertools.combinations(new_players, 2):
                    matches.append({"隊伍 A": p1, "隊伍 B": p2, "A 得分": None, "B 得分": None})
                
                new_df = pd.DataFrame(matches)
                save_data_to_sheet(new_df)
                st.success("新賽程已建立！請切換分頁輸入成績。")
