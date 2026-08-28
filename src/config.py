import os

from dotenv import load_dotenv


load_dotenv()
load_dotenv(".env.transcricao")
load_dotenv(".env.fetch-site")

ATTACHMENTS_MAX_ITEMS = int(os.getenv("ATTACHMENTS_MAX_ITEMS", "10"))

SYSTEM_PROMPT_FILE = os.getenv("SYSTEM_PROMPT_FILE")
ROUTER_CLASSIFICATION_PROMPT = os.getenv("ROUTER_CLASSIFICATION_PROMPT")
SEARCH_AGENT_PROMPT = os.getenv("SEARCH_AGENT_PROMPT")
TRANSCRIPTION_AGENT_PROMPT = os.getenv("TRANSCRIPTION_AGENT_PROMPT")
IMAGE_AGENT_PROMPT = os.getenv(
    "IMAGE_AGENT_PROMPT",
    "prompts/image_agent_prompt.md",
)
IMAGE_AUTHENTICITY_PROMPT = os.getenv(
    "IMAGE_AUTHENTICITY_PROMPT",
    "prompts/image_authenticity_prompt.md",
)
YOUTUBE_AGENT_PROMPT = os.getenv(
    "YOUTUBE_AGENT_PROMPT",
    "prompts/youtube_agent_prompt.md",
)
ROUTER_SYNTHESIS_PROMPT = os.getenv("ROUTER_SYNTHESIS_PROMPT")
REANALYSIS_SYNTHESIS_PROMPT = os.getenv(
    "REANALYSIS_SYNTHESIS_PROMPT",
    "prompts/reanalysis_synthesis_prompt.md",
)
DUPLICATE_ANALYSIS_JUDGE_PROMPT = os.getenv(
    "DUPLICATE_ANALYSIS_JUDGE_PROMPT",
    "prompts/duplicate_analysis_judge_prompt.md",
)

TRANSCRIPTION_REQUEST_URL = os.getenv("TRANSCRIPTION_REQUEST_URL")
TRANSCRIPTION_STATUS_URL = os.getenv("TRANSCRIPTION_STATUS_URL")
TRANSCRIPTION_API_KEY = os.getenv("TRANSCRIPTION_API_KEY")
TRANSCRIPTION_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("TRANSCRIPTION_REQUEST_TIMEOUT_SECONDS", "60")
)
TRANSCRIPTION_POLL_INTERVAL_SECONDS = float(
    os.getenv("TRANSCRIPTION_POLL_INTERVAL_SECONDS", "5")
)
TRANSCRIPTION_TIMEOUT_SECONDS = float(
    os.getenv("TRANSCRIPTION_TIMEOUT_SECONDS", "480")
)
TRANSCRIPTION_MEDIA_RELAY_ENABLED = (
    os.getenv("TRANSCRIPTION_MEDIA_RELAY_ENABLED", "false").lower() == "true"
)
TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS = {
    host.strip().lower()
    for host in os.getenv(
        "TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS",
        "nat-bot.mpac.mp.br",
    ).split(",")
    if host.strip()
}

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCS_OBJECT_PREFIX = os.getenv(
    "GCS_OBJECT_PREFIX",
    "transcription-media",
)
GCS_SIGNED_URL_TTL_SECONDS = int(
    os.getenv("GCS_SIGNED_URL_TTL_SECONDS", "900")
)
GCS_MEDIA_MAX_SIZE_MIB = int(os.getenv("GCS_MEDIA_MAX_SIZE_MIB", "250"))
GCS_SERVICE_ACCOUNT_FILE = os.getenv("GCS_SERVICE_ACCOUNT_FILE")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "vllm").strip().lower()
SEARCH_GOOGLE_SEARCH_ENABLED = (
    os.getenv("SEARCH_GOOGLE_SEARCH_ENABLED", "false").strip().lower() == "true"
)

FETCH_SITE_BASE_URL = (os.getenv("FETCH_SITE_BASE_URL") or "").rstrip("/")
FETCH_SITE_BEARER_TOKEN = os.getenv("FETCH_SITE_BEARER_TOKEN")
FETCH_SITE_SUBMIT_URL = os.getenv(
    "FETCH_SITE_SUBMIT_URL",
    f"{FETCH_SITE_BASE_URL}/document_to_markdown",
)
FETCH_SITE_STATUS_URL_TEMPLATE = os.getenv(
    "FETCH_SITE_STATUS_URL_TEMPLATE",
    f"{FETCH_SITE_BASE_URL}/status/{{task_id}}",
)
FETCH_SITE_TIMEOUT_SECONDS = float(
    os.getenv("FETCH_SITE_TIMEOUT_SECONDS", "60")
)
FETCH_SITE_POLL_INTERVAL_SECONDS = float(
    os.getenv("FETCH_SITE_POLL_INTERVAL_SECONDS", "2")
)
