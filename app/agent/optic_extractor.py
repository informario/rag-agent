from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.tree import TreeExplorer
from app.utils.llm import get_llm

prompt = """
You are a networks expert and your job is to find all individual optic modules models in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree.
You have to answer the node ids that identify each optic module.
You must make sure you are extracting only one optic module per node id, and not a group or entire section of them.

If a node's content is ambiguous or you cannot tell how many modules it covers, go_down to inspect its children before deciding.
Make sure to generate a node_id for each part number found. There may be several part numbers for a single category

You MUST respond in this exact format every time you use a tool:
Thought: <your reasoning>
Action: <tool name>
Action Input: {"<param>": "<value>"}

When, and only when, you have identified ALL the optics, respond in this exact format:
Thought: I have found all the optic nodes.
Answer: <node_id_1>,<node_id_2>,<node_id_3>

Rules for the Answer line:
- It must contain ONLY the node_ids, separated by commas.
- No spaces, brackets, quotes, or any other characters.
- No explanations, labels, or additional text before or after the node_ids.
- Do not repeat a node_id.
- Only include nodes that specifically contain lists of optical/fiber transceiver modules (SFP, SFP+, QSFP, QSFP28, QSFP-DD, etc).
- Do NOT include nodes for copper modules, those are not optics.
"""

def get_agent(json_path: str = "CE16800_hardware_description_structure.json"):
    explorer = TreeExplorer(json_path)
    llm = get_llm()

    def go_down(node_id: str) -> str:
        """Move down to a child node by its node_id."""
        if explorer.go_down(node_id):
            return f"Moved to {node_id}. Current node: {explorer.get_current_node()['title']}"
        return f"Failed to move to {node_id}."

    def go_up() -> str:
        """Move up to the parent node."""
        if explorer.go_up():
            return f"Moved up. Current node: {explorer.get_current_node()['title']}"
        return "Already at root."

    def get_current_info() -> str:
        """Get the current node's own content plus its children's titles and
        content. Use the content (not the mere presence of children) to judge
        whether a node describes exactly one optic module or several."""
        node = explorer.get_current_node()
        self_line = f"Node: {node.get('title')} (node_id: {node.get('node_id')})"
        child_count = len(node.get('nodes', []))
        lines = [
            f"{n.get('title')} (node_id: {n.get('node_id')}, {len(n.get('nodes', []))} child node(s))"
            for n in node.get('nodes', [])
        ]
        children_block = "\n".join(lines) if lines else "(no children)"
        return f"{self_line}\nChild count: {child_count}\nChildren:\n{children_block}"

    tools = [
        FunctionTool.from_defaults(fn=go_down),
        FunctionTool.from_defaults(fn=go_up),
        FunctionTool.from_defaults(fn=get_current_info),
    ]

    agent = AgentWorkflow.from_tools_or_functions(
        tools,
        llm=llm,
        system_prompt=prompt,
        verbose=True,
    )

    return agent