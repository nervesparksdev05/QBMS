import streamlit as st
from dotenv import load_dotenv
import os
import json
import tempfile
import base64
from io import BytesIO
import matplotlib.pyplot as plt
from flask_backend.pdf_parser import parse_pdf
from utils.model_interface import generate_questions_with_duplicate_check, solve_questions, update_questions_with_user_selections, generate_diagrams_for_selected_questions, generate_diagram_with_instructions, convert_question_difficulty
from utils.diagram_generator import DiagramGenerator
from components.difficulty_selector import create_difficulty_selector
import traceback, re
import numpy as np 
import math
from difflib import SequenceMatcher
import pandas as pd
from datetime import datetime
import requests
import warnings
from matplotlib import font_manager
import matplotlib
import uuid
import subprocess
import fitz
from PIL import Image


# Set page configuration
st.set_page_config(
    page_title="Question Generator",
    page_icon="📚",
    layout="wide"
)

load_dotenv()
# from api_server import start_api_server

DIAGRAM_FOLDER = os.path.join(os.getcwd(), "temp_diagrams")
os.makedirs(DIAGRAM_FOLDER, exist_ok=True)

# if start_api_server():
#     print("API server started on port 5001")

# Create necessary directories
os.makedirs("data/uploaded", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/generated", exist_ok=True)
os.makedirs("data/diagrams", exist_ok=True)  # Directory for diagram images
os.makedirs("data/question_database", exist_ok=True)

col1, col2, col3 = st.columns([1, 2, 3])
with col1:
    st.image("logo.png", width=400)

# Initialize session state
if 'documents' not in st.session_state:
    st.session_state.documents = {}
if 'selected_doc' not in st.session_state:
    st.session_state.selected_doc = None
if 'generated_questions' not in st.session_state:
    st.session_state.generated_questions = []
if 'selected_for_diagrams' not in st.session_state:
    st.session_state.selected_for_diagrams = []  # Store questions selected for diagrams
if 'diagram_questions' not in st.session_state:
    st.session_state.diagram_questions = []  # Store questions with diagrams
if 'generated_solutions' not in st.session_state:
    st.session_state.generated_solutions = {}
if 'latex_diagrams' not in st.session_state:
    st.session_state.latex_diagrams = {}  # Store rendered diagrams
if 'conversation_data' not in st.session_state:
    st.session_state.conversation_data = None

frontend_url = os.getenv("FRONTEND_URL")
backend_url = os.getenv("BACKEND_FLASK_QBMS_APP")

def load_conversation_data():
    query_params = st.query_params
    conversation_id = query_params.get('conversation_id')
    
    if conversation_id and st.session_state.conversation_data is None:
        try:
            response = requests.get(f'{backend_url}/api/conversation/{conversation_id}')
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    st.session_state.conversation_data = result.get('data')
                    # st.success(f"Loaded conversation: {st.session_state.conversation_data.get('topic', 'Unknown Topic')}")
                    return True
                else:
                    st.error("Failed to load conversation data")
            else:
                st.error(f"Error fetching conversation: {response.status_code}")
        except Exception as e:
            st.error(f"Error loading conversation: {str(e)}")
    
    return False

load_conversation_data()

# Load existing documents
# def load_existing_documents():
#     if os.path.exists("data/documents_index.json"):
#         with open("data/documents_index.json", "r") as f:
#             return json.load(f)
#     return {}

def load_existing_documents():
    try:
        response = requests.get(f"{backend_url}/api/documents-index")
        if response.status_code == 200:
            return response.json()
        else:
            return {}
    except Exception as e:
        st.error(f"Error fetching documents index: {e}")
        return {}

# Save documents index
def save_documents_index():
    with open("data/documents_index.json", "w") as f:
        json.dump(st.session_state.documents, f)

# Load existing documents on startup
if not st.session_state.documents:
    st.session_state.documents = load_existing_documents()

# Function to load previously generated questions
def load_previous_questions():
    """Load all previously generated questions from the generated directory"""
    all_questions = []
    if os.path.exists("data/generated"):
        for filename in os.listdir("data/generated"):
            if filename.endswith("_questions.json") or filename.endswith("_questions_with_diagrams.json"):
                try:
                    with open(os.path.join("data/generated", filename), "r") as f:
                        data = json.load(f)
                        if "questions" in data and isinstance(data["questions"], list):
                            all_questions.extend(data["questions"])
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
    
    return all_questions

def render_diagram(matplotlib_code, question_id):
    """
    Render diagram code to an in-memory buffer using matplotlib.
    (Ensure this function is correctly implemented and accessible)
    """
    # --- Add your existing render_diagram implementation here ---
    # This should return a BytesIO buffer or None
    try:
        # Assuming render_matplotlib_code exists and returns a buffer
        buffer = render_matplotlib_code(matplotlib_code, question_id)
        return buffer
    except ImportError:
         # Fallback or placeholder implementation if import fails
        print("Warning: render_matplotlib_code not found. Using placeholder.")
        try:
            fig, ax = plt.subplots(figsize=(3, 2))
            ax.text(0.5, 0.5, f"Diagram for {question_id}\n(Placeholder - Check Renderer)",
                   horizontalalignment='center', verticalalignment='center', fontsize=8)
            ax.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=200)
            plt.close(fig)
            buffer.seek(0)
            return buffer
        except Exception as e:
            print(f"Error creating placeholder diagram: {e}")
            return None
    except Exception as e:
        print(f"Error in render_diagram: {e}")
        return None

def display_matplotlib_diagram(image_path, caption="Diagram", target_height=400):
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as file:
                image_bytes = file.read()
                print(f"Read {len(image_bytes)} bytes from file")
            
            # Open the image to get its dimensions
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            
            # Calculate new width to maintain aspect ratio
            aspect_ratio = width / height
            new_width = int(aspect_ratio * target_height)
            
            # Display image with calculated width
            st.image(image_bytes, caption=caption, width=new_width)
            
            # Clean up
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image file: {image_path}")
        except Exception as cleanup_error:
            print(f"Warning: Error processing or deleting image file {image_path}: {str(cleanup_error)}")
    else:
        # Don't display warning here, the calling function handles absence
        pass

# Function to display questions with diagrams and selection checkboxes - FIXED to avoid nested expanders
def display_questions_with_selection(questions, show_diagrams=True, enable_selection=False,  content="", subject="", tab="", enable_quiz_mode=False):
    # Initialize widget key counter in session state if it doesn't exist
    if 'widget_key_counter' not in st.session_state:
        st.session_state.widget_key_counter = 0

    if 'question_modifications' not in st.session_state:
        st.session_state.question_modifications = {}

    if 'function_call_counter' not in st.session_state:
        st.session_state.function_call_counter = 0

    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = {}
    if 'quiz_score' not in st.session_state:
        st.session_state.quiz_score = 0
    if 'quiz_completed' not in st.session_state:
        st.session_state.quiz_completed = False
    
    function_call_id = st.session_state.function_call_counter
    st.session_state.function_call_counter += 1
    
    selected_question_ids = [] # Renamed for clarity

    total_questions = len(questions)

    if enable_quiz_mode:
        st.markdown("## 📝 Quiz Mode")
        progress_col1, progress_col2 = st.columns([3, 1])
        with progress_col1:
            answered_questions = len(st.session_state.quiz_answers)
            st.progress(answered_questions / total_questions)
        with progress_col2:
            st.metric("Progress", f"{answered_questions}/{total_questions}")

    for i, question in enumerate(questions):
        question_id = question.get('id', f'q{i+1}')
        # Generate a simple but unique key by combining question ID, index, and session timestamp
        # This will ensure uniqueness across page reruns
        if 'session_timestamp' not in st.session_state:
            import time
            st.session_state.session_timestamp = str(int(time.time()))
        
        unique_key_base = f"{question_id}_{i}_{st.session_state.session_timestamp}"

        # st.markdown(f"### Question {i+1} ({question.get('difficulty', 'medium').capitalize()})")
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown(f"### Question {i+1} ({question.get('difficulty', 'medium').capitalize()})")
        
        with col2:
            if tab == "generation":
                # Difficulty conversion dropdown
                difficulty_key = f"difficulty_{unique_key_base}"
                current_difficulty = question.get('difficulty', 'medium')
                new_difficulty = st.selectbox(
                    "Change difficulty level:",
                    options=["easy", "medium", "hard"],
                    index=["easy", "medium", "hard"].index(current_difficulty),
                    key=difficulty_key
                )
                
                # If difficulty changed, handle the conversion
                if new_difficulty != current_difficulty:
                    convert_btn_key = f"convert_btn_{unique_key_base}"
                    if st.button("Convert Question", key=convert_btn_key):
                        try:
                            with st.spinner(f"Converting question to {new_difficulty} difficulty..."):
                                content = st.session_state.get('content', {})
                                subject = question.get('subject', 'general')
                                
                                modified_question = convert_question_difficulty(
                                    question, 
                                    content,
                                    subject, 
                                    new_difficulty
                                )
                                
                                questions[i] = modified_question
                                
                                if modified_question.get('requires_diagram', False):
                                    st.session_state.question_modifications[question_id] = {
                                        'action': 'regenerate_diagram',
                                        'difficulty': new_difficulty
                                    }
                                
                                st.success(f"Question converted to {new_difficulty} difficulty!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Failed to convert question: {str(e)}")



        # --- Checkbox Logic ---
        if enable_selection:
            # Checkbox is always available if selection is enabled
            # Label changes based on whether diagram code already exists
            has_generated_code = bool(question.get('diagram_matplotlib'))
            checkbox_label = "Regenerate diagram" if has_generated_code else "Select to generate diagram"
            is_selected = st.checkbox(checkbox_label, key=f"select_{unique_key_base}")
            if is_selected:
                selected_question_ids.append(question_id) # Collect IDs for processing later

        st.markdown(f"**{question['question']}**")

        # --- Diagram Display Logic ---
        # Only show the diagram section if diagram_matplotlib *actually exists*
        if show_diagrams and question.get('diagram_matplotlib'):
            st.subheader("Diagram")
            try:
                # Attempt to render the existing diagram code
                diagram_buffer = render_diagram(question['diagram_matplotlib'], question_id)

                if diagram_buffer:
                    display_matplotlib_diagram(
                        diagram_buffer,
                        caption=f"Diagram for Question {i+1}"
                    )

                    # --- Modified Key Generation Logic ---
                    # Increment the counter for each widget to ensure uniqueness
                    st.session_state.widget_key_counter += 1
                    
                    modify_key = f"modify_btn_{question_id}_{i}"


                    instruction_state_key = f"instructions_state_{question_id}_{i}"

                    if tab != "generation":
                        instruction_state_key += f"{function_call_id}"

                    if tab != "generation":
                        modify_key += f"{function_call_id}"

                    modification_instructions = st.text_area(
                        "Instructions to modify diagram:",
                        key=instruction_state_key,
                        height=100
                    )


                    if st.button("Modify Diagram", key=modify_key):
                        print("here", modification_instructions)
                        if modification_instructions:
                            with st.spinner("Regenerating diagram with new instructions..."):
                                try:
                                    modified_diagram_code = generate_diagram_with_instructions(
                                        question,
                                        modification_instructions
                                    )
                                    if modified_diagram_code:
                                        question['diagram_matplotlib'] = modified_diagram_code
                                        st.success("Diagram modification code generated! Re-rendering...")
                                        st.rerun()
                                    else:
                                        st.error("Failed to generate modified diagram code.")
                                except ImportError:
                                    st.error("Diagram modification function not available.")
                                except Exception as gen_e:
                                    st.error(f"Error during diagram modification: {gen_e}")
                        else:
                            st.warning("Please enter modification instructions.")

                else:
                    # Code exists, but rendering failed
                    st.warning(f"Diagram code exists for Question {i+1}, but failed to render.")
            except Exception as e:
                st.error(f"Error displaying diagram for Question {i+1}: {str(e)}")

        # --- Options Display ---
        st.subheader("Options")
        options = question.get('options', [])
        correct_answer = question.get('correct_answer', '') # Ensure correct_answer is available
        if not options:
             st.warning("No options generated for this question.")
        else:
            # for j, option in enumerate(options):
            #     option_letter = chr(65 + j)
            #     is_correct = option == correct_answer 
            #     if is_correct:
            #         st.markdown(f"- {option_letter}. {option}")
            #     else:
            #         st.markdown(f"- {option_letter}. {option}")
            if enable_quiz_mode:
                # Quiz mode - radio buttons for selection
                selected_option = st.radio(
                    f"Select your answer for Question {i+1}:",
                    options=options,
                    key=f"quiz_option_{unique_key_base}",
                    index=None if question_id not in st.session_state.quiz_answers else options.index(st.session_state.quiz_answers[question_id])
                )
                
                # Store the selected answer
                if selected_option:
                    st.session_state.quiz_answers[question_id] = selected_option
                    
                    
            else:
                # Regular mode - just display options
                for j, option in enumerate(options):
                    option_letter = chr(65 + j)
                    is_correct = option == correct_answer
                    if is_correct:
                        st.markdown(f"✅ **{option_letter}. {option}** (Correct)")
                    else:
                        st.markdown(f"- {option_letter}. {option}")

        st.caption(f"Source: {question.get('source', 'Not specified')}")
        st.markdown("---")
    
    if enable_quiz_mode:
        st.markdown("## Quiz Completion")
        
        answered_count = len(st.session_state.quiz_answers)
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.write(f"Questions answered: {answered_count}/{total_questions}")
        
        with col2:
            if answered_count == total_questions:
                if st.button("🎯 Complete Quiz", type="primary"):
                    calculate_and_submit_quiz_results(questions)
        
        with col3:
            if st.button("🔄 Reset Quiz"):
                st.session_state.quiz_answers = {}
                st.session_state.quiz_score = 0
                st.session_state.quiz_completed = False
                st.rerun()

    return selected_question_ids # Return the list of IDs selected via checkbox

