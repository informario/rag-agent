import os
from dotenv import load_dotenv
from llama_index.llms.openrouter import OpenRouter
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic

prompt = """
You are a networks expert. You will be given a slice of a hardware datasheet PDF (in English) describing one or more linecards. Your job is to extract the specifications of the ONE linecard that is completely and fully described within this slice, and output them as JSON.

Extract the following fields:
- model_name (e.g. "CR8DE6LEJKLP")
- description (e.g. "6-Port 800GBase-QSFP-DD + 36-Port 400GBase-QSFP-DD Integrated Line Processing Unit")
- port_configuration: one entry per physical port type found in the text (the example below shows only two port types, but a linecard may have any number of port types — do not limit yourself to QSFP-DD-800/400, use whatever port types actually appear).
  For each port type, extract:
  - port_count: the number of physical ports of that type
  - speeds: a dictionary of every supported speed and breakout combination mentioned in the text, and the resulting number of ports after applying that speed/breakout.
    - Format each key as "<n>x<speed>", where <n> is the number of resulting ports and <speed> is the speed per port (e.g. "1x800G", "4x100G", "4x10G"). Use "1x<speed>" for a native, non-broken-out speed (e.g. "1x400G"), not just "<speed>".
    - The value is always the total COUNT of resulting ports for that combination (i.e., after breakout, not before).
  - supported_optics: list of optical module names supported for that port type, as they appear in the text.

Rules:
- Do not invent, guess, or infer any information that is not explicitly present in the text. If a field or value cannot be found in the slice, set it to null (or an empty list [] for supported_optics if no optics are mentioned).
- All numeric fields (port_count and the values inside speeds) must be JSON numbers (integers), never strings.
- There will never be more than one complete linecard in a single slice. If the slice contains partial information from other linecards (overlap), ignore it and focus only on the one linecard that is fully covered.
- Your response must be ONLY a single valid JSON object: no markdown, no code fences (no ```), no explanations, no extra text before or after. It must be directly parseable by a standard JSON parser.

Example of expected output format (this is illustrative only — port types, keys, and values will vary depending on the actual linecard):
{
  "model_name": "CR8DE6LEJKLP",
  "description": "6-Port 800GBase-QSFP-DD + 36-Port 400GBase-QSFP-DD Integrated Line Processing Unit",
  "port_configuration": {
    "qsfp_dd_800": {
      "port_count": 6,
      "speeds": {
        "1x800G": 6,
        "1x400G": 6,
        "4x100G": 36
      },
      "supported_optics": [
        "800Gbps QSFP-DD Optical Module",
        "400Gbps QSFP-DD Optical Module"
      ]
    },
    "qsfp_dd_400": {
      "port_count": 36,
      "speeds": {
        "1x100G": 48,
        "4x10G": 144
      },
      "supported_optics": [
        "400Gbps QSFP-DD Optical Module",
        "200Gbps QSFP-DD Optical Module",
        "100Gbps QSFP28 Optical Module",
        "100Gbps QSFP28 BIDI Optical Module"
      ]
    }
  }
}
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

def parse_linecard(text: str):
    llm = get_llm()
    
    # We use a simple prompt for the LLM now, since we don't need tools.
    # The system prompt is already defined in 'prompt'.
    full_prompt = f"{prompt}\n\nHere is the PDF slice:\n{text}"
    
    response = llm.complete(full_prompt)
    return response.text
