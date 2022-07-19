import config
import logging

from flask_login import UserMixin
from sqlalchemy import create_engine, update
from sqlalchemy import Boolean, Column, Integer, JSON, String, VARCHAR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import scoped_session, sessionmaker
from typing import List

logger = logging.getLogger(__name__)

"""
Database Setup
"""

db = create_engine(
    config.database_url,
    isolation_level="REPEATABLE READ",
    echo_pool=True,
    pool_pre_ping=True,
)
base = declarative_base()
session_factory = sessionmaker(db, autocommit=False, autoflush=False)
Session = scoped_session(session_factory)

"""
Database Clases
"""


class Serializer(object):
    def serialize(self):
        return {c: getattr(self, c) for c in inspect(self).attrs.keys()}

    @staticmethod
    def serialize_list(l):
        return [m.serialize() for m in l]


class Incident(base, Serializer):
    __tablename__ = "incidents"

    incident_id = Column(VARCHAR(50), primary_key=True, nullable=False)
    channel_id = Column(VARCHAR(50), nullable=False)
    channel_name = Column(VARCHAR(50), nullable=False)
    status = Column(VARCHAR(50), nullable=False)
    severity = Column(VARCHAR(50), nullable=False)
    bp_message_ts = Column(VARCHAR(50), nullable=False)
    dig_message_ts = Column(VARCHAR(50), nullable=False)
    sp_message_ts = Column(VARCHAR(50))
    sp_incident_id = Column(VARCHAR(50))
    created_at = Column(VARCHAR(50))
    updated_at = Column(VARCHAR(50))
    last_update_sent = Column(VARCHAR(50))
    tags = Column(VARCHAR(500))
    commander = Column(VARCHAR(50))
    technical_lead = Column(VARCHAR(50))
    communications_liaison = Column(VARCHAR(50))

    def serialize(self):
        d = Serializer.serialize(self)
        return d


class OperationalData(base, Serializer):
    __tablename__ = "opdata"

    id = Column((String(30)), primary_key=True, nullable=False)
    data = Column(VARCHAR(250))
    json_data = Column(JSON)
    updated_at = Column(VARCHAR(50))

    def serialize(self):
        d = Serializer.serialize(self)
        return d


class AuditLog(base, Serializer):
    __tablename__ = "auditlog"

    incident_id = Column(String(30), primary_key=True, nullable=False)
    data = Column(JSON)

    def serialize(self):
        d = Serializer.serialize(self)
        return d


class User(UserMixin, base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True)
    password = Column(String(100))
    name = Column(String(100))
    role = Column(String(20))
    is_admin = Column(Boolean, default=False)
    is_disabled = Column(Boolean, default=False)


base.metadata.create_all(db)

"""
Helper Methods
"""


def db_verify():
    """
    Verify database is reachable
    """
    try:
        conn = db.connect()
        conn.close()
        return True
    except:
        return False


"""
Incident Management
"""


def db_read_all_incidents(return_json: bool = False) -> List:
    """
    Return all rows from incidents table
    """
    try:
        all_incidents = Session.query(Incident)
        all_incidents_list = []
        for inc in all_incidents:
            if return_json:
                all_incidents_list.append(inc.serialize())
            else:
                all_incidents_list.append(inc)
        return all_incidents_list
    except Exception as error:
        logger.error(
            f"Incident lookup query failed when returning all incidents: {error}"
        )
    finally:
        Session.close()


def db_read_open_incidents() -> List:
    """
    Return all rows from incidents table for open (non-resolved) incidents
    """
    try:
        open_incidents = Session.query(Incident).filter(Incident.status != "resolved")
        open_incidents_list = []
        for inc in open_incidents:
            open_incidents_list.append(inc)
        return open_incidents_list
    except Exception as error:
        logger.error(
            f"Incident lookup query failed when returning open incidents: {error}"
        )
    finally:
        Session.close()


def db_read_incident(incident_id: str, return_json: bool = False) -> Incident:
    """
    Read from database
    """
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        if return_json:
            return incident.serialize()
        else:
            return incident
    except Exception as error:
        logger.error(f"Incident lookup query failed for {incident_id}: {error}")
        raise error
    finally:
        Session.close()


def db_update_incident_created_at_col(incident_id: str, created_at: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.created_at = created_at
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_last_update_sent_col(channel_id: str, last_update_sent: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.channel_id == channel_id).one()
        )
        incident.last_update_sent = last_update_sent
        Session.commit()
    except Exception as error:
        incident = (
            Session.query(Incident).filter(Incident.channel_id == channel_id).one()
        )
        logger.error(f"Incident update failed for {incident.incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_role(incident_id: str, role: str, user: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        if "incident_commander" in role:
            incident.commander = user
        elif "technical_lead" in role:
            incident.technical_lead = user
        elif "communications_liaison" in role:
            incident.communications_liaison = user
        else:
            logger.error(f"{role} is not a valid choice.")
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_updated_at_col(incident_id: str, updated_at: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.updated_at = updated_at
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_severity_col(incident_id: str, severity: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.severity = severity
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_sp_id_col(incident_id: str, sp_incident_id: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.sp_incident_id = sp_incident_id
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_sp_ts_col(incident_id: str, ts: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.sp_message_ts = ts
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_update_incident_status_col(incident_id: str, status: str):
    try:
        incident = (
            Session.query(Incident).filter(Incident.incident_id == incident_id).one()
        )
        incident.status = status
        Session.commit()
    except Exception as error:
        logger.error(f"Incident update failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_write_incident(
    incident_id,
    channel_id,
    channel_name,
    status,
    severity,
    bp_message_ts,
    dig_message_ts,
):
    """
    Write incident entry to database

    Args:
        incident_id - The formatted channel name (title) for the incident (primary key)
        channel_id - ID of the incident channel
        channel_name - Slack channel name
        status - Status of the incident
        severity - Severity of the incident
        bp_message_ts - Boilerplate message creation timestamp
        dig_message_ts - Digest channel message creation timestamp
    """
    try:
        incident = Incident(
            incident_id=incident_id,
            channel_id=channel_id,
            channel_name=channel_name,
            status=status,
            severity=severity,
            bp_message_ts=bp_message_ts,
            dig_message_ts=dig_message_ts,
        )
        Session.add(incident)
        Session.commit()
    except Exception as error:
        logger.error(f"Incident row create failed for {incident_id}: {error}")
        Session.rollback()
    finally:
        Session.close()


"""
User Management
"""


def db_user_lookup(email: str = None, id: int = None, all: bool = False):
    if all:
        try:
            logger.debug(f"Attempting to return all users...")
            user = Session.query(User)
            return user
        except Exception as error:
            logger.error(f"User lookup failed: {error}")
        finally:
            Session.close()
    elif not all and email != None:
        try:
            logger.debug(f"Attempting to lookup user {email}...")
            user = Session.query(User).filter(User.email == email).first()
            return user
        except Exception as error:
            logger.error(f"User lookup failed for {email}: {error}")
        finally:
            Session.close()
    elif not all and id != None:
        try:
            logger.debug(f"Attempting to lookup user id {id}...")
            user = Session.query(User).filter(User.id == id).first()
            return user
        except Exception as error:
            logger.error(f"User lookup failed for {email}: {error}")
        finally:
            Session.close()


def db_user_create(
    email: str,
    name: str,
    password: str,
    role: str,
    is_admin: bool = False,
):
    try:
        new_user = User(
            email=email,
            name=name,
            password=password,
            role=role,
            is_admin=is_admin,
        )
        Session.add(new_user)
        Session.commit()
    except Exception as error:
        logger.error(f"User creation failed for {email}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_user_delete(email: str):
    try:
        Session.query(User).filter(User.email == email).delete()
        Session.commit()
    except Exception as error:
        logger.error(f"User deletion failed for {email}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_user_disable(email: str):
    try:
        user = Session.query(User).filter(User.email == email).one()
        user.is_disabled = True
        Session.commit()
    except Exception as error:
        logger.error(f"User disable failed for {email}: {error}")
        Session.rollback()
    finally:
        Session.close()


def db_user_enable(email: str):
    try:
        user = Session.query(User).filter(User.email == email).one()
        user.is_disabled = False
        Session.commit()
    except Exception as error:
        logger.error(f"User enable failed for {email}: {error}")
        Session.rollback()
    finally:
        Session.close()