def calculate_and_submit_quiz_results(questions):
    """Calculate quiz score and redirect to results page"""
    try:
        # Calculate score
        correct_answers = 0
        total_questions = len(questions)
        detailed_results = []
        
        for question in questions:
            question_id = question.get('id')
            user_answer = st.session_state.quiz_answers.get(question_id)
            correct_answer = question.get('correct_answer', '')
            
            is_correct = user_answer == correct_answer
            if is_correct:
                correct_answers += 1
            
            detailed_results.append({
                'question_id': question_id,
                'question': question['question'],
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'difficulty': question.get('difficulty', 'medium')
            })
        
        # Calculate percentage
        score_percentage = (correct_answers / total_questions) * 100
        
        # Prepare results data
        quiz_results = {
            'quiz_id': f"quiz_{int(datetime.now().timestamp())}",
            'timestamp': datetime.now().isoformat(),
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'score_percentage': score_percentage,
            'detailed_results': detailed_results,
            'conversation_topic': st.session_state.conversation_data.get('topic', 'Unknown') if st.session_state.conversation_data else 'Document-based Quiz'
        }
        
        # Send results to API server
        # response = requests.post('http://localhost:5001/api/quiz-results', {
        #     'Content-Type': 'application/json',
        # }, json=quiz_results)
        # print(response)
        
        # if response.status_code == 200:
        #     result = response.json()
        #     quiz_results_id = result.get('quiz_id')
            
            # Show immediate results
        st.success(f"🎉 Quiz Completed!")
        st.metric("Your Score", f"{correct_answers}/{total_questions}", f"{score_percentage:.1f}%")
        
        if score_percentage >= 80:
            st.success("🌟 Excellent performance!")
        elif score_percentage >= 60:
            st.info("👍 Good job! Keep practicing.")
        else:
            st.warning("📚 Consider reviewing the material again.")
        
        st.session_state.quiz_completed = True
        st.session_state.quiz_score = score_percentage
        
        redirect_url = frontend_url
        st.info("Redirecting to results page in 10 seconds...")
        st.markdown(f"""
            <meta http-equiv="refresh" content="3;url={redirect_url}">
            <script>
                setTimeout(function() {{
                    window.location.href = "{redirect_url}";
                }}, 10000);
            </script>
        """, unsafe_allow_html=True)
        
            
        # else:
        #     st.error("Failed to save quiz results. Please try again.")
            
    except Exception as e:
        st.error(f"Error calculating quiz results: {str(e)}")

