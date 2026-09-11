from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from loyalty_v2.application.v1_migration_service import LegacyCustomerRow, V1MigrationService
from loyalty_v2.db.session import SessionFactory


def load_rows(path: Path) -> list[LegacyCustomerRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input JSON must contain a list of customers")
    rows: list[LegacyCustomerRow] = []
    for item in payload:
        rows.append(LegacyCustomerRow(
            source_customer_id=str(item["source_customer_id"]),
            telegram_id=int(item["telegram_id"]),
            first_name=str(item["first_name"]),
            phone=str(item["phone"]),
            birth_date=date.fromisoformat(str(item["birth_date"])),
            points_balance=int(item.get("points_balance", 0)),
        ))
    return rows


async def run(args) -> int:
    rows = load_rows(Path(args.input))
    service = V1MigrationService()
    async with SessionFactory() as session:
        async with session.begin():
            if args.apply:
                result = await service.apply(session, organization_id=UUID(args.organization_id), rows=rows)
            else:
                result = await service.dry_run(session, organization_id=UUID(args.organization_id), rows=rows)
        print(json.dumps({"run_id": str(result.id), "mode": result.mode, "status": result.status, "stats": result.stats, "errors": result.errors}, ensure_ascii=False, default=str, indent=2))
        return 0 if result.status == "completed" else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="V1 -> V2 customer migration. Dry-run is the default.")
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--input", required=True, help="JSON export with normalized V1 customer rows")
    parser.add_argument("--apply", action="store_true", help="Perform the import. Without this flag only validation/dry-run is executed.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
