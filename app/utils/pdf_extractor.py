import json
import os
import fitz  # PyMuPDF

class PDFExtractor:
    def __init__(self, pdf_path, json_path):
        self.pdf_path = pdf_path
        self.json_path = json_path
        self.doc = fitz.open(pdf_path)
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.nodes = {}
        self._build_node_map(self.data.get('structure', []))

    def _build_node_map(self, nodes):
        for node in nodes:
            if 'node_id' in node:
                self.nodes[node['node_id']] = node
            if 'nodes' in node:
                self._build_node_map(node['nodes'])

    def get_text_for_node(self, node_id):
        if node_id not in self.nodes:
            return f"Node {node_id} not found."
        
        node = self.nodes[node_id]
        
        page_indices = set()
        def collect_pages(n):
            start = n.get('start_index')
            end = n.get('end_index')
            if start is not None and end is not None:
                for p in range(start, end + 1):
                    page_indices.add(p)
            
            for child in n.get('nodes', []):
                collect_pages(child)

        collect_pages(node)
        
        if not page_indices:
            return "No page indices for this node or its children."

        sorted_pages = sorted(list(page_indices))
        
        text = ""
        for page_num_1based in sorted_pages:
            page_idx = page_num_1based - 1 # fitz is 0-based
            if 0 <= page_idx < len(self.doc):
                page = self.doc[page_idx]
                # Using "text" with 'sort=True' to help with table structure
                # Alternatively "html" or "dict" for even more structure, 
                # but "text" is usually best for LLM context if it preserves layout.
                text += page.get_text("text", sort=True) + "\n"
        
        return text
