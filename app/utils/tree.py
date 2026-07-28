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
        self.id_map = {"root": self.root}
        self._build_parent_map(self.root)

    def _build_parent_map(self, node):
        if 'nodes' in node:
            for child in node['nodes']:
                if 'node_id' in child:
                    self.parent_map[child['node_id']] = node
                    self.id_map[child['node_id']] = child
                    self._build_parent_map(child)

    def is_leaf(self, node_id):
        """A node is a leaf if it has no 'nodes' key, or an empty children list."""
        node = self.id_map.get(node_id)
        if node is None:
            return False
        return not node.get('nodes')

    def get_leaf_descendants(self, node_id):
        """Return node_ids of all leaf descendants under node_id (or [node_id] if already a leaf)."""
        node = self.id_map.get(node_id)
        if node is None:
            return []
        if self.is_leaf(node_id):
            return [node_id]
        leaves = []
        for child in node.get('nodes', []):
            cid = child.get('node_id')
            if cid is None:
                continue
            leaves.extend(self.get_leaf_descendants(cid))
        return leaves

    def validate_answer(self, node_ids):
        """
        Check the agent's final list of node_ids.
        - valid: genuine leaves
        - expanded: {group_node_id: [leaf_node_ids under it]} for anything
                    the agent stopped on too early
        - unknown: node_ids not in the tree at all
        """
        valid, expanded, unknown = [], {}, []
        for nid in node_ids:
            if nid not in self.id_map:
                unknown.append(nid)
            elif self.is_leaf(nid):
                valid.append(nid)
            else:
                expanded[nid] = self.get_leaf_descendants(nid)
        return {"valid": valid, "expanded": expanded, "unknown": unknown}

    def get_node_by_id(self, node_id):
        return self.id_map.get(node_id)

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