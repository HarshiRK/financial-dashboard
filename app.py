import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set page config
st.set_page_config(page_title="Financial Dashboard", layout="wide")

def load_and_process_data(file_path):
    # Load raw CSV
    df = pd.read_csv(file_path, header=None)
    
    # 1. Find the row containing "Particulars" to identify the start of data
    header_row_idx = None
    for i, row in df.iterrows():
        if "Particulars" in row.values:
            header_row_idx = i
            break
    
    if header_row_idx is None:
        st.error("Could not find 'Particulars' column. Please check your file format.")
        return None

    # 2. Extract Month Names (Searching the rows above 'Particulars')
    # Usually, months are 2 rows above 'Particulars' in XYZ format
    month_row = df.iloc[header_row_idx - 2]
    months = []
    for i, val in enumerate(month_row):
        if pd.notna(val) and str(val).strip() != '':
            months.append((str(val).strip(), i))

    # 3. Process data for each detected month
    all_data = []
    for month_name, col_index in months:
        try:
            # In XYZ format, the 4 columns are: Opening, Debit, Credit, Closing
            # We map these relative to the month's starting column
            month_df = pd.DataFrame({
                'Account': df.iloc[header_row_idx + 1:, 0],
                'Month': month_name,
                'Opening': pd.to_numeric(df.iloc[header_row_idx + 1:, col_index - 1], errors='coerce'),
                'Debit': pd.to_numeric(df.iloc[header_row_idx + 1:, col_index], errors='coerce'),
                'Credit': pd.to_numeric(df.iloc[header_row_idx + 1:, col_index + 1], errors='coerce'),
                'Closing': pd.to_numeric(df.iloc[header_row_idx + 1:, col_index + 2], errors='coerce')
            })
            all_data.append(month_df)
        except Exception:
            continue

    if not all_data:
        st.error("Could not parse month columns. Ensure your Debit/Credit columns align with the Month headers.")
        return None

    combined = pd.concat(all_data).dropna(subset=['Account'])
    combined[['Opening', 'Debit', 'Credit', 'Closing']] = combined[['Opening', 'Debit', 'Credit', 'Closing']].fillna(0)
    
    # Categorization Logic
    def categorize(acc):
        acc = str(acc).lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'inventory', 'deposit', 'prepaid']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'liability', 'debt', 'capital', 'reserves', 'equity']): return 'Liabilities & Equity'
        if any(x in acc for x in ['revenue', 'sales', 'income']): return 'Revenue'
        return 'Expenses'
    
    combined['Category'] = combined['Account'].apply(categorize)
    return combined

# --- Streamlit UI ---
st.title("📊 Trial Balance Dashboard")
st.markdown("### Upload your updated **trialbal2.csv** to see your financial summary.")

uploaded_file = st.sidebar.file_uploader("Upload CSV", type="csv")

if uploaded_file:
    data = load_and_process_data(uploaded_file)
    
    if data is not None:
        # Sidebar selection
        months_available = data['Month'].unique()
        selected_month = st.sidebar.selectbox("Select Month", months_available)
        
        # Filter data
        m_data = data[data['Month'] == selected_month]
        
        # Metrics
        assets = m_data[m_data['Category'] == 'Assets']['Closing'].sum()
        liabilities = m_data[m_data['Category'] == 'Liabilities & Equity']['Closing'].sum()
        rev = m_data[m_data['Category'] == 'Revenue']['Closing'].sum()
        exp = m_data[m_data['Category'] == 'Expenses']['Closing'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Assets", f"{assets:,.2f}")
        c2.metric("Liabilities & Equity", f"{liabilities:,.2f}")
        c3.metric("Total Revenue", f"{rev:,.2f}")
        c4.metric("Net Profit/Loss", f"{(rev - exp):,.2f}")

        st.divider()

        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Asset vs. Liability Distribution")
            pie_data = m_data.groupby('Category')['Closing'].sum().abs().reset_index()
            fig = px.pie(pie_data, values='Closing', names='Category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.subheader("Transaction Volume")
            # Filter out accounts with 0 activity for clarity
            active_tx = m_data[(m_data['Debit'] > 0) | (m_data['Credit'] > 0)].nlargest(10, 'Debit')
            fig2 = px.bar(active_tx, x='Account', y=['Debit', 'Credit'], barmode='group', title="Top 10 Active Accounts")
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Detailed Monthly Data")
        st.dataframe(m_data, use_container_width=True)
else:
    st.info("Waiting for file upload...")
