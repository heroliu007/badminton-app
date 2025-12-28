import streamlit as st
import pandas as pd
import itertools
import graphviz
import gspread
from google.oauth2 import service_account

# =======================
# 設定與 CSS 優化
# =======================
st.set_page_config(page_title="雲端同步循環賽系統", layout="wide", page_icon="🏸")

st.markdown("""
<style>
    .stDataFrame { margin: 0 auto; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    h3 { color: #2c3e50; }
    .stButton button { width: 100%; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# =======================
# 0. Google Sheets 連線設定
# =======================

@st.cache_resource
def get_gsheet_connection():
    """建立與 Google Sheets 的連線 (快取以避免重複連線)"""
    try:
        # 讀取 Secrets
        key_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets["spreadsheets"]["sheet_url"]
        
        # 驗證
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_info(key_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # 開啟試算表
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0) # 讀取第一個工作表
        return worksheet
    except Exception as e:
        st.error(f"連線失敗：{e}")
        return None

def load_data_from_sheet(worksheet):
    """從試算表讀取資料轉為 DataFrame"""
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        # 確保得分欄位是數字，處理空字串
        cols = ["A 得分", "B 得分"]
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        st.warning("試算表可能是空的或格式有誤，將建立新賽程。")
        return pd.DataFrame()

def save_data_to_sheet(worksheet, df):
    """將 DataFrame 寫回試算表"""
    try:
        # 將 NaN 轉為 None (JSON 寫入時需要) 或空字串
        df_save = df.copy()
        df_save = df_save.fillna("")
        
        # 1. 清空舊資料
        worksheet.clear()
        
        # 2. 寫入標題與內容
        # update 方法需要 list of lists
        data_to_write = [df_save.columns.values.tolist()] + df_save.values.tolist()
        worksheet.update(data_to_write)
        st.toast("✅ 資料已成功同步至 Google Sheets！", icon="☁️")
    except Exception as e:
        st.error(f"寫入失敗：{e}")

# =======================
# 1. 核心邏輯區
# =======================

def generate_schedule(players):
    """產生單循環賽程的初始資料結構"""
    matches = []
    # 確保不會自己打自己，且不重複
    for p1, p2 in itertools.combinations(players, 2):
        matches.append({
            "隊伍 A": p1,
            "隊伍 B": p2,
            "A 得分": None,
            "B 得分": None
        })
    return pd.DataFrame(matches)

def calculate_rankings(df_matches, players):
    """計算積分與排名"""
    stats = {p: {"勝": 0, "敗": 0, "得失分": 0, "總得分": 0} for p in players}
    
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2) and s1 != "" and s2 != "":
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
    df_rank = df_rank.sort_values(by=["勝", "得失分", "總得分"], ascending=False)
    df_rank.reset_index(drop=True, inplace=True)
    df_rank.index += 1 
    return df_rank

def create_cross_table(df_matches, players):
    """產生交叉勝敗表"""
    cross_df = pd.DataFrame("-", index=players, columns=players)
    for p in players: cross_df.at[p, p] = "❌"

    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        if pd.notna(s1) and pd.notna(s2) and s1 != "" and s2 != "":
            cross_df.at[p1, p2] = f"{int(s1)}:{int(s2)}"
            cross_df.at[p2, p1] = f"{int(s2)}:{int(s1)}"
    return cross_df

def draw_network(df_matches):
    """繪製勝敗關係圖"""
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR', layout='circo')
    graph.attr('node', shape='ellipse', style='filled', color='lightblue')
    
    has_result = False
    for index, row in df_matches.iterrows():
        p1 = row["隊伍 A"]
        p2 = row["隊伍 B"]
        s1 = row["A 得分"]
        s2 = row["B 得分"]
        
        graph.node(p1)
        graph.node(p2)

        if pd.notna(s1) and pd.notna(s2) and s1 != "" and s2 != "":
            has_result = True
            if s1 > s2:
                graph.edge(p1, p2, label=f"{int(s1)}:{int(s2)}", color='green')
            elif s2 > s1:
                graph.edge(p2, p1, label=f"{int(s2)}:{int(s1)}", color='green')
    
    if not has_result:
        graph.attr(label='(輸入比分並儲存後，箭頭會出現)')
        
    return graph

# =======================
# 2. 網頁介面區 (UI)
# =======================

st.title("🏸 雲端循環賽系統 (Google Sheets)")

# 初始化連線
worksheet = get_gsheet_connection()

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 這裡的邏輯：如果 Sheet 是空的，顯示預設名單；如果有資料，從資料中提取名單
    st.info("💡 系統會優先讀取 Google Sheet 的資料。若要重新開始，請按下方重置按鈕。")
    
    default_players_text = "張三/李四\n王五/趙六\nTeam A\nTeam B\nTeam C"
    raw_text = st.text_area("參賽名單 (用於重置賽程)", default_players_text, height=150)
    input_players_list = [p.strip() for p in raw_text.split('\n') if p.strip()]

    if st.button("🚨 重置並覆蓋 Sheet"):
        confirm_reset = True 
        # 實際重置邏輯
        new_df = generate_schedule(input_players_list)
        save_data_to_sheet(worksheet, new_df)
        st.session_state["local_df"] = new_df
        st.rerun()

# --- 資料載入邏輯 ---
# 每次畫面刷新，我們優先檢查 session state，如果沒有才去讀 Sheet
if "local_df" not in st.session_state:
    with st.spinner('正在從 Google Sheets 讀取資料...'):
        df_cloud = load_data_from_sheet(worksheet)
        
    if df_cloud.empty:
        # 如果雲端是空的，就用側邊欄名單建立新的
        st.session_state["local_df"] = generate_schedule(input_players_list)
    else:
        st.session_state["local_df"] = df_cloud

# 確保我們有目前的參賽者名單 (從 DataFrame 提取，以防雲端資料跟側邊欄不一致)
current_df = st.session_state["local_df"]
if not current_df.empty:
    players_in_data = list(set(current_df["隊伍 A"]).union(set(current_df["隊伍 B"])))
else:
    players_in_data = input_players_list

# --- 主畫面 ---
if len(players_in_data) < 2:
    st.error("目前無賽程資料，請檢查名單或雲端連線。")
else:
    # 第一區：輸入
    st.subheader("1️⃣ 輸入比分")
    
    col_edit, col_save = st.columns([4, 1])
    
    with col_edit:
        edited_df = st.data_editor(
            st.session_state["local_df"],
            column_config={
                "A 得分": st.column_config.NumberColumn(min_value=0, max_value=100),
                "B 得分": st.column_config.NumberColumn(min_value=0, max_value=100),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="data_editor_key" 
        )

    with col_save:
        st.write(" ") # 排版用
        st.write(" ")
        # 儲存按鈕
        if st.button("💾 上傳雲端", type="primary"):
            save_data_to_sheet(worksheet, edited_df)
            st.session_state["local_df"] = edited_df # 更新本地狀態

    # 計算資料
    rank_df = calculate_rankings(edited_df, players_in_data)
    cross_df = create_cross_table(edited_df, players_in_data)

    # 第二區：表格與圖表
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["📊 排名與統計圖", "🕸️ 勝敗關係圖", "🔢 交叉勝敗表"])

    with tab1:
        col_rank, col_chart = st.columns([1, 1.5])
        with col_rank:
            st.markdown("#### 目前排名")
            st.dataframe(rank_df.style.highlight_max(axis=0, color="#d1e7dd"), use_container_width=True)
        with col_chart:
            st.markdown("#### 得失分統計")
            st.bar_chart(rank_df.set_index("隊伍")["得失分"], color="#3498db")

    with tab2:
        st.markdown("#### 🔄 對戰食物鏈")
        st.caption("箭頭表示：贏家 -> 輸家")
        try:
            st.graphviz_chart(draw_network(edited_df))
        except Exception:
            st.warning("圖表產生中...")

    with tab3:
        st.markdown("#### ❌ 傳統交叉表")
        st.dataframe(cross_df, use_container_width=True)
