import logging

from bot.db import db
from bot.shared import tools
from typing import Dict, List

logger = logging.getLogger(__name__)


def read(incident_id: str) -> List[Dict]:
    """
    Read audit log
    """
    try:
        if db.Session.query(db.AuditLog).filter_by(incident_id=incident_id).all():
            try:
                existing_row = (
                    db.Session.query(db.AuditLog)
                    .filter_by(incident_id=incident_id)
                    .one()
                )
                return existing_row.data
            except Exception as error:
                logger.error(
                    f"Audit log row lookup failed for incident {incident_id}: {error}"
                )
        else:
            logger.warning(f"No audit log record for {incident_id}")
    except Exception as error:
        logger.error(f"Audit log row lookup failed for incident {incident_id}: {error}")
    finally:
        db.Session.close()


def write(incident_id: str, event: str, content: str = "", user: str = ""):
    """
    Write an audit log for an incident

    Logs are appended to a JSON list
    """
    try:
        # Create the row if it doesn't exist
        if not db.Session.query(db.AuditLog).filter_by(incident_id=incident_id).all():
            try:
                row = db.AuditLog(incident_id=incident_id, data=[])
                db.Session.add(row)
                db.Session.commit()
            except Exception as error:
                logger.error(
                    f"Audit log row create failed for incident {incident_id}: {error}"
                )
        existing_row = (
            db.Session.query(db.AuditLog).filter_by(incident_id=incident_id).one()
        )
        data = existing_row.data
        print()
        data.append(
            {
                "log": event,
                "user": user,
                "content": content,
                "ts": tools.fetch_timestamp(),
            }
        )
        db.Session.execute(
            db.update(db.AuditLog)
            .where(db.AuditLog.incident_id == incident_id)
            .values(data=data)
        )
        db.Session.commit()
    except Exception as error:
        logger.error(f"Audit log row create failed for incident {incident_id}: {error}")
        db.Session.rollback()
    finally:
        db.Session.close()
