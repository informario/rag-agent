from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.llm import get_llm

prompt = """
You are a networks expert. You will be given a small PDF slice that was selected
from an exact optic-category heading in a hardware datasheet. Your job is to
catalog only that requested optic category.

Use the `record_optics` tool exactly once if, and only if, the requested category
is actually described in the slice. Record its explicitly listed product model
names and all explicitly listed optical Ethernet standards/types (for example,
["1000BASE-SX", "1000BASE-LX"]). An empty module list is allowed when the
source proves the category/standards but does not name individual products.

Do not record a neighboring category, an electrical module, a table of contents,
or information inferred from the requested category name. Do not invent product
names or standards. If the requested category is not verifiably described, do
not call the tool and answer done.

You MUST respond in this exact format every time you use a tool:
Thought: <your reasoning>
Action: <tool name>
Action Input: {"<param>": "<value>"}

When you have finished reviewing the provided text and called `record_optics` the optic found, respond in this exact format:
Thought: I have recorded the optic from this section.
Answer: done
"""

class OpticsRegistry:
    """Accumulates optics found by the agent, categorized by module type."""

    def __init__(self):
        self._optics: dict[str, dict] = {}

    def add(self, category: str, module_names: list[str], standards: list[str] = None, node_id: str = None) -> str:
        if category not in self._optics:
            self._optics[category] = {"modules": set(), "standards": set(), "nodes": set()}
        
        bucket = self._optics[category]["modules"]
        added_modules = [n for n in module_names if n not in bucket]
        bucket.update(module_names)
        
        standards_bucket = self._optics[category]["standards"]
        added_standards = []
        if standards:
            added_standards = [s for s in standards if s not in standards_bucket]
            standards_bucket.update(standards)
        
        if node_id:
            self._optics[category]["nodes"].add(node_id)

        return f"Recorded {len(added_modules)} new module(s) and {len(added_standards)} new standard(s) under '{category}'."

    def to_dict(self) -> dict:
        return {
            "optics": {
                category: {
                    "modules": sorted(list(data["modules"])),
                    "standards": sorted(list(data["standards"])),
                    "nodes": sorted(list(data["nodes"]))
                }
                for category, data in self._optics.items()
            }
        }

def get_agent(registry: OpticsRegistry, supported_optic: str, node_id: str = None):
    llm = get_llm()

    def record_optics(module_names: list[str], standards: list[str] = None) -> str:
        """Record explicit models and standards for the requested optic category only."""
        return registry.add(supported_optic, module_names, standards, node_id)

    tools = [
        FunctionTool.from_defaults(fn=record_optics),
    ]

    agent = AgentWorkflow.from_tools_or_functions(
        tools,
        llm=llm,
        system_prompt=prompt,
        verbose=True,
    )

    return agent
