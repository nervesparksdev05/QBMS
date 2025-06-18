import os
import re
import io
import json
import base64
import traceback
import numpy as np
import matplotlib.pyplot as plt
import requests
from matplotlib import rcParams

# Set up matplotlib for high-quality diagrams
rcParams['figure.figsize'] = (8, 6)
rcParams['font.size'] = 12
rcParams['axes.labelsize'] = 12
rcParams['axes.titlesize'] = 14
rcParams['xtick.labelsize'] = 10
rcParams['ytick.labelsize'] = 10

def extract_and_render_diagrams(code_text, question_id):
    """
    Extract Python code from the provided text and render it as an image.
    
    Args:
        code_text (str): Text containing Python/matplotlib code
        question_id (str): ID of the question for file naming
        
    Returns:
        str: Path to the rendered image file
    """
    try:
        # Create diagrams directory if it doesn't exist
        os.makedirs("data/diagrams", exist_ok=True)
        
        # Clean up the code: remove markdown code blocks if present
        code = code_text
        if "```python" in code_text:
            code_blocks = re.findall(r"```python(.*?)```", code_text, re.DOTALL)
            if code_blocks:
                code = code_blocks[0].strip()
        elif "```" in code_text:
            code_blocks = re.findall(r"```(.*?)```", code_text, re.DOTALL)
            if code_blocks:
                code = code_blocks[0].strip()
                
        # Clean up previous figure to avoid overlays
        plt.close('all')
        
        # Remove plt.show() and plt.savefig() to prevent premature rendering
        code = re.sub(r"plt\.show\(\)", "", code)
        code = re.sub(r"plt\.savefig\([^\)]+\)", "", code)
        
        # Define the output path
        output_path = f"data/diagrams/diagram_{question_id}.png"
        
        # Append code to save the plot to the file
        modified_code = code + f"""
# Save the figure to file with higher resolution
plt.savefig("{output_path}", format='png', dpi=200, bbox_inches='tight')
plt.close()
"""
        
        # Execute the code in a safe environment
        namespace = {
            "plt": plt,
            "np": np,
            "io": io,
            "math": __import__('math'),
            "__builtins__": __builtins__,
        }
        
        exec(modified_code, namespace)
        
        # Verify the file was created
        if os.path.exists(output_path):
            return output_path
        else:
            print(f"Warning: Diagram file not created for {question_id}")
            return None
            
    except Exception as e:
        print(f"Error rendering diagram for {question_id}: {str(e)}")
        traceback.print_exc()
        
        # Generate a placeholder image with the error message
        plt.figure(figsize=(8, 6))
        plt.text(0.5, 0.5, f"Diagram Error: {str(e)}", 
               horizontalalignment='center', verticalalignment='center', fontsize=12)
        plt.axis('off')
        
        # Save the placeholder
        error_path = f"data/diagrams/error_{question_id}.png"
        plt.savefig(error_path)
        plt.close()
        
        return error_path

def process_solution_file(solution_file_path, question_file_path):
    """
    Process solution file to render diagrams
    
    Args:
        solution_file_path (str): Path to solution JSON file
        question_file_path (str): Path to question JSON file
        
    Returns:
        str: Path to processed solution file
    """
    try:
        # Load solutions
        with open(solution_file_path, 'r') as f:
            solutions = json.load(f)
        
        # Load questions to get context
        with open(question_file_path, 'r') as f:
            questions_data = json.load(f)
        
        questions = questions_data.get('questions', [])
        questions_dict = {q.get('id'): q for q in questions}
        
        # Process each solution
        for question_id, solution in solutions.items():
            # Skip if no diagram is needed
            if not solution.get('diagram_code') and not solution.get('diagram_description'):
                continue
                
            # Get context from the question
            question = questions_dict.get(question_id, {})
            subject = question.get('subject', 'Physics')
            
            # If we have Python code, render it
            if solution.get('diagram_code'):
                image_path = extract_and_render_diagrams(solution['diagram_code'], f"solution_{question_id}")
                if image_path:
                    solution['diagram_image_path'] = image_path
            
            # If we have description but no code, generate it
            elif solution.get('diagram_description'):
                # Generate diagram code
                diagram_code = generate_diagram_code(
                    solution['diagram_description'],
                    subject,
                    question.get('question', '')
                )
                
                if diagram_code:
                    solution['diagram_code'] = diagram_code
                    image_path = extract_and_render_diagrams(diagram_code, f"solution_{question_id}")
                    if image_path:
                        solution['diagram_image_path'] = image_path
        
        # Save updated solutions
        processed_path = solution_file_path.replace('.json', '_processed.json')
        with open(processed_path, 'w') as f:
            json.dump(solutions, f, indent=2)
            
        return processed_path
        
    except Exception as e:
        print(f"Error processing solution file: {str(e)}")
        traceback.print_exc()
        return None

def generate_diagram_code(description, subject, question_text):
    """
    Generate matplotlib code for diagram based on description
    
    Args:
        description (str): Description of the diagram
        subject (str): Subject area (Physics, Math, Chemistry, etc.)
        question_text (str): Text of the question
        
    Returns:
        str: Python/matplotlib code for the diagram
    """
 
    
    # Define prompt template for matplotlib code generation
    template = """Create Python code using matplotlib to generate a diagram based on this description:
Description: {description}
Subject area: {subject}
Question context: {question}

Your response should ONLY contain valid, executable Python/matplotlib code without any explanation.
The code should:
1. Import necessary libraries (matplotlib.pyplot, numpy, etc.)
2. Create a clear, educational-quality diagram
3. Include appropriate labels, axes, and annotations
4. NOT include plt.show() or file saving commands - I'll handle that part
5. For {subject} diagrams, use appropriate approaches:
   - For mathematics: Functions, geometric shapes, coordinate systems
   - For physics: Force diagrams, circuits, vectors, motion paths
   - For chemistry: Molecular structures, reaction diagrams
   - For biology: Cell structures, anatomical diagrams

Return ONLY executable matplotlib code, wrapped in ```python and ``` tags.
"""
    
    # Format prompt
    prompt = template.format(
        description=description,
        subject=subject,
        question=question_text
    )
    
    try:
        # Call Ollama API
        response = requests.post('http://192.168.138.255:11434/api/generate', 
                              json={
                                  "model": "gemme3:4b",
                                  "prompt": prompt,
                                  "stream": False
                              })
        
        if response.status_code == 200:
            response_data = response.json()
            code_text = response_data.get('response', '')
            
            # Extract Python code if wrapped in markdown code blocks
            code_match = re.search(r'```python(.*?)```', code_text, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            else:
                code = code_text.strip()
                
            return f"```python\n{code}\n```"
        else:
            print(f"Error calling API: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error generating diagram code: {str(e)}")
        return None

class DiagramGenerator:
    def __init__(self):
        """Initialize DiagramGenerator class"""
        pass
        
    def render_latex_to_image(self, latex_file, output_path):
        """
        This is a placeholder method - we're now using matplotlib instead of LaTeX
        
        Args:
            latex_file (str): Path to LaTeX file
            output_path (str): Path to output image
            
        Returns:
            bool: Always returns False to indicate LaTeX rendering is not supported
        """
        print("LaTeX rendering not supported, using matplotlib instead")
        return False
        
    def process_solution_file(self, solution_file_path, question_file_path):
        """Wrapper method for process_solution_file function"""
        return process_solution_file(solution_file_path, question_file_path)