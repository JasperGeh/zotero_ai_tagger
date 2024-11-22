import os
from dotenv import load_dotenv
from pyzotero import zotero
from anthropic import Anthropic
import json
from typing import List, Dict, Set, Optional
import time
from pathlib import Path
import requests
import PyPDF2
from io import BytesIO
from bs4 import BeautifulSoup
import logging
from dataclasses import dataclass

@dataclass
class ProcessingOptions:
    url_fallback: bool  # -u flag: Look up URL only when no PDF
    url_always: bool    # -U flag: Always look up URL
    parse_pdf: bool     # -p flag: Parse PDF attachments
    tags_file: Optional[Path]  # -t flag: Path to tags file

class ZoteroTagger:
    def __init__(self, options: ProcessingOptions):
        load_dotenv()
        
        # Load required environment variables
        required_vars = {
            'ZOTERO_LIBRARY_ID': os.getenv('ZOTERO_LIBRARY_ID'),
            'ZOTERO_LIBRARY_TYPE': os.getenv('ZOTERO_LIBRARY_TYPE', 'group'),
            'ZOTERO_API_KEY': os.getenv('ZOTERO_API_KEY'),
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY')
        }
        
        # Validate environment variables
        missing = [k for k, v in required_vars.items() if not v]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
            
        self.zot = zotero.Zotero(
            required_vars['ZOTERO_LIBRARY_ID'],
            required_vars['ZOTERO_LIBRARY_TYPE'],
            required_vars['ZOTERO_API_KEY']
        )
        self.anthropic = Anthropic(api_key=required_vars['ANTHROPIC_API_KEY'])
        self.options = options
        self.existing_tags: Set[str] = set()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('zotero_tagger.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.load_existing_tags()

    def load_existing_tags(self):
        """Load existing tags from specified file or create new set."""
        if self.options.tags_file and self.options.tags_file.exists():
            with open(self.options.tags_file, 'r', encoding='utf-8') as f:
                self.existing_tags = set(line.strip() for line in f if line.strip())
            self.logger.info(f"Loaded {len(self.existing_tags)} existing tags from {self.options.tags_file}")
        else:
            self.existing_tags = set()
            self.logger.info("Starting with empty tags set")

    def save_existing_tags(self):
        """Save current tags to file if specified."""
        if self.options.tags_file:
            with open(self.options.tags_file, 'w', encoding='utf-8') as f:
                for tag in sorted(self.existing_tags):
                    f.write(f"{tag}\n")
            self.logger.info(f"Saved {len(self.existing_tags)} tags to {self.options.tags_file}")

    def extract_text_from_pdf(self, pdf_url: str) -> Optional[str]:
        """
        Download and extract text from a PDF file.
        Returns first 2000 words or None if extraction fails.
        """
        if not self.options.parse_pdf:
            return None
            
        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
            
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from first few pages (up to 5 pages)
            text = ""
            for page in pdf_reader.pages[:5]:
                text += page.extract_text() + "\n"
            
            # Limit to first 2000 words
            words = text.split()
            return " ".join(words[:2000])
            
        except Exception as e:
            self.logger.error(f"Error extracting PDF text: {str(e)}")
            return None

    def extract_text_from_webpage(self, url: str, has_pdf: bool) -> Optional[str]:
        """
        Extract main content text from a webpage based on URL processing flags.
        Returns first 2000 words or None if extraction fails or skipped.
        """
        # Check if we should process the URL based on flags
        if not (self.options.url_always or 
                (self.options.url_fallback and not has_pdf)):
            return None
            
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Extract text from main content areas
            content = ""
            for tag in ['article', 'main', '.content', '.post', '.entry']:
                elements = soup.select(tag)
                if elements:
                    content = " ".join(elem.get_text(strip=True) for elem in elements)
                    break
            
            if not content:
                content = soup.body.get_text(strip=True)
            
            # Limit to first 2000 words
            words = content.split()
            return " ".join(words[:2000])
            
        except Exception as e:
            self.logger.error(f"Error extracting webpage content: {str(e)}")
            return None

    def get_document_metadata(self, item) -> Dict:
        """Extract relevant metadata from a Zotero item."""
        data = item.get('data', {})
        metadata = {
            'title': data.get('title', ''),
            'abstract': data.get('abstractNote', ''),
            'key': data.get('key', ''),
            'item_type': data.get('itemType', ''),
            'existing_tags': [tag['tag'] for tag in data.get('tags', [])],
            'url': data.get('url', ''),
            'pdf_attachment': None
        }
        
        # Check for PDF attachments
        try:
            attachments = self.zot.children(metadata['key'])
            for attachment in attachments:
                if (attachment['data']['contentType'] == 'application/pdf' and 
                    'url' in attachment['data']):
                    metadata['pdf_attachment'] = attachment['data']['url']
                    break
        except Exception as e:
            self.logger.error(f"Error getting attachments: {str(e)}")
        
        return metadata

    def get_claude_suggestions(self, metadata: Dict) -> List[str]:
        """
        Get tag suggestions from Claude based on all available document content.
        """
        content_parts = []
        
        if metadata['title']:
            content_parts.append(f"Title: {metadata['title']}")
        
        if metadata['abstract']:
            content_parts.append(f"Abstract: {metadata['abstract']}")
        
        has_pdf = bool(metadata['pdf_attachment'])
        
        # Process URL content based on flags
        if metadata['url']:
            webpage_content = self.extract_text_from_webpage(metadata['url'], has_pdf)
            if webpage_content:
                content_parts.append(f"Webpage content: {webpage_content}")
        
        # Process PDF content if flag is set
        if has_pdf and self.options.parse_pdf:
            pdf_content = self.extract_text_from_pdf(metadata['pdf_attachment'])
            if pdf_content:
                content_parts.append(f"PDF content: {pdf_content}")
        
        # Adjust prompt based on available content
        if len(content_parts) == 1 and metadata['title']:
            prompt = f"""Please suggest 3-5 relevant tags for this document based only on its title.
            Apply suitable tags from this existing set: {sorted(list(self.existing_tags))}
            Create new tags if one of the central concepts from the paper is not among the existing tags. The document is already from an AI/ML collection, so refrain from setting generic tags like 'Machine Learning' or 'Computer Science'. 
            Tags should be in Capital Case with spaces as separators (e.g., LLM Jailbreaking, Protein Design, ...)
            Be conservative with tag suggestions when working with title only.

            {content_parts[0]}

            Please respond with ONLY the tags, one per line, nothing else."""
        else:
            prompt = f"""Please analyze this document and suggest 3-5 relevant tags.
            Apply suitable tags from this existing set: {sorted(list(self.existing_tags))}
            Create new tags if one of the central concepts from the paper is not among the existing tags. The document is already from an AI/ML collection, so refrain from setting generic tags like 'Machine Learning' or 'Computer Science'. 
            Tags should be in Capital Case with spaces as separators (e.g., LLM Jailbreaking, Protein Design, ...)

            {chr(10).join(content_parts)}

            Please respond with ONLY the tags, one per line, nothing else."""

        try:
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=150,
                temperature=0,
                system="You are a helpful academic librarian who creates consistent, descriptive tags for academic papers, reports, and blog posts.",
                messages=[{"role": "user", "content": prompt}]
            )

            suggested_tags = [tag.strip() for tag in response.content[0].text.split('\n') if tag.strip()]
            
            # Add any new tags to our existing set
            self.existing_tags.update(suggested_tags)
            self.save_existing_tags()
            
            return suggested_tags
            
        except Exception as e:
            self.logger.error(f"Error getting Claude suggestions: {str(e)}")
            return []

    def update_item_tags(self, item_key: str, new_tags: List[str]):
        """Update a Zotero item with new tags."""
        try:
            item = self.zot.item(item_key)
            current_tags = item['data']['tags']
            
            # Add new tags while preserving existing ones
            for tag in new_tags:
                if tag not in [t['tag'] for t in current_tags]:
                    current_tags.append({'tag': tag})
            
            item['data']['tags'] = current_tags
            self.zot.update_item(item)
        except Exception as e:
            self.logger.error(f"Error updating item {item_key}: {str(e)}")

    def process_library(self, limit: int = None):
        """Process all items in the Zotero library/group."""
        items = self.zot.top(limit=limit)
        total_items = len(items)

        for i, item in enumerate(items, 1):
            metadata = self.get_document_metadata(item)
            self.logger.info(f"\nProcessing item {i}/{total_items}: {metadata['title']}")
            self.logger.info(f"Item type: {metadata['item_type']}")
            
            if not metadata['title']:
                self.logger.warning("Skipping item with no title")
                continue

            try:
                suggested_tags = self.get_claude_suggestions(metadata)
                
                if suggested_tags:
                    self.logger.info(f"Suggested tags: {suggested_tags}")
                    self.logger.info(f"Existing tags: {metadata['existing_tags']}")
                    
                    self.update_item_tags(metadata['key'], suggested_tags)
                    self.logger.info("Tags updated successfully")
                else:
                    self.logger.warning("No tags were suggested")
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error processing item: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Automatically tag Zotero library items using Claude')
    parser.add_argument('-u', '--url-fallback', action='store_true',
                      help='Look up URL only when no PDF is attached')
    parser.add_argument('-U', '--url-always', action='store_true',
                      help='Always look up URL content')
    parser.add_argument('-p', '--parse-pdf', action='store_true',
                      help='Parse PDF attachments')
    parser.add_argument('-t', '--tags-file', type=Path,
                      help='Path to text file with existing tags (one per line)')
    parser.add_argument('-l', '--limit', type=int,
                      help='Limit number of items to process')
    
    args = parser.parse_args()
    
    # Create ProcessingOptions from command line arguments
    options = ProcessingOptions(
        url_fallback=args.url_fallback,
        url_always=args.url_always,
        parse_pdf=args.parse_pdf,
        tags_file=args.tags_file
    )
    
    # Initialize and run tagger
    tagger = ZoteroTagger(options)
    tagger.process_library(limit=args.limit)

if __name__ == "__main__":
    main()
