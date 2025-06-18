import requests
import json
import os
import re
from pathlib import Path
import traceback

def load_prompt_template(template_file):
    """Load prompt template from file"""
    template_path = os.path.join("prompts", template_file)
    try:
        with open(template_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # If template file doesn't exist yet, return a default template
        if template_file == "question_gen.txt":
            return """You are an expert question generator for educational purposes.
Generate {num_questions} questions based on the provided content.
The questions should be of varying difficulty: {difficulty_distribution}
Subject: {subject}

Content:
{content}

Generate questions in the following JSON format:
{
  "questions": [
    {
      "id": "q1",
      "question": "Question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "difficulty": "easy|medium|hard",
      "source": "Chapter 1",
      "requires_diagram": true,
      "diagram_description": "Description of what the diagram should show"
    }
  ]
}

IMPORTANT: Do not use LaTeX tikzpicture environment in your response. For questions that need diagrams, just set requires_diagram to true and provide a text description of what the diagram should show.
Make sure to create appropriate questions for the subject and content provided.
"""
        elif template_file == "solution_gen.txt":
            return """You are an expert solution provider for educational questions.
Generate detailed solutions for the following questions:

{questions}

Generate solutions in the following JSON format:
{
  "question_id": {
    "explanation": "Detailed step-by-step explanation",
    "diagram_description": "Description of what the diagram should show if needed"
  }
}

Provide thorough explanations with appropriate steps and reasoning.
"""

def generate_questions(content, subject, num_questions, difficulty_distribution):
    try:
        # Format difficulty distribution for prompt
        difficulty_format = ", ".join([f"{count} {level}" for level, count in difficulty_distribution.items()])
        
        # Format content for prompt
        content_formatted = "\n\n".join([f"--- {('Chapter' if len(content) > 1 else 'Page')} {num} ---\n{text}" 
                                      for num, text in content.items()])
        
        # Load question generation prompt template
        template = load_prompt_template("question_gen.txt")
        
        # Format prompt with stronger emphasis on question count
        prompt = template.format(
            num_questions=num_questions,
            difficulty_distribution=difficulty_format,
            subject=subject,
            content=content_formatted
        )

        # Add explicit instruction about question count
        prompt = prompt.replace("Generate {num_questions} questions", 
                               f"Generate EXACTLY {num_questions} questions. This is a requirement, not a suggestion.")
        
        print("prompt ->", prompt)
        
        # Call Ollama API
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               })
        
        if response.status_code == 200:
            response_data = response.json()
            # Extract JSON from response
            print("response_data", response_data)
            generated_text = response_data.get('response', '')
            
            json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'(\{.*"questions":\s*\[.+?\]\s*\})', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = generated_text
            
            try:
                # Parse JSON
                result = json.loads(json_str)
                questions = result.get('questions', [])
                
                # Ensure exactly num_questions are returned
                if len(questions) < num_questions:
                    # If too few questions, try a second request for the remaining questions
                    print(f"Model returned only {len(questions)} questions. Requesting {num_questions - len(questions)} more...")
                    
                    # Request for remaining questions
                    remaining_prompt = prompt.replace(
                        f"Generate EXACTLY {num_questions} questions", 
                        f"Generate EXACTLY {num_questions - len(questions)} additional questions"
                    )
                    
                    additional_questions = request_additional_questions(
                        remaining_prompt, 
                        num_questions - len(questions)
                    )
                    
                    # Combine questions
                    questions.extend(additional_questions)
                    
                # If still too many or too few, adjust the list
                if len(questions) > num_questions:
                    questions = questions[:num_questions]  # Truncate if too many
                
                # Ensure each question has required fields
                for i, question in enumerate(questions):
                    if 'id' not in question:
                        question['id'] = f"q{i+1}"
                    if 'requires_diagram' not in question:
                        question['requires_diagram'] = False
                    if 'diagram_description' not in question:
                        question['diagram_description'] = f"Diagram for question: {question['question']}"
                    # Add a new field to track if user has selected this question for diagram generation
                    question['user_selected_for_diagram'] = False
                
                return questions
            except json.JSONDecodeError:
                print("Failed to parse JSON from model response")
                print("Response:", generated_text[:500])  # Print part of the response for debugging
                return []
        
        else:
            print(f"Error calling Ollama API: {response.status_code}")
            print(response.text)
            return []
            
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        traceback.print_exc()
        return []

def request_additional_questions(prompt, num_needed):
    """Request additional questions if initial response had too few"""
    try:
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                              json={
                                  "model": "gemme3:4b",
                                  "prompt": prompt,
                                  "stream": False
                              })
        
        if response.status_code == 200:
            response_data = response.json()
            generated_text = response_data.get('response', '')
            
            # Extract JSON using the same pattern as the main function
            json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'(\{.*"questions":\s*\[.+?\]\s*\})', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = generated_text
            
            try:
                result = json.loads(json_str)
                return result.get('questions', [])[:num_needed]  # Only take what's needed
            except json.JSONDecodeError:
                print("Failed to parse JSON from additional questions response")
                return []
        
        return []
    except Exception as e:
        print(f"Error getting additional questions: {str(e)}")
        return []
    
def generate_solutions(questions):
    """
    Generate solutions for questions using Gemma 3:27b model via Ollama
    
    Args:
        questions (list): List of question dictionaries
    
    Returns:
        dict: Dictionary mapping question IDs to solutions
    """
    try:
        # Format questions for prompt
        questions_formatted = json.dumps(questions, indent=2)
        
        # Load solution generation prompt template
        template = load_prompt_template("solution_gen.txt")
        
        # Check if the template contains tikzpicture placeholder
        if "{tikzpicture}" in template:
            # Format prompt with both placeholders
            prompt = template.format(questions=questions_formatted, tikzpicture="\\begin{tikzpicture}...\\end{tikzpicture}")
        else:
            # Format prompt with just the questions
            prompt = template.format(questions=questions_formatted)
        
        # Print debug info
        print(f"=================================================> solutions generation")
        
        # Call Ollama API with timeout
        response = requests.post('http://192.168.31.137:11434/api/generate', 
                               json={
                                   "model": "gemme3:4b",
                                   "prompt": prompt,
                                   "stream": False
                               },
                               timeout=60)  # Add timeout
        
        if response.status_code == 200:
            response_data = response.json()
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",response_data)
            # Extract text from response
            generated_text = response_data.get('response', '')
            print(f"Received response of length: {len(generated_text)} characters")
            
            # Create a basic fallback solution dictionary
            fallback_solutions = {}
            for question in questions:
                question_id = question.get("id", "unknown")
                fallback_solutions[question_id] = {
                    "explanation": f"Solution for question: {question.get('text', '')}",
                    "diagram_latex": ""
                }
            
            # Try to parse JSON from the response
            try:
                # First, look for JSON code block
                json_match = re.search(r'```json\s*(.+?)\s*```', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                
                # Next, try to find JSON without code blocks
                json_match = re.search(r'(\{.*"q\d+":\s*\{.+?\}\s*\})', generated_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                
                # Try to extract solution data without proper JSON format
                solutions = {}
                for question in questions:
                    q_id = question.get("id", "unknown")
                    q_pattern = rf"QUESTION ID:\s*{q_id}\s*EXPLANATION:\s*(.+?)(?=QUESTION ID:|DIAGRAM:|$)"
                    explanation_match = re.search(q_pattern, generated_text, re.DOTALL)
                    
                    explanation = explanation_match.group(1).strip() if explanation_match else "No explanation available."
                    
                    # Look for diagram
                    diagram_pattern = rf"DIAGRAM:\s*true\s*LATEX:\s*(.+?)(?=QUESTION ID:|$)"
                    diagram_match = re.search(diagram_pattern, generated_text, re.DOTALL)
                    diagram_latex = diagram_match.group(1).strip() if diagram_match else ""
                    
                    solutions[q_id] = {
                        "explanation": explanation,
                        "diagram_latex": diagram_latex
                    }
                
                if solutions:
                    return solutions
                
                # If all else fails, use the fallback
                print("Couldn't parse structured data from response, using fallback solutions")
                return fallback_solutions
                
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Failed to parse response: {e}")
                return fallback_solutions
        
        else:
            print(f"Error calling Ollama API: {response.status_code}")
            print(response.text)
            return {}
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return {}
    except Exception as e:
        print(f"Error generating solutions: {e}")
        traceback.print_exc()  # Now traceback is imported
        return {}

def save_to_json(data, filename, directory="data/generated"):
    """
    Save data to a JSON file
    
    Args:
        data: Data to save
        filename (str): Filename to save to
        directory (str): Directory to save to
        
    Returns:
        str: Path to saved file
    """
    try:
        # Ensure directory exists
        os.makedirs(directory, exist_ok=True)
        
        # Create full file path
        file_path = os.path.join(directory, filename)
        
        # Save data to file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved data to {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving data to {filename}: {e}")
        return None

def generate_and_save_questions(content, subject, chapter_name, num_questions, difficulty_distribution):
    """
    Generate questions and save them to a JSON file
    
    Args:
        content (dict): Dictionary mapping chapter/page numbers to content
        subject (str): Subject of the content
        chapter_name (str): Name or number of the chapter/section
        num_questions (int): Number of questions to generate
        difficulty_distribution (dict): Distribution of difficulty levels
        
    Returns:
        tuple: (questions_list, file_path)
    """
    # Generate questions
    questions = generate_questions(content, subject, num_questions, difficulty_distribution)
    
    # Add subject field to each question
    for question in questions:
        question['subject'] = subject
    
    # Create filename from subject and chapter
    filename = f"{subject.lower().replace(' ', '_')}_{chapter_name}_questions.json"
    
    # Save questions to file
    file_path = save_to_json({"questions": questions}, filename)
    
    return questions, file_path

def generate_and_save_solutions(questions, subject, chapter_name):
    """
    Generate solutions for questions and save them to a JSON file
    
    Args:
        questions (list): List of question dictionaries
        subject (str): Subject of the content
        chapter_name (str): Name or number of the chapter/section
        
    Returns:
        tuple: (solutions_dict, file_path)
    """
    # Generate solutions
    solutions = generate_solutions(questions)
    
    # Create filename from subject and chapter
    filename = f"{subject.lower().replace(' ', '_')}_{chapter_name}_solutions.json"
    
    # Save solutions to file
    file_path = save_to_json(solutions, filename)
    
    return solutions, file_path

def process_diagrams_for_files(questions_path, solutions_path=None):
    """
    Process diagrams for question and solution files
    
    Args:
        questions_path (str): Path to questions JSON file
        solutions_path (str): Path to solutions JSON file
        
    Returns:
        tuple: (processed_questions_path, processed_solutions_path)
    """
    try:
        from utils.diagram_generator import DiagramGenerator
        
        # Initialize diagram generator
        generator = DiagramGenerator()
        
        # Process questions file
        processed_questions_path = None
        if questions_path:
            processed_questions_path = generator.process_question_file(questions_path)
        
        # Process solutions file
        processed_solutions_path = None
        if solutions_path:
            processed_solutions_path = generator.process_solution_file(solutions_path, questions_path)
        
        return processed_questions_path, processed_solutions_path
    except Exception as e:
        print(f"Error processing diagrams: {e}")
        return None, None

def generate_complete_question_set(content, subject, chapter_name, num_questions, difficulty_distribution):
    """
    Generate a complete set of questions and solutions with diagrams
    
    Args:
        content (dict): Dictionary mapping chapter/page numbers to content
        subject (str): Subject of the content
        chapter_name (str): Name or number of the chapter/section
        num_questions (int): Number of questions to generate
        difficulty_distribution (dict): Distribution of difficulty levels
        
    Returns:
        tuple: (processed_questions_path, processed_solutions_path)
    """
    # Generate and save questions
    questions, questions_path = generate_and_save_questions(
        content, subject, chapter_name, num_questions, difficulty_distribution
    )
    
    # Generate and save solutions
    solutions, solutions_path = generate_and_save_solutions(
        questions, subject, chapter_name
    )
    
    # Process diagrams for both files
    processed_questions_path, processed_solutions_path = process_diagrams_for_files(
        questions_path, solutions_path
    )
    
    return processed_questions_path, processed_solutions_path

# Example usage:
if __name__ == "__main__":
    content = {
        "1": "Sample content for chapter 1...",
        "2": "Sample content for chapter 2..."
    }
    subject = "Physics"
    chapter_name = "chapter_1"
    num_questions = 5
    difficulty_distribution = {"easy": 2, "medium": 2, "hard": 1}
    
    # Generate complete question set with diagrams
    q_path, s_path = generate_complete_question_set(
        content, subject, chapter_name, num_questions, difficulty_distribution
    )
    
    print(f"Generated and processed questions: {q_path}")
    print(f"Generated and processed solutions: {s_path}")