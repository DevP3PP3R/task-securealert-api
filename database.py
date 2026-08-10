import json
import sqlite3
from datetime import datetime


DATABASE_NAME = "securealert.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL
                CHECK (severity IN ('low', 'medium', 'high')),
            timestamp TEXT NOT NULL,
            metadata TEXT
        )
        """
    )

    connection.commit()
    connection.close()


def insert_event(event):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO events (
            device_id,
            event_type,
            severity,
            timestamp,
            metadata
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event.device_id,
            event.event_type,
            event.severity,
            event.timestamp.isoformat(),
            json.dumps(event.metadata) if event.metadata is not None else None,
        ),
    )

    connection.commit()
    event_id = cursor.lastrowid
    connection.close()

    return event_id


def get_events(
    device_id: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
):
    connection = get_connection()

    query = """
        SELECT id, device_id, event_type, severity, timestamp, metadata
        FROM events
        WHERE TRUE
    """
    parameters = []

    if device_id is not None:
        query += " AND device_id = ?"
        parameters.append(device_id)

    if severity is not None:
        query += " AND severity = ?"
        parameters.append(severity)

    if event_type is not None:
        query += " AND event_type = ?"
        parameters.append(event_type)

    if from_ is not None:
        query += " AND julianday(timestamp) >= julianday(?)"
        parameters.append(from_.isoformat())

    if to is not None:
        query += " AND julianday(timestamp) <= julianday(?)"
        parameters.append(to.isoformat())

    count_query = f"SELECT COUNT(*) FROM ({query}) AS filtered_events"
    total = connection.execute(count_query, parameters).fetchone()[0]

    offset = (page - 1) * page_size

    query += """
        ORDER BY julianday(timestamp) DESC
        LIMIT ? OFFSET ?
    """  # Rule: order by timestamp in descending order

    rows = connection.execute(
        query,
        [*parameters, page_size, offset],
    ).fetchall()

    connection.close()

    events = [
        {
            **dict(row),
            "metadata": (
                json.loads(row["metadata"])
                if row["metadata"] is not None
                else None
            ),
        }
        for row in rows
    ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "events": events,
    }


def get_event_summary(from_: datetime, to: datetime):
    connection = get_connection()

    date_condition = """
        WHERE julianday(timestamp) >= julianday(?)
        AND julianday(timestamp) <= julianday(?)
    """
    parameters = [from_.isoformat(), to.isoformat()]

    total_events = connection.execute(
        f"SELECT COUNT(*) FROM events {date_condition}",
        parameters,
    ).fetchone()[0]

    severity_rows = connection.execute(
        f"""
        SELECT severity, COUNT(*) AS event_count
        FROM events
        {date_condition}
        GROUP BY severity
        """,
        parameters,
    ).fetchall()

    event_type_rows = connection.execute(
        f"""
        SELECT event_type, COUNT(*) AS event_count
        FROM events
        {date_condition}
        GROUP BY event_type
        """,
        parameters,
    ).fetchall()

    most_active_row = connection.execute(
        f"""
        SELECT device_id, COUNT(*) AS event_count
        FROM events
        {date_condition}
        GROUP BY device_id
        ORDER BY event_count DESC, device_id ASC
        LIMIT 1
        """,
        parameters,
    ).fetchone()

    connection.close()

    by_severity = {
        "low": 0,
        "medium": 0,
        "high": 0,
    }
    by_severity.update(
        {row["severity"]: row["event_count"] for row in severity_rows}
    )

    by_event_type = {
        "motion_detected": 0,
        "intrusion_alert": 0,
        "camera_offline": 0,
    }
    by_event_type.update(
        {row["event_type"]: row["event_count"] for row in event_type_rows}
    )

    return {
        "total_events": total_events,
        "by_severity": by_severity,
        "by_event_type": by_event_type,
        "most_active_device": (
            most_active_row["device_id"]
            if most_active_row is not None
            else None
        ),
        "high_severity_rate": (
            round(by_severity["high"] / total_events, 3)
            if total_events > 0
            else 0.0
        ),
    }