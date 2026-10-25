"""조건 검증, 검색, 추천 점수, 비교. 프로그램 사실은 DB에서 가져온다."""

from datetime import date
import re

from .config import CATEGORIES, SOURCE_URL
from .database import list_programs, find_program
from .errors import ServiceError

CRITERIA_KEYS = {"category", "keywords", "target_keyword", "apply_from", "apply_until", "only_open"}


def validate_criteria(value):
    if not isinstance(value, dict) or set(value) - CRITERIA_KEYS:
        raise ServiceError("검색 조건의 형식을 확인해주세요.")
    category = value.get("category") or None
    if category not in (*CATEGORIES, None):
        raise ServiceError("지원하는 분야를 선택해주세요.")
    keywords = value.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 5:
        raise ServiceError("관심 키워드는 최대 5개까지 입력할 수 있습니다.")
    if any(not isinstance(word, str) or not 1 <= len(word.strip()) <= 30 for word in keywords):
        raise ServiceError("키워드는 1~30자의 문자열이어야 합니다.")
    keywords = list(dict.fromkeys(word.strip() for word in keywords))
    target = value.get("target_keyword") or None
    if target is not None and (not isinstance(target, str) or len(target) > 40):
        raise ServiceError("대상 키워드는 40자 이내로 입력해주세요.")
    only_open = value.get("only_open", True)
    if not isinstance(only_open, bool):
        raise ServiceError("모집 상태 조건의 형식을 확인해주세요.")
    dates = {}
    for field in ("apply_from", "apply_until"):
        raw = value.get(field) or None
        if raw is not None:
            if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                raise ServiceError("날짜는 YYYY-MM-DD 형식으로 입력해주세요.")
            try:
                date.fromisoformat(raw)
            except ValueError:
                raise ServiceError("실제 존재하는 날짜를 입력해주세요.") from None
        dates[field] = raw
    if dates["apply_from"] and dates["apply_until"] and dates["apply_from"] > dates["apply_until"]:
        raise ServiceError("검색 시작일이 종료일보다 늦습니다.")
    return {"category": category, "keywords": keywords, "target_keyword": target.strip() if target else None, **dates, "only_open": only_open}


def recruitment(program, as_of):
    start, end = program["application_start"], program["application_end"]
    current = as_of.isoformat()
    source = program["source_status"]
    if not start or not end or start > end:
        return "unknown", "기간 확인 필요"
    if current > end:
        return ("check", "상태 확인 필요") if source == "모집중" else ("closed", "신청기간 종료")
    if current < start:
        return ("check", "상태 확인 필요") if source == "모집마감" else ("upcoming", "신청 예정")
    if source != "모집중":
        return "check", "상태 확인 필요"
    return "open", "신청기간 내"


def public_program(program, as_of):
    status, label = recruitment(program, as_of)
    fields = ("id", "title", "category", "target_text", "application_start", "application_end", "schedule_start", "schedule_end", "source_status", "organizer", "contact_phone", "homepage_url", "source_registered_at", "fetched_at")
    result = {name: program[name] for name in fields}
    result.update(status=status, status_label=label, source_url=SOURCE_URL)
    result["days_left"] = (date.fromisoformat(program["application_end"]) - as_of).days if program["application_end"] else None
    result["notice"] = "대상 조건과 실제 접수 여부는 원문에서 확인해주세요."
    return result


def recommendation_reasons(program, criteria, as_of):
    score, reasons = 0, []
    if criteria["category"]:
        score += 5
        reasons.append(f"선택한 {criteria['category']}에 해당합니다.")
    for word in criteria["keywords"]:
        if word.casefold() in program["title"].casefold():
            score += 4
            reasons.append(f"사업명에 ‘{word}’이(가) 들어 있습니다.")
        elif word.casefold() in (program["target_text"] + " " + program["organizer"]).casefold():
            score += 1
            reasons.append(f"대상 또는 기관 정보에 ‘{word}’이(가) 들어 있습니다.")
    if criteria["target_keyword"]:
        score += 2
        reasons.append(f"대상 원문에 ‘{criteria['target_keyword']}’이(가) 들어 있습니다. 참가 자격 확정은 아닙니다.")
    if recruitment(program, as_of)[0] == "open":
        score += 1
        reasons.append("수집된 모집 상태와 날짜가 모두 현재 신청기간에 해당합니다.")
    return score, reasons


def search(path, criteria, as_of, mode="search", page=1):
    matched = []
    for program in list_programs(path, criteria["category"]):
        if criteria["only_open"] and recruitment(program, as_of)[0] != "open":
            continue
        text = (program["title"] + " " + program["target_text"] + " " + program["organizer"]).casefold()
        if criteria["keywords"] and not any(word.casefold() in text for word in criteria["keywords"]):
            continue
        if criteria["target_keyword"] and criteria["target_keyword"].casefold() not in program["target_text"].casefold():
            continue
        # 신청기간과 사용자가 고른 기간이 하루라도 겹치는 항목을 찾는다.
        start, end = program["application_start"], program["application_end"]
        if criteria["apply_from"] and (not end or end < criteria["apply_from"]):
            continue
        if criteria["apply_until"] and (not start or start > criteria["apply_until"]):
            continue
        item = public_program(program, as_of)
        score, reasons = recommendation_reasons(program, criteria, as_of)
        item.update(score=score, reasons=reasons if mode == "recommend" else [])
        matched.append(item)
    def order(item):
        return (item["status"] != "open", -(item["score"] if mode == "recommend" else 0), item["application_end"] or "9999-12-31", item["id"])
    matched.sort(key=order)
    count, page_size = len(matched), 12
    return {
        "items": matched[(page - 1) * page_size:page * page_size],
        "total": count, "page": page, "page_size": page_size,
        "pages": (count + page_size - 1) // page_size,
        "criteria": criteria, "mode": mode, "as_of": as_of.isoformat(),
        "notice": "조건에 맞는 항목이 없습니다. 분야나 키워드를 줄여 다시 찾아보세요." if not count else "홈페이지의 실제 접수 여부와 대상 조건을 확인해주세요.",
    }


def detail(path, program_id, as_of):
    program = find_program(path, program_id)
    if not program:
        raise ServiceError("항목을 찾을 수 없습니다. 데이터가 갱신되었다면 다시 검색해주세요.", 404, "program_not_found")
    return public_program(program, as_of)


def compare(path, ids, as_of):
    if not isinstance(ids, list) or not 2 <= len(ids) <= 3:
        raise ServiceError("비교할 프로그램을 2~3개 선택해주세요.")
    if any(type(program_id) is not int or program_id < 1 for program_id in ids) or len(set(ids)) != len(ids):
        raise ServiceError("서로 다른 프로그램을 선택해주세요.")
    return {"items": [detail(path, program_id, as_of) for program_id in ids], "as_of": as_of.isoformat()}
