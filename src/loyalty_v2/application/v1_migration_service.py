from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import CustomerService, PointsService
from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.migration_models import LegacyCustomerMapping, MigrationRun
from loyalty_v2.db.models import Customer, LedgerEntryType


@dataclass(frozen=True, slots=True)
class LegacyCustomerRow:
    source_customer_id: str
    telegram_id: int
    first_name: str
    phone: str
    birth_date: date
    points_balance: int = 0


@dataclass(frozen=True, slots=True)
class MigrationValidation:
    valid_rows: tuple[LegacyCustomerRow, ...]
    errors: tuple[dict, ...]


class V1MigrationService:
    def __init__(self) -> None:
        self.customers = CustomerService()
        self.points = PointsService()

    async def validate(self, session: AsyncSession, *, organization_id: UUID, rows: list[LegacyCustomerRow]) -> MigrationValidation:
        valid: list[LegacyCustomerRow] = []
        errors: list[dict] = []
        seen_source: set[str] = set()
        seen_phone: set[str] = set()
        seen_telegram: set[int] = set()
        today = date.today()

        for index, row in enumerate(rows):
            row_errors: list[str] = []
            source_id = row.source_customer_id.strip()
            phone = row.phone.strip()
            name = row.first_name.strip()
            if not source_id: row_errors.append("missing source_customer_id")
            if source_id in seen_source: row_errors.append("duplicate source_customer_id in import")
            if not name: row_errors.append("missing first_name")
            if not phone: row_errors.append("missing phone")
            if phone in seen_phone: row_errors.append("duplicate phone in import")
            if row.telegram_id in seen_telegram: row_errors.append("duplicate telegram_id in import")
            if row.birth_date > today: row_errors.append("birth_date is in the future")
            if row.points_balance < 0: row_errors.append("negative points_balance")

            mapped = await session.scalar(select(LegacyCustomerMapping.id).where(
                LegacyCustomerMapping.organization_id == organization_id,
                LegacyCustomerMapping.source == "v1",
                LegacyCustomerMapping.source_customer_id == source_id,
            ))
            if mapped is not None: row_errors.append("source_customer_id already migrated")
            existing_phone = await session.scalar(select(Customer.id).where(Customer.organization_id == organization_id, Customer.phone == phone))
            if existing_phone is not None: row_errors.append("phone already exists in V2")
            existing_identity = await session.scalar(select(CustomerAuthIdentity.id).where(
                CustomerAuthIdentity.organization_id == organization_id,
                CustomerAuthIdentity.provider == "telegram",
                CustomerAuthIdentity.external_subject == str(row.telegram_id),
                CustomerAuthIdentity.is_active.is_(True),
            ))
            if existing_identity is not None: row_errors.append("telegram identity already exists in V2")

            seen_source.add(source_id); seen_phone.add(phone); seen_telegram.add(row.telegram_id)
            if row_errors:
                errors.append({"row": index, "source_customer_id": source_id, "errors": row_errors})
            else:
                valid.append(LegacyCustomerRow(source_id, row.telegram_id, name, phone, row.birth_date, row.points_balance))
        return MigrationValidation(tuple(valid), tuple(errors))

    async def dry_run(self, session: AsyncSession, *, organization_id: UUID, rows: list[LegacyCustomerRow]) -> MigrationRun:
        result = await self.validate(session, organization_id=organization_id, rows=rows)
        run = MigrationRun(
            organization_id=organization_id,
            source="v1",
            mode="dry_run",
            status="completed" if not result.errors else "completed_with_errors",
            stats={"input": len(rows), "valid": len(result.valid_rows), "errors": len(result.errors)},
            errors=list(result.errors),
            finished_at=datetime.now(timezone.utc),
        )
        session.add(run); await session.flush(); return run

    async def apply(self, session: AsyncSession, *, organization_id: UUID, rows: list[LegacyCustomerRow]) -> MigrationRun:
        result = await self.validate(session, organization_id=organization_id, rows=rows)
        run = MigrationRun(
            organization_id=organization_id,
            source="v1",
            mode="apply",
            status="running",
            stats={"input": len(rows), "valid": len(result.valid_rows), "errors": len(result.errors), "imported": 0},
            errors=list(result.errors),
        )
        session.add(run); await session.flush()
        if result.errors:
            run.status = "blocked"
            run.finished_at = datetime.now(timezone.utc)
            return run

        imported = 0
        for row in result.valid_rows:
            registered = await self.customers.register(
                session,
                organization_id=organization_id,
                provider="telegram",
                external_subject=str(row.telegram_id),
                first_name=row.first_name,
                phone=row.phone,
                birth_date=row.birth_date,
            )
            if row.points_balance > 0:
                await self.points.apply(
                    session,
                    organization_id=organization_id,
                    customer_id=registered.customer.id,
                    delta=row.points_balance,
                    entry_type=LedgerEntryType.MIGRATION,
                    reference_type="v1_customer",
                    reason="V1 opening balance",
                    idempotency_key=f"migration:v1:{row.source_customer_id}:opening-balance",
                )
            session.add(LegacyCustomerMapping(
                organization_id=organization_id,
                source="v1",
                source_customer_id=row.source_customer_id,
                customer_id=registered.customer.id,
                opening_balance=row.points_balance,
            ))
            imported += 1

        run.stats = {**run.stats, "imported": imported}
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        await session.flush()
        return run
