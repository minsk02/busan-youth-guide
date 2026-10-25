"""Validate the real Busan Youth API without printing credentials or raw records.

Uses only the Python standard library. Raw responses stay in ignored data/raw/.
The shareable report contains aggregate metadata, never individual records.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://apis.data.go.kr/6260000/YouthSupProgService/getYouthSupProg"
SOURCE = "https://www.data.go.kr/data/15163604/openapi.do"
KST = timezone(timedelta(hours=9))
FIELDS = (
    "busPlcNm", "bizNm", "trgtNm", "aplyBgngYmd", "aplyEndYmd",
    "schdlBgngYmd", "schdlEndYmd", "paReStat", "mngtMson",
    "inqryTlphnNo", "hopgUrlAddr", "frstRegistPnttm",
)
DATE_FIELDS = ("aplyBgngYmd", "aplyEndYmd", "schdlBgngYmd", "schdlEndYmd")
FILTER_FIELDS = {"busPlcNm", "bizNm", "aplyBgngYmd", "aplyEndYmd", "paReStat"}


class ValidationError(Exception):
    """A safe error that does not contain request URLs or server-supplied text."""


def load_key(env_path: Path) -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key and env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"\s*(?:export\s+)?DATA_GO_KR_SERVICE_KEY\s*=\s*(.*?)\s*$", line)
            if match:
                key = match.group(1)
                if key[:1] in ("'", '"') and key[-1:] == key[:1]:
                    key = key[1:-1]
                else:
                    key = re.split(r"\s+#", key, maxsplit=1)[0].strip()
                break
    if not key:
        raise ValidationError("DATA_GO_KR_SERVICE_KEY is missing or empty.")
    # unquote does not change literal '+'. urlencode encodes the raw key once.
    return unquote(key)


def parse_page(payload: bytes) -> dict:
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        # Gateway errors can be XML even when JSON was requested.
        try:
            xml = ET.fromstring(payload)
            code = xml.findtext(".//returnReasonCode") or xml.findtext(".//resultCode")
        except ET.ParseError:
            code = None
        safe_code = code if code and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code) else "unknown"
        raise ValidationError(f"Non-JSON API response (gateway code: {safe_code}).") from None
    try:
        response = document["response"]
        code = str(response["header"]["resultCode"])
        if code != "00":
            safe_code = code if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code) else "unknown"
            raise ValidationError(f"API business failure (code: {safe_code}).")
        body = response["body"]
        items = body.get("items")
        if items in (None, ""):
            items = []
        elif isinstance(items, dict):
            items = items.get("item", [])
        if items in (None, ""):
            items = []
        elif isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValidationError("Invalid API item structure.")
        result = {
            "items": items,
            "total_count": int(body["totalCount"]),
            "page_no": int(body["pageNo"]),
            "num_rows": int(body["numOfRows"]),
        }
        if result["total_count"] < 0 or result["page_no"] < 1 or result["num_rows"] < 1:
            raise ValidationError("Invalid API pagination values.")
        return result
    except (KeyError, TypeError, ValueError):
        raise ValidationError("Unexpected API response schema.") from None


def fetch_page(key: str, page_no: int, rows: int, filters: dict | None = None) -> tuple[bytes, dict]:
    filters = filters or {}
    if set(filters) - FILTER_FIELDS:
        raise ValidationError("Unsupported API filter name.")
    query = urlencode({
        "serviceKey": key, "pageNo": page_no,
        "numOfRows": rows, "resultType": "json",
        **filters,
    })
    request = Request(ENDPOINT + "?" + query, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=25) as response:
            payload = response.read()
    except HTTPError as error:
        raise ValidationError(f"API HTTP failure: {error.code}. Request URL suppressed.") from None
    except (URLError, TimeoutError, OSError):
        raise ValidationError("API network or timeout failure. Request URL suppressed.") from None
    return payload, parse_page(payload)


def fingerprint(item: dict) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def collect_pages(fetch, rows: int, max_pages: int, save_page=None) -> tuple[list[dict], dict]:
    records, totals, sizes = [], [], []
    page_hashes: set[str] = set()
    stop_reason = "max_pages_reached"
    for page_no in range(1, max_pages + 1):
        payload, page = fetch(page_no, rows)
        if page["page_no"] != page_no:
            raise ValidationError("API returned an unexpected page number.")
        if save_page:
            save_page(page_no, payload)
        totals.append(page["total_count"])
        sizes.append(len(page["items"]))
        page_hash = fingerprint({"items": page["items"]})
        if page["items"] and page_hash in page_hashes:
            stop_reason = "repeated_page_detected"
            break
        page_hashes.add(page_hash)
        records.extend(page["items"])
        if not page["items"]:
            stop_reason = "empty_page"
            break
        if len(records) >= page["total_count"]:
            stop_reason = "reported_total_reached"
            break
    complete = bool(totals) and len(set(totals)) == 1 and len(records) == totals[0]
    complete = complete and stop_reason in ("reported_total_reached", "empty_page")
    return records, {
        "reported_total": totals[0] if totals else None,
        "reported_totals_consistent": len(set(totals)) == 1,
        "pages_requested": len(totals), "page_sizes": sizes,
        "collected_count": len(records), "complete": complete,
        "stop_reason": stop_reason,
    }


def parse_date(value) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def is_missing(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def summarize(records: list[dict], as_of: date) -> dict:
    missing = {field: sum(is_missing(item.get(field)) for item in records) for field in FIELDS}
    invalid_dates = {
        field: sum(not is_missing(item.get(field)) and parse_date(item.get(field)) is None for item in records)
        for field in DATE_FIELDS
    }
    statuses, categories = Counter(), Counter()
    periods = Counter({"within": 0, "before": 0, "after": 0, "unknown": 0, "reversed": 0})
    status_conflicts = 0
    date_ranges = {}
    for field in DATE_FIELDS:
        parsed = [value for item in records if (value := parse_date(item.get(field))) is not None]
        date_ranges[field] = {"min": str(min(parsed)) if parsed else None, "max": str(max(parsed)) if parsed else None}
    valid_urls, invalid_urls = 0, 0
    for item in records:
        status = str(item.get("paReStat") or "(missing)").strip()
        statuses[status] += 1
        categories[str(item.get("busPlcNm") or "(missing)").strip()] += 1
        start, end = parse_date(item.get("aplyBgngYmd")), parse_date(item.get("aplyEndYmd"))
        if start is None or end is None:
            periods["unknown"] += 1
        elif start > end:
            periods["reversed"] += 1
        elif as_of < start:
            periods["before"] += 1
        elif as_of > end:
            periods["after"] += 1
        else:
            periods["within"] += 1
        if status == "모집중" and end is not None and as_of > end:
            status_conflicts += 1
        value = item.get("hopgUrlAddr")
        if not is_missing(value):
            try:
                url = urlsplit(str(value).strip())
                valid = url.scheme in ("http", "https") and bool(url.hostname) and not url.username and not url.password
            except ValueError:
                valid = False
            valid_urls += int(valid)
            invalid_urls += int(not valid)
    registration_dates = [str(item["frstRegistPnttm"]) for item in records if not is_missing(item.get("frstRegistPnttm"))]
    return {
        "observed_fields": sorted({field for item in records for field in item}),
        "missing_count": missing, "invalid_date_count": invalid_dates,
        "date_ranges": date_ranges,
        "source_status_counts": dict(statuses), "category_counts": dict(categories),
        "application_period_vs_as_of": dict(periods),
        "source_recruiting_but_end_date_passed": status_conflicts,
        "exact_duplicate_record_count": len(records) - len({fingerprint(item) for item in records}),
        "homepage_url_syntax": {"valid": valid_urls, "invalid": invalid_urls, "missing": missing["hopgUrlAddr"], "destination_checked": False},
        "registration_date_range": {"min": min(registration_dates) if registration_dates else None, "max": max(registration_dates) if registration_dates else None},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(KST).date())
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--check-filters", action="store_true", help="Also probe category and recruitment filters.")
    args = parser.parse_args()
    if not 1 <= args.rows <= 100 or not 1 <= args.max_pages <= 100:
        parser.error("rows must be 1..100 and max-pages must be 1..100")
    try:
        key = load_key(ROOT / ".env")
        checked_at = datetime.now(KST)
        run_dir = ROOT / "data" / "raw" / checked_at.strftime("%Y%m%dT%H%M%S%f")
        run_dir.mkdir(parents=True, exist_ok=False)
        def save_page(number, payload):
            (run_dir / f"page-{number:03d}.json").write_bytes(payload)
        records, pagination = collect_pages(lambda page, rows: fetch_page(key, page, rows), args.rows, args.max_pages, save_page)
        filter_checks = []
        if args.check_filters and pagination["complete"]:
            for field, value in (("busPlcNm", "교육분야"), ("paReStat", "모집중")):
                payload, filtered = fetch_page(key, 1, args.rows, {field: value})
                (run_dir / f"filter-{field}.json").write_bytes(payload)
                expected_count = sum(item.get(field) == value for item in records)
                filter_checks.append({
                    "field": field, "value": value,
                    "reported_total": filtered["total_count"],
                    "expected_count_from_full_collection": expected_count,
                    "sample_count": len(filtered["items"]),
                    "sample_matches_filter": all(item.get(field) == value for item in filtered["items"]),
                    "reported_total_matches_local_count": filtered["total_count"] == expected_count,
                })
        report = {
            "checked_at_kst": checked_at.isoformat(), "as_of": args.as_of.isoformat(),
            "endpoint": ENDPOINT, "source": SOURCE,
            "request": {"pageNo": 1, "numOfRows": args.rows, "resultType": "json"},
            "http_status": 200, "result_code": "00", "pagination": pagination,
            "quality": summarize(records, args.as_of),
            "filter_checks": filter_checks,
            "limitations": [
                "Homepage destinations and actual application availability were not checked.",
                "Source recruitment labels are not independently verified.",
                "Date counts use inclusive parsed date ranges, not a confirmed eligibility decision.",
                "No unique source identifier, address, or fee field was observed unless listed in observed_fields.",
            ],
        }
        report_dir = ROOT / "data" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "youth-program-validation.json"
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if key in output or urlencode({"serviceKey": key}) in output:
            raise ValidationError("Credential detected in report; report was not written.")
        report_path.write_text(output, encoding="utf-8")
        print(f"Validated {len(records)} rows across {pagination['pages_requested']} pages; complete={pagination['complete']}")
        print("Aggregate report: data/reports/youth-program-validation.json")
        print("Raw responses are local and excluded from Git.")
        if not pagination["complete"]:
            return 2
        failed_filters = [check for check in filter_checks if not (
            check["sample_matches_filter"] and check["reported_total_matches_local_count"]
        )]
        if failed_filters:
            print(f"Warning: {len(failed_filters)} upstream filter check(s) failed; use local filtering.")
            return 3
        return 0
    except ValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print("Local file operation failed; details suppressed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
