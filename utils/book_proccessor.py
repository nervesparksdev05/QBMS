import re

def process_book(book_path):
    """
    Process a book text file and extract content by chapters
    
    Args:
        book_path (str): Path to the book text file
    
    Returns:
        list: List of dictionaries containing chapter info and content
    """
    chapters = []
    
    try:
        with open(book_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Try to identify chapter pattern
        chapter_pattern = re.compile(r'Chapter\s+(\d+)[\s:]+(.+?)(?=Chapter\s+\d+|\Z)', re.DOTALL | re.IGNORECASE)
        matches = chapter_pattern.findall(content)
        
        if matches:
            # Chapters identified
            for chapter_num, chapter_content in matches:
                chapters.append({
                    "number": int(chapter_num),
                    "title": f"Chapter {chapter_num}",
                    "content": chapter_content.strip()
                })
        else:
            # Try alternate chapter pattern
            alt_pattern = re.compile(r'(\d+)[\.\s]+(.+?)(?=\d+[\.\s]+|\Z)', re.DOTALL)
            matches = alt_pattern.findall(content)
            
            if matches:
                for chapter_num, chapter_content in matches:
                    chapters.append({
                        "number": int(chapter_num),
                        "title": f"Chapter {chapter_num}",
                        "content": chapter_content.strip()
                    })
            else:
                # No chapters found, treat as a single chapter
                chapters.append({
                    "number": 1,
                    "title": "Chapter 1",
                    "content": content.strip()
                })
        
        return chapters
    
    except Exception as e:
        print(f"Error processing book: {e}")
        return [{
            "number": 1,
            "title": "Chapter 1",
            "content": "Error processing book content"
        }]