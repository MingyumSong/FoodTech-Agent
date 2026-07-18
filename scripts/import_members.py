"""회원 명단 CLI 임포트 (T-007) — 서비스 로직은 app/services/member_import.py.

로컬 DB:   uv run python scripts/import_members.py 명단.xlsx --program "최고책임자과정" --dry-run
운영 DB:   DATABASE_URL="$SUPABASE_URL" uv run python scripts/import_members.py 명단.xlsx ...
(운영은 배포 API POST /api/members/import + ADMIN_TOKEN 사용도 가능)
"""

import argparse
import json
from pathlib import Path

from sqlmodel import Session

from app.db import engine
from app.services.member_import import import_members


def main() -> None:
    parser = argparse.ArgumentParser(description="회원 명단 CSV/XLSX 업서트")
    parser.add_argument("file", help="구글시트에서 다운로드한 CSV/XLSX 경로")
    parser.add_argument(
        "--program", default=None, help="이 명단의 프로그램명 (member_programs 연결)"
    )
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 리포트만")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"파일 없음: {path}")

    with Session(engine) as session:
        report = import_members(
            session, path.read_bytes(), path.name, program=args.program, dry_run=args.dry_run
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
