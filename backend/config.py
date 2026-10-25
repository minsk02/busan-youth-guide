"""프로젝트 설정. 인증키는 서버에서만 읽는다."""

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
CATEGORIES = ("교육분야", "참여·권리분야", "복지·문화분야", "일자리분야", "주거분야")
SOURCE_URL = "https://www.data.go.kr/data/15163604/openapi.do"


def settings():
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.removeprefix("export ").split("=", 1)
            value = value.strip()
            if value[:1] in ("'", '"') and value[-1:] == value[:1]:
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].strip()
            values[name.strip()] = value
    values.update(os.environ)
    return {
        "DATABASE": str(ROOT / "data" / "app.db"),
        "DATA_GO_KR_SERVICE_KEY": values.get("DATA_GO_KR_SERVICE_KEY", ""),
        "OPENAI_API_KEY": values.get("OPENAI_API_KEY", ""),
        "OPENAI_MODEL": values.get("OPENAI_MODEL", "gpt-4o-mini"),
        "AI_RATE_LIMIT": 12,
        "TODAY": None,
    }


def today():
    return datetime.now(KST).date()


def now_iso():
    return datetime.now(KST).isoformat(timespec="seconds")
