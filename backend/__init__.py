"""웹 화면과 JSON API를 연결한다."""

from collections import Counter, deque
from datetime import date
import sqlite3
from threading import Lock
import time
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .ai import interpret_query
from .config import ROOT, CATEGORIES, settings, today
from .database import init_database, list_programs, latest_sync
from .errors import ServiceError
from .programs import validate_criteria, search, detail, compare, recruitment


def create_app(overrides=None):
    app = Flask(__name__, template_folder=str(ROOT / "frontend"), static_folder=str(ROOT / "frontend/static"))
    app.config.update(settings())
    app.config.update(MAX_CONTENT_LENGTH=16 * 1024, JSON_SORT_KEYS=False)
    app.config.update(overrides or {})
    app.json.ensure_ascii = False
    init_database(app.config["DATABASE"])
    ai_requests = deque()
    rate_lock = Lock()

    def current_date():
        return date.fromisoformat(app.config["TODAY"]) if app.config["TODAY"] else today()

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ServiceError("JSON 객체 형식으로 요청해주세요.")
        return value

    @app.before_request
    def check_origin():
        origin = request.headers.get("Origin")
        if request.method == "POST" and origin and urlsplit(origin).netloc != request.host:
            raise ServiceError("같은 서비스 화면에서 요청해주세요.", 403, "origin_denied")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ServiceError)
    def service_error(error):
        return jsonify(error={"code": error.code, "message": error.message}), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error={"code": "http_error", "message": "요청 주소, 형식 또는 크기를 확인해주세요."}), error.code

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        return jsonify(error={"code": "database_error", "message": "저장된 데이터를 읽지 못했습니다. 잠시 후 다시 시도해주세요."}), 503

    @app.get("/")
    def index():
        if not (ROOT / "frontend/index.html").exists():
            return "화면 파일이 아직 없습니다. 전달받은 frontend 폴더를 추가해주세요.", 503
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        programs = list_programs(app.config["DATABASE"])
        statuses = Counter(recruitment(program, current_date())[0] for program in programs)
        sync = latest_sync(app.config["DATABASE"])
        return jsonify(
            total=len(programs), open_count=statuses["open"],
            categories=list(CATEGORIES), as_of=current_date().isoformat(),
            fetched_at=max((program["fetched_at"] for program in programs), default=None),
            last_sync_status=sync["status"] if sync else None,
            ai_configured=bool(app.config["OPENAI_API_KEY"]),
        )

    @app.post("/api/interpret")
    def interpret():
        value = body()
        if set(value) != {"query"}:
            raise ServiceError("query 필드에 질문을 입력해주세요.")
        with rate_lock:
            current = time.monotonic()
            while ai_requests and current - ai_requests[0] >= 60:
                ai_requests.popleft()
            limit = app.config["AI_RATE_LIMIT"]
            if limit and len(ai_requests) >= limit:
                raise ServiceError("AI 요청이 많습니다. 잠시 후 다시 시도해주세요.", 429, "rate_limited")
            ai_requests.append(current)
        result = interpret_query(value["query"], app.config["OPENAI_API_KEY"], app.config["OPENAI_MODEL"], current_date())
        return jsonify(result)

    @app.post("/api/search")
    def program_search():
        value = body()
        if set(value) - {"criteria", "mode", "page"}:
            raise ServiceError("지원하지 않는 요청 항목이 있습니다.")
        criteria = validate_criteria(value.get("criteria", {}))
        mode, page = value.get("mode", "search"), value.get("page", 1)
        if mode not in ("search", "recommend") or type(page) is not int or not 1 <= page <= 1000:
            raise ServiceError("검색 방식과 페이지 번호를 확인해주세요.")
        if not list_programs(app.config["DATABASE"]):
            raise ServiceError("아직 수집된 데이터가 없습니다. 먼저 데이터 수집을 실행해주세요.", 503, "data_empty")
        return jsonify(search(app.config["DATABASE"], criteria, current_date(), mode, page))

    @app.get("/api/programs/<int:program_id>")
    def program_detail(program_id):
        return jsonify(detail(app.config["DATABASE"], program_id, current_date()))

    @app.post("/api/compare")
    def program_compare():
        value = body()
        if set(value) != {"ids"}:
            raise ServiceError("비교할 프로그램 ID를 입력해주세요.")
        return jsonify(compare(app.config["DATABASE"], value["ids"], current_date()))

    return app
