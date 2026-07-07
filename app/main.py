import json
import os
from dotenv import load_dotenv
from app.utils.pdf_extractor import PDFExtractor
from app.agent.linecard_parser import parse_linecard

load_dotenv()

def run_extraction():
    """
    agent = get_agent("app/database/CE16800_hardware_description_structure.json")
    response = agent.run(user_msg="Find all the linecards in this document and return their node_ids.")
    print("Agent Response:")
    print(str(response)) #Answer: 0130,0135,0139,0140,0144,0149,0153,0154,0159,0163,0164,0168,0173,0177,0180,0185,0188
    """

    answer = "Answer: 0159"#0130,0135,0139,0140,0144,0149,0153,0154,0159,0163,0164,0168,0173,0177,0180,0185,0188"
    node_ids = answer.replace("Answer: ", "").split(",")
    
    pdf_path = "CE16800_hardware_description.pdf"
    json_path = "app/database/CE16800_hardware_description_structure.json"
    
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


if __name__ == "__main__":
    run_extraction()

    """
    pdf_path = "CE16800_hardware_description.pdf"
    json_path = "app/database/CE16800_hardware_description_structure.json"
    extractor = PDFExtractor(pdf_path, json_path)
    node_ids = ["0130","0135","0139","0140"]
    for node_id in node_ids:
        text = extractor.get_text_for_node(node_id)
        print(text)
    """