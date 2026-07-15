from llama_index.core.agent.workflow import AgentWorkflow
from llama_index.core.tools import FunctionTool
from app.utils.llm import get_llm
from app.utils.pdf_extractor import PDFExtractor

prompt = """
You are a networks expert. You will be given a slice of a hardware datasheet PDF (in English) describing one or more optics pluggable transceivers. Your job is to extract the specifications of the ONE optic that is completely and fully described within this slice, and output them as JSON.

Use the `record_optics` tool to save the optic found in this section under its category name (e.g. "GE eSFP Optical Modules", "10GE SFP+ Optical Modules").
Also, you must include all optical port standards/types, only if explicitly listed (e.g. ["1000BASE-SX", "1000BASE-LX"]).

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

def get_agent(registry: OpticsRegistry, node_id: str = None):
    llm = get_llm()

    def record_optics(category: str, module_names: list[str], standards: list[str] = None) -> str:
        """Record a list of optical modules and their standards found under a given optic module category.
        (e.g. category='GE eSFP Optical Modules', module_names=['SFP-GE-SX-MM850'], standards=['1000BASE-SX'])."""
        return registry.add(category, module_names, standards, node_id)

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
