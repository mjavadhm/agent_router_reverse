import os
from dotenv import load_dotenv

load_dotenv()

UPSTREAM_URL = os.getenv("UPSTREAM_URL", "https://agentrouter.org").rstrip("/")
CLINE_USER_AGENT = os.getenv("CLINE_USER_AGENT", "Cline/4.1.17")
STAINLESS_LANG = os.getenv("STAINLESS_LANG", "js")
STAINLESS_RUNTIME = os.getenv("STAINLESS_RUNTIME", "node")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
