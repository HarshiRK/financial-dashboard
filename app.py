import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Financial Dashboard", layout="wide")

# --- CLEAN NUMBER FUNCTION ---
def clean_to_float(v):
    if pd.isna(v) or str(v).strip() == "":
        return 0.0
    
    s = str(v).upper().strip()
    is_credit = any(x in s for x in ["CR", "-", "("])
    
    s = re.sub(r'[^0-9.]', '', s)
    
    try:
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        val = float(s) if s else 0.0
        return -val if is_credit else val
    except:
        return 0.0


# --- UNIVERSAL PARSER (FIXED) ---
def universal_parser(file):
    try:
        df = pd.read_csv(file, header=None)

        # Find header row
        header_idx = None
        for i, row in df.iterrows():
            if any("particular" in str(x).lower() for x in row.values):
                header_idx = i
                break

        if header_idx is None:
            return None, "Error: 'Particulars' column not found."

        header_row = df.iloc[header_idx]
        data_rows = df.iloc[header_idx + 1:]

        # Find account columns
        account_cols = []
        for i, val in enumerate(header_row):
            if "particular" in str(val).lower():
                account_cols.append(i)

        all_month_data = []
        month_keywords = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec","202"]

        # Loop columns
        for i, val in enumerate(header_row):
            h_name = str(val).lower().strip()

            # ✅ ONLY closing balance
            if "closing" in h_name:

                # Find closest account column on LEFT
                my_account_col = None
                for ac in reversed(account_cols):
                    if ac < i:
                        my_account_col = ac
                        break

                if my_account_col is None:
                    continue

                # Find month
                month = "Total"
                for r in range(header_idx):
                    for c in range(i, my_account_col - 1, -1):
                        cell = str(df.iloc[r, c]).lower()
                        if any(m in cell for m in month_keywords):
                            month = df.iloc[r, c]
                            break

                # Extract data
                temp = pd.DataFrame()
                temp['Account'] = data_rows.iloc[:, my_account_col].astype(str).str.strip()
                
                # Remove wrong rows
                temp = temp[~temp['Account'].str.match(r'^[0-9.\sDrCr()-]+$', na=False)]

                temp['Amount'] = data_rows.iloc[:, i].apply(clean_to_float)
                temp['Month'] = month

                temp = temp[temp['Account'].notna()]
                temp = temp[temp['Account'] != ""]

                all_month_data.append(temp)

        if not all_month_data:
            return None, "No Closing Balance columns found."

        final_df = pd.concat(all_month_data).reset_index(drop=True)
        return final_df, None

    except Exception as e:
        return None, f"Error: {str(e)}"


# --- STREAMLIT UI ---
st.title("📊 Master Financial Dashboard")
st.markdown("Designed for multi-column and side-by-side Trial Balances.")

uploaded = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded:
    data, err = universal_parser(uploaded)

    if err:
        st.error(err)

    elif data is not None:

        # ✅ FIXED CATEGORY FUNCTION
        def quick_cat(x):
            if pd.isna(x):
                return 'Expenses'
            
            x = str(x).lower().strip()

            if any(i in x for i in ['cash', 'bank', 'receivable', 'asset', 'inventory']):
                return 'Assets'
            if any(i in x for i in ['payable', 'loan', 'capital', 'equity', 'reserve', 'liability']):
                return 'Equity & Liab'
            if any(i in x for i in ['sale', 'revenue', 'income']):
                return 'Revenue'
            
            return 'Expenses'

        data['Category'] = data['Account'].apply(quick_cat)

        # DEBUG (remove later)
        st.write("Preview Data:", data.head())

        # Month filter
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

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Financial Composition")
            fig = px.pie(view, values=view['Amount'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Data Table")
            st.dataframe(view[['Account', 'Category', 'Amount']], use_container_width=True, height=400)
