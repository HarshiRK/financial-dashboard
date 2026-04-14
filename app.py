import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="XYZ Financial Dashboard", layout="wide")

def clean_currency(value):
    """Removes 'Dr', 'Cr', commas, and spaces to convert to a number."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    s = str(value).upper()
    # Check for Credit suffix
    is_credit = "CR" in s
    # Remove non-numeric characters except decimal and minus
    s = s.replace("DR", "").replace("CR", "").replace(",", "").strip()
    try:
        num = float(s)
        return -num if is_credit else num
    except:
        return 0.0

def load_xyz_data(file):
    df = pd.read_csv(file, header=None)
    
    # 1. Identify rows
    # Row 3 (index 3) = Months
    # Row 4 (index 4) = Closing/Opening labels
    # Row 5 (index 5) = Specific Headers (Particulars, Balance)
    month_row = df.iloc[3]
    type_row = df.iloc[4]
    header_row = df.iloc[5]
    
    # 2. Find all 'Closing Balance' columns
    # In your file, these are columns where Row 4 is 'Closing' and Row 5 is 'Balance'
    closing_indices = []
    for i in range(len(type_row)):
        t_val = str(type_row[i]).strip().lower()
        h_val = str(header_row[i]).strip().lower()
        if t_val == "closing" and h_val == "balance":
            # Find the associated month name (looking left from this column)
            month_name = "Unknown"
            for j in range(i, -1, -1):
                if pd.notna(month_row[j]) and str(month_row[j]).strip() != "":
                    month_name = str(month_row[j]).strip().replace('[','').replace(']','')
                    break
            closing_indices.append((i, month_name))

    # 3. Extract Data
    all_data = []
    data_rows = df.iloc[6:] # Accounts start at Row 6
    
    for col_idx, m_name in closing_indices:
        temp_df = pd.DataFrame({
            'Account': data_rows.iloc[:, 0].astype(str).str.strip(),
            'Month': m_name,
            'Closing_Balance': data_rows.iloc[:, col_idx].apply(clean_currency)
        })
        # Filter out empty or total rows
        temp_df = temp_df[temp_df['Account'] != "nan"]
        temp_df = temp_df[temp_df['Account'] != ""]
        all_data.append(temp_df)
    
    if not all_data:
        return None
        
    final_df = pd.concat(all_data).reset_index(drop=True)

    # 4. Smart Categorization
    def categorize(acc):
        acc = acc.lower()
        if any(x in acc for x in ['cash', 'bank', 'receivable', 'inventory', 'deposit', 'prepaid', 'fixed assets']): return 'Assets'
        if any(x in acc for x in ['payable', 'loan', 'liability', 'capital', 'reserves', 'equity', 'share']): return 'Equity & Liabilities'
        if any(x in acc for x in ['revenue', 'sales', 'income']): return 'Revenue'
        return 'Expenses'
    
    final_df['Category'] = final_df['Account'].apply(categorize)
    return final_df

# --- Dashboard UI ---
st.title("📊 XYZ Trial Balance Dashboard")
st.info("Upload your 'XYZ sample trial balance.csv' to see the visualization.")

uploaded_file = st.sidebar.file_uploader("Upload CSV File", type="csv")

if uploaded_file:
    data = load_xyz_data(uploaded_file)
    
    if data is not None:
        # Month Selector
        months = data['Month'].unique()
        selected_month = st.sidebar.selectbox("Select Month", months)
        
        m_data = data[data['Month'] == selected_month]
        
        # Dashboard Calculations
        assets = m_data[m_data['Category'] == 'Assets']['Closing_Balance'].sum()
        liab_eq = m_data[m_data['Category'] == 'Equity & Liabilities']['Closing_Balance'].sum()
        
        # Display Cards
        c1, c2, c3 = st.columns(3)
        # We use abs() for display because liabilities are stored as negative in this code
        c1.metric("Total Assets", f"₹{abs(assets):,.2f}")
        c2.metric("Equity & Liabilities", f"₹{abs(liab_eq):,.2f}")
        c3.metric("Balance Check", "Balanced ✅" if round(assets + liab_eq, 2) == 0 else "Unbalanced ⚠️")
        
        st.divider()
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Composition (Assets vs Liabilities)")
            # Create data for pie chart
            pie_df = pd.DataFrame({
                'Category': ['Assets', 'Equity & Liabilities'],
                'Value': [abs(assets), abs(liab_eq)]
            })
            fig = px.pie(pie_df, values='Value', names='Category', hole=0.4, 
                         color_discrete_sequence=['#2E86C1', '#D35400'])
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.subheader("Top 10 Accounts by Value")
            top10 = m_data.iloc[m_data['Closing_Balance'].abs().argsort()[-10:]]
            fig2 = px.bar(top10, x=top10['Closing_Balance'].abs(), y='Account', 
                          orientation='h', color='Category')
            st.plotly_chart(fig2, use_container_width=True)
            
        st.subheader("Detailed Closing Balances")
        st.dataframe(m_data[['Account', 'Category', 'Closing_Balance']], use_container_width=True)
    else:
        st.error("The file format did not match the XYZ sample. Please check headers.")
