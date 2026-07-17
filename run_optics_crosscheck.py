import os
import json
import glob
from app.agent.optics_crosscheck import load_optics_data, load_ethernet_standards, process_linecard

def main():
    try:
        optics_data = load_optics_data()
        ethernet_standards = load_ethernet_standards()
        
        linecards_dir = os.path.join("app", "database", "linecards")
        json_files = glob.glob(os.path.join(linecards_dir, "*.json"))
        
        if not json_files:
            print(f"No JSON files found in {linecards_dir}")
            return

        for file_path in json_files:
            filename = os.path.basename(file_path)
            if filename == "linecard_nodes.json":
                continue
                
            print(f"Processing {filename}...")
            with open(file_path, "r", encoding="utf-8") as f:
                linecard_data = json.load(f)
                
            updated_data = process_linecard(linecard_data, optics_data, ethernet_standards)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=2)
                
        print("Successfully updated all linecard files.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
