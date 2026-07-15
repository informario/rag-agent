pip install -r requirements.txt

create .env file inside app directory
LLM_PROVIDER=openrouter
API_KEY=sk-or-v1-<complete-here>
MODEL=gpt-oss-120b:exacto

tested with openrouter oss 120b:exacto

python -m app.app
