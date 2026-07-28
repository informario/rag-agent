from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.tree import TreeExplorer
from app.utils.llm import get_llm

prompt = """
You are a networks expert and your job is to find all the linecards in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree.
You have to answer the node ids that identify each linecard
You must make sure you are extracting only one linecard per node id, and not a group or entire section of them.
Make sure you reach the bottom of the tree to find the individual linecards, and not just the sections that contain them.
Make sure you are extracting a linecard, not a processor unit, switch fabric, or any other piece of equipment.

CRITICAL RULE ABOUT LEAVES:
- A node_id is only a valid linecard answer if get_current_info reports it as a LEAF node (no children).
- If a node has children, it is a GROUP/FAMILY, not a linecard — you MUST go_down into every child
  before considering that branch finished, even if the group's title looks like a product name
  (e.g. "LPUF-1T" is often a family name, not the individual linecard).
- Never include a node_id in your final Answer unless you have personally visited it with go_down
  and confirmed via get_current_info that it has no children.

You MUST respond in this exact format every time you use a tool:
Thought: <your reasoning>
Action: <tool name>
Action Input: {"<param>": "<value>"}

When, and only when, you have identified ALL the linecards, respond in this exact format:
Thought: I have found all the linecards.
Answer: <node_id_1>,<node_id_2>,<node_id_3>

Strict rules for the Answer line:
- It must contain ONLY the node_ids, separated by commas.
- No spaces, brackets, quotes, or any other characters.
- No explanations, labels, or additional text before or after the node_ids.
- Do not repeat a node_id.
- If only one linecard is found, return a single node_id with no commas.
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
            return f"Node: {node.get('title')}\nThis is a LEAF node (no children). It can be a valid linecard answer."
        child_list = [f"{n.get('title')} (node_id: {n.get('node_id')})" for n in children]
        return (f"Node: {node.get('title')}\n"
                f"This is a GROUP node with {len(children)} children — it is NOT itself a valid linecard.\n"
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