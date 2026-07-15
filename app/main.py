import json
import os
from dotenv import load_dotenv
from app.utils.llm import get_llm, get_summary_memory
from app.utils.pdf_extractor import PDFExtractor
from app.agent.linecard_parser import parse_linecard
from app.agent.linecard_extractor import get_agent as get_linecard_agent
from app.agent.optic_extractor import get_agent as get_optics_node_agent
from app.agent.optic_parser import get_agent as get_optics_parser_agent, OpticsRegistry

load_dotenv()

async def extract_linecards(json_path):
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
    
    with open(os.path.join(output_dir, "linecard_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(node_list, f, indent=2)
    
    return node_ids_str

async def extract_optics(json_path):
    node_extractor_agent = get_optics_node_agent(json_path)
    llm = get_llm()
    memory = get_summary_memory(llm)
    node_response = await node_extractor_agent.run(
        user_msg="Find all the sections that list optic modules and return their node_ids.", 
        max_iterations=500,
        memory=memory
    )
    node_ids_str = str(node_response.response.content)

    # Save node IDs to file
    output_dir = "app/database/optics"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Process the string to get a clean list
    clean_ids = node_ids_str
    if "Answer: " in clean_ids:
        clean_ids = clean_ids.split("Answer: ")[-1].strip()
    node_list = [nid.strip() for nid in clean_ids.split(",") if nid.strip()]

    with open(os.path.join(output_dir, "optic_nodes.json"), "w", encoding="utf-8") as f:
        json.dump(node_list, f, indent=2)

    return node_ids_str

async def parse_optics(node_ids, json_path, pdf_path):
    # If node_ids is None, try to read from file
    if node_ids is None:
        nodes_file = "app/database/optics/optic_nodes.json"
        if os.path.exists(nodes_file):
            with open(nodes_file, "r", encoding="utf-8") as f:
                node_ids = json.load(f)
        else:
            return {}

    # Handle both string, list and AgentOutput
    if isinstance(node_ids, list):
        pass # Already a list
    elif not isinstance(node_ids, str):
        if hasattr(node_ids, 'response') and hasattr(node_ids.response, 'content'):
            node_ids = str(node_ids.response.content)
        else:
            node_ids = str(node_ids)

    if isinstance(node_ids, str):
        # Find the Answer part
        if "Answer: " in node_ids:
            node_ids = node_ids.split("Answer: ")[-1].strip()
        
        node_ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
    
    registry = OpticsRegistry()
    extractor = PDFExtractor(pdf_path, json_path)
    llm = get_llm()
    
    for node_id in node_ids:
        print(f"Processing optic node: {node_id}")
        parser_agent = get_optics_parser_agent(registry, node_id=node_id)
        text = extractor.get_text_for_node(node_id)
        if text and "not found" not in text:
            memory = get_summary_memory(llm)
            await parser_agent.run(
                user_msg=f"Extract optics from this text:\n\n{text}", 
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
