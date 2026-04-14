import streamlit as st
import pandas as pd
import plotly.express as px

# Setup
st.set_page_config(page_title="Closing Balance Dashboard", layout="wide")

def load_data(file):
    # Load file
    df = pd.read_csv(file, header=None)
    
    # 1. Find the row where the data starts (Particulars)
    header_idx = None
    for i, row in df.iterrows():
        if "Particulars" in row.values:
            header_idx = i
            break
    
    if header_idx is None:
        st.error("Could not find 'Particulars' column. Check your CSV.")
        return None

    # 2. Find the month names (usually 2-3 rows above Particulars)
    # We'll look for any row above header that has text
    months = []
    for r in range(header_idx):
        for c, val in enumerate(df.iloc[r]):
            if pd.notna(val) and len(str(val)) > 2:
                months.append({"name": str(val).strip(), "col": c})

    # 3. Extract Account Names and Closing Balances
    all_data = []
    header_row = df.iloc[header_idx]
    
    for m in months:
        # For each month, find the nearest "Closing" or "Balance" column to its right
        closing_col = -1
        # In XYZ format, Closing Balance is usually 4 columns to the right of the month start
        # We search for the keyword "Closing" or "Balance" in the header row
        for search_col in range(m['col'], len(header_row)):
            cell = str(header_row[search_col]).lower()
            if "closing" in cell or "balance" in cell:
                # If there are two "Balances", we want the second one (Closing)
                closing_col = search_col 
        
        if closing_col != -1:
            month_df = pd.DataFrame({
                'Account': df.iloc[header_idx+1:, 0],
                'Month': m['name'],
                'Closing_Balance': pd.to_numeric(df.iloc[header_idx+1:, closing_col], errors='coerce').fillna(0)
            })
            all_data.append(month_df)

    if not all_data:
        st.error("Could not find a 'Closing Balance' column.")
        return None

    combined = pd.concat(all_data).dropna(subset=['Account'])
    
    # Categorize
    def categorize(acc):
        acc = str(acc).lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'inventory']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'capital', 'equity']): return 'Liabilities & Equity'
        if any(x in acc for x in ['revenue', 'sale', 'income']): return 'Revenue'
        return 'Expenses'
    
    combined['Category'] = combined['Account'].apply(categorize)
    return combined

# --- UI ---
st.title("💰 Closing Balance Dashboard")
uploaded_file = st.sidebar.file_uploader("Upload your Trial Balance CSV", type="csv")

if uploaded_file:
    data = load_data(uploaded_file)
    if data is not None:
        month = st.sidebar.selectbox("Select Month", data['Month'].unique())
        filtered = data[data['Month'] == month]
        
        # Dashboard Cards
        assets = filtered[filtered['Category'] == 'Assets']['Closing_Balance'].sum()
        liabilities = filtered[filtered['Category'] == 'Liabilities & Equity']['Closing_Balance'].sum()
        profit = filtered[filtered['Category'] == 'Revenue']['Closing_Balance'].sum() - filtered[filtered['Category'] == 'Expenses']['Closing_Balance'].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Assets", f"${assets:,.2f}")
        c2.metric("Liabilities & Equity", f"${liabilities:,.2f}")
        c3.metric("Estimated Net Position", f"${profit:,.2f}")

        st.divider()
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Balance Sheet Composition")
            fig = px.pie(filtered[filtered['Category'].isin(['Assets', 'Liabilities & Equity'])], 
                         values='Closing_Balance', names='Category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
        with col_b:
            st.subheader("Top Account Balances")
            top10 = filtered.nlargest(10, 'Closing_Balance')
            fig2 = px.bar(top10, x='Closing_Balance', y='Account', orientation='h')
            st.plotly_chart(fig2, use_container_width=True)
            
        st.subheader("Detailed Data Table")
        st.dataframe(filtered, use_container_width=True)
