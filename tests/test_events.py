import database
import main
from fastapi.testclient import TestClient

from main import app

from rate_limiter import DeviceRateLimiter

def test_event_api_workflow_with_isolated_database(tmp_path, monkeypatch):
    test_database = tmp_path / "test_securealert.db"

    monkeypatch.setattr(
        database,
        "DATABASE_NAME",
        str(test_database),
    )
    database.create_table()

    # Timestamps are intentionally out of order.
    test_events = [
        {
            "device_id": "cam-south-01",
            "event_type": "motion_detected",
            "severity": "low",
            "timestamp": "2024-11-14T03:22:10Z",
            "metadata": {
                "zone": "storage",
                "confidence": 0.72,
            },
        },
        {
            "device_id": "cam-south-02",
            "event_type": "intrusion_alert",
            "severity": "high",
            "timestamp": "2024-11-15T04:22:10Z",
            "metadata": {
                "zone": "entrance",
                "confidence": 0.98,
            },
        },
        {
            "device_id": "cam-east-01",
            "event_type": "motion_detected",
            "severity": "low",
            "timestamp": "2024-11-15T06:22:10Z",
            "metadata": {
                "zone": "lobby",
                "confidence": 0.88,
            },
        },
        {
            "device_id": "cam-south-02",
            "event_type": "motion_detected",
            "severity": "low",
            "timestamp": "2024-11-15T03:22:10Z",
            "metadata": {
                "zone": "entrance",
                "confidence": 0.91,
            },
        },
        {
            "device_id": "cam-north-01",
            "event_type": "camera_offline",
            "severity": "medium",
            "timestamp": "2024-11-15T05:22:10Z",
            "metadata": {
                "zone": "parking",
                "confidence": 0.84,
            },
        },
    ]

    with TestClient(app) as client:
        for event in test_events:
            response = client.post("/events", json=event)
            assert response.status_code == 201, response.text

        page_responses = [
            client.get(
                "/events",
                params={
                    "page": page,
                    "page_size": 2,
                },
            )
            for page in (1, 2, 3)
        ]

        for response in page_responses:
            assert response.status_code == 200, response.text

        pages = [response.json() for response in page_responses]

        assert [page["total"] for page in pages] == [5, 5, 5]
        assert [page["page"] for page in pages] == [1, 2, 3]
        assert [page["page_size"] for page in pages] == [2, 2, 2]
        assert [len(page["events"]) for page in pages] == [2, 2, 1]

        paginated_events = [
            event
            for page in pages
            for event in page["events"]
        ]

        # timestamps should be in descending order and there should be no duplicates between pages.
        assert [event["id"] for event in paginated_events] == [
            3,
            5,
            2,
            4,
            1,
        ]
        assert len({
            event["id"]
            for event in paginated_events
        }) == 5

        assert paginated_events[0]["metadata"] == {
            "zone": "lobby",
            "confidence": 0.88,
        }

        summary_response = client.get(
            "/events/summary",
            params={
                "from": "2024-11-15T00:00:00Z",
                "to": "2024-11-16T00:00:00Z",
            },
        )

        assert summary_response.status_code == 200, summary_response.text

        assert summary_response.json() == {
            "total_events": 4,
            "by_severity": {
                "low": 2,
                "medium": 1,
                "high": 1,
            },
            "by_event_type": {
                "motion_detected": 2,
                "intrusion_alert": 1,
                "camera_offline": 1,
            },
            "most_active_device": "cam-south-02",
            "high_severity_rate": 0.25,
        }

def test_post_events_rate_limit_by_device(tmp_path, monkeypatch):
    test_database = tmp_path / "test_rate_limit.db"
    current_time = [0.0]

    monkeypatch.setattr(
        database,
        "DATABASE_NAME",
        str(test_database),
    )
    monkeypatch.setattr(
        main,
        "event_rate_limiter",
        DeviceRateLimiter(
            limit=100,
            window_seconds=60,
            clock=lambda: current_time[0],
        ),
    )

    event = {
        "device_id": "cam-rate-limit-01",
        "event_type": "motion_detected",
        "severity": "low",
        "timestamp": "2024-11-15T03:22:10Z",
        "metadata": None,
    }

    with TestClient(app) as client:
        for _ in range(100):
            response = client.post("/events", json=event)
            assert response.status_code == 201, response.text

        rate_limited_response = client.post("/events", json=event)

        assert rate_limited_response.status_code == 429
        assert rate_limited_response.json() == {
            "detail": (
                "Rate limit exceeded for device 'cam-rate-limit-01'. "
                "Maximum is 100 requests per minute."
            ),
        }

        # A different device has its own rate limit.
        other_device_response = client.post(
            "/events",
            json={
                **event,
                "device_id": "cam-rate-limit-02",
            },
        )
        assert other_device_response.status_code == 201

        # Requests are allowed again after the 60-second window expires.
        current_time[0] = 60.0
        expired_window_response = client.post("/events", json=event)
        assert expired_window_response.status_code == 201