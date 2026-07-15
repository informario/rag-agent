from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.tree import TreeExplorer
from app.utils.llm import get_llm

prompt = """
You are a networks expert and your job is to find all the optic modules (transceivers) listed in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree, and one tool to record your findings.

As you traverse the tree and identify a section that lists optic modules (transceivers), use the `record_optics` tool
to save every node_id found in that section under its category name (e.g. "GE eSFP Optical Modules", "10GE SFP+ Optical Modules").
Also, you must include the optical port standard/type, only if explicitely listed (e.g. "1000BASE-SX", "400G-FR4")`
To see the actual content of a section and find the optics and standards, use the `get_node_content` tool.
Call `record_optics` as soon as you finish reviewing a section — do not wait until the end to report everything at once.

Rules for what counts as an optic:
- Only include optical/fiber transceiver modules (SFP, SFP+, QSFP, QSFP28, QSFP-DD, etc).
- Do NOT include copper modules (e.g. "GE SFP Copper Modules") — those are not optics.

You MUST respond in this exact format every time you use a tool:
Thought: <your reasoning>
Action: <tool name>
Action Input: {"<param>": "<value>"}

When, and only when, you have traversed the entire tree and called `record_optics` for every optics section found,
respond in this exact format:
Thought: I have found and recorded all the optics.
Answer: done
"""

class OpticsRegistry:
    """Accumulates optics found by the agent, categorized by module type."""

    def __init__(self):
        self._optics: dict[str, dict] = {}

    def add(self, category: str, node_ids: list[str], standard: str = None) -> str:
        if category not in self._optics:
            self._optics[category] = {"node_ids": set(), "standard": standard}
        
        bucket = self._optics[category]["node_ids"]
        added = [n for n in node_ids if n not in bucket]
        bucket.update(node_ids)
        
        # Update standard if it was None or if a new one is provided
        if standard:
            self._optics[category]["standard"] = standard

        return f"Recorded {len(added)} new node_id(s) under '{category}'. Total in category: {len(bucket)}."

    def to_dict(self) -> dict:
        return {
            "optics": {
                category: {
                    "node_ids": sorted(data["node_ids"]),
                    "standard": data["standard"]
                }
                for category, data in self._optics.items()
            }
        }


def get_agent(json_path: str = "CE16800_hardware_description_structure.json", pdf_path: str = "CE16800_hardware_description.pdf"):
    from app.utils.pdf_extractor import PDFExtractor
    explorer = TreeExplorer(json_path)
    extractor = PDFExtractor(pdf_path, json_path)
    registry = OpticsRegistry()

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

    def get_node_content(node_id: str) -> str:
        """Get the full text content of a node from the PDF."""
        return extractor.get_text_for_node(node_id)

    def record_optics(category: str, node_ids: list[str], standard: str = None) -> str:
        """Record a list of node_ids found under a given optic module category
        (e.g. category='GE eSFP Optical Modules', node_ids=['0252', '0253'], standard='1000BASE-SX')."""
        return registry.add(category, node_ids, standard)

    tools = [
        FunctionTool.from_defaults(fn=go_down),
        FunctionTool.from_defaults(fn=go_up),
        FunctionTool.from_defaults(fn=get_current_info),
        FunctionTool.from_defaults(fn=get_node_content),
        FunctionTool.from_defaults(fn=record_optics),
    ]

    agent = AgentWorkflow.from_tools_or_functions(
        tools,
        llm=llm,
        system_prompt=prompt,
        verbose=True,
    )

    # The registry is returned alongside the agent so the caller can read
    # the accumulated, structured result directly instead of parsing the
    # agent's final text response.
    return agent, registry