import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Universal Finance Dashboard", layout="wide")

def clean_to_float(value):
    """The 'Dr/Cr' Remover: Cleans any currency string into a math-ready number."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    s = str(value).upper()
    # 1. Identify if it's a Credit (negative)
    is_credit = "CR" in s or "-" in s or "(" in s
    # 2. Remove all non-numeric characters (Dr, Cr, symbols, commas)
    s = re.sub(r'[^0-9.]', '', s)
    try:
        num = float(s)
        return -num if is_credit else num
    except:
        return 0.0

def process_file(file):
    df = pd.read_csv(file, header=None)
    
    # --- FIND THE TABLE START ---
    header_idx = None
    for i, row in df.iterrows():
        row_str = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
        if any(key in row_str for key in ["particulars", "account", "description"]):
            header_idx = i
            break
            
    if header_idx is None:
        st.error("Could not find the Account/Particulars column.")
        return None

    header_row = df.iloc[header_idx]
    data_rows = df.iloc[header_idx + 1:]
    all_chunks = []

    # --- DETECT FORMAT TYPE ---
    # We look for columns labeled Balance, Closing, Debit, or Credit
    cols_found = []
    for i, val in enumerate(header_row):
        v = str(val).lower()
        if any(keyword in v for keyword in ["balance", "closing", "debit", "credit"]):
            # Find the month name above this column
            month = "Current Period"
            for r in range(header_idx):
                cell = str(df.iloc[r, i])
                if any(m in cell for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "202"]):
                    month = cell.strip().replace('[','').replace(']','')
                    break
            cols_found.append({"idx": i, "name": v, "month": month})

    # --- EXTRACT DATA ---
    # Group by month
    unique_months = list(set([c['month'] for c in cols_found]))
    
    for m in unique_months:
        m_cols = [c for c in cols_found if c['month'] == m]
        temp_df = pd.DataFrame({'Account': data_rows.iloc[:, 0].astype(str).str.strip(), 'Month': m})
        
        # If there's a Balance/Closing column, use it directly
        balance_col = next((c for c in m_cols if "balance" in c['name'] or "closing" in c['name']), None)
        
        if balance_col:
            temp_df['Final_Value'] = data_rows.iloc[:, balance_col['idx']].apply(clean_to_float)
        else:
            # If no balance column, calculate from Debit and Credit
            deb_col = next((c for c in m_cols if "debit" in c['name']), None)
            cre_col = next((c for c in m_cols if "credit" in c['name']), None)
            
            d_vals = data_rows.iloc[:, deb_col['idx']].apply(clean_to_float) if deb_col else 0
            c_vals = data_rows.iloc[:, cre_col['idx']].apply(clean_to_float) if cre_col else 0
            temp_df['Final_Value'] = d_vals - c_vals

        temp_df = temp_df[temp_df['Account'] != "nan"]
        all_chunks.append(temp_df)

    final_df = pd.concat(all_chunks).reset_index(drop=True)

    # Universal Categories
    def quick_cat(acc):
        acc = acc.lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'asset', 'inventory']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'liab', 'equity', 'capital']): return 'Liabilities/Equity'
        if any(x in acc for x in ['sale', 'revenue', 'income']): return 'Revenue'
        return 'Expenses'
    
    final_df['Category'] = final_df['Account'].apply(quick_cat)
    return final_df

# --- UI ---
st.title("📊 Universal Trial Balance Dashboard")

file = st.sidebar.file_uploader("Upload any Trial Balance (CSV)", type="csv")

if file:
    data = process_file(file)
    if data is not None:
        month = st.sidebar.selectbox("Select Month/Period", data['Month'].unique())
        view = data[data['Month'] == month]
        
        # Metrics
        assets = view[view['Category'] == 'Assets']['Final_Value'].sum()
        liabs = view[view['Category'] == 'Liabilities/Equity']['Final_Value'].sum()
        rev = view[view['Category'] == 'Revenue']['Final_Value'].sum()
        exp = view[view['Category'] == 'Expenses']['Final_Value'].sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Assets", f"{abs(assets):,.2f}")
        k2.metric("Total Liab/Equity", f"{abs(liabs):,.2f}")
        k3.metric("Revenue", f"{abs(rev):,.2f}")
        k4.metric("Net Profit", f"{(abs(rev) - abs(exp)):,.2f}")

        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Financial Composition")
            fig = px.pie(view, values=view['Final_Value'].abs(), names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Account Ranking")
            top = view.nlargest(10, 'Final_Value')
            fig2 = px.bar(top, x='Final_Value', y='Account', orientation='h', color='Category')
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(view, use_container_width=True)
