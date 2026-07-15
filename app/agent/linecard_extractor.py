from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.tree import TreeExplorer
from app.utils.llm import get_llm

prompt = """
You are a networks expert and your job is to find all the linecards in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree.

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
        """Get information about the current node and its children."""
        node = explorer.get_current_node()
        children = [f"{n.get('title')} (node_id: {n.get('node_id')})" for n in node.get('nodes', [])]
        return f"Node: {node.get('title')}\nChildren:\n" + "\n".join(children)

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