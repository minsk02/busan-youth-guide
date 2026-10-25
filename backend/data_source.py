"""부산 API에서 완전한 수집본을 받은 뒤 DB에 반영한다."""

import json
from urllib.parse import unquote, urlsplit

from scripts.validate_youth_api import collect_pages, fetch_page, fingerprint, parse_date, ValidationError
from .config import now_iso
from .database import start_sync, fail_sync, save_snapshot
from .errors import ServiceError


def safe_homepage(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def normalize(record, fetched_at):
    if not isinstance(record, dict) or not isinstance(record.get("bizNm"), str) or not record["bizNm"].strip():
        raise ServiceError("사업명이 없는 응답이 있어 이번 수집본을 저장하지 않았습니다.", 502, "invalid_source")

    def text(field):
        value = record.get(field)
        return value.strip() if isinstance(value, str) else ""

    def day(field):
        parsed = parse_date(record.get(field))
        return parsed.isoformat() if parsed else None

    return {
        "content_hash": fingerprint(record),
        "title": text("bizNm"), "category": text("busPlcNm"),
        "target_text": text("trgtNm"),
        "application_start": day("aplyBgngYmd"), "application_end": day("aplyEndYmd"),
        "schedule_start": day("schdlBgngYmd"), "schedule_end": day("schdlEndYmd"),
        "source_status": text("paReStat"), "organizer": text("mngtMson"),
        "contact_phone": text("inqryTlphnNo") or None,
        "homepage_url": safe_homepage(text("hopgUrlAddr")),
        "source_registered_at": text("frstRegistPnttm") or None,
        "raw_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        "fetched_at": fetched_at,
    }


def sync_programs(path, key, fetcher=None):
    if not key:
        raise ServiceError("공공데이터 인증키가 설정되지 않았습니다.", 503, "data_key_missing")
    run_id = start_sync(path)
    try:
        fetcher = fetcher or (lambda page, rows: fetch_page(unquote(key), page, rows))
        raw, pagination = collect_pages(fetcher, 100, 30)
        if not pagination["complete"] or not raw:
            raise ServiceError("수집이 불완전하거나 0건입니다. 기존 데이터를 유지합니다.", 502, "incomplete_source")
        fetched_at = now_iso()
        records = [normalize(record, fetched_at) for record in raw]
        stored = save_snapshot(path, records, run_id, len(raw))
        return {"source_count": len(raw), "stored_count": stored, "duplicate_count": len(raw) - stored, "fetched_at": fetched_at}
    except (ValidationError, ServiceError) as error:
        message = error.message if isinstance(error, ServiceError) else "공공데이터 API 호출 또는 응답 검증에 실패했습니다."
        fail_sync(path, run_id, message)
        raise ServiceError(message, 502, "sync_failed") from None
    except Exception:
        fail_sync(path, run_id, "데이터 저장에 실패했습니다. 기존 수집본을 확인해주세요.")
        raise ServiceError("데이터 저장에 실패했습니다. 기존 수집본을 확인해주세요.", 500, "storage_failed") from None
