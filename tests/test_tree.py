import os
from app.utils.tree import TreeExplorer

def test_navigation():
    json_path = os.path.join('app', 'database', 'CE16800_hardware_description_structure.json')
    explorer = TreeExplorer(json_path)

    explorer.go_down("0004")
    assert explorer.current_node['node_id'] == "0004"
    assert explorer.current_node['title'] == "Cabinet"

    explorer.go_down("0005")
    assert explorer.current_node['node_id'] == "0005"
    assert explorer.current_node['title'] == "Introduction to the A610-22 Cabinet"
    assert explorer.go_down("0006") == False

    explorer.go_up()
    assert explorer.current_node['node_id'] == "0004"
    assert explorer.current_node['title'] == "Cabinet"

    explorer.go_up()
    assert explorer.current_node['node_id'] == "root"
    assert explorer.current_node['title'] == "CE16800_hardware_description.pdf"

    assert explorer.go_up() == False
    explorer.go_down("0004")
    explorer.go_down("0005")
    explorer.reset_to_root()
    assert explorer.current_node['node_id'] == "root"
    assert explorer.current_node['title'] == "CE16800_hardware_description.pdf"