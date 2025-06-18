import streamlit as st
import os
import json
import tempfile
from utils.pdf_parser import parse_pdf
from utils.book_proccessor import process_book
from utils.model_interface import generate_questions, generate_solutions
from components.difficulty_selector import create_difficulty_selector
from components.question_display import display_questions

# Set page configuration
st.set_page_config(
    page_title="Question Generator",
    page_icon="📚",
    layout="wide"
)

# Create necessary directories
os.makedirs("data/uploaded", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/generated", exist_ok=True)

# Initialize session state
if 'documents' not in st.session_state:
    st.session_state.documents = {}
if 'selected_doc' not in st.session_state:
    st.session_state.selected_doc = None
if 'generated_questions' not in st.session_state:
    st.session_state.generated_questions = []
if 'generated_solutions' not in st.session_state:
    st.session_state.generated_solutions = {}

# Load existing documents
def load_existing_documents():
    if os.path.exists("data/documents_index.json"):
        with open("data/documents_index.json", "r") as f:
            return json.load(f)
    return {}

# Save documents index
def save_documents_index():
    with open("data/documents_index.json", "w") as f:
        json.dump(st.session_state.documents, f)

# Load existing documents on startup
if not st.session_state.documents:
    st.session_state.documents = load_existing_documents()

# App title
st.markdown("Generate custom questions from your PDFs for competitive exams")

# Tabs for main navigation
upload_tab, generate_tab = st.tabs(["Upload Document", "Generate Questions"])

# Upload Document Tab
with upload_tab:
    st.header("Upload PDF Document")
    
    exam_options = ["JEE Mains", "NEET", "GATE", "UPSC", "Other"]
    exam_type = st.selectbox("Select Exam Type", exam_options)
    
    if exam_type == "Other":
        exam_type = st.text_input("Enter Exam Name")
    
    subject = st.text_input("Subject (e.g., Physics, Chemistry, Biology)")
    
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_uploader")
    
    if uploaded_file is not None and subject and exam_type:
        if st.button("Process Document"):
            with st.spinner("Processing PDF..."):
                # Save uploaded file temporarily
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
                temp_file.close()
                
                # Process PDF
                document_id = f"{subject.lower().replace(' ', '_')}_{len(st.session_state.documents) + 1}"
                text_by_page = parse_pdf(temp_file_path)
                
                st.session_state.documents[document_id] = {
                    "type": "pdf",
                    "name": uploaded_file.name,
                    "subject": subject,
                    "exam_type": exam_type,
                    "content": text_by_page,
                    "path": f"data/processed/{document_id}.json"
                }
                
                # Save processed content
                with open(f"data/processed/{document_id}.json", "w") as f:
                    json.dump({
                        "type": "pdf",
                        "name": uploaded_file.name,
                        "subject": subject,
                        "exam_type": exam_type,
                        "content": text_by_page
                    }, f)
                
                os.unlink(temp_file_path)  # Remove temp file
                save_documents_index()  # Save updated document index
                st.success(f"Document processed successfully! You can now generate questions for {subject}.")

# Generate Questions Tab
with generate_tab:
    st.header("Generate Questions")
    
    if not st.session_state.documents:
        st.info("No documents uploaded yet. Please upload PDFs in the 'Upload Document' tab.")
    else:
        # Document selection
        st.subheader("1. Select Document")
        
        # Group documents by subject
        subjects = {}
        for doc_id, doc in st.session_state.documents.items():
            subject = doc["subject"]
            if subject not in subjects:
                subjects[subject] = []
            subjects[subject].append((doc_id, doc["name"], doc["exam_type"]))
        
        selected_subject = st.selectbox(
            "Select Subject",
            options=list(subjects.keys())
        )
        
        if selected_subject:
            docs_in_subject = subjects[selected_subject]
            doc_options = [f"{name} ({exam})" for _, name, exam in docs_in_subject]
            doc_ids = [doc_id for doc_id, _, _ in docs_in_subject]
            
            selected_doc_index = st.selectbox(
                "Select PDF",
                options=range(len(doc_options)),
                format_func=lambda x: doc_options[x]
            )
            
            selected_doc_id = doc_ids[selected_doc_index]
            st.session_state.selected_doc = selected_doc_id
            
            # Show document info
            doc = st.session_state.documents[selected_doc_id]
            st.write(f"Exam: {doc['exam_type']}")
            st.write(f"Pages: {len(doc['content'])}")
            
            # Question generation settings
            st.subheader("2. Question Generation Settings")
            
            col1, col2 = st.columns(2)
            
            with col1:
                num_questions = st.number_input("Number of Questions", min_value=1, max_value=50, value=10)
                page_range = st.slider("Page Range", 1, len(doc['content']), (1, min(5, len(doc['content']))))
            
            with col2:
                difficulty_options = create_difficulty_selector(num_questions)
            
            # Generate button
            if st.button("Generate Questions"):
                with st.spinner(f"Generating {num_questions} questions "):
                    # Prepare content from selected pages
                    content_to_use = {i+1: page for i, page in enumerate(doc['content']) 
                                    if i+1 >= page_range[0] and i+1 <= page_range[1]}
                    
                    # Generate questions
                    questions = generate_questions(
                        content=content_to_use,
                        subject=doc['subject'],
                        num_questions=num_questions,
                        difficulty_distribution=difficulty_options
                    )
                    
                    # Store generated questions
                    st.session_state.generated_questions = questions
                    question_file_path = f"data/generated/{st.session_state.selected_doc}_questions.json"
                    with open(question_file_path, "w") as f:
                        json.dump(questions, f)
                    
                    st.success(f"Generated {len(questions)} questions!")
            
            # Display generated questions
            if st.session_state.generated_questions:
                st.subheader("Generated Questions")
                display_questions(st.session_state.generated_questions)
                
                # Generate solutions
                if st.button("Generate Solutions"):
                    with st.spinner("Generating solutions..."):
                        solutions = generate_solutions(st.session_state.generated_questions)
                        st.session_state.generated_solutions = solutions
                        
                        # Save solutions
                        solution_file_path = f"data/generated/{st.session_state.selected_doc}_solutions.json"
                        with open(solution_file_path, "w") as f:
                            json.dump(solutions, f)
                        
                        st.success("Solutions generated!")
                        
                        # Display solutions
                        st.subheader("Solutions")
                        for i, (question_id, solution) in enumerate(solutions.items()):
                            with st.expander(f"Solution for Question {i+1}"):
                                st.markdown(solution["explanation"])
                                
                                if solution.get("diagram_latex"):
                                    st.subheader("Diagram")
                                    st.text(solution["diagram_latex"])
                                    # Note: In a production app, you'd render the LaTeX here
