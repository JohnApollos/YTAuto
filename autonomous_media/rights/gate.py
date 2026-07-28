from autonomous_media.db.models import RightsRecord
from sqlalchemy.orm import Session

class RightsGate:
    def __init__(self, session_maker):
        self.session_maker = session_maker

    def is_cleared(self, source_video_id: str) -> bool:
        with self.session_maker() as session:
            record = session.query(RightsRecord).filter_by(source_video_id=source_video_id).first()
            return record is not None and record.status == "cleared"

    def flag(self, source_video_id: str, reason: str):
        with self.session_maker() as session:
            record = session.query(RightsRecord).filter_by(source_video_id=source_video_id).first()
            if not record:
                record = RightsRecord(source_video_id=source_video_id, status="flagged", flag_reason=reason)
                session.add(record)
            else:
                record.status = "flagged"
                record.flag_reason = reason
            session.commit()
