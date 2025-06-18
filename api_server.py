import streamlit as st
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import base64
import tempfile
import os
import json
from utils.pdf_parser import parse_pdf
import time

# Create Flask app for API endpoints
api_app = Flask(__name__)
CORS(api_app)  

conversation_storage = {}

# File-based storage as backup
STORAGE_DIR = "data/conversations"
os.makedirs(STORAGE_DIR, exist_ok=True)

def load_existing_documents():
    if os.path.exists("data/documents_index.json"):
        with open("data/documents_index.json", "r") as f:
            return json.load(f)
    return {}

@api_app.route('/api/upload-document', methods=['POST'])
def upload_document():
    try:
        data = request.json
    
        file_data = data.get('file_data')
        filename = data.get('filename')
        subject = data.get('subject')
        exam_type = data.get('exam_type')
        
        if not all([file_data, filename, subject, exam_type]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        file_bytes = base64.b64decode(file_data)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(file_bytes)
        temp_file_path = temp_file.name
        temp_file.close()
        
        text_by_page, images_by_page = parse_pdf(temp_file_path)

        # Load current documents from file
        documents = {}
        document_id = f"{subject.lower().replace(' ', '')}_1"

        
        # Store document data
        documents[document_id] = {
            "type": "pdf",
            "name": filename,
            "subject": subject,
            "exam_type": exam_type,
            "content": text_by_page,
            "images": images_by_page,
            "path": f"data/processed/{document_id}.json"
        }

        # Save to processed file
        os.makedirs("data/processed", exist_ok=True)
        with open(f"data/processed/{document_id}.json", "w") as f:
            json.dump({
                "type": "pdf",
                "name": filename,
                "subject": subject,
                "exam_type": exam_type,
                "content": text_by_page,
                "images": images_by_page
            }, f)

        # Save updated documents index
        with open("data/documents_index.json", "w") as f:
            json.dump(documents, f)

        os.unlink(temp_file_path)

        return jsonify({
            'success': True,
            'message': f'Document processed successfully! You can now generate questions for {subject}.',
            'document_id': document_id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_app.route('/api/conversation', methods=['POST'])
def store_conversation():
    try:
        data = request.json
        conversation_id = data.get('conversationId')
        conversation_data = data.get('data')
        
        if not conversation_id or not conversation_data:
            return jsonify({'error': 'Missing conversationId or data'}), 400
        
        # Store in memory
        conversation_storage[conversation_id] = {
            'data': conversation_data,
            'timestamp': time.time()
        }
        
        # Also save to file as backup
        file_path = os.path.join(STORAGE_DIR, f"{conversation_id}.json")
        with open(file_path, 'w') as f:
            json.dump(conversation_data, f)
        
        return jsonify({
            'success': True,
            'conversationId': conversation_id,
            'message': 'Conversation data stored successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_app.route('/api/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    try:
        # First try in-memory storage
        if conversation_id in conversation_storage:
            return jsonify({
                'success': True,
                'data': conversation_storage[conversation_id]['data']
            })
        
        # Fallback to file storage
        file_path = os.path.join(STORAGE_DIR, f"{conversation_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            return jsonify({
                'success': True,
                'data': data
            })
        
        return jsonify({'error': 'Conversation not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def cleanup_old_conversations():
    """Clean up conversations older than 1 hour"""
    while True:
        current_time = time.time()
        to_remove = []
        
        for conv_id, conv_data in conversation_storage.items():
            if current_time - conv_data['timestamp'] > 3600:  # 1 hour
                to_remove.append(conv_id)
        
        for conv_id in to_remove:
            del conversation_storage[conv_id]
            # Also remove file
            file_path = os.path.join(STORAGE_DIR, f"{conv_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
        
        time.sleep(300)

@api_app.route('/api/quiz-results', methods=['POST'])
def store_quiz_results():
    """Store quiz results and return quiz ID"""
    try:
        print("here")
        data = request.json
        quiz_id = data.get('quiz_id')

        print(data, quiz_id)
        
        if not quiz_id:
            quiz_id = f"quiz_{int(time.time())}"
            data['quiz_id'] = quiz_id
        
        # Store in memory
        conversation_storage[f"quiz_{quiz_id}"] = {
            'data': data,
            'timestamp': time.time(),
            'type': 'quiz_results'
        }
        
        # Also save to file
        quiz_file_path = os.path.join(STORAGE_DIR, f"quiz_{quiz_id}.json")
        with open(quiz_file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            'success': True,
            'quiz_id': quiz_id,
            'message': 'Quiz results stored successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_app.route('/api/quiz-results/<quiz_id>', methods=['GET'])
def get_quiz_results(quiz_id):
    """Retrieve quiz results by ID"""
    try:
        storage_key = f"quiz_{quiz_id}"
        
        # First try in-memory storage
        if storage_key in conversation_storage:
            return jsonify({
                'success': True,
                'data': conversation_storage[storage_key]['data']
            })
        
        # Fallback to file storage
        file_path = os.path.join(STORAGE_DIR, f"quiz_{quiz_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            return jsonify({
                'success': True,
                'data': data
            })
        
        return jsonify({'error': 'Quiz results not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API server is running'})

def run_api():
    api_app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

# Start API server function
def start_api_server():
    if 'api_started' not in st.session_state:
        st.session_state.api_started = True
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        time.sleep(1)
        return True
    return False