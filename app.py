import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="Financial Dashboard", layout="wide")

def load_and_process_data(file_path):
    # Load raw CSV and ignore empty rows
    df = pd.read_csv(file_path, header=None).dropna(how='all')
    
    # 1. FIND DATA HEADERS
    # We look for the row that contains 'Particulars' AND 'Debit'
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if "particulars" in vals and "debit" in vals:
            header_idx = i
            break
            
    if header_idx is None:
        st.error("Could not find data headers. Please ensure 'Particulars' and 'Debit' are in your file.")
        return None

    # 2. FIND MONTHS
    # We search the rows ABOVE the header for anything that looks like a month/year
    month_data = []
    month_regex = re.compile(r'(january|february|march|april|may|june|july|august|september|october|november|december|202\d)', re.IGNORECASE)
    
    for r in range(header_idx):
        for c, val in enumerate(df.iloc[r]):
            if pd.notna(val) and month_regex.search(str(val)):
                clean_month = str(val).replace('[','').replace(']','').strip()
                month_data.append({'name': clean_month, 'col_start': c})

    # 3. EXTRACT DATA BLOCKS
    all_months_data = []
    header_row = df.iloc[header_idx]
    
    for m in month_data:
        # Find the Debit and Credit columns belonging to THIS month
        # They are usually at or to the right of the month label
        m_col = m['col_start']
        
        # We look for the next two non-empty numeric columns for Debit/Credit
        try:
            # We filter data rows (everything below header)
            data_rows = df.iloc[header_idx + 1:]
            
            # Find which column index has 'Debit' for this specific month section
            # In your file, Debit is often 2 columns over from Particulars
            # We look for 'Debit' in the header row starting from the month's column
            debit_col_local = -1
            credit_col_local = -1
            
            for col_i in range(m_col, len(header_row)):
                cell_val = str(header_row[col_i]).strip().lower()
                if cell_val == 'debit' and debit_col_local == -1:
                    debit_col_local = col_i
                elif cell_val == 'credit' and credit_col_local == -1:
                    credit_col_local = col_i
                if debit_col_local != -1 and credit_col_local != -1:
                    break

            temp_df = pd.DataFrame({
                'Account': data_rows.iloc[:, m_col].astype(str),
                'Month': m['name'],
                'Debit': pd.to_numeric(data_rows.iloc[:, debit_col_local], errors='coerce').fillna(0),
                'Credit': pd.to_numeric(data_rows.iloc[:, credit_col_local], errors='coerce').fillna(0)
            })
            
            # Filter out header/empty rows within the data
            temp_df = temp_df[temp_df['Account'] != 'nan']
            temp_df = temp_df[~temp_df['Account'].str.contains('Particulars', case=False)]
            
            # Calculate Balance
            temp_df['Closing'] = temp_df['Debit'] - temp_df['Credit']
            all_months_data.append(temp_df)
        except Exception as e:
            continue

    if not all_months_data:
        return None
        
    final_df = pd.concat(all_months_data).reset_index(drop=True)
    
    # Simple Category Logic
    def quick_cat(x):
        x = x.lower()
        if any(i in x for i in ['cash', 'bank', 'receivable', 'inventory', 'prepaid', 'asset']): return 'Assets'
        if any(i in x for i in ['payable', 'loan', 'capital', 'equity', 'reserve']): return 'Liabilities/Equity'
        if any(i in x for i in ['revenue', 'sales', 'income']): return 'Revenue'
        return 'Expenses'

    final_df['Category'] = final_df['Account'].apply(quick_cat)
    return final_df

# --- UI ---
st.title("📊 Financial Trial Balance Dashboard")
file = st.sidebar.file_uploader("Upload CSV", type="csv")

if file:
    data = load_and_process_data(file)
    if data is not None:
        sel_month = st.sidebar.selectbox("Select Month", data['Month'].unique())
        df_view = data[data['Month'] == sel_month]
        
        # Metrics
        rev = df_view[df_view['Category'] == 'Revenue']['Closing'].sum()
        exp = df_view[df_view['Category'] == 'Expenses']['Closing'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Revenue", f"${abs(rev):,.2f}")
        c2.metric("Total Expenses", f"${abs(exp):,.2f}")
        c3.metric("Net Profit/Loss", f"${(abs(rev) - abs(exp)):,.2f}")
        
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Category Breakdown")
            fig = px.pie(df_view, values=df_view['Closing'].abs(), names='Category', hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("Account Details")
            st.dataframe(df_view[['Account', 'Debit', 'Credit', 'Closing']], height=400)
    else:
        st.error("Data processing failed. Check your CSV structure.")
