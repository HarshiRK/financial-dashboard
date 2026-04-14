import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Finance Dashboard", layout="wide")

def clean_to_float(value):
    """Forcefully removes Dr, Cr, currency symbols, and commas."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    s = str(value).upper()
    is_credit = "CR" in s or "-" in s or "(" in s
    s = re.sub(r'[^0-9.]', '', s)
    try:
        num = float(s)
        return -num if is_credit else num
    except:
        return 0.0

def process_universal(file):
    df = pd.read_csv(file, header=None)
    
    # 1. Find Header Row
    header_idx = None
    for i, row in df.iterrows():
        row_str = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
        if any(key in row_str for key in ["particulars", "account", "description"]):
            header_idx = i
            break
            
    if header_idx is None:
        st.error("Could not find 'Particulars' or 'Account' header.")
        return None

    header_row = df.iloc[header_idx]
    data_rows = df.iloc[header_idx + 1:]
    
    # 2. Map Columns
    target_cols = []
    for i, col_name in enumerate(header_row):
        name = str(col_name).lower()
        if any(k in name for k in ["balance", "closing", "debit", "credit"]):
            # Look up for a month name
            month = "Total/Current"
            for r in range(header_idx):
                cell = str(df.iloc[r, i])
                if any(m in cell for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]):
                    month = cell.strip().replace('[','').replace(']','')
                    break
            target_cols.append({"idx": i, "type": name, "month": month})

    if not target_cols:
        st.error("No Balance or Debit/Credit columns detected.")
        return None

    # 3. Build Data
    results = []
    unique_months = list(dict.fromkeys([c['month'] for c in target_cols])) # Maintains order
    
    for m in unique_months:
        m_cols = [c for c in target_cols if c['month'] == m]
        temp_df = pd.DataFrame()
        temp_df['Account'] = data_rows.iloc[:, 0].astype(str).str.strip()
        temp_df['Month'] = m
        
        # Logic: Prefer Closing/Balance, otherwise Debit-Credit
        bal_col = next((c for c in m_cols if "balance" in c['type'] or "closing" in c['type']), None)
        if bal_col:
            temp_df['Amount'] = data_rows.iloc[:, bal_col['idx']].apply(clean_to_float)
        else:
            deb = next((c for c in m_cols if "debit" in c['type']), None)
            cre = next((c for c in m_cols if "credit" in c['type']), None)
            d_val = data_rows.iloc[:, deb['idx']].apply(clean_to_float) if deb else 0
            c_val = data_rows.iloc[:, cre['idx']].apply(clean_to_float) if cre else 0
            temp_df['Amount'] = d_val - c_val
            
        temp_df = temp_df[temp_df['Account'] != "nan"]
        results.append(temp_df)

    final = pd.concat(results).reset_index(drop=True)
    
    # Simple Categorization
    def categorize(acc):
        acc = acc.lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'asset', 'inventory']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'liab', 'equity', 'capital', 'reserve']): return 'Liabilities/Equity'
        if any(x in acc for x in ['sale', 'revenue', 'income']): return 'Revenue'
        return 'Expenses'
    
    final['Category'] = final['Account'].apply(categorize)
    return final

# --- UI ---
st.title("📊 Universal Trial Balance Dashboard")

uploaded_file = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded_file:
    data = process_universal(uploaded_file)
    if data is not None:
        # Check if Month exists to prevent KeyError
        if 'Month' in data.columns:
            m_list = data['Month'].unique()
            selected_month = st.sidebar.selectbox("Select Month", m_list)
            df_view = data[data['Month'] == selected_month]
        else:
            df_view = data

        # Metrics
        assets = df_view[df_view['Category'] == 'Assets']['Amount'].sum()
        liabilities = df_view[df_view['Category'] == 'Liabilities/Equity']['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"₹{abs(assets):,.2f}")
        c2.metric("Liabilities & Equity", f"₹{abs(liabilities):,.2f}")
        c3.metric("Status", "Balanced ✅" if abs(round(assets + liabilities, 2)) < 10 else "Check Data ⚠️")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Financial Mix")
            fig = px.pie(df_view, values=df_view['Amount'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("Account List")
            st.dataframe(df_view[['Account', 'Category', 'Amount']], use_container_width=True)
