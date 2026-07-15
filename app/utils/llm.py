import os
from dotenv import load_dotenv
from llama_index.llms.openrouter import OpenRouter
from llama_index.llms.openai import OpenAI
from llama_index.llms.anthropic import Anthropic

def get_llm():
    load_dotenv("app/.env")
    provider = os.getenv("LLM_PROVIDER")
    model = os.getenv("MODEL")
    api_key = os.getenv("API_KEY")

    if provider == "openai":
        return OpenAI(model=model, api_key=api_key)
    elif provider == "anthropic":
        return Anthropic(
            model=model, 
            api_key=api_key, 
            default_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
        )
    elif provider == "openrouter":
        return OpenRouter(
            api_key=api_key,
            model=model,
            max_tokens=4096,
            context_window=131072,
            extra_headers={
                "X-Cache-Control": "ephemeral"
            },
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
