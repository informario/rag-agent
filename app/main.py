import asyncio
from dotenv import load_dotenv
from app.agent.linecard_extractor import get_agent

load_dotenv()

async def run_extraction():
    agent = get_agent("app/database/CE16800_hardware_description_structure.json")
    response = await agent.run(user_msg="Find all the linecards in this document and return their node_ids.")
    print("Agent Response:")
    print(str(response))

if __name__ == "__main__":
    asyncio.run(run_extraction())