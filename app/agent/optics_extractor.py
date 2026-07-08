import asyncio
import os
from dotenv import load_dotenv
from llama_index.core.agent.workflow import AgentWorkflow, ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openrouter import OpenRouter
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic
from app.utils.tree import TreeExplorer

prompt = """
You are a networks expert and your job is to find all the optic modules (transceivers) listed in a switch datasheet.
You will be provided with a hierarchical tree structure that represents the contents of a document.
You will be provided with a series of tools which you will use to traverse the tree, and one tool to record your findings.

As you traverse the tree and identify a section that lists optic modules (transceivers), use the `record_optics` tool
to save every node_id found in that section under its category name (e.g. "GE eSFP Optical Modules", "10GE SFP+ Optical Modules").
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

def get_llm():
    load_dotenv("app/.env")
    provider = os.getenv("LLM_PROVIDER")
    model = os.getenv("MODEL")
    api_key = os.getenv("API_KEY")

    if provider == "openai":
        return OpenAI(model=model, api_key=api_key)
    elif provider == "anthropic":
        return Anthropic(model=model, api_key=api_key)
    elif provider == "openrouter":
        return OpenRouter(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            context_window=131072,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


class OpticsRegistry:
    """Accumulates optics found by the agent, categorized by module type."""

    def __init__(self):
        self._optics: dict[str, set[str]] = {}

    def add(self, category: str, node_ids: list[str]) -> str:
        bucket = self._optics.setdefault(category, set())
        added = [n for n in node_ids if n not in bucket]
        bucket.update(node_ids)
        return f"Recorded {len(added)} new node_id(s) under '{category}'. Total in category: {len(bucket)}."

    def to_dict(self) -> dict:
        return {"optics": {category: sorted(ids) for category, ids in self._optics.items()}}


def get_agent(json_path: str = "app/database/CE16800_hardware_description_structure.json"):
    explorer = TreeExplorer(json_path)
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

    def record_optics(category: str, node_ids: list[str]) -> str:
        """Record a list of node_ids found under a given optic module category
        (e.g. category='GE eSFP Optical Modules', node_ids=['0252', '0253'])."""
        return registry.add(category, node_ids)

    tools = [
        FunctionTool.from_defaults(fn=go_down),
        FunctionTool.from_defaults(fn=go_up),
        FunctionTool.from_defaults(fn=get_current_info),
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