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

CRITICAL RULE ABOUT LEAVES:
- A node_id is only a valid optic module answer if get_current_info reports it as a LEAF node (no children).
- If a node has children, it is a GROUP/FAMILY, not an individual optic module — you MUST go_down into every child
  before considering that branch finished, even if the group's title looks like a part number.
- Never include a node_id in your final Answer unless you have personally visited it with go_down
  and confirmed via get_current_info that it has no children.

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
        """Get all content about the current node and its children."""
        node = explorer.get_current_node()
        children = node.get('nodes', [])
        if not children:
            return f"Node: {node.get('title')}\nThis is a LEAF node (no children). It can be a valid optic module answer."
        child_list = [f"{n.get('title')} (node_id: {n.get('node_id')})" for n in children]
        return (f"Node: {node.get('title')}\n"
                f"This is a GROUP node with {len(children)} children — it is NOT itself a valid optic module.\n"
                f"Children:\n" + "\n".join(child_list))

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