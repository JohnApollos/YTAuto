from datetime import datetime, timezone
from autonomous_media.db.models import RightsRecord, SystemEvent
from sqlalchemy.orm import Session
from autonomous_media.logging import get_logger

logger = get_logger("rights.gate")

# Spec §11.4: statuses that allow publishing without a manual override
CLEARED_STATUSES = {"owned", "licensed", "permission_granted"}


class RightsGate:
    """
    Spec §11.4: every content_source carries a rights_records status.
    A clip inherits its source's status. Publishing is blocked unless the status
    is in CLEARED_STATUSES, or a manual, audit-logged override is recorded.

    Deliberately does NOT support 'fair_use_asserted' as an auto-clearable status
    (spec §8.3, §11.4) — fair use is a legal judgment, not a software checkbox.
    """

    def __init__(self, session_maker):
        self.session_maker = session_maker

    def is_cleared(self, content_source_id: str) -> bool:
        """Return True only if this source's rights status is in the cleared set."""
        with self.session_maker() as session:
            record = (
                session.query(RightsRecord)
                .filter_by(content_source_id=content_source_id)
                .first()
            )
            if record is None:
                return False
            return record.status in CLEARED_STATUSES

    def get_status(self, content_source_id: str) -> str:
        """Return the current rights status string, or 'unknown' if no record exists."""
        with self.session_maker() as session:
            record = (
                session.query(RightsRecord)
                .filter_by(content_source_id=content_source_id)
                .first()
            )
            return record.status if record else "unknown"

    def set_status(
        self,
        content_source_id: str,
        new_status: str,
        reviewed_by: str,
        evidence_ref: str | None = None,
    ):
        """
        Update a rights record status. Every call is audit-logged (spec §14.6).
        Valid statuses: owned | licensed | permission_granted | unknown | denied.
        'fair_use_asserted' is intentionally excluded from this list.
        """
        valid = {"owned", "licensed", "permission_granted", "unknown", "denied"}
        if new_status not in valid:
            raise ValueError(f"Invalid rights status '{new_status}'. Must be one of: {valid}")

        with self.session_maker() as session:
            record = (
                session.query(RightsRecord)
                .filter_by(content_source_id=content_source_id)
                .first()
            )
            now = datetime.now(timezone.utc)
            if not record:
                record = RightsRecord(
                    content_source_id=content_source_id,
                    status=new_status,
                    evidence_ref=evidence_ref,
                    reviewed_by=reviewed_by,
                    reviewed_at=now,
                )
                session.add(record)
            else:
                old_status = record.status
                record.status = new_status
                record.evidence_ref = evidence_ref
                record.reviewed_by = reviewed_by
                record.reviewed_at = now

            # Audit log — spec §14.6
            event = SystemEvent(
                event_type="rights.status.updated",
                payload={
                    "content_source_id": str(content_source_id),
                    "new_status": new_status,
                    "reviewed_by": reviewed_by,
                    "evidence_ref": evidence_ref,
                },
                trace_id=f"rights-{content_source_id}",
            )
            session.add(event)
            session.commit()

        logger.info(
            "rights.status.updated",
            extra={"content_source_id": content_source_id, "new_status": new_status, "reviewed_by": reviewed_by},
        )
