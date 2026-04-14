import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Financial Dashboard", layout="wide")

def clean_to_float(v):
    """Aggressive cleaner for Dr/Cr and formatted numbers."""
    if pd.isna(v) or str(v).strip() == "": return 0.0
    s = str(v).upper().strip()
    is_credit = any(x in s for x in ["CR", "-", "("])
    # Extract only digits and decimal
    s = re.sub(r'[^0-9.]', '', s)
    try:
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        val = float(s) if s else 0.0
        return -val if is_credit else val
    except: return 0.0

def universal_parser(file):
    try:
        df = pd.read_csv(file, header=None)
        
        # 1. Find the Main Header (row containing 'Particulars')
        header_idx = None
        for i, row in df.iterrows():
            if any("particular" in str(x).lower() for x in row.values):
                header_idx = i
                break
        
        if header_idx is None:
            return None, "Error: Could not find 'Particulars' header."

        header_row = df.iloc[header_idx]
        data_rows = df.iloc[header_idx + 1:]
        
        # 2. Identify every 'Particulars' or Account column
        # This handles your change where you added Particulars for every month.
        account_cols = []
        for i, val in enumerate(header_row):
            v_str = str(val).lower()
            if "particular" in v_str or "account" in v_str or v_str == "`":
                account_cols.append(i)
        
        all_month_data = []
        month_keywords = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]

        # 3. Process the file horizontally
        for i, val in enumerate(header_row):
            h_name = str(val).lower().strip()
            # We look for "Balance" columns that are NOT "Opening"
            prev_val = str(df.iloc[header_idx-1, i]).lower().strip() if header_idx > 0 else ""
            
            if "balance" in h_name or "closing" in h_name:
                if "opening" in h_name or "opening" in prev_val:
                    continue # Skip opening balances
                
                # Find the closest Account/Particulars column to the LEFT
                my_account_col = 0
                for ac in account_cols:
                    if ac <= i: my_account_col = ac
                    else: break
                
                # Find Month label (search up from this balance column)
                month = "Total"
                found_m = False
                for r_search in range(header_idx):
                    for c_search in range(i, my_account_col - 1, -1):
                        cell = str(df.iloc[r_search, c_search])
                        if any(m in cell for m in month_keywords):
                            month = cell.strip().replace('[','').replace(']','')
                            found_m = True
                            break
                    if found_m: break
                
                # 4. Extract Data Segment
                temp = pd.DataFrame()
                temp['Account'] = data_rows.iloc[:, my_account_col].astype(str).str.strip()
                temp['Amount'] = data_rows.iloc[:, i].apply(clean_to_float)
                temp['Month'] = month
                
                # Filter out empty or header-like rows
                temp = temp[~temp['Account'].str.lower().isin(['nan', 'total', 'grand total', 'particulars', '', '`'])]
                all_month_data.append(temp)

        if not all_month_data:
            return None, "No Closing Balance columns detected."

        return pd.concat(all_month_data).reset_index(drop=True), None

    except Exception as e:
        return None, f"Parsing Error: {str(e)}"

# --- STREAMLIT UI ---
st.title("📊 Master Financial Dashboard")
st.markdown("Designed for multi-column and side-by-side Trial Balances.")

uploaded = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded:
    data, err = universal_parser(uploaded)
    if err:
        st.error(err)
    elif data is not None:
        # Simple Categorization Logic
        def quick_cat(x):
            x = x.lower()
            if any(i in x for i in ['cash', 'bank', 'receivable', 'asset', 'inventory']): return 'Assets'
            if any(i in x for i in ['payable', 'loan', 'capital', 'equity', 'reserve', 'liability']): return 'Equity & Liab'
            if any(i in x for i in ['sale', 'revenue', 'income']): return 'Revenue'
            return 'Expenses'
        
        data['Category'] = data['Account'].apply(quick_cat)
        
        # Month Filter
        months = list(data['Month'].unique())
        sel_month = st.sidebar.selectbox("Select Month", months)
        view = data[data['Month'] == sel_month]
        
        # Metrics
        assets = view[view['Category'] == 'Assets']['Amount'].sum()
        liab = view[view['Category'] == 'Equity & Liab']['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"₹{abs(assets):,.2f}")
        c2.metric("Equity & Liabilities", f"₹{abs(liab):,.2f}")
        c3.metric("Status", "Balanced ✅" if abs(assets + liab) < 100 else "Difference ⚠️")
        
        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Financial Composition")
            fig = px.pie(view, values=view['Amount'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("Data Table")
            st.dataframe(view[['Account', 'Category', 'Amount']], use_container_width=True, height=400)
