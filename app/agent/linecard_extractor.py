import asyncio
import os
from llama_index.core.agent.workflow import AgentWorkflow, ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openrouter import OpenRouter
from app.utils.tree import TreeExplorer

prompt = """
You are a networks expert and your job is to find all the linecards in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree.
When all done, you will return a list of node_id separated by commas.

You MUST respond in this exact format every time:
Thought: <your reasoning>
Action: <tool name>
Action Input: {"<param>": "<value>"}

When you have the final answer:
Thought: I have found all the linecards.
Answer: <comma separated node_ids>
"""

def get_agent(json_path: str = "app/database/CE16800_hardware_description_structure.json"):
    explorer = TreeExplorer(json_path)

    llm = OpenRouter(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model="openai/gpt-oss-120b",
        max_tokens=4096,
        context_window=131072,
    )

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