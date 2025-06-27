import streamlit as st
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import threading
import base64
import tempfile
import os
import json
from pdf_parser import parse_pdf
import time
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import chromadb
from datetime import datetime

load_dotenv()

api_app = Flask(__name__)
CORS(api_app)  

CHROMA_DB_PATH = "data/chroma_db"
OPENAI_API_KEY = os.getenv("CHATGPT_API_KEY")
print("key", OPENAI_API_KEY)

conversation_storage = {}

STORAGE_DIR = "data/conversations"
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

class RAGSystem:
    def __init__(self):
        print("Initializing RAG system...")  
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
            api_key=OPENAI_API_KEY, 
        )
        print("Embeddings initialized:", self.embeddings) 
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        try:
            self.vectorstore = Chroma(
                persist_directory=CHROMA_DB_PATH,
                embedding_function=self.embeddings
            )
            if not hasattr(self.vectorstore, '_collection'):
                raise Exception("Chroma collection not initialized properly")
        except Exception as e:
            print(f"Failed to initialize Chroma: {str(e)}")
            raise

    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        self.delete_document(doc_id, silent=True)
        chunks = self.text_splitter.split_text(text)
        documents = [
            Document(page_content=chunk, metadata={
                "doc_id": doc_id,
                "chunk_index": i,
                "created_at": datetime.utcnow().isoformat(), 
                **(metadata or {})
            }) for i, chunk in enumerate(chunks)
        ]
        if documents:
            self.vectorstore.add_documents(documents)
            return len(documents)
        return 0

    def delete_document(self, doc_id: str, silent: bool = False):
        collection = self.vectorstore._collection
        existing = collection.get(where={"doc_id": doc_id})
        if existing and existing.get("ids"):
            collection.delete(where={"doc_id": doc_id})
            return len(existing["ids"])
        elif not silent:
            print(f"No chunks found for document {doc_id}")
        return 0

    def search(self, query: str, n_results: int = 5, doc_id: str = None):
        try:
            filters = {"doc_id": doc_id} if doc_id else None
            
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=n_results,
                filter=filters
            )
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                })
            return formatted_results
            
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []

    def get_relevant_content(self, query: str, max_tokens: int = 120000, doc_id: str = None):
        try:
            all_results = []
            token_count = 0
            n_results = 20

            if doc_id:
                results = self.search(query, n_results=n_results, doc_id=doc_id)
                for result in results:
                    content = result["content"]
                    estimated_tokens = len(content.split()) * 1.33
                    if token_count + estimated_tokens <= max_tokens:
                        all_results.append(result)
                        token_count += estimated_tokens
                if token_count >= max_tokens * 0.8:
                    return all_results

            remaining_tokens = max_tokens - token_count
            if remaining_tokens > 10000:
                results = self.search(query, n_results=n_results)
                for result in results:
                    if doc_id and result["metadata"].get("doc_id") == doc_id:
                        continue
                        
                    content = result["content"]
                    estimated_tokens = len(content.split()) * 1.33
                    if token_count + estimated_tokens <= max_tokens:
                        all_results.append(result)
                        token_count += estimated_tokens
                    else:
                        break

            all_results.sort(key=lambda x: x["score"], reverse=True)
            return all_results
            
        except Exception as e:
            print(f"Error in get_relevant_content: {str(e)}")
            return []
    
rag_system = RAGSystem()

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

        full_text = "\n".join(text_by_page)

        documents = {}
        document_id = f"{subject.lower().replace(' ', '')}_1"

        metadata = {
            "filename": filename,
            "subject": subject,
            "exam_type": exam_type,
            "pages": len(text_by_page)
        }
        rag_system.add_document(document_id, full_text, metadata)

        documents[document_id] = {
            "type": "pdf",
            "name": filename,
            "subject": subject,
            "exam_type": exam_type,
            "content": text_by_page,
            "images": images_by_page,
            "path": f"data/processed/{document_id}.json"
        }

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
    
@api_app.route('/api/search-content', methods=['POST'])
def search_content():
    try:
        # Get and validate input
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        query = data.get('query')
        doc_id = data.get('doc_id')
        max_tokens = data.get('max_tokens', 120000)

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        # Perform search
        results = rag_system.get_relevant_content(query, max_tokens=max_tokens, doc_id=doc_id)
        
        # Return properly formatted response
        return jsonify({
            'success': True,
            'results': results,
            'total_chunks': len(results),
            'estimated_tokens': sum(len(r['content'].split()) * 1.33 for r in results)
        })

    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@api_app.route('/api/documents-index')
def get_index():
    with open("data/documents_index.json") as f:
        return jsonify(json.load(f))

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
        if conversation_id in conversation_storage:
            return jsonify({
                'success': True,
                'data': conversation_storage[conversation_id]['data']
            })
        
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
    try:
        data = request.json
        quiz_id = data.get('quiz_id')

        print(data, quiz_id)
        
        if not quiz_id:
            quiz_id = f"quiz_{int(time.time())}"
            data['quiz_id'] = quiz_id
        
        conversation_storage[f"quiz_{quiz_id}"] = {
            'data': data,
            'timestamp': time.time(),
            'type': 'quiz_results'
        }

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
        
        if storage_key in conversation_storage:
            return jsonify({
                'success': True,
                'data': conversation_storage[storage_key]['data']
            })
        
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

if __name__ == "__main__":
    cleanup_thread = threading.Thread(target=cleanup_old_conversations, daemon=True)
    cleanup_thread.start()
    api_app.run(host="0.0.0.0", port=5001, debug=False)