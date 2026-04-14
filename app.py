import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set page config
st.set_page_config(page_title="Financial Trial Balance Dashboard", layout="wide")

def load_and_process_data(file_path):
    """Parses the complex XYZ Trial Balance format into a clean dataset."""
    df = pd.read_csv(file_path)
    
    # Identify month headers (usually in row 2) and metric headers (row 4)
    month_row = df.iloc[2]
    months = [(val, i) for i, val in enumerate(month_row) if pd.notna(val) and val != '']
    
    all_data = []
    for month_name, start_idx in months:
        # Extract the 4 columns for each month relative to the month label position
        temp_df = pd.DataFrame({
            'Account': df.iloc[5:, 0], # Column A: Particulars
            'Month': month_name,
            'Opening': pd.to_numeric(df.iloc[5:, start_idx-1], errors='coerce').fillna(0),
            'Debit': pd.to_numeric(df.iloc[5:, start_idx], errors='coerce').fillna(0),
            'Credit': pd.to_numeric(df.iloc[5:, start_idx+1], errors='coerce').fillna(0),
            'Closing': pd.to_numeric(df.iloc[5:, start_idx+2], errors='coerce').fillna(0)
        })
        all_data.append(temp_df)
    
    combined = pd.concat(all_data).dropna(subset=['Account'])
    
    # Categorize Accounts based on keywords
    def categorize(acc):
        acc = str(acc).lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'inventory', 'asset', 'prepaid']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'liability', 'debt']): return 'Liabilities'
        if any(x in acc for x in ['capital', 'stock', 'equity', 'reserves']): return 'Equity'
        if any(x in acc for x in ['revenue', 'sales', 'income']): return 'Revenue'
        return 'Expenses'
    
    combined['Category'] = combined['Account'].apply(categorize)
    return combined

# --- UI Components ---
st.title("📊 Trial Balance Dashboard")
st.sidebar.header("Settings")

uploaded_file = st.sidebar.file_uploader("Upload your updated Trial Balance (CSV)", type="csv")

if uploaded_file:
    data = load_and_process_data(uploaded_file)
    
    # Sidebar Filters
    selected_month = st.sidebar.selectbox("Select Month", data['Month'].unique())
    month_data = data[data['Month'] == selected_month]
    
    # --- Key Metrics (KPIs) ---
    assets = month_data[month_data['Category'] == 'Assets']['Closing'].sum()
    liabilities = month_data[month_data['Category'] == 'Liabilities']['Closing'].sum()
    revenue = month_data[month_data['Category'] == 'Revenue']['Closing'].sum()
    expenses = month_data[month_data['Category'] == 'Expenses']['Closing'].sum()
    net_profit = revenue - expenses

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Assets", f"${assets:,.2f}")
    col2.metric("Total Liabilities", f"${liabilities:,.2f}")
    col3.metric("Total Revenue", f"${revenue:,.2f}")
    col4.metric("Net Profit/Loss", f"${net_profit:,.2f}", delta=net_profit)

    # --- Visualizations ---
    st.divider()
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Account Category Distribution")
        cat_totals = month_data.groupby('Category')['Closing'].sum().abs().reset_index()
        fig_pie = px.pie(cat_totals, values='Closing', names='Category', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("Monthly Transaction Volume (Debit vs Credit)")
        monthly_tx = data.groupby('Month')[['Debit', 'Credit']].sum().reset_index()
        fig_bar = px.bar(monthly_tx, x='Month', y=['Debit', 'Credit'], barmode='group')
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Top 10 Expenses")
    top_exp = month_data[month_data['Category'] == 'Expenses'].nlargest(10, 'Closing')
    fig_exp = px.bar(top_exp, x='Closing', y='Account', orientation='h', color='Closing')
    st.plotly_chart(fig_exp, use_container_width=True)

    # Data Table
    st.subheader("Detailed Monthly View")
    st.dataframe(month_data, use_container_width=True)
else:
    st.info("Please upload your CSV file to view the dashboard.")
