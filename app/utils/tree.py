import json

class TreeExplorer:
    def __init__(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.doc_name = self.data.get('doc_name')
        self.structure = self.data.get('structure', [])
        
        # Root is a virtual node representing the document
        self.root = {
            "title": self.doc_name,
            "node_id": "root",
            "nodes": self.structure
        }
        self.current_node = self.root
        self.parent_map = {}
        self._build_parent_map(self.root)

    def _build_parent_map(self, node):
        if 'nodes' in node:
            for child in node['nodes']:
                if 'node_id' in child:
                    self.parent_map[child['node_id']] = node
                    self._build_parent_map(child)

    def get_current_node(self):
        return self.current_node

    def go_down(self, node_id):
        if 'nodes' in self.current_node:
            for child in self.current_node['nodes']:
                if child.get('node_id') == node_id:
                    self.current_node = child
                    return True
        return False

    def go_up(self):
        parent = self.parent_map.get(self.current_node.get('node_id'))
        if parent:
            self.current_node = parent
            return True
        return False

    def reset_to_root(self):
        self.current_node = self.root