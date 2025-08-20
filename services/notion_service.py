import os
from notion_client import Client

class NotionService:
    def __init__(self):
        self.client = Client(auth=os.environ["NOTION_SECRET"])
        self.database_id = os.environ["NOTION_DATABASE_ID"]
        self.TITLE_PROP = os.getenv("NOTION_TITLE_PROP", "Name")
        self.NOTES_PROP = os.getenv("NOTION_NOTES_PROP", "Summary")

    def fetch_all_notes_text(self) -> str:
        """
        Recursively collect text from the main database and all nested child databases.
        Handles both database properties and full page body blocks.
        """
        all_notes = self._fetch_notes_recursive(self.database_id)
        return "\n\n".join([note for note in all_notes if note]).strip()

    def _fetch_notes_recursive(self, database_id: str, visited_dbs=None) -> list[str]:
        """
        Recursively fetch notes from a database and all its child databases.
        Uses visited_dbs set to prevent infinite loops.
        """
        if visited_dbs is None:
            visited_dbs = set()
        
        # Prevent infinite loops by tracking visited databases
        if database_id in visited_dbs:
            return []
        
        visited_dbs.add(database_id)
        notes = []
        
        try:
            cursor = None
            while True:
                resp = self.client.databases.query(
                    database_id=database_id,
                    start_cursor=cursor
                )
                
                for page in resp["results"]:
                    page_id = page["id"]
                    
                    # Check if this page contains a child database
                    if self._is_child_database(page):
                        # Recursively fetch from child database
                        child_notes = self._fetch_notes_recursive(page_id, visited_dbs.copy())
                        notes.extend(child_notes)
                    else:
                        # Extract text from regular page
                        page_text = self._extract_page_content(page, page_id)
                        if page_text:
                            notes.append(page_text)
                
                if not resp.get("has_more"):
                    break
                cursor = resp.get("next_cursor")
                
        except Exception as e:
            print(f"Warning: Could not fetch from database {database_id}: {e}")
            # Continue processing other databases
        
        return notes

    def _is_child_database(self, page: dict) -> bool:
        """
        Check if a page represents a child database.
        This checks for database-type properties or specific indicators.
        """
        # Check if page object type indicates it's a database
        if page.get("object") == "database":
            return True
        
        # Check if page has database-related properties
        properties = page.get("properties", {})
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get("type")
            # Look for relation properties that might point to child databases
            if prop_type == "relation":
                return True
        
        # Check if page has child blocks that might be databases
        if page.get("has_children", False):
            try:
                # Check first few child blocks to see if any are databases
                blocks = self.client.blocks.children.list(block_id=page["id"], page_size=5)
                for block in blocks.get("results", []):
                    if block.get("type") == "child_database":
                        return True
            except:
                pass
        
        return False

    def _extract_page_content(self, page: dict, page_id: str) -> str:
        """
        Extract all text content from a page including properties and body blocks.
        """
        content_parts = []
        
        # 1) Extract property text (e.g., Summary, Title)
        props = page.get("properties", {})
        
        # Extract from the specified NOTES_PROP
        notes_prop = props.get(self.NOTES_PROP)
        if notes_prop:
            prop_type = notes_prop.get("type")
            if prop_type in ("rich_text", "title"):
                blocks = notes_prop[prop_type]
                text = "".join([b.get("plain_text", "") for b in blocks]).strip()
                if text:
                    content_parts.append(text)
        
        # Extract from title property if different from NOTES_PROP
        if self.TITLE_PROP != self.NOTES_PROP:
            title_prop = props.get(self.TITLE_PROP)
            if title_prop and title_prop.get("type") == "title":
                title_blocks = title_prop["title"]
                title_text = "".join([b.get("plain_text", "") for b in title_blocks]).strip()
                if title_text:
                    content_parts.append(f"Title: {title_text}")
        
        # 2) Extract full page body text (recursive through blocks)
        page_body = self._extract_page_text(page_id)
        if page_body:
            content_parts.append(page_body)
        
        return "\n\n".join(content_parts).strip()

    # ---------- Existing helper methods (enhanced) ----------

    def _extract_page_text(self, page_id: str) -> str:
        """Extract text from all blocks in a page, handling nested structures."""
        out = []
        try:
            for block in self._iter_blocks(page_id):
                text = self._block_to_text(block)
                if text:
                    out.append(text)
        except Exception as e:
            print(f"Warning: Could not extract text from page {page_id}: {e}")
        
        return "\n".join(out).strip()

    def _iter_blocks(self, block_id: str):
        """Yield all blocks under block_id, recursively with pagination handling."""
        try:
            start_cursor = None
            while True:
                resp = self.client.blocks.children.list(
                    block_id=block_id, 
                    start_cursor=start_cursor
                )
                
                for block in resp.get("results", []):
                    yield block
                    
                    # Handle child databases within blocks
                    if block.get("type") == "child_database":
                        child_db_id = block.get("id")
                        if child_db_id:
                            # Recursively fetch from child database
                            child_notes = self._fetch_notes_recursive(child_db_id)
                            for note in child_notes:
                                if note:
                                    # Yield as a synthetic block for consistent processing
                                    yield {
                                        "type": "paragraph",
                                        "paragraph": {
                                            "rich_text": [{"plain_text": note}]
                                        }
                                    }
                    
                    # Dive into children if the block has them
                    elif block.get("has_children"):
                        yield from self._iter_blocks(block["id"])
                
                if not resp.get("has_more"):
                    break
                start_cursor = resp.get("next_cursor")
                
        except Exception as e:
            print(f"Warning: Could not iterate blocks for {block_id}: {e}")

    def _rich_text_plain(self, rich_text: list) -> str:
        """Extract plain text from Notion rich text objects."""
        return "".join([r.get("plain_text", "") for r in (rich_text or [])]).strip()

    def _block_to_text(self, block: dict) -> str:
        """Convert a Notion block to plain text."""
        block_type = block.get("type")
        if not block_type:
            return ""
        
        data = block.get(block_type, {})
        
        # Handle common text containers
        if block_type in ("paragraph", "heading_1", "heading_2", "heading_3",
                         "callout", "quote", "toggle", "to_do", "bulleted_list_item",
                         "numbered_list_item"):
            return self._rich_text_plain(data.get("rich_text", []))
        
        # Handle code blocks
        elif block_type == "code":
            code = self._rich_text_plain(data.get("rich_text", []))
            lang = data.get("language", "")
            return f"[code {lang}]\n{code}" if code else ""
        
        # Handle tables
        elif block_type == "table":
            return "[Table content]"  # Could be enhanced to extract table data
        
        # Handle child databases (already handled in _iter_blocks)
        elif block_type == "child_database":
            return ""  # Content is handled recursively
        
        # Handle other block types
        elif block_type in ("image", "file", "video", "audio"):
            caption = data.get("caption", [])
            caption_text = self._rich_text_plain(caption)
            return f"[{block_type.title()}: {caption_text}]" if caption_text else f"[{block_type.title()}]"
        
        return ""
