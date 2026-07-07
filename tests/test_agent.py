from app.agent.linecard_extractor import get_agent
import os

def test_agent_initialization():
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "sk-dummy"
    
    agent = get_agent()
    assert agent is not None
    
    # In AgentWorkflow, tools are stored in the workflow context or 
    # we can check if they are correctly passed to the workflow.
    # For now, let's just check if it initializes without error.

if __name__ == "__main__":
    test_agent_initialization()

