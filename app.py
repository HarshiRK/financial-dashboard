import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Master Financial Dashboard", layout="wide")

def clean_val(v):
    """Universal number cleaner: handles 'Dr/Cr', currency, and formatting."""
    if pd.isna(v) or str(v).strip() == "": return 0.0
    s = str(v).upper().strip()
    # Detect Credit (Liability/Revenue)
    is_credit = any(x in s for x in ["CR", "-", "("])
    # Keep only digits and decimal points
    s = re.sub(r'[^0-9.]', '', s)
    try:
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        num = float(s) if s else 0.0
        return -num if is_credit else num
    except: return 0.0

def process_any_file(file):
    try:
        df = pd.read_csv(file, header=None)
        
        # 1. Identify all Header Rows (Finding 'Particulars' or 'Account')
        header_idx = None
        for i, row in df.iterrows():
            row_str = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if any(k in row_str for k in ["particulars", "account"]):
                header_idx = i
                break
        
        if header_idx is None:
            return None, "Error: Could not find 'Particulars' or 'Account' header."

        header_row = df.iloc[header_idx]
        data_rows = df.iloc[header_idx + 1:]
        
        # 2. Find ALL 'Particulars' columns (important for side-by-side files like trialbal2)
        part_cols = [i for i, v in enumerate(header_row) if any(k in str(v).lower() for k in ["particular", "account"])]
        
        all_segments = []
        month_keywords = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]

        # 3. Process each segment of the CSV
        for start_col in part_cols:
            # Find the end of this segment (until the next Particulars column or end of file)
            end_col = len(header_row)
            for p in part_cols:
                if p > start_col:
                    end_col = p
                    break
            
            # Within this segment, find columns that mean 'Balance' or 'Closing'
            for c in range(start_col, end_col):
                h_val = str(header_row[c]).lower()
                # Check row above for "Closing" context
                prev_val = str(df.iloc[header_idx-1, c]).lower() if header_idx > 0 else ""
                
                if "balance" in h_val or "closing" in h_val:
                    # Skip if it's explicitly an "Opening" balance
                    if "opening" in h_val or "opening" in prev_val:
                        continue
                        
                    # Find the Month (Search rows above this column)
                    month_label = "Total/Current"
                    found_m = False
                    for r in range(header_idx):
                        for search_c in range(c, start_col - 1, -1):
                            cell = str(df.iloc[r, search_c])
                            if any(m in cell for m in month_keywords):
                                month_label = cell.strip().replace('[','').replace(']','')
                                found_m = True
                                break
                        if found_m: break
                    
                    # Extract the actual data
                    temp = pd.DataFrame()
                    temp['Account'] = data_rows.iloc[:, start_col].astype(str).str.strip()
                    temp['Amount'] = data_rows.iloc[:, c].apply(clean_val)
                    temp['Month'] = month_label
                    # Filter out garbage rows
                    temp = temp[~temp['Account'].str.lower().isin(['nan', 'total', 'grand total', 'particulars', ''])]
                    all_segments.append(temp)

        if not all_segments:
            return None, "No data found. Check if your columns are labeled 'Particulars' and 'Balance'."

        return pd.concat(all_segments).reset_index(drop=True), None

    except Exception as e:
        return None, f"Fatal Error: {str(e)}"

# --- INTERFACE ---
st.title("📊 Universal Trial Balance Dashboard")

uploaded = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded:
    data, err = process_any_file(uploaded)
    if err:
        st.error(err)
    elif data is not None:
        # Category Logic
        def quick_cat(x):
            x = x.lower()
            if any(i in x for i in ['cash', 'bank', 'receivable', 'asset', 'inventory']): return 'Assets'
            if any(i in x for i in ['payable', 'loan', 'capital', 'equity', 'reserve', 'liability']): return 'Equity & Liab'
            if any(i in x for i in ['sale', 'revenue', 'income']): return 'Revenue'
            return 'Expenses'
        
        data['Category'] = data['Account'].apply(quick_cat)
        
        # Period Selector
        periods = list(data['Month'].unique())
        sel_period = st.sidebar.selectbox("Choose Period", periods)
        df_view = data[data['Month'] == sel_period]
        
        # Display Cards
        assets = df_view[df_view['Category'] == 'Assets']['Amount'].sum()
        liab = df_view[df_view['Category'] == 'Equity & Liab']['Amount'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"₹{abs(assets):,.2f}")
        c2.metric("Equity & Liabilities", f"₹{abs(liab):,.2f}")
        c3.metric("Accounting Check", "Balanced ✅" if abs(assets + liab) < 100 else "Difference Found ⚠️")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Asset Breakdown")
            fig = px.pie(df_view[df_view['Category']=='Assets'], values='Amount', names='Account', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Data List")
            st.dataframe(df_view[['Account', 'Category', 'Amount']], use_container_width=True, height=400)
