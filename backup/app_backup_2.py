import streamlit as st
import os
import json
import tempfile
import base64
from io import BytesIO
import matplotlib.pyplot as plt
from flask_backend.pdf_parser import parse_pdf
from utils.model_interface import generate_questions_with_duplicate_check, generate_solutions, update_questions_with_user_selections, generate_diagrams_for_selected_questions
from utils.diagram_generator import DiagramGenerator
from components.difficulty_selector import create_difficulty_selector
import traceback, re
import numpy as np 
import math
from difflib import SequenceMatcher
import pandas as pd
from datetime import datetime
import requests
import builtins
import textwrap

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
os.makedirs("data/diagrams", exist_ok=True)  # Directory for diagram images
os.makedirs("data/question_database", exist_ok=True)

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

# Function to render LaTeX to image
def render_diagram(code, question_id):
    """
    Render matplotlib code to an image and save it
    
    Args:
        code (str): Matplotlib code for the diagram
        question_id (str): ID of the question
        
    Returns:
        str: Path to the saved image
    """
    try:
        from utils.generate_diagram import extract_and_render_diagrams
        
        # Use the diagram generator to render the code
        output_path = extract_and_render_diagrams(code, question_id)
        
        if output_path and os.path.exists(output_path):
            return output_path
        else:
            # If rendering fails, create a placeholder image
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.text(0.5, 0.5, f"Diagram for Question {question_id}", 
                   horizontalalignment='center', verticalalignment='center', fontsize=14)
            ax.axis('off')
            
            # Save the placeholder diagram
            placeholder_path = f"data/diagrams/placeholder_{question_id}.png"
            plt.savefig(placeholder_path)
            plt.close(fig)
            return placeholder_path
            
    except Exception as e:
        print(f"Error rendering diagram: {e}")
        return None

def display_matplotlib_diagram(buffer, caption="Diagram"):
    """
    Display a matplotlib diagram from a BytesIO buffer in Streamlit with reduced size
    
    Args:
        buffer (BytesIO): Buffer containing the rendered matplotlib image
        caption (str): Caption for the diagram
    """
    if buffer and buffer.getvalue():
        st.image(buffer, caption=caption, width=300)  # Set width to 300 pixels
    else:
        st.warning("No diagram available to display")

# Function to display questions with diagrams and selection checkboxes - FIXED to avoid nested expanders
# Function to display questions with diagrams and selection checkboxes - FIXED to avoid nested expanders
# Function to display questions with diagrams and selection checkboxes - FIXED to avoid nested expanders
# Function to display questions with diagrams and selection checkboxes - FIXED
def display_questions_with_selection(questions, context_prefix, show_diagrams=True, enable_selection=False):
    selected_questions = []

    for i, question in enumerate(questions):
        question_id = question.get('id', f'q{i+1}')
        # Use context_prefix for uniqueness across different calls
        unique_key_base = f"{context_prefix}_{question_id}_{i}"

        st.markdown(f"### Question {i+1} ({question.get('difficulty', 'medium').capitalize()})")

        if enable_selection:
            has_diagram = question.get('requires_diagram', False)
            checkbox_label = "Generate diagram for this question" if not has_diagram else "Regenerate diagram"
            select_key = f"{unique_key_base}_select_cb" # Specific key for checkbox
            is_selected = st.checkbox(checkbox_label, key=select_key)
            if is_selected:
                selected_questions.append(question_id)

        st.markdown(f"**{question['question']}**")

        if show_diagrams and question.get('requires_diagram', False):
            st.subheader("Diagram")

            if question.get('diagram_latex'):
                try:
                    diagram_buffer = render_latex_diagram(question['diagram_latex'], question_id)
                    if diagram_buffer:
                        display_matplotlib_diagram(
                            diagram_buffer,
                            caption=f"Diagram for Question {i+1}"
                        )

                        # Add "Modify Diagram" button and input field for instructions
                        modify_key = f"{unique_key_base}_modify_btn" # Specific key for modify button
                        instructions_key = f"{unique_key_base}_instructions_ta" # Specific key for text area

                        modification_instructions = st.text_area(
                            "Modification instructions:",
                            "",
                            key=instructions_key  # Using the unique instructions key
                        )

                        if st.button("Modify Diagram", key=modify_key):
                            if modification_instructions:
                                with st.spinner("Regenerating diagram with new instructions..."):
                                    modified_diagram_code = generate_diagram_with_instructions(
                                        question,
                                        modification_instructions
                                    )

                                    if modified_diagram_code:
                                        question['diagram_latex'] = modified_diagram_code # Update in session state implicitly

                                        # Re-render the diagram immediately (optional, st.rerun might handle it)
                                        # diagram_buffer = render_latex_diagram(modified_diagram_code, question_id)
                                        # if diagram_buffer:
                                        #     # Displaying again might cause issues if not careful with state
                                        #     # display_matplotlib_diagram(diagram_buffer, caption=f"Modified Diagram for Question {i+1}")
                                        #     st.success("Diagram modified successfully! Rerunning...")
                                        #     st.rerun() # Force rerun to reflect update
                                        # else:
                                        #     st.error("Failed to render modified diagram.")
                                        st.success("Diagram code updated. Rerunning to display changes...")
                                        st.rerun() # Rerun needed to show modified diagram
                                    else:
                                        st.error("Failed to generate modified diagram.")
                            else:
                                st.warning("Please enter modification instructions.")
                    else:
                        st.warning("Failed to render diagram")

                except Exception as e:
                    st.error(f"Error displaying diagram: {e}")

            elif question.get('diagram_description'):
                st.info(f"Diagram description: {question['diagram_description']}")
                st.warning("Diagram not yet generated")

        st.subheader("Options")
        options = question.get('options', [])
        for j, option in enumerate(options):
            option_letter = chr(65 + j)
            is_correct = option == question.get('correct_answer', '')
            if is_correct:
                st.markdown(f"- **{option_letter}. {option} ✓**")
            else:
                st.markdown(f"- {option_letter}. {option}")

        st.caption(f"Source: {question.get('source', 'Not specified')}")
        st.markdown("---")  # Add a separator between questions

    return selected_questions

# New function to generate a diagram with modification instructions
def generate_diagram_with_instructions(question, instructions):
    """
    Generate a modified diagram based on user instructions.
    
    Args:
        question (dict): The question dictionary containing original diagram data
        instructions (str): User instructions for modifying the diagram
        
    Returns:
        str: Modified diagram code
    """
    try:
        # Prepare the prompt for diagram modification
        description = question.get('diagram_description', '')
        q_text = question.get('question', '')
        subject = question.get('subject', 'Physics')
        original_code = question.get('diagram_latex', '')
        
        # Load diagram generation template
        
        # If template doesn't exist, create a default one
        
        template = """Modify the existing diagram code based on the following instructions:

Original diagram description: {description}
Subject area: {subject}
Question context: {question}
User modification instructions: {instructions}

Original diagram code:
{original_code}

Please modify the code to incorporate the user's instructions. Return the complete, modified code.
Ensure the diagram remains suitable for an exam question paper with minimal styling,
clear labels, and no color (only use black lines, markers, and text).

Return only the modified code, no explanations or additional text.
"""
        
        # Format prompt with all necessary information
        prompt = template.format(
            description=description,
            subject=subject,
            question=q_text,
            instructions=instructions,
            original_code=original_code
        )
        
        print(f"Generating modified diagram for question {question.get('id')}: {q_text[:50]}...")
        
        # Call the model to generate the modified diagram
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               })
        
        if response.status_code == 200:
            response_data = response.json()
            modified_code = response_data.get('response', '')
            
            # Remove any code block markers if present
            modified_code = re.sub(r'```python\s*|\s*```', '', modified_code)
            modified_code = modified_code.strip()
            
            # Save the modification instructions in the question for reference
            question['diagram_modification_history'] = question.get('diagram_modification_history', [])
            question['diagram_modification_history'].append({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'instructions': instructions
            })
            
            return modified_code
        else:
            print(f"Error calling Ollama API: {response.status_code}")
            print(response.text)
            return ""
            
    except Exception as e:
        print(f"Error generating modified diagram: {str(e)}")
        traceback.print_exc()
        return ""

def render_latex_diagram(latex_code, question_id):
    """
    Render diagram code to an in-memory buffer using matplotlib
    
    Args:
        latex_code (str): Code for the diagram (now expected to be matplotlib Python code)
        question_id (str): ID of the question
        
    Returns:
        BytesIO: Buffer containing the rendered image
    """
    try:
        if latex_code.strip().startswith('\\') or '\\documentclass' in latex_code:
            fig = plt.figure(figsize=(6, 4))
            plt.text(0.5, 0.5, "Complex LaTeX diagram\n(Rendered as placeholder)", 
                    size=16, ha='center', va='center')
            plt.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight')
            plt.close(fig)
            buffer.seek(0)
            return buffer
        else:
            return render_matplotlib_code(latex_code, question_id)
            
    except Exception as e:
        print(f"Error rendering diagram: {e}")
        traceback.print_exc()
        return None

def render_matplotlib_code(code, question_id=""):
    """
    Render matplotlib Python code, typically extracted from markdown,
    to an in-memory buffer with reduced size.

    Args:
        code (str): A string potentially containing a Python code block
                    within ```python ... ``` markers.
        question_id (str): An identifier (optional, used for logging).

    Returns:
        BytesIO or None: A BytesIO buffer containing the PNG image data if successful,
                         None otherwise.
    """
    if not code or not isinstance(code, str):
        print(f"Error rendering matplotlib code (ID: {question_id}): Input code is empty or not a string.")
        return None

    extracted_code = None
    try:
        # --- 1. Extract Code STRICTLY within ```python ... ``` ---
        # Use re.IGNORECASE for flexibility (```Python, ```PYTHON etc.)
        code_match = re.search(r'```python\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)

        if code_match:
            raw_extracted_code = code_match.group(1)
            # Dedent the extracted code block to fix indentation issues
            dedented_code = textwrap.dedent(raw_extracted_code).strip()
            extracted_code = dedented_code
            print(f"Extracted and dedented code block for ID: {question_id}") # Debugging print
        else:
            # --- Strict Mode: If no ```python block, assume it's not executable ---
            # Check if the *entire* string looks like maybe it IS code
            # (e.g., starts with 'import' or 'plt.') as a potential fallback
            # for simple cases, but still warn. This is OPTIONAL and can be removed
            # if strict ```python requirement is preferred.
            trimmed_code = code.strip()
            if trimmed_code.startswith(('import ', 'import\n', 'plt.', 'np.', 'fig,', 'ax =', '#')) and '```' not in trimmed_code:
                 print(f"Warning for ID {question_id}: No '```python ... ```' block found, but input starts like code. Attempting to run entire input.")
                 extracted_code = textwrap.dedent(trimmed_code).strip() # Still dedent
            else:
                 print(f"Error rendering matplotlib code (ID: {question_id}): Could not find a valid '```python ... ```' block. Input contains non-code text or is incorrectly formatted.")
                 # You could optionally print the first few lines of 'code' here for debugging
                 # print("--- Start of input ---")
                 # print('\n'.join(code.splitlines()[:5]))
                 # print("----------------------")
                 return None # Fail explicitly if no block found and it doesn't look like code

        if not extracted_code: # If extraction somehow resulted in empty string
             print(f"Error rendering matplotlib code (ID: {question_id}): Extracted code block is empty.")
             return None

        # --- 2. Clean the extracted code ---
        # Remove any plt.show() calls to prevent blocking
        cleaned_code = re.sub(r"plt\.show\s*\(\s*\)", "", extracted_code, flags=re.MULTILINE)
        # Remove any plt.savefig() calls to avoid conflicts
        cleaned_code = re.sub(r"plt\.savefig\s*\([^)]*\)", "", cleaned_code, flags=re.MULTILINE) # Allow empty parens too

        # --- 3. Prepare the execution code ---
        # Using rcParams for better state management (applied within exec scope)
        # Imports are handled by the user's code or exec_globals
        prefix_code = f"""
import matplotlib.pyplot as plt
import numpy as np # Ensure np is available if user forgets import
import math      # Ensure math is available if user forgets import
plt.close('all') # Ensure clean state before script runs
plt.rcParams['figure.figsize'] = (4, 3) # Inches (width, height)
plt.rcParams['figure.dpi'] = 100 # Base DPI, savefig overrides later if needed
# print("Matplotlib state reset and params set.") # Debug print
"""
        # Prepare buffer for output
        # Add code to save to buffer
        suffix_code = f"""
# print("Code execution finished. Checking for figures...") # Debug print
# Ensure a figure exists before trying to save
figure_numbers = plt.get_fignums()
if figure_numbers: # Check if there are any active figures
    # print(f"Figures found: {{figure_numbers}}. Saving figure {{figure_numbers[-1]}} to buffer.") # Debug print
    # Select the last figure created if multiple exist, or the only one
    plt.figure(figure_numbers[-1]) # Explicitly select the figure to save
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    # print("Figure saved to buffer.") # Debug print
    plt.close('all') # Close all figures after saving
else:
    print(f"Warning for ID {question_id}: No Matplotlib figure generated by the code.")

buffer.seek(0)
# print("Buffer seek 0 done.") # Debug print
"""
        # --- 4. Execute the code ---
        full_code_to_exec = prefix_code + cleaned_code + "\n" + suffix_code

        buffer = BytesIO()

        # Define the execution environment globals
        exec_globals = {
            # Provide common modules, user code can still import them
            "plt": plt,
            "np": np,
            "math": math,
            "BytesIO": BytesIO,
            "buffer": buffer,
            "question_id": question_id,
            "__builtins__": builtins
        }

        print(f"--- Executing code for ID: {question_id} ---")
        # Uncomment below to see the exact code being executed (can be long)
        # print(full_code_to_exec)
        print(f"--- Running user code snippet (first/last few lines): ---")
        code_lines = cleaned_code.splitlines()
        if len(code_lines) > 10:
            print('\n'.join(code_lines[:5]))
            print("...")
            print('\n'.join(code_lines[-5:]))
        else:
            print(cleaned_code)
        print("--- End of user code snippet ---")


        compiled_code = compile(full_code_to_exec, f"<matplotlib_code_{question_id}>", 'exec')
        exec(compiled_code, exec_globals)

        # Check if the buffer actually received data
        buffer.seek(0) # Rewind buffer before checking value
        if buffer.getvalue():
            print(f"Successfully rendered plot to buffer for ID: {question_id}")
            return buffer
        else:
            # Check if a warning about no figure was printed during execution
            # (This check might be complex depending on how print is captured)
            # Simpler check: If buffer is empty, code likely ran but produced no plot.
            print(f"Warning/Error rendering matplotlib code (ID: {question_id}): Buffer is empty after execution. Code ran but might not have produced a plottable figure.")
            return None # Return None if no plot was saved

    # Error Handling block remains largely the same
    except SyntaxError as e:
        print(f"!!! Syntax Error rendering matplotlib code (ID: {question_id}) !!!")
        print(f"Error message: {e}")
        # Try to get more context from traceback if available
        line_offset = prefix_code.count('\n') # Calculate offset caused by prefix
        user_code_line = e.lineno - line_offset
        print(f"Error likely occurred near line {user_code_line} of the *extracted* user code.")

        if e.text:
            print(f"Problematic line ({e.lineno} in full execution context): {e.text.rstrip()}")
            # Show context from the *original* extracted code if possible
            print("--- User Code Context ---")
            lines = cleaned_code.splitlines() # Use cleaned code for context
            start = max(0, user_code_line - 4)
            end = min(len(lines), user_code_line + 3)
            for i in range(start, end):
                 # Highlight the approximate error line
                 prefix = ">> " if i == user_code_line -1 else "   "
                 print(f"{prefix}{i+1:03d}: {lines[i]}")
            print("-------------------------")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"!!! Runtime Error rendering matplotlib code (ID: {question_id}) !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        # Add similar line number calculation for runtime errors if possible
        tb = traceback.extract_tb(e.__traceback__)
        if tb:
            # Find the frame corresponding to the executed code
            exec_filename = f"<matplotlib_code_{question_id}>"
            frame = next((f for f in reversed(tb) if f.filename == exec_filename), None)
            if frame:
                 line_offset = prefix_code.count('\n')
                 user_code_line = frame.lineno - line_offset
                 print(f"Error likely occurred near line {user_code_line} of the *extracted* user code.")
                 print("--- User Code Context ---")
                 lines = cleaned_code.splitlines()
                 start = max(0, user_code_line - 4)
                 end = min(len(lines), user_code_line + 3)
                 for i in range(start, end):
                     prefix = ">> " if i == user_code_line -1 else "   "
                     print(f"{prefix}{i+1:03d}: {lines[i]}")
                 print("-------------------------")

        traceback.print_exc()
        return None

# --- Example Usage (No changes needed here) ---
if __name__ == '__main__':

    # Example 1: Code with ```python markers and plt.show()
    code1 = """
    Some text before the code block.
    ```python
    import matplotlib.pyplot as plt
    import numpy as np

    # This code is indented in the source string
    x = np.linspace(0, 2 * np.pi, 100)
    y = np.sin(x)

    plt.plot(x, y)
    plt.title("Sine Wave Example 1")
    plt.xlabel("Radians")
    plt.ylabel("Value")
    plt.grid(True)
    # plt.show() # This should be removed by the function
    ```
    Some text after the code block, like the explanation that caused the original error.
    This revised response provides a complete, runnable Python script...
    """

    # Example 2: Code without markers, but starts like code (will attempt fallback)
    code2 = """
# This code is NOT in a markdown block but starts like code
import matplotlib.pyplot as plt
import numpy as np

# Data for plotting
t = np.arange(0.0, 2.0, 0.01)
s = 1 + np.sin(2 * np.pi * t)

fig, ax = plt.subplots()
ax.plot(t, s)

ax.set(xlabel='time (s)', ylabel='voltage (mV)',
       title='Simple Plot Example 2')
ax.grid()

# This should be removed by the function
# plt.savefig("should_be_removed.png")
    """

    # Example 3: Code with a syntax error inside ```python
    code3 = """
    ```python
    # Code with Syntax error
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.linspace(0, 10, 50)
    y = x**2
    plt.plot(x, y # Missing closing parenthesis
    plt.title("Syntax Error Example")
    ```
    """

    # Example 4: Code that doesn't produce a plot (inside ```python)
    code4 = """
    ```python
    # Code that runs but makes no plot
    import numpy as np
    a = np.array([1, 2, 3])
    result = np.sum(a)
    # No plt.plot or similar is called
    print(f"Calculation result: {result}") # Should print during exec
    ```
    """

    # Example 5: Empty code string
    code5 = ""

    # Example 6: Code with valid python but runtime plot error (inside ```python)
    code6 = """
    ```python
    # Runtime error example
    import matplotlib.pyplot as plt
    import numpy as np
    plt.plot([1, 2], [1]) # Mismatched array sizes -> ValueError
    plt.title("Runtime Plot Error")
    ```
    """

    # Example 7: Mixed prose WITHOUT ```python markers (SHOULD FAIL)
    code7 = """
    Let's plot a line:
    import matplotlib.pyplot as plt
    plt.plot([1, 2, 3], [1, 4, 9])
    This plot shows a quadratic relationship.
    plt.title("Mixed prose")
    """

    # Example 8: Code starting with comments (should be handled by dedent)
    code8 = """
    ```python
        # Leading comment line
        # Another comment
    import matplotlib.pyplot as plt
    import numpy as np
    x = np.array([1, 2, 3])
    y = x * 2
    plt.plot(x, y)
    plt.title("Leading Comments Example")
    ```
    """

    # Example 9: Malformed markdown (should fail)
    code9 = """
    ```python
    print("Hello")
    # Missing closing backticks
    """

    examples = {
        "ex1_markers_indent": code1,
        "ex2_no_markers_looks_like_code": code2,
        "ex3_syntax_error": code3,
        "ex4_no_plot": code4,
        "ex5_empty": code5,
        "ex6_runtime_error": code6,
        "ex7_mixed_prose_no_markers": code7, # EXPECT FAILURE
        "ex8_leading_comments": code8,
        "ex9_malformed_markdown": code9, # EXPECT FAILURE (regex won't match)
    }

    results = {}

    for qid, code_to_run in examples.items():
        print(f"\n--- Running Test: {qid} ---")
        buffer = render_matplotlib_code(code_to_run, qid)
        results[qid] = buffer

        if buffer:
            print(f"-> Success for {qid}: Received buffer of size {len(buffer.getvalue())} bytes.")
            # You could save the buffer to a file here for verification:
            # with open(f"test_output_{qid}.png", "wb") as f:
            #     f.write(buffer.getvalue())
            # print(f"   (Saved to test_output_{qid}.png)")
        else:
            print(f"-> Failed or No Plot for {qid}: Received None.") # Adjusted message

    print("\n--- Test Summary ---")
    for qid, result in results.items():
        # Define expected outcomes
        expected_success = ["ex1", "ex2", "ex4", "ex8"] # ex4 runs but makes no plot, so buffer is None - technically not a failure of the runner
        expected_failure = ["ex3", "ex5", "ex6", "ex7", "ex9"]
        status = "Success (Plot Rendered)" if result else "No Plot / Failed"
        expectation = "PASSED"
        qid_base = qid.split('_')[0] # Check base name like 'ex1'

        if result and qid_base not in expected_success:
             expectation = "UNEXPECTED SUCCESS (Check Logic)"
        elif not result and qid_base in expected_success:
             # Special case: ex4 is expected success *running*, but no plot buffer.
             if qid == "ex4_no_plot":
                 status = "Success (Code Ran, No Plot Expected)" # More specific status
             else:
                 expectation = "UNEXPECTED FAILURE (Check Logic)"
        elif not result and qid_base in expected_failure:
             expectation = "PASSED (Failure Expected)"


        print(f"{qid:<30}: {status:<30} ({expectation})")

def render_latex_with_renderer(latex_code, question_id):
    """
    Render LaTeX code to an image using matplotlib's LaTeX capabilities
    
    This is a simplified version. For full LaTeX with TikZ, you would need 
    to use a tool like pdflatex or a LaTeX rendering service.
    """
    try:
        # Prepare the output path
        output_dir = "data/diagrams"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{question_id}_diagram.png"
        
        # For simple LaTeX math, use matplotlib
        if '$' in latex_code and not '\\documentclass' in latex_code:
            # Extract math content between $ symbols if present
            match = re.search(r'\$(.*?)\$', latex_code, re.DOTALL)
            if match:
                math_content = match.group(1)
            else:
                math_content = latex_code
                
            fig = plt.figure(figsize=(6, 4))
            plt.text(0.5, 0.5, f"${math_content}$", 
                    size=20, ha='center', va='center')
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(output_path, dpi=200)
            plt.close(fig)
            
            return output_path
        
        # For more complex LaTeX, especially TikZ diagrams, create a placeholder
        # showing that external LaTeX rendering is needed
        else:
            fig = plt.figure(figsize=(6, 4))
            plt.text(0.5, 0.5, "Complex LaTeX diagram\n(Requires external LaTeX renderer)", 
                   size=16, ha='center', va='center')
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(output_path, dpi=200)
            plt.close(fig)
            
            # Save the LaTeX code to a .tex file for external processing
            tex_path = f"{output_dir}/{question_id}_diagram.tex"
            with open(tex_path, 'w') as f:
                f.write(latex_code)
                
            print(f"LaTeX code saved to {tex_path} for external rendering")
            return output_path
    
    except Exception as e:
        print(f"Error rendering LaTeX: {e}")
        traceback.print_exc()
        return None

# Function to process diagrams for specific questions
def process_diagrams_for_selected_questions(all_questions, selected_ids):
    updated_questions = update_questions_with_user_selections(all_questions, selected_ids)
    diagram_latex_codes = generate_diagrams_for_selected_questions(updated_questions)
    
    for question in updated_questions:
        question_id = question.get('id')
        if question_id in diagram_latex_codes:
            question['requires_diagram'] = True
            question['diagram_latex'] = diagram_latex_codes[question_id]
    
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
st.markdown("# Educational Question Generator")
st.markdown("Generate custom questions from your PDFs for competitive exams")

# Tabs for main navigation
upload_tab, generate_tab, view_all_tab = st.tabs(["Upload Document", "Generate Questions", "View All Questions"])

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
            page_range = st.slider("Page Range", 1, len(doc['content']), (1, min(5, len(doc['content']))))
            difficulty_options = create_difficulty_selector(num_questions)
            
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
                        difficulty_distribution=difficulty_options
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

                # CALL SITE 1: Selection
                selected_questions = display_questions_with_selection(
                    st.session_state.generated_questions,
                    context_prefix="select", # <--- ADDED PREFIX
                    show_diagrams=True,
                    enable_selection=True
                )

                # Store selected questions
                st.session_state.selected_for_diagrams = selected_questions

                # Show Generate Diagrams button only if questions are selected
                if selected_questions:
                    if st.button("Generate Diagrams for Selected Questions"):
                       # ... (diagram generation logic) ...
                       st.rerun()

                # Display tabs for viewing questions
                all_tab, diagram_tab = st.tabs(["All Questions", "Questions with Diagrams"])

                with all_tab:
                    st.subheader("All Generated Questions")
                    # CALL SITE 2: All Questions Tab
                    display_questions_with_selection(
                        st.session_state.generated_questions,
                        context_prefix="all_view", # <--- ADDED PREFIX
                        enable_selection=False
                    )

                with diagram_tab:
                    diagram_questions = filter_diagram_questions(st.session_state.generated_questions) # Filter fresh data
                    st.session_state.diagram_questions = diagram_questions # Update state if needed

                    if diagram_questions:
                        st.subheader(f"Questions with Diagrams ({len(diagram_questions)})")
                        # CALL SITE 3: Diagram Questions Tab
                        display_questions_with_selection(
                            diagram_questions,
                            context_prefix="diagram_view", # <--- ADDED PREFIX
                            show_diagrams=True,
                            enable_selection=False
                        )
                    else:
                        st.info("No questions with diagrams were generated or selected.")
                
                # Generate solutions button
                if st.button("Generate Solutions"):
                    with st.spinner("Generating solutions..."):
                        solutions = generate_solutions(st.session_state.generated_questions)
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
                                # Use a container instead of expander to avoid nesting
                                st.markdown(f"### Solution for Question {i+1}")
                                st.markdown(solution.get("explanation", "No explanation available"))
                                
                                if solution.get("diagram_latex"):
                                    st.subheader("Diagram")
                                    # Use a container for the code
                                    st.markdown("**LaTeX code:**")
                                    st.code(solution["diagram_latex"], language="latex")
                                    
                                    solution_image_path = render_latex_diagram(
                                        solution["diagram_latex"], 
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
        sources = sorted(list(set(q.get('source', 'Unknown') for q in all_questions)))
        
        # Create column layout for filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_subject = st.multiselect("Filter by Subject", subjects, default=subjects)
        with col2:
            filter_difficulty = st.multiselect("Filter by Difficulty", difficulties, default=difficulties)
        with col3:
            filter_source = st.multiselect("Filter by Source", sources, default=sources)
            
        # Add search functionality
        search_query = st.text_input("Search questions", "")
        
        # Apply filters and search
        filtered_questions = []
        for q in all_questions:
            if (q.get('subject', 'Unknown') in filter_subject and
                q.get('difficulty', 'medium') in filter_difficulty and
                q.get('source', 'Unknown') in filter_source):
                
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
                        "Has Diagram": "Yes" if q.get('requires_diagram', False) else "No",
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
                        
                        if question.get('diagram_latex'):
                            try:
                                diagram_buffer = render_latex_diagram(
                                    question['diagram_latex'], 
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
                # Subject distribution
                st.subheader("Questions by Subject")
                subject_counts = {}
                for q in filtered_questions:
                    subject = q.get('subject', 'Unknown')
                    subject_counts[subject] = subject_counts.get(subject, 0) + 1
                
                # Create bar chart
                fig, ax = plt.subplots(figsize=(10, 6))
                subjects = list(subject_counts.keys())
                counts = list(subject_counts.values())
                
                # Sort by count
                sorted_data = sorted(zip(subjects, counts), key=lambda x: x[1], reverse=True)
                subjects, counts = zip(*sorted_data) if sorted_data else ([], [])
                
                ax.bar(subjects, counts)
                ax.set_xlabel('Subject')
                ax.set_ylabel('Number of Questions')
                ax.set_title('Questions by Subject')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                st.pyplot(fig)
                
                # Difficulty distribution
                st.subheader("Questions by Difficulty")
                difficulty_counts = {}
                for q in filtered_questions:
                    difficulty = q.get('difficulty', 'medium')
                    difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
                
                # Create pie chart
                fig, ax = plt.subplots(figsize=(8, 8))
                difficulties = list(difficulty_counts.keys())
                counts = list(difficulty_counts.values())
                
                # Define colors for difficulties
                colors = {'easy': 'green', 'medium': 'blue', 'hard': 'red'}
                difficulty_colors = [colors.get(d, 'gray') for d in difficulties]
                
                ax.pie(counts, labels=difficulties, autopct='%1.1f%%', startangle=90, colors=difficulty_colors)
                ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
                ax.set_title('Questions by Difficulty')
                st.pyplot(fig)
                
                # Diagram distribution
                st.subheader("Questions with Diagrams")
                diagram_count = sum(1 for q in filtered_questions if q.get('requires_diagram', False))
                no_diagram_count = len(filtered_questions) - diagram_count
                
                fig, ax = plt.subplots(figsize=(8, 8))
                ax.pie([diagram_count, no_diagram_count], 
                       labels=['With Diagram', 'Without Diagram'], 
                       autopct='%1.1f%%', 
                       startangle=90,
                       colors=['orange', 'lightgray'])
                ax.axis('equal')
                ax.set_title('Questions with Diagrams')
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