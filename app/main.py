import json
import os
from dotenv import load_dotenv
from app.utils.llm import get_llm, get_summary_memory
from app.utils.pdf_extractor import PDFExtractor
from app.utils.tree import TreeExplorer
from app.agent.linecard_parser import parse_linecard
from app.agent.linecard_extractor import get_agent as get_linecard_agent
from app.agent.optic_extractor import collect_supported_optics, find_optic_targets
from app.agent.optic_parser import get_agent as get_optics_parser_agent, OpticsRegistry
from app.agent.optics_crosscheck import load_optics_data, load_ethernet_standards, process_linecard
from app.agent.switch_model_extractor import get_agent as get_switch_model_node_agent
from app.agent.switch_model_parser import SwitchModelRegistry, parse_switch_models as parse_switch_models_text

load_dotenv()

async def extract_linecards(json_path):
    from app.utils.tree import TreeExplorer
    explorer = TreeExplorer(json_path)
    agent = get_linecard_agent(json_path)
    llm = get_llm()
    memory = get_summary_memory(llm)
    response = await agent.run(
        user_msg="Find all the linecards in this document and return their node_ids.", 
        max_iterations=500,
        memory=memory
    )
    node_ids_str = str(response.response.content)
    
    # Save node IDs to file
    output_dir = "app/database/linecards"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process the string to get a clean list
    clean_ids = node_ids_str
    if "Answer: " in clean_ids:
        clean_ids = clean_ids.split("Answer: ")[-1].strip()
    node_list = [nid.strip() for nid in clean_ids.split(",") if nid.strip()]
    
    # Validate and auto-expand group nodes
    check = explorer.validate_answer(node_list)
    final_ids = list(check["valid"])
    for group_id, leaves in check["expanded"].items():
        print(f"Warning: agent returned group node {group_id}, auto-expanding to leaves {leaves}")
        final_ids.extend(leaves)
    
    if check["unknown"]:
        print(f"Warning: agent returned unknown node_ids: {check['unknown']}")
    
    with open(os.path.join(output_dir, "linecard_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(final_ids, f, indent=2)
    
    return node_ids_str

async def extract_optics(json_path, linecards=None):
    """Find only optic categories required by the current linecard files.

    This is intentionally deterministic and does not create an LLM workflow or
    summary memory. It therefore has constant memory use with respect to the
    size of the document tree. When ``linecards`` is None, it reads every
    available linecard JSON file, which supports a previously completed
    linecard-extraction run.
    """
    linecard_model_names = linecards.keys() if isinstance(linecards, dict) else None
    supported_optics = collect_supported_optics(model_names=linecard_model_names)
    targets = find_optic_targets(json_path, supported_optics)

    output_dir = "app/database/optics"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "optic_targets.json"), "w", encoding="utf-8") as file:
        json.dump(targets, file, indent=2)
    # Retain the former lightweight artifact for callers that only need ids.
    node_ids = list(dict.fromkeys(target["node_id"] for target in targets))
    with open(os.path.join(output_dir, "optic_nodes.json"), "w", encoding="utf-8") as file:
        json.dump(node_ids, file, indent=2)
    return targets

async def extract_switch_models(json_path):
    """Locate product-level switch-model sections without expanding them to leaves."""
    from app.utils.tree import TreeExplorer

    explorer = TreeExplorer(json_path)
    agent = get_switch_model_node_agent(json_path)
    memory = get_summary_memory(get_llm())
    response = await agent.run(
        user_msg="Find every concrete modular switch model section and return its node_ids.",
        max_iterations=300,
        memory=memory,
    )

    response_text = str(response.response.content)
    answer = response_text.split("Answer: ", 1)[-1].strip() if "Answer: " in response_text else response_text.strip()
    requested_ids = [node_id.strip() for node_id in answer.split(",") if node_id.strip()]

    # Switch-model nodes can be non-leaf product sections. Unlike linecards/optics,
    # expanding them would destroy the product-level PDF slice.
    final_ids = []
    for node_id in requested_ids:
        if explorer.get_node_by_id(node_id) is None:
            print(f"Warning: switch-model agent returned unknown node_id: {node_id}")
        elif node_id not in final_ids:
            final_ids.append(node_id)

    output_dir = "app/database/switch_models"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "switch_model_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(final_ids, f, indent=2)
    return final_ids

def _load_switch_models_json(response: str):
    """Recover one JSON object or array from an LLM response."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip().rsplit("```", 1)[0]
    decoder = json.JSONDecoder()
    # Besides a clean response, tolerate prose such as "Here is the JSON:" or
    # a fence label that was not on the first line.
    starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
    if not starts:
        raise json.JSONDecodeError("No JSON object or array found", cleaned, 0)
    data, _ = decoder.raw_decode(cleaned, min(starts))
    # The prompt requests one object per selected switch-model node. Accept a
    # list too, so malformed model output can still be recovered.
    return [data] if isinstance(data, dict) else data if isinstance(data, list) else []

async def parse_switch_models(node_ids, json_path, pdf_path):
    """Extract sparse, verified modular-switch records from located PDF sections."""
    if node_ids is None:
        nodes_file = "app/database/switch_models/switch_model_nodes.json"
        if not os.path.exists(nodes_file):
            return []
        with open(nodes_file, "r", encoding="utf-8") as f:
            node_ids = json.load(f)

    if isinstance(node_ids, str):
        node_ids = [node_id.strip() for node_id in node_ids.split(",") if node_id.strip()]

    explorer = TreeExplorer(json_path)
    extractor = PDFExtractor(pdf_path, json_path)
    registry = SwitchModelRegistry()
    for node_id in node_ids:
        node = explorer.get_node_by_id(node_id)
        node_title = node.get("title", "") if node else ""
        print(f"Processing switch-model node: {node_id} ({node_title})")
        text = extractor.get_text_for_node(node_id)
        if not text or "not found" in text:
            print(f"Text extraction failed for switch-model node {node_id}")
            continue
        raw_response = ""
        try:
            raw_response = parse_switch_models_text(text, node_title)
            records = _load_switch_models_json(raw_response)
        except json.JSONDecodeError:
            output_dir = "app/database/switch_models"
            os.makedirs(output_dir, exist_ok=True)
            raw_filename = os.path.join(output_dir, f"raw_{node_id}.txt")
            with open(raw_filename, "w", encoding="utf-8") as f:
                f.write(raw_response)
            print(f"Switch-model parser returned invalid JSON for node {node_id}; saved {raw_filename}.")
            registry.add_many([{"model_name": node_title}])
            continue
        # A selected node identifies exactly one switch model. Preserve that
        # title even if its PDF slice mentions component part numbers or other
        # models, and retain one identity-only record if no facts are found.
        normalized_records = [
            {**record, "model_name": node_title}
            for record in records
            if isinstance(record, dict)
        ]
        registry.add_many(normalized_records or [{"model_name": node_title}])

    switch_models = registry.to_list()
    output_dir = "app/database/switch_models"
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "switch_models.json"), "w", encoding="utf-8") as f:
        json.dump(switch_models, f, indent=2)
    return switch_models



async def parse_optics(node_ids, json_path, pdf_path):
    # If node_ids is None, try to read from file
    if node_ids is None:
        nodes_file = "app/database/optics/optic_targets.json"
        if os.path.exists(nodes_file):
            with open(nodes_file, "r", encoding="utf-8") as f:
                node_ids = json.load(f)
        else:
            return {}

    if isinstance(node_ids, str):
        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]

    # Compatibility with the old list-of-node-ids API. New callers provide a
    # node/category target so the registry key exactly matches linecard data.
    targets = []
    for item in node_ids:
        if isinstance(item, dict) and item.get("node_id") and item.get("supported_optic"):
            targets.append(item)
        elif isinstance(item, str):
            targets.append({"node_id": item, "supported_optic": item})

    registry = OpticsRegistry()
    extractor = PDFExtractor(pdf_path, json_path)
    llm = get_llm()
    
    for target in targets:
        node_id = target["node_id"]
        supported_optic = target["supported_optic"]
        print(f"Processing optic node: {node_id}")
        parser_agent = get_optics_parser_agent(registry, supported_optic, node_id=node_id)
        text = extractor.get_text_for_node(node_id)
        if text and "not found" not in text:
            memory = get_summary_memory(llm)
            await parser_agent.run(
                user_msg=(f"Requested optic category: {supported_optic}\n\n"
                          f"Extract this category from the PDF slice:\n\n{text}"),
                max_iterations=100,
                memory=memory
            )
    
    optics_data = registry.to_dict()
    
    output_dir = "app/database/optics"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    with open(os.path.join(output_dir, "optics.json"), "w", encoding="utf-8") as f:
        json.dump(optics_data, f, indent=2)
    print(f"Saved {output_dir}/optics.json")
    
    return optics_data

async def parse_linecards(node_ids, json_path, pdf_path):
    # If node_ids is None, try to read from file
    if node_ids is None:
        nodes_file = "app/database/linecards/linecard_nodes.json"
        if os.path.exists(nodes_file):
            with open(nodes_file, "r", encoding="utf-8") as f:
                node_ids = json.load(f)
        else:
            return {}

    # Handle both string, list and AgentOutput (though extract_linecards now returns string)
    if isinstance(node_ids, list):
        pass # Already a list
    elif not isinstance(node_ids, str):
        if hasattr(node_ids, 'response') and hasattr(node_ids.response, 'content'):
            node_ids = str(node_ids.response.content)
        else:
            node_ids = str(node_ids)

    if isinstance(node_ids, str):
        # The prompt asks for "Answer: <ids>", so we need to find that part
        if "Answer: " in node_ids:
            node_ids = node_ids.split("Answer: ")[-1].strip()
        
        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
    extractor = PDFExtractor(pdf_path, json_path)

    linecards_dir = "app/database/linecards"
    if not os.path.exists(linecards_dir):
        os.makedirs(linecards_dir)

    parsed_linecards = {}
    for node_id in node_ids:
        print(f"Processing node: {node_id}")
        text = extractor.get_text_for_node(node_id)

        if text and "not found" not in text:
            json_response = parse_linecard(text)

            # Save raw response anyway to avoid data loss (API cost)
            raw_filename = os.path.join(linecards_dir, f"raw_{node_id}.txt")
            with open(raw_filename, 'w', encoding='utf-8') as f:
                f.write(json_response)

            # Attempt to clean markdown if present
            cleaned_response = json_response.strip()
            if cleaned_response.startswith("```"):
                # Remove opening ```json or ```
                cleaned_response = cleaned_response.split("\n", 1)[-1]
                # Remove closing ```
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response.rsplit("```", 1)[0]
                cleaned_response = cleaned_response.strip()

            try:
                data = json.loads(cleaned_response)
                model_name = data.get("model_name")
                if model_name:
                    filename = os.path.join(linecards_dir, f"{model_name}.json")
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"Saved {filename}")
                    # Optionally remove the raw file if success
                    if os.path.exists(raw_filename):
                        os.remove(raw_filename)
                    parsed_linecards[model_name] = data
                else:
                    print(f"No model_name found in response for node {node_id}")
            except json.JSONDecodeError:
                print(f"Failed to parse JSON for node {node_id}")
                print(f"Raw response saved to {raw_filename}")
        else:
            print(f"Text extraction failed for node {node_id}")
    return parsed_linecards

def run_optics_crosscheck_on_data(linecards_data):
    """
    Applies the optics cross-check to the provided linecards data.
    Updates the data in-place and also updates the JSON files on disk.
    """
    try:
        optics_data = load_optics_data()
        ethernet_standards = load_ethernet_standards()
        
        linecards_dir = os.path.join("app", "database", "linecards")
        
        for model_name, data in linecards_data.items():
            print(f"Applying cross-check to {model_name}...")
            updated_data = process_linecard(data, optics_data, ethernet_standards)
            
            # Save the updated data back to disk
            filename = os.path.join(linecards_dir, f"{model_name}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, indent=2)
                
        return linecards_data
    except Exception as e:
        print(f"Error during optics cross-check: {e}")
        return linecards_data