# New function to generate a diagram with modification instructions
# def generate_diagram_with_instructions(question, instructions):
#     """
#     Generate a modified diagram based on user instructions.
    
#     Args:
#         question (dict): The question dictionary containing original diagram data
#         instructions (str): User instructions for modifying the diagram
        
#     Returns:
#         str: Modified diagram code
#     """
#     try:
#         # Prepare the prompt for diagram modification
#         description = question.get('diagram_description', '')
#         q_text = question.get('question', '')
#         subject = question.get('subject', 'Physics')
#         original_code = question.get('diagram_matplotlib', '')
        
#         # Load diagram generation template
        
#         # If template doesn't exist, create a default one
        
#         template = """Modify the existing diagram code based on the following instructions:

# Original diagram description: {description}
# Subject area: {subject}
# Question context: {question}
# User modification instructions: {instructions}

# Original diagram code:
# {original_code}

# Please modify the code to incorporate the user's instructions. Return the complete, modified code.
# Ensure the diagram remains suitable for an exam question paper with minimal styling,
# clear labels, and no color (only use black lines, markers, and text), and stictly dont give me answer for the question only give necessesary information.

# Return only the modified code, no explanations or additional text.
# """
        
#         # Format prompt with all necessary information
#         prompt = template.format(
#             description=description,
#             subject=subject,
#             question=q_text,
#             instructions=instructions,
#             original_code=original_code
#         )
        
#         print(f"Generating modified diagram for question {question.get('id')}: {q_text[:50]}...")
        
#         # Call the model to generate the modified diagram
#         response = requests.post('http://192.168.31.137:11434/api/generate', 
#                                json={
#                                    "model": "gemma3:27b",
#                                    "prompt": prompt,
#                                    "stream": False
#                                })
        
#         if response.status_code == 200:
#             response_data = response.json()
#             modified_code = response_data.get('response', '')
            
#             # Remove any code block markers if present
#             modified_code = re.sub(r'```python\s*|\s*```', '', modified_code)
#             modified_code = modified_code.strip()
            
#             # Save the modification instructions in the question for reference
#             question['diagram_modification_history'] = question.get('diagram_modification_history', [])
#             question['diagram_modification_history'].append({
#                 'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 'instructions': instructions
#             })
            
#             return modified_code
#         else:
#             print(f"Error calling Ollama API: {response.status_code}")
#             print(response.text)
#             return ""
            
#     except Exception as e:
#         print(f"Error generating modified diagram: {str(e)}")
#         traceback.print_exc()
#         return ""

def render_diagram(matplotlib_code, question_id):
    """
    Render diagram code to an in-memory buffer using matplotlib
    
    Args:
        latex_code (str): Code for the diagram (now expected to be matplotlib Python code)
        question_id (str): ID of the question
        
    Returns:
        BytesIO: Buffer containing the rendered image
    """
    try:
        return render_matplotlib_code(matplotlib_code, question_id)
            
    except Exception as e:
        print(f"Error rendering diagram: {e}")
        traceback.print_exc()
        return None

def render_matplotlib_code(code, question_id, diagram_type=None, figsize=(4, 3), dpi=150):
    try:
        file_base = str(uuid.uuid4())
        tex_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.tex")
        pdf_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.pdf")
        log_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.log")
        aux_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.aux")
        image_path = os.path.join(DIAGRAM_FOLDER, f"{file_base}.png") 

        os.makedirs(DIAGRAM_FOLDER, exist_ok=True)

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", DIAGRAM_FOLDER, tex_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            print(f"pdflatex failed for question {question_id}:")
            error_lines = result.stdout.split('\n')
            for i, line in enumerate(error_lines):
                if "error:" in line.lower() or "emergency stop" in line.lower():
                    print("  " + line)
                    for j in range(1, 4):
                        if i + j < len(error_lines):
                            context_line = error_lines[i + j].strip()
                            if context_line:
                                print("  " + context_line)
            return None
        
        if not os.path.exists(pdf_path):
            print(f"PDF file not found at {pdf_path}")
            return None
        
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)

        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

        pix.save(image_path)
        doc.close()
        
        print(f"Successfully converted PDF to high-quality PNG: {image_path}")

        temp_files = [tex_path, pdf_path, log_path, aux_path]
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not delete temporary file {file_path}: {str(cleanup_error)}")

        print(f"Successfully compiled LaTeX code and converted to image")
        return image_path
        
    except Exception as e:
        print(f"Error rendering matplotlib code for question {question_id}: {str(e)}")
        traceback.print_exc()
        return None

# Function to process diagrams for specific questions
def process_diagrams_for_selected_questions(all_questions, selected_ids):
    updated_questions = update_questions_with_user_selections(all_questions, selected_ids)
    diagram_matplotlib_code = generate_diagrams_for_selected_questions(updated_questions)
    
    for question in updated_questions:
        question_id = question.get('id')
        if question_id in diagram_matplotlib_code:
            question['requires_diagram'] = True
            question['diagram_matplotlib'] = diagram_matplotlib_code[question_id]
    
    return updated_questions

# Function to filter questions with diagrams
def filter_diagram_questions(questions):
    """Filter questions that require diagrams"""
    return [q for q in questions if q.get('requires_diagram', False)]

def save_to_question_database(questions, source_document=None):
    """
    Save questions to the centralized question database with title matching
    
    Args:
        questions (list): List of question dictionaries
        source_document (str): Source document ID or name
    """
    # Create a timestamp for the database file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Load existing database if it exists
    db_path = "data/question_database/all_questions.json"
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            try:
                existing_db = json.load(f)
                existing_questions = existing_db.get("questions", [])
            except json.JSONDecodeError:
                existing_questions = []
    else:
        existing_questions = []
    
    # Add source to each question if provided
    if source_document:
        for question in questions:
            if "source" not in question or not question["source"]:
                question["source"] = source_document
    
    # Add generation timestamp and ensure title exists
    for question in questions:
        question["generated_on"] = timestamp
        
        # Generate a title if not present
        if "title" not in question or not question["title"]:
            # Create a title from the first few words of the question (max 10 words)
            question_text = question.get('question', '')
            words = question_text.split()[:10]
            title = ' '.join(words)
            if len(title) > 100:  # Limit title length
                title = title[:97] + '...'
            question["title"] = title
    
    # Process each question - update if title matches, otherwise add as new
    new_questions_count = 0
    updated_questions_count = 0
    
    # Create a dictionary of existing questions by title for faster lookup
    existing_question_dict = {}
    for q in existing_questions:
        if "title" in q and q["title"]:
            existing_question_dict[q["title"]] = q
    
    final_questions = []
    processed_titles = set()  # Track processed titles to avoid duplicates
    
    # First process all existing questions
    for existing_q in existing_questions:
        title = existing_q.get("title", "")
        
        # Skip if we've already processed this title
        if title in processed_titles:
            continue
            
        # Check if this question should be updated
        found_update = False
        for new_q in questions:
            if new_q.get("title", "") == title:
                # Update the existing question with new data, preserving the ID
                updated_q = {**existing_q, **new_q}
                final_questions.append(updated_q)
                processed_titles.add(title)
                updated_questions_count += 1
                found_update = True
                break
                
        # If no update was found, keep the original
        if not found_update:
            final_questions.append(existing_q)
            processed_titles.add(title)
    
    # Now add any new questions that weren't updates
    for new_q in questions:
        title = new_q.get("title", "")
        if title and title not in processed_titles:
            final_questions.append(new_q)
            processed_titles.add(title)
            new_questions_count += 1
    
    # Save updated database
    with open(db_path, "w") as f:
        json.dump({"questions": final_questions}, f, indent=2)
    
    # Return counts of new and updated questions
    return new_questions_count, updated_questions_count

# Function to load all questions from the database
def load_question_database():
    """Load all questions from the centralized question database"""
    db_path = "data/question_database/all_questions.json"
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            try:
                data = json.load(f)
                return data.get("questions", [])
            except json.JSONDecodeError:
                return []
    return []

# Improve the duplicate question detection function
def is_duplicate_question(question, existing_questions, similarity_threshold=0.8):
    """
    Check if a question is too similar to any existing questions
    
    Args:
        question (dict): The new question to check
        existing_questions (list): List of existing question dictionaries
        similarity_threshold (float): Threshold for considering questions similar (0-1)
        
    Returns:
        bool: True if the question is a duplicate, False otherwise
    """
    from difflib import SequenceMatcher
    
    question_text = question.get('question', '').lower()
    question_id = question.get('id', '')
    
    if not question_text:
        return False
    
    for existing in existing_questions:
        # If IDs match and aren't empty, it's the same question
        if question_id and question_id == existing.get('id', ''):
            return True
            
        existing_text = existing.get('question', '').lower()
        if not existing_text:
            continue
        
        # Calculate similarity ratio
        similarity = SequenceMatcher(None, question_text, existing_text).ratio()
        if similarity >= similarity_threshold:
            return True
    
    return False

# App title
st.markdown("# AI Question Bank Management System")

# Tabs for main navigation
upload_tab, generate_tab, view_all_tab = st.tabs(["Upload Document", "Generate Questions", "View All Questions"])

# Upload Document Tab
with upload_tab:
    st.header("Upload PDF Document")

    exam_options = ["Class X", "Class XI", "Class XII" , "Other"]
    exam_type = st.selectbox("Select Exam Type", exam_options)

    if exam_type == "Other":
        exam_type = st.text_input("Enter Exam Name")

    subject = st.text_input("Subject (e.g. Physics, Maths)")

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
                document_id = f"{subject.lower().replace(' ', '')}_{len(st.session_state.documents) + 1}"
                text_by_page, images_by_page = parse_pdf(temp_file_path)

                st.session_state.documents[document_id] = {
                    "type": "pdf",
                    "name": uploaded_file.name,
                    "subject": subject,
                    "exam_type": exam_type,
                    "content": text_by_page,
                    "images": images_by_page,
                    "path": f"data/processed/{document_id}.json"
                }

                # Save processed content
                with open(f"data/processed/{document_id}.json", "w") as f:
                    json.dump({
                        "type": "pdf",
                        "name": uploaded_file.name,
                        "subject": subject,
                        "exam_type": exam_type,
                        "content": text_by_page,
                        "images": images_by_page
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
            subjects[subject].append((doc_id, doc["name"], doc.get("exam_type", "Unknown")))
        
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
            
            num_questions = st.number_input("Number of Questions", min_value=1, max_value=50, value=10)
            # page_range = st.slider("Page Range", 1, len(doc['content']), (1, min(5, len(doc['content']))))
            page_range = st.slider("Page Range", 1, len(doc['content']), (1, len(doc['content'])))
            difficulty_options = create_difficulty_selector(num_questions)
            
            if st.session_state.conversation_data:
                st.info(f"🎯 Questions will be generated based on your conversation about: **{st.session_state.conversation_data.get('topic')}**")
                conversation_data = st.session_state.conversation_data
            else:
                st.info("💡 No conversation data found. Questions will be generated from the document only.")
                conversation_data = None
            
            # Generate Questions button
            if st.button("Generate Questions"):
                with st.spinner(f"Generating {num_questions} questions..."):
                    # Prepare content from selected pages
                    content_to_use = {i+1: page for i, page in enumerate(doc['content']) 
                                    if i+1 >= page_range[0] and i+1 <= page_range[1]}
                    
                    # Generate questions with duplicate checking
                    questions = generate_questions_with_duplicate_check(
                        content=content_to_use,
                        subject=doc['subject'],
                        num_questions=num_questions,
                        difficulty_distribution=difficulty_options,
                        conversation_data=conversation_data
                    )
                    
                    # Add subject and ensure each question has a title
                    for question in questions:
                        question['subject'] = doc['subject']
                        
                        # Generate title if not present
                        if 'title' not in question or not question['title']:
                            question_text = question.get('question', '')
                            words = question_text.split()[:10]
                            title = ' '.join(words)
                            if len(title) > 100:  # Limit title length
                                title = title[:97] + '...'
                            question['title'] = title
                    
                    # Store generated questions
                    st.session_state.generated_questions = questions
                    st.session_state.selected_for_diagrams = []  # Reset selected questions
                    st.session_state.diagram_questions = filter_diagram_questions(questions)
                    
                    # Save questions to file
                    question_file_path = f"data/generated/{st.session_state.selected_doc}_questions.json"
                    with open(question_file_path, "w") as f:
                        json.dump({"questions": questions}, f)
                    
                    # Save to centralized question database
                    new_count, updated_count = save_to_question_database(questions, doc['name'])
                    
                    st.success(f"Generated {len(questions)} questions! Added {new_count} new questions and updated {updated_count} existing questions in the database.")
                    
            # Display questions and allow selection for diagrams
            if st.session_state.generated_questions:
                st.subheader("3. Select Questions for Diagrams")
                st.info("Check the questions you want to generate diagrams for:")

                content_to_use = {i+1: page for i, page in enumerate(doc['content']) 
                                    if i+1 >= page_range[0] and i+1 <= page_range[1]}
                
                selected_questions = display_questions_with_selection(
                    st.session_state.generated_questions, 
                    show_diagrams=True, 
                    enable_selection=True,
                    content=content_to_use,
                    subject=doc['subject'],
                    tab="generation",
                    enable_quiz_mode=True
                )
                
                # Store selected questions
                st.session_state.selected_for_diagrams = selected_questions
                
                # Show Generate Diagrams button only if questions are selected
                if selected_questions:
                    if st.button("Generate Diagrams for Selected Questions"):
                        with st.spinner(f"Generating diagrams for {len(selected_questions)} questions..."):
                            # Process diagrams for selected questions
                            updated_questions = process_diagrams_for_selected_questions(
                                st.session_state.generated_questions,
                                selected_questions
                            )
                            
                            # Update session state
                            st.session_state.generated_questions = updated_questions
                            st.session_state.diagram_questions = filter_diagram_questions(updated_questions)
                            
                            # Save questions to file
                            question_file_path = f"data/generated/{st.session_state.selected_doc}_questions_with_diagrams.json"
                            with open(question_file_path, "w") as f:
                                json.dump({"questions": updated_questions}, f)
                            
                            st.success(f"Generated diagrams for {len(selected_questions)} questions!")
                            st.rerun()  # Use st.rerun() instead of st.experimental_rerun()
                
                # Display tabs for viewing questions
                all_tab, diagram_tab = st.tabs(["All Questions", "Questions with Diagrams"])
                
                with all_tab:
                    st.subheader("All Generated Questions")
                    display_questions_with_selection(st.session_state.generated_questions, enable_selection=False)
                
                with diagram_tab:
                    diagram_questions = st.session_state.diagram_questions
                    if diagram_questions:
                        st.subheader(f"Questions with Diagrams ({len(diagram_questions)})")
                        display_questions_with_selection(diagram_questions, show_diagrams=True, enable_selection=False)
                    else:
                        st.info("No questions with diagrams were generated. Select questions and click 'Generate Diagrams for Selected Questions'.")
                
                # Generate solutions button
                if st.button("Generate Solutions"):
                    with st.spinner("Generating solutions..."):
                        solutions = solve_questions(st.session_state.generated_questions)
                        st.session_state.generated_solutions = solutions
                        
                        # Save solutions
                        solution_file_path = f"data/generated/{st.session_state.selected_doc}_solutions.json"
                        with open(solution_file_path, "w") as f:
                            json.dump(solutions, f)
                        
                        # Process solution diagrams if needed
                        diagram_generator = DiagramGenerator()
                        question_file_path = f"data/generated/{st.session_state.selected_doc}_questions.json"
                        processed_solution_path = diagram_generator.process_solution_file(
                            solution_file_path, 
                            question_file_path
                        )
                        
                        if processed_solution_path:
                            with open(processed_solution_path, 'r') as f:
                                st.session_state.generated_solutions = json.load(f)
                        
                        st.success("Solutions generated!")
                        
                        # Display solutions
                        st.subheader("Solutions")
                        for i, question in enumerate(st.session_state.generated_questions):
                            question_id = question.get('id', f'q{i+1}')
                            if question_id in st.session_state.generated_solutions:
                                solution = st.session_state.generated_solutions[question_id]
                                
                                # Display solution
                                st.markdown(f"### Solution for Question {i+1}")
                                
                                # Display correct answer
                                st.markdown(f"**Correct Answer:** {solution.get('correct_answer', 'Not provided')}")
                                
                                # Display explanation
                                st.markdown(f"**Explanation:** {solution.get('explanation', 'No explanation available')}")
                                
                                # Display key insights if available
                                if solution.get("key_insights"):
                                    st.markdown(f"**Key Insights:** {solution.get('key_insights')}")
                                
                                # Display diagram if available
                                if solution.get("diagram_matplotlib"):
                                    st.subheader("Diagram")
                                    # Use a container for the code
                                    st.markdown("**LaTeX code:**")
                                    st.code(solution["diagram_matplotlib"], language="latex")
                                    
                                    solution_image_path = render_diagram(
                                        solution["diagram_matplotlib"], 
                                        f"solution_{question_id}"
                                    )
                                    if solution_image_path and os.path.exists(solution_image_path):
                                        st.image(solution_image_path, caption="Solution Diagram")
                                    else:
                                        st.info("Solution diagram would be rendered here.")
                                
                                st.markdown("---")  # Add a separator between solutions

with view_all_tab:
    st.header("Question Database")
    
    # Load all questions from the database
    all_questions = load_question_database()
    
    if not all_questions:
        st.info("No questions have been generated yet. Generate questions in the 'Generate Questions' tab.")
    else:
        st.write(f"Found {len(all_questions)} questions in the database.")
        
        # Add filtering options
        subjects = sorted(list(set(q.get('subject', 'Unknown') for q in all_questions)))
        difficulties = sorted(list(set(q.get('difficulty', 'medium') for q in all_questions)))
        
        # Create column layout for filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_subject = st.multiselect("Filter by Subject", subjects, default=subjects)
        with col2:
            filter_difficulty = st.multiselect("Filter by Difficulty", difficulties, default=difficulties)
        
            
        # Add search functionality
        search_query = st.text_input("Search questions", "")
        
        # Apply filters and search
        filtered_questions = []
        for q in all_questions:
            if (q.get('subject', 'Unknown') in filter_subject and
                q.get('difficulty', 'medium') in filter_difficulty):
                
                # Apply search if provided
                if search_query:
                    question_text = q.get('question', '').lower()
                    if search_query.lower() in question_text:
                        filtered_questions.append(q)
                else:
                    filtered_questions.append(q)
        
        st.write(f"Showing {len(filtered_questions)} questions after filtering.")
        
        # Sort questions (newest first)
        filtered_questions.sort(key=lambda q: q.get('generated_on', ''), reverse=True)
        
        # Setup tabs for different views
        list_tab, analyze_tab = st.tabs(["Question List", "Question Analytics"])
        
        with list_tab:
            # Create a data table for better viewing
            if filtered_questions:
                # Convert to DataFrame for better display
                df_data = []
                for i, q in enumerate(filtered_questions):
                    df_data.append({
                        "ID": q.get('id', f'q{i}'),
                        "Question": q.get('question', 'No question text'),
                        "Subject": q.get('subject', 'Unknown'),
                        "Difficulty": q.get('difficulty', 'medium').capitalize(),
                        "Source": q.get('source', 'Unknown'),

                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)
                
                # Detail view for selected question
                st.subheader("Question Details")
                selected_question_idx = st.selectbox(
                    "Select a question to view details", 
                    range(len(filtered_questions)),
                    format_func=lambda i: filtered_questions[i].get('question', '')[:50] + "..."
                )
                
                if selected_question_idx is not None:
                    question = filtered_questions[selected_question_idx]
                    st.markdown(f"### {question.get('question', 'No question text')}")
                    
                    st.markdown("#### Options")
                    options = question.get('options', [])
                    correct_answer = question.get('correct_answer', '')
                    
                    for j, option in enumerate(options):
                        option_letter = chr(65 + j)
                        is_correct = option == correct_answer
                        if is_correct:
                            st.markdown(f"- **{option_letter}. {option} ✓**")
                        else:
                            st.markdown(f"- {option_letter}. {option}")
                    
                    # Display diagram if available
                    if question.get('requires_diagram', False):
                        st.subheader("Diagram")
                        
                        if question.get('diagram_matplotlib'):
                            try:
                                diagram_buffer = render_diagram(
                                    question['diagram_matplotlib'], 
                                    question.get('id', f'q{selected_question_idx}')
                                )
                                if diagram_buffer:
                                    display_matplotlib_diagram(
                                        diagram_buffer, 
                                        caption=f"Diagram for Question"
                                    )
                                else:
                                    st.warning("Failed to render diagram")
                            except Exception as e:
                                st.error(f"Error displaying diagram: {e}")
                        
                        elif question.get('diagram_description'):
                            st.info(f"Diagram description: {question['diagram_description']}")
                            st.warning("Diagram not yet generated")
                    
                    # Show metadata
                    st.subheader("Metadata")
                    metadata_cols = st.columns(3)
                    with metadata_cols[0]:
                        st.write(f"**Subject:** {question.get('subject', 'Unknown')}")
                    with metadata_cols[1]:
                        st.write(f"**Difficulty:** {question.get('difficulty', 'medium').capitalize()}")
                    with metadata_cols[2]:
                        st.write(f"**Source:** {question.get('source', 'Unknown')}")
                    
                    # Show generation timestamp if available
                    if 'generated_on' in question:
                        st.write(f"**Generated on:** {question.get('generated_on', 'Unknown')}")
            else:
                st.info("No questions match your current filters.")
        
        with analyze_tab:
            st.subheader("Question Analytics")
            
            # Create analysis visualizations
            if filtered_questions:
                col1, col2, col3 = st.columns(3)

                # Subject distribution
                with col1:
                    st.subheader("By Subject")
                    subject_counts = {}
                    for q in filtered_questions:
                        subject = q.get('subject', 'Unknown')
                        subject_counts[subject] = subject_counts.get(subject, 0) + 1
                    
                    fig, ax = plt.subplots(figsize=(4, 3))  # Smaller size
                    subjects = list(subject_counts.keys())
                    counts = list(subject_counts.values())
                    sorted_data = sorted(zip(subjects, counts), key=lambda x: x[1], reverse=True)
                    subjects, counts = zip(*sorted_data) if sorted_data else ([], [])
                    ax.bar(subjects, counts)
                    ax.set_xlabel('Subject')
                    ax.set_ylabel('Count')
                    ax.set_title('Subjects')
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    st.pyplot(fig)

                # Difficulty distribution
                with col2:
                    st.subheader("By Difficulty")
                    difficulty_counts = {}
                    for q in filtered_questions:
                        difficulty = q.get('difficulty', 'medium')
                        difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1

                    fig, ax = plt.subplots(figsize=(4, 3))  # Smaller size
                    difficulties = list(difficulty_counts.keys())
                    counts = list(difficulty_counts.values())
                    colors = {'easy': 'green', 'medium': 'blue', 'hard': 'red'}
                    difficulty_colors = [colors.get(d, 'gray') for d in difficulties]
                    ax.pie(counts, labels=difficulties, autopct='%1.1f%%', startangle=90, colors=difficulty_colors)
                    ax.axis('equal')
                    ax.set_title('Difficulty')
                    st.pyplot(fig)

            else:
                st.info("No questions available for analysis based on your current filters.")

        # Add ability to export filtered questions
        st.subheader("Export Questions")
        if filtered_questions:
            if st.button("Export Filtered Questions to JSON"):
                export_path = f"data/exports/questions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                os.makedirs("data/exports", exist_ok=True)
                
                with open(export_path, "w") as f:
                    json.dump({"questions": filtered_questions}, f, indent=2)
                
                st.success(f"Exported {len(filtered_questions)} questions to {export_path}")
                
                # Provide download link
                with open(export_path, "r") as f:
                    st.download_button(
                        label="Download JSON File",
                        data=f,
                        file_name=f"questions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )