"""Tree-navigation agent used to locate switch-model sections in a datasheet."""

from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool

from app.utils.llm import get_llm
from app.utils.tree import TreeExplorer


prompt = """
You locate individual switch models in a hardware datasheet.
The document is available only through the tree-navigation tools. Traverse the
tree; do not rely on product knowledge or infer product names from a series
name.

Goal: return the node_id for every product-level switch-model section. A
product-level switch-model node may have children such as "Slot Layout", "Power",
or "Technical Specifications". In that case, return the product node, NOT its
children: its page range plus descendants is needed to extract the full modular switch
specification. Do not return a generic enclosure section, a naming
convention, cabinet/rack, card, fan, power module, or a cross-reference.

Traversal rules:
- Start at the root and inspect every relevant child of sections whose title or
  summary could contain switch-model information.
- Use get_current_info before deciding whether a node is a switch model, a group, or
  irrelevant.
- When a group can contain switch models, visit every child before leaving it.
- A node is a valid answer only when its title or its own summary identifies one
  concrete switch model. A node that only introduces a family is not a
  valid answer.
- Return no ids if there are no concrete modular switch sections. Never guess ids.

When using a tool, respond exactly as:
Thought: <brief reason>
Action: <tool name>
Action Input: {"<parameter>": "<value>"}

When finished, respond exactly as:
Thought: I have found all concrete switch-model sections.
Answer: <node_id_1>,<node_id_2>

The Answer line must contain only unique node_ids separated by commas, with no
spaces or other text. If none are found, use an empty Answer line.
"""


def get_agent(json_path: str):
    """Build an agent that navigates ``json_path`` using TreeExplorer tools."""
    explorer = TreeExplorer(json_path)

    def go_down(node_id: str) -> str:
        """Move to a direct child of the current node by its node_id."""
        if explorer.go_down(node_id):
            return f"Moved to {node_id}. Current node: {explorer.get_current_node()['title']}"
        return f"Failed to move to {node_id}; it is not a child of the current node."

    def go_up() -> str:
        """Move from the current node to its parent."""
        if explorer.go_up():
            return f"Moved up. Current node: {explorer.get_current_node()['title']}"
        return "Already at root."

    def get_current_info() -> str:
        """Show the current node's title, summary, and direct children."""
        node = explorer.get_current_node()
        children = node.get("nodes", [])
        summary = node.get("summary")
        # Summaries are navigation aids, not extraction evidence. Bound their
        # size so a verbose node cannot consume the workflow context.
        if summary and len(summary) > 4000:
            summary = summary[:4000] + "\n[summary truncated]"

        result = [f"Node: {node.get('title')} (node_id: {node.get('node_id')})"]
        if summary:
            result.extend(["Summary:", summary])
        if children:
            result.append(f"This is a GROUP node with {len(children)} children:")
            result.extend(
                f"- {child.get('title')} (node_id: {child.get('node_id')})"
                for child in children
            )
        else:
            result.append("This node has no children.")
        return "\n".join(result)

    tools = [
        FunctionTool.from_defaults(fn=go_down),
        FunctionTool.from_defaults(fn=go_up),
        FunctionTool.from_defaults(fn=get_current_info),
    ]
    return AgentWorkflow.from_tools_or_functions(
        tools,
        llm=get_llm(),
        system_prompt=prompt,
        verbose=True,
    )
