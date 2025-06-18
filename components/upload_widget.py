import streamlit as st
import os

def create_upload_widget():
    """
    Create file upload widget with additional metadata fields
    
    Returns:
        tuple: (file_data, metadata)
    """
    uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        # Metadata fields
        st.subheader("Document Metadata")
        
        doc_type = st.radio("Document Type", ["PDF", "Book"], horizontal=True)
        subject = st.text_input("Subject")
        
        # Additional fields for books
        book_metadata = {}
        if doc_type == "Book":
            book_metadata["title"] = st.text_input("Book Title")
            book_metadata["author"] = st.text_input("Author (optional)")
        
        # Process button
        if st.button("Process Document"):
            # Save uploaded file
            save_dir = "data/uploaded"
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, uploaded_file.name)
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                print(f"File saved to {file_path}")
            
            # Return file data and metadata
            metadata = {
                "type": doc_type.lower(),
                "subject": subject,
                "path": file_path,
                "name": uploaded_file.name
            }
            
            if doc_type == "Book":
                metadata.update(book_metadata)
            
            return (file_path, metadata)
    
    return (None, None)