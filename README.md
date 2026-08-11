# SecureAlert API

SecureAlert API is a backend service that receives security events from edge devices such as cameras and sensors, stores them in SQLite, and allows a dashboard to retrieve event lists and summary data.

Responsibilities for HTTP request handling, input validation, data persistence, and rate limiting are separated into individual files, while unnecessary abstractions are avoided for this small, single-table service.

## Key Features

- Create security events and persist them in SQLite
- Validate device IDs, event types, severity levels, and ISO 8601 date-time values
- Filter events by device, severity, event type, and time range
- Sort events newest first and paginate results
- Aggregate total events, counts by severity and event type, the most active device, and the high-severity event rate
- Allow up to 100 event creation requests per device within the most recent 60 seconds
- Return HTTP 400 for invalid requests and HTTP 429 when the rate limit is exceeded
- Run integration tests against a temporary SQLite database

## Local Setup

This project was developed and tested with Python 3.11.9.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment using the command for your operating system.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

## Running the Server

From the project root, run:

```bash
python -m uvicorn main:app --reload
```

Once the server is running, the following URLs are available:

- API: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

On the first run, the application automatically creates the `securealert.db` file and the `events` table in the project root.

## Running the Tests

```bash
python -m pytest -v
```

The tests use a temporary database separate from the development `securealert.db`, so they do not affect local application data.

## Project Structure

| Path | Responsibility |
|---|---|
| `main.py` | FastAPI application, database initialization at startup, routes, and HTTP error handling |
| `schemas.py` | Event creation schema and allowed event types and severity levels |
| `database.py` | SQLite connection, table creation, persistence, filtered queries, and summary aggregation |
| `rate_limiter.py` | Thread-safe sliding-window rate limiting per device |
| `tests/test_events.py` | API integration tests using a temporary SQLite database |
| `requirements.txt` | Packages required to run and test the application |

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Check whether the server is running |
| `POST` | `/events` | Validate and store an event |
| `GET` | `/events` | Filter, sort, and paginate events |
| `GET` | `/events/summary` | Retrieve an event summary for a specified time range |

### Health Check

`GET /`

```json
{
  "message": "SecureAlert API is running"
}
```

### Create an Event

`POST /events`

Example request:

```json
{
  "device_id": "cam-south-01",
  "event_type": "motion_detected",
  "severity": "low",
  "timestamp": "2024-11-15T03:22:10Z",
  "metadata": {
    "zone": "entrance",
    "confidence": 0.91
  }
}
```

`metadata` is optional; all other fields are required.

`device_id` must be between 3 and 64 characters. `timestamp` must be a valid ISO 8601 date-time value.

Supported `event_type` values:

- `motion_detected`
- `intrusion_alert`
- `camera_offline`

Supported `severity` values:

- `low`
- `medium`
- `high`

On success, the API returns HTTP 201 with the generated ID and the stored event data.

```json
{
  "id": 1,
  "device_id": "cam-south-01",
  "event_type": "motion_detected",
  "severity": "low",
  "timestamp": "2024-11-15T03:22:10+00:00",
  "metadata": {
    "zone": "entrance",
    "confidence": 0.91
  }
}
```

If 100 requests from the same `device_id` have already been allowed within the most recent 60 seconds, the API returns HTTP 429. Rejected requests are not added to the rate-limit history.

### Retrieve Events

`GET /events`

All query parameters are optional. When multiple filters are provided, only events that satisfy every condition are returned.

| Parameter | Description |
|---|---|
| `device_id` | Return events whose device ID exactly matches the value; must be 3–64 characters when provided |
| `severity` | Return events with the specified severity |
| `event_type` | Return events of the specified type |
| `from` | Return events that occurred at or after this time |
| `to` | Return events that occurred at or before this time |
| `page` | Page number; default `1`, minimum `1` |
| `page_size` | Events per page; default `20`, range `1`–`100` |

Example request:

```text
GET /events?device_id=cam-south-01&severity=high&from=2024-11-15T00:00:00Z&page=1&page_size=20
```

Example response:

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "events": [
    {
      "id": 1,
      "device_id": "cam-south-01",
      "event_type": "intrusion_alert",
      "severity": "high",
      "timestamp": "2024-11-15T03:22:10+00:00",
      "metadata": {
        "zone": "entrance",
        "confidence": 0.91
      }
    }
  ]
}
```

`total` is the total number of events matching the filters before pagination is applied. Events are returned in descending order by `timestamp`.

### Retrieve an Event Summary

`GET /events/summary`

Both `from` and `to` are required, and both boundary times are inclusive.

```text
GET /events/summary?from=2024-11-15T00:00:00Z&to=2024-11-16T00:00:00Z
```

Example response:

```json
{
  "total_events": 4,
  "by_severity": {
    "low": 2,
    "medium": 1,
    "high": 1
  },
  "by_event_type": {
    "motion_detected": 2,
    "intrusion_alert": 1,
    "camera_offline": 1
  },
  "most_active_device": "cam-south-02",
  "high_severity_rate": 0.25
}
```

If `from` is later than `to`, the API returns HTTP 400. If no events exist within the range, counts by event type and severity and `high_severity_rate` are returned as `0`, while `most_active_device` is returned as `null`.

## Technology Choices and Design

### Python and FastAPI

Python was chosen because its concise syntax makes the API behavior and edge cases easy to express clearly. FastAPI and Pydantic provide type-based validation, allowing the following rules to be enforced at the API boundary:

- Distinguishing required and optional fields
- Restricting event types and severity levels with `Literal`
- Restricting device ID and pagination ranges with `Field` and `Query`
- Validating ISO 8601 date-time strings
- Automatically generating OpenAPI documentation

FastAPI returns HTTP 422 for request validation errors by default. To follow the task specification, a `RequestValidationError` handler converts these responses to HTTP 400 and includes structured error details.

### SQLite and `sqlite3`

A relational database was selected because the primary event fields have a consistent structure and the required queries focus on exact-value filters, time-range searches, and grouped aggregations.

SQLite requires no separate database server or credentials and persists data in a single file, making the application easy to run and review locally. It also provides transactions, parameterized queries, filtering, sorting, and aggregation, which are sufficient for the current scope.

Instead of using an ORM, the application writes SQL directly through Python's built-in `sqlite3` module. With one table and a limited number of query paths, this keeps the actual query behavior easy to inspect. The optional `metadata` field, whose structure may vary, is stored as a JSON string and converted back to an object in API responses.

Event timestamps are stored as ISO 8601 strings, while SQLite's `julianday()` function is used for filtering and sorting. This allows date-time values with different representations to be compared chronologically rather than lexicographically.

### In-Memory Sliding-Window Rate Limiting

Rate limiting is implemented with a sliding window that records recent request times in a `deque` for each `device_id`.

Each new request is handled as follows:

1. Read the current elapsed time using `time.monotonic()`.
2. Remove request timestamps older than the 60-second window.
3. Reject the request if 100 timestamps remain.
4. Otherwise, record the current time and allow the request.

Because the limiter checks the 60 seconds immediately preceding each request rather than a fixed one-minute interval, it reduces bursts around minute boundaries. A `deque` allows expired timestamps to be removed efficiently from the front, and `time.monotonic()` prevents system clock changes from affecting elapsed-time calculations. Because FastAPI's synchronous handlers may run across multiple threads, access to the shared state is protected with a `Lock`.

This implementation is designed for a single process. Restarting the server clears the request history, and rate-limit counts are not shared across multiple processes or servers.

## Assumptions and Behavioral Decisions

- The `from` and `to` values in time ranges are both inclusive, following the specification's “on or after” and “on or before” wording.
- Recency is determined by the event's `timestamp`, not by insertion order. The relative order of events with identical timestamps is not guaranteed.
- If multiple devices are tied for the highest event count, the first `device_id` in ascending order is returned to keep the result deterministic.
- `high_severity_rate` is returned as `0.0` when there are no events and rounded to three decimal places when events exist.
- `metadata` accepts a JSON object or `null` without predefined internal fields and is not currently used as a filter.
- Every valid `POST /events` request is treated as a new event. Because no source event ID or idempotency key is provided, retransmitting the same event may create a duplicate record.
- Because the request body must be validated before the `device_id` can be identified, malformed requests return HTTP 400 and do not count toward the per-device rate limit.
- An allowed request is recorded by the rate limiter before the database write. If persistence later fails, the request still counts toward the current 60-second window.
- For event list queries, `from` and `to` are independent optional filters. If both are provided, `from` must be earlier than or equal to `to`; otherwise, the API returns HTTP 400.
- Authentication, authorization, and event update and deletion operations are outside the current scope.

## Error Handling

| Scenario | Status Code |
|---|---:|
| Event created successfully | `201` |
| Events or summary retrieved successfully | `200` |
| Missing required fields or invalid body/query values | `400` |
| `from` is later than `to` in a time-range request | `400` |
| Per-device event creation rate limit exceeded | `429` |
| Unhandled server or database error | `500` |

Input validation errors include FastAPI/Pydantic's structured error details describing the location and cause of each issue.

## Testing Approach

Integration tests cover the full path from API requests to SQLite because the primary risks lie in the interactions among routing, persistence, sorting, pagination, aggregation, and rate limiting.

The event API workflow test stores five events with intentionally unordered timestamps in a temporary database and verifies:

- HTTP 201 responses when events are created
- Storage and restoration of JSON `metadata`
- Newest-first sorting independent of insertion order
- Pagination across multiple pages
- Consistent total counts and no duplicate events across pages
- Summary results for a specified time range
- Counts by severity and event type
- The most active device
- The high-severity event rate

The rate-limit test injects a controllable fake clock so it does not need to wait for 60 real seconds, and verifies:

- The first 100 requests from the same device are allowed
- The 101st request returns HTTP 429
- A separate limit is applied to another device
- Requests are allowed again after 60 seconds

## Future Improvements

1. **Prevent duplicate events**  
   Accept a source event ID or idempotency key to prevent device retransmissions from being stored as duplicate records.

2. **Define a clear time-zone policy**  
   Require timestamps to include time-zone information and normalize all timestamps to UTC before storing them.
