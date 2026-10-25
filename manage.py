"""사용법: python manage.py sync 또는 python manage.py status"""

import argparse
import json
import sys

from backend.config import settings
from backend.database import init_database, latest_sync, list_programs
from backend.data_source import sync_programs
from backend.errors import ServiceError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "status"))
    args = parser.parse_args()
    config = settings()
    init_database(config["DATABASE"])
    try:
        if args.command == "sync":
            result = sync_programs(config["DATABASE"], config["DATA_GO_KR_SERVICE_KEY"])
        else:
            result = {"stored_count": len(list_programs(config["DATABASE"])), "latest_sync": latest_sync(config["DATABASE"])}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except ServiceError as error:
        print(error.message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
