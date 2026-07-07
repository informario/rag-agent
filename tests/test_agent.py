from app.agent.linecard_extractor import get_agent
import os

def test_agent_initialization():
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "sk-dummy"
    
    agent = get_agent()
    assert agent is not None
    assert len(agent.get_tools()) == 3
    
    tool_names = [tool.metadata.name for tool in agent.get_tools()]
    assert "go_down" in tool_names
    assert "go_up" in tool_names
    assert "get_current_info" in tool_names

if __name__ == "__main__":
    test_agent_initialization()

