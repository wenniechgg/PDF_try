import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import camelot
import io
import os
import tempfile

# --- Helper Functions (from your original script) ---
def normalize_text(text):
    """Lowercases and normalizes whitespace in a string."""
    return ' '.join(text.lower().split())

def find_pages_with_keywords(pdf_bytes, keywords):
    """Finds pages in a PDF that contain all specified keywords."""
    matched_pages = []
    # Open PDF from bytes in memory
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    for page_num, page in enumerate(doc, start=1):
        text = normalize_text(page.get_text("text"))
        if all(keyword.lower() in text for keyword in keywords):
            matched_pages.append(page_num)
            
    return matched_pages

def contains_numbers_and_text(df):
    """Checks if a DataFrame contains both numbers and text."""
    has_number = df.apply(lambda col: col.astype(str).str.contains(r'\d').any(), axis=0).any()
    has_text = df.apply(lambda col: col.astype(str).str.contains(r'[A-Za-z]', case=False).any(), axis=0).any()
    return has_number and has_text

# --- Streamlit App Interface ---
st.set_page_config(layout="wide")
st.title("📄 PDF Table Extractor")
st.markdown("Upload a PDF and enter keywords to find and extract relevant tables into an Excel file.")

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("⚙️ Controls")
    
    # 1. File Uploader
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    # 2. Keyword Input
    st.markdown("Enter keywords, one per line. The app will find pages containing **all** keywords.")
    keywords_input = st.text_area("Keywords", height=100, placeholder="e.g.,\nsektor ekonomi\nkredit yang diberikan")
    
    # 3. Extraction Button
    extract_button = st.button("Extract Tables", type="primary")

# --- Main Area for Results ---
if extract_button and uploaded_file is not None:
    keywords = [keyword.strip() for keyword in keywords_input.split('\n') if keyword.strip()]
    
    if not keywords:
        st.warning("Please enter at least one keyword.")
    else:
        with st.spinner("Processing PDF... This may take a moment."):
            pdf_bytes = uploaded_file.getvalue()
            
            # Find pages with keywords
            matched_pages = find_pages_with_keywords(pdf_bytes, keywords)
            
            if not matched_pages:
                st.warning("No pages found containing all the specified keywords.")
            else:
                st.info(f"Keywords found on pages: {', '.join(map(str, matched_pages))}")
                
                # Camelot needs a file path, so we save the in-memory file to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(pdf_bytes)
                    tmp_path = tmp.name
                
                try:
                    page_str = ",".join(map(str, matched_pages))
                    tables = camelot.read_pdf(tmp_path, pages=page_str, flavor="stream")
                finally:
                    os.remove(tmp_path) # Clean up the temporary file
                
                valid_tables = [table.df for table in tables if contains_numbers_and_text(table.df)]
                
                if not valid_tables:
                    st.warning("Found matching pages, but could not extract valid tables from them.")
                else:
                    st.success(f"Successfully extracted {len(valid_tables)} valid table(s)!")
                    
                    # Prepare Excel file in memory for download
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        for i, df in enumerate(valid_tables, start=1):
                            processed_df = df.copy()
                            # Clean and convert data types using your logic
                            for col in processed_df.columns:
                                cleaned_col = processed_df[col].astype(str).str.replace(',', '').str.strip()
                                numeric_col = pd.to_numeric(cleaned_col, errors='coerce')
                                processed_df[col] = numeric_col.fillna(cleaned_col)
                            
                            processed_df.to_excel(writer, sheet_name=f"Table_{i}", index=False)
                    
                    # Provide download button
                    st.download_button(
                        label="📥 Download Extracted Tables as Excel",
                        data=output.getvalue(),
                        file_name="extracted_tables.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    # Display the extracted tables
                    for i, df in enumerate(valid_tables, start=1):
                        st.subheader(f"Table {i}")
                        st.dataframe(df)

elif extract_button and uploaded_file is None:
    st.warning("Please upload a PDF file first.")
