import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Financial Dashboard", layout="wide")

def clean_amount(v):
    """Universal number cleaner: handles 'Dr/Cr', currency, and formatting."""
    if pd.isna(v) or str(v).strip() == "": return 0.0
    s = str(v).upper().strip()
    is_credit = any(x in s for x in ["CR", "-", "("])
    s = re.sub(r'[^0-9.]', '', s)
    try:
        if s.count('.') > 1: # Fixes strings like 1.234.56
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        num = float(s) if s else 0.0
        return -num if is_credit else num
    except: return 0.0

def process_file(file):
    try:
        df = pd.read_csv(file, header=None)
        
        # 1. Locate the header row (contains 'Particulars' or 'Account')
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if any(k in row_str for k in ["particulars", "account"]):
                header_idx = i
                break
        
        if header_idx is None:
            return None, "System could not identify the 'Particulars' or 'Account' column."

        header_row = df.iloc[header_idx]
        data_rows = df.iloc[header_idx + 1:]
        all_data = []

        # 2. Find every 'Balance' or 'Closing' column
        for i, col_val in enumerate(header_row):
            col_name = str(col_val).lower().strip()
            # We look for 'Balance' columns that aren't 'Opening'
            prev_row_val = str(df.iloc[header_idx-1, i]).lower() if header_idx > 0 else ""
            
            if "balance" in col_name and "opening" not in col_name and "opening" not in prev_row_val:
                # A. Find the closest 'Particulars' column to the left
                account_col_idx = 0
                for c in range(i, -1, -1):
                    if "particular" in str(header_row[c]).lower() or "account" in str(header_row[c]).lower():
                        account_col_idx = c
                        break
                
                # B. Identify the Month (Search rows above and to the left)
                month = "Current Period"
                found_m = False
                month_keywords = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]
                for r in range(header_idx):
                    for c in range(i, account_col_idx - 1, -1):
                        cell = str(df.iloc[r, c])
                        if any(m in cell for m in month_keywords):
                            month = cell.strip()
                            found_m = True
                            break
                    if found_m: break
                
                # C. Extract Data
                temp_df = pd.DataFrame()
                temp_df['Account'] = data_rows.iloc[:, account_col_idx].astype(str).str.strip()
                temp_df['Amount'] = data_rows.iloc[:, i].apply(clean_amount)
                temp_df['Month'] = month
                # Remove junk rows (totals, empty lines)
                temp_df = temp_df[~temp_df['Account'].str.lower().isin(['nan', 'total', 'grand total', '', 'particulars'])]
                all_data.append(temp_df)

        if not all_data:
            return None, "No valid balance columns found. Ensure headers contain 'Balance' or 'Closing'."

        return pd.concat(all_data).reset_index(drop=True), None

    except Exception as e:
        return None, f"Error processing file: {str(e)}"

# --- APP UI ---
st.title("📊 Universal Trial Balance Dashboard")
st.markdown("Upload any Trial Balance CSV (compatible with side-by-side or vertical formats).")

uploaded_file = st.sidebar.file_uploader("Upload Trial Balance", type="csv")

if uploaded_file:
    data, err = process_file(uploaded_file)
    
    if err:
        st.error(err)
    elif data is not None:
        # Category Logic
        def categorize(acc):
            acc = acc.lower()
            if any(x in acc for x in ['cash', 'bank', 'receivable', 'asset', 'inventory', 'stock', 'prepaid']): return 'Assets'
            if any(x in acc for x in ['payable', 'loan', 'capital', 'equity', 'reserve', 'liability', 'tax']): return 'Equity & Liab'
            if any(x in acc for x in ['sale', 'revenue', 'income', 'indirect inc']): return 'Revenue'
            return 'Expenses'
        
        data['Category'] = data['Account'].apply(categorize)
        
        # Month Selector
        m_list = list(data['Month'].unique())
        selected_month = st.sidebar.selectbox("Select Month/Period", m_list)
        view = data[data['Month'] == selected_month]
        
        # KPIs
        assets = view[view['Category'] == 'Assets']['Amount'].sum()
        liab = view[view['Category'] == 'Equity & Liab']['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"₹{abs(assets):,.2f}")
        c2.metric("Equity & Liabilities", f"₹{abs(liab):,.2f}")
        c3.metric("Balance Status", "Balanced ✅" if abs(assets + liab) < 100 else "Difference ⚠️")

        st.divider()
        
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Financial Mix")
            fig = px.pie(view, values=view['Amount'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.subheader("Top Accounts")
            top_accounts = view.nlargest(10, 'Amount')
            fig2 = px.bar(top_accounts, x='Amount', y='Account', orientation='h', color='Category')
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Detailed Data")
        st.dataframe(view[['Account', 'Category', 'Amount']], use_container_width=True, height=400)
