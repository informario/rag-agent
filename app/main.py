import json
import os
from dotenv import load_dotenv
from app.utils.pdf_extractor import PDFExtractor
from app.agent.linecard_parser import parse_linecard
from app.agent.linecard_extractor import get_agent as get_linecard_agent
from app.agent.optics_extractor import get_agent as get_optics_agent

load_dotenv()

async def extract_linecards(json_path):
    agent = get_linecard_agent(json_path)
    response = await agent.run(user_msg="Find all the linecards in this document and return their node_ids.", max_iterations=500)
    return response

async def extract_optics(json_path):
    agent, registry = get_optics_agent(json_path)
    response = await agent.run(user_msg="Find all the optics in this document and return their node_ids.", max_iterations=500)
    return response, registry.to_dict()

def parse_linecards(node_ids, json_path, pdf_path):
    node_ids = node_ids.replace("Answer: ", "").split(",")
    extractor = PDFExtractor(pdf_path, json_path)

    if not os.path.exists("app/database"):
        os.makedirs("app/database")

    for node_id in node_ids:
        print(f"Processing node: {node_id}")
        text = extractor.get_text_for_node(node_id)

        if text and "not found" not in text:
            json_response = parse_linecard(text)

            # Save raw response anyway to avoid data loss (API cost)
            raw_filename = f"app/database/raw_{node_id}.txt"
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
                    filename = f"app/database/{model_name}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    print(f"Saved {filename}")
                    # Optionally remove the raw file if success
                    if os.path.exists(raw_filename):
                        os.remove(raw_filename)
                else:
                    print(f"No model_name found in response for node {node_id}")
            except json.JSONDecodeError:
                print(f"Failed to parse JSON for node {node_id}")
                print(f"Raw response saved to {raw_filename}")
        else:
            print(f"Text extraction failed for node {node_id}")


async def run_extraction():
    pdf_path = "CE16800_hardware_description.pdf"
    json_path = "app/database/CE16800_hardware_description_structure.json"

    #linecard_node_ids = await extract_linecards(json_path)
    response, registry = await extract_optics(json_path)
    print("##")
    print(response)
    print("##")
    print(registry)
    #parse_linecards(linecard_node_ids, json_path, pdf_path)




if __name__ == "__main__":
    import asyncio
    asyncio.run(run_extraction())
