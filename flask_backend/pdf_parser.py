import PyPDF2
import re
import os

def parse_pdf(pdf_path):
    """
    Parse a PDF file and extract text and images by page
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        tuple: (list of strings containing text from each page, list of images by page)
    """
    text_by_page = []
    images_by_page = []  # Add this list for images
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                # Clean text
                text = re.sub(r'\s+', ' ', text).strip()
                text_by_page.append(text)
                
                # Add empty list for images on this page
                # Note: PyPDF2 doesn't easily extract images, so we're just adding
                # placeholders here. You would need additional code to extract actual images.
                images_by_page.append([])
                
        return text_by_page, images_by_page  # Return both values
    
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return [], []  # Return empty lists for both