import json
import csv
import os
from app.model.diff import match_strings

def load_optics_data():
    optics_path = os.path.join("app", "database", "optics", "optics.json")
    with open(optics_path, "r", encoding="utf-8") as f:
        return json.load(f)["optics"]

def load_ethernet_standards():
    standards_path = os.path.join("app", "agent", "ethernet_standards.csv")
    standards = {}
    with open(standards_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            standards[row["nombre"]] = row["speedxbreakout"]
    return standards

def normalize_speed(s):
    return "".join(s.lower().split()).replace("ge", "g")

def speeds_match(s1, s2):
    return normalize_speed(s1) == normalize_speed(s2)

def process_linecard(linecard_data, optics_data, ethernet_standards):
    port_configs = linecard_data.get("port_configuration", {})
    for port_name, config in port_configs.items():
        supported_optics = config.get("supported_optics", [])
        speeds = config.get("speeds", {})
        explicit_speeds = {}
        
        for supported_optic_name in supported_optics:
            # Find matching optics categories in optics_data
            for optics_category, category_data in optics_data.items():
                if match_strings(supported_optic_name, optics_category):
                    # Found a matching category, check its standards
                    for standard_name in category_data.get("standards", []):
                        # Find matching standard in ethernet_standards
                        for eth_std_name, speedxbreakout in ethernet_standards.items():
                            if match_strings(standard_name, eth_std_name):
                                # Found a matching standard, check if its speed is in linecard speeds
                                for speed_key, speed_val in speeds.items():
                                    if speeds_match(speedxbreakout, speed_key):
                                        explicit_speeds[speed_key] = speed_val
        
        config["explicitley_supported_speeds"] = explicit_speeds
    
    return linecard_data
