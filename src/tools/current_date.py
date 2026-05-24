from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool


@tool("current_date")
def current_date() -> str:
    """Retorna a data e hora atual no formato YYYY-MM-DD H:i:s."""
    tz = ZoneInfo("America/Rio_Branco")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
