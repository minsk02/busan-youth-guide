"""키·DB 없이 전달할 소스 묶음을 만든다."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "handoff"
FRIEND_FILES = (
    "frontend/index.html", "frontend/static/style.css",
    "frontend/static/app.js",
)


def write_zip(path, files):
    with ZipFile(path, "w", ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            bundle.write(ROOT / name, name)


def main():
    TARGET.mkdir(exist_ok=True)
    for name in FRIEND_FILES:
        if not (ROOT / name).is_file():
            raise SystemExit("화면 파일이 없어 묶음을 만들지 않았습니다.")
    write_zip(TARGET / "frontend-files.zip", FRIEND_FILES)
    files = {"app.py", "manage.py", "requirements.txt", ".env.example", ".gitignore", "README.md"}
    for folder in ("backend", "frontend", "scripts", "tests", "data/reports"):
        files.update(str(path.relative_to(ROOT)).replace("\\", "/") for path in (ROOT / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    write_zip(TARGET / "busan-youth-guide-source.zip", files)
    print("Created handoff/frontend-files.zip and handoff/busan-youth-guide-source.zip")


if __name__ == "__main__":
    main()
