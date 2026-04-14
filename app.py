import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Financial Dashboard", layout="wide")

def safe_float(value):
    """Prevents crashes by cleaning data and returning 0.0 if the cell is messy."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    try:
        s = str(value).upper()
        is_credit = any(x in s for x in ["CR", "-", "("])
        # Remove everything except numbers and decimals
        num_str = re.sub(r'[^0-9.]', '', s)
        if not num_str: return 0.0
        num = float(num_str)
        return -num if is_credit else num
    except:
        return 0.0

def process_data(file):
    try:
        df = pd.read_csv(file, header=None)
        
        # 1. Locate the Start of Data (Particulars)
        header_idx = None
        for i, row in df.iterrows():
            row_txt = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if "particulars" in row_txt or "account" in row_txt:
                header_idx = i
                break
        
        if header_idx is None:
            return None, "Could not find Account/Particulars column."

        # 2. Identify Valid Numeric Columns (Balance, Debit, Credit)
        header_row = df.iloc[header_idx]
        data_rows = df.iloc[header_idx + 1:]
        col_maps = []

        for i, col_val in enumerate(header_row):
            name = str(col_val).lower()
            if any(k in name for k in ["balance", "closing", "debit", "credit"]):
                # Search for month label in the rows above
                label = "Total"
                for r in range(max(0, header_idx-5), header_idx):
                    cell = str(df.iloc[r, i])
                    if any(m in cell for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]):
                        label = cell.strip().replace('[','').replace(']','')
                        break
                col_maps.append({"idx": i, "type": name, "month": label})

        if not col_maps:
            return None, "No numeric columns (Debit/Credit/Balance) found."

        # 3. Create Final Clean Table
        final_list = []
        months = list(dict.fromkeys([c['month'] for c in col_maps]))
        
        for m in months:
            m_cols = [c for c in col_maps if c['month'] == m]
            temp = pd.DataFrame()
            temp['Account'] = data_rows.iloc[:, 0].astype(str).str.strip()
            temp['Month'] = m
            
            # Math Logic
            bal_col = next((c for c in m_cols if "balance" in c['type'] or "closing" in c['type']), None)
            if bal_col:
                temp['Amount'] = data_rows.iloc[:, bal_col['idx']].apply(safe_float)
            else:
                deb = next((c for c in m_cols if "debit" in c['type']), None)
                cre = next((c for c in m_cols if "credit" in c['type']), None)
                d_val = data_rows.iloc[:, deb['idx']].apply(safe_float) if deb else 0
                c_val = data_rows.iloc[:, cre['idx']].apply(safe_float) if cre else 0
                temp['Amount'] = d_val - c_val
            
            # Remove empty account rows
            temp = temp[temp['Account'] != "nan"]
            final_list.append(temp)

        return pd.concat(final_list).reset_index(drop=True), None
        
    except Exception as e:
        return None, f"System Error: {str(e)}"

# --- UI ---
st.title("📊 Universal Trial Balance Dashboard")
st.write("Upload any CSV Trial Balance to get started.")

uploaded = st.sidebar.file_uploader("Choose CSV File", type="csv")

if uploaded:
    data, err = process_data(uploaded)
    
    if err:
        st.error(err)
    elif data is not None:
        # Category Logic
        def quick_cat(x):
            x = x.lower()
            if any(i in x for i in ['cash', 'bank', 'receivable', 'asset']): return 'Assets'
            if any(i in x for i in ['payable', 'loan', 'capital', 'equity']): return 'Liabilities'
            if any(i in x for i in ['sale', 'revenue', 'income']): return 'Revenue'
            return 'Expenses'
        
        data['Category'] = data['Account'].apply(quick_cat)
        
        # Month Filter
        m_opt = data['Month'].unique()
        sel_m = st.sidebar.selectbox("Select Period", m_opt)
        view = data[data['Month'] == sel_m]
        
        # Display Stats
        a_val = view[view['Category'] == 'Assets']['Amount'].sum()
        l_val = view[view['Category'] == 'Liabilities']['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"₹{abs(a_val):,.2f}")
        c2.metric("Total Liab/Equity", f"₹{abs(l_val):,.2f}")
        c3.metric("Status", "Balanced ✅" if abs(a_val + l_val) < 10 else "Difference ⚠️")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Financial Breakdown")
            fig = px.pie(view, values=view['Amount'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Account List")
            st.dataframe(view[['Account', 'Category', 'Amount']], height=400, use_container_width=True)
