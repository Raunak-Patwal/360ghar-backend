# Bug Reporting API — POST Endpoints

This document explains how client applications can submit bug reports to the 360Ghar backend. Use these endpoints when users encounter issues and want to report them from the web, mobile, or agent-facing apps.

## Base URL and Authentication

- **Base path**: `/api/v1`
- **Auth**: Supabase-issued bearer token is required. Every request must include `Authorization: Bearer <access_token>`.
- **Content types**: JSON (`application/json`) or multipart form-data (`multipart/form-data`) depending on the endpoint variant.

If the token is missing, malformed, revoked, or belongs to an inactive account, the API responds with `401 Unauthorized` (or `403` for inactive users).

## Bug Report Resource Schema

All bug report payloads share the same logical fields.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `source` | `string` | Yes | Surface where the issue was reported (e.g. `mobile`, `web`, `agent_portal`). |
| `bug_type` | `enum` | Yes | High-level category. One of `ui_bug`, `functionality_bug`, `performance_issue`, `crash`, `feature_request`, `other`. |
| `severity` | `enum` | Yes | Impact level. One of `low`, `medium`, `high`, `critical`. |
| `title` | `string` | Yes | Short summary (1–200 chars). |
| `description` | `string` | Yes | Detailed explanation of the issue. |
| `steps_to_reproduce` | `string` | No | Ordered steps that consistently reproduce the bug. |
| `expected_behavior` | `string` | No | What the user expected to happen. |
| `actual_behavior` | `string` | No | What actually occurred. |
| `device_info` | `object` | No | Arbitrary JSON describing the device or environment (OS/version/model, network, etc.). |
| `app_version` | `string` | No | App version string where the bug was seen. |
| `media_urls` | `string[]` | No | List of previously hosted media assets related to the bug. Automatically populated when uploading media with the multipart endpoint. |
| `tags` | `string[]` | No | Additional labels to assist filtering/searching. |

Responses also include metadata that the server controls:

- `id`: integer bug identifier
- `user_id`: ID of the reporter (nullable for future unauthenticated submissions)
- `status`: workflow state (`open`, `in_progress`, `resolved`, `closed`); defaults to `open`
- `assigned_to`: ID of the user handling the bug (nullable)
- `resolution`: resolution notes (nullable)
- `resolved_at`: timestamp set when status first transitions to `resolved`
- `created_at`, `updated_at`: audit timestamps

---

## POST `/api/v1/bugs/`

Create a bug report using a JSON payload. Use this variant when no files need to be uploaded (for example, when the client already hosts screenshots and can pass their URLs in `media_urls`).

- **Auth**: required (Bearer)
- **Content-Type**: `application/json`
- **Success status**: `200 OK` (FastAPI default for POST)
- **Response body**: `BugReportResponse` object described above

### Sample Request

```bash
curl -X POST "https://api.360ghar.com/api/v1/bugs/" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
        "source": "mobile",
        "bug_type": "functionality_bug",
        "severity": "high",
        "title": "Cannot save property to favorites",
        "description": "Tap on the heart icon fails silently on listing screens.",
        "steps_to_reproduce": "1. Login\n2. Open any property\n3. Tap the heart",
        "expected_behavior": "Property should be added to favorites and icon should toggle",
        "actual_behavior": "Icon flashes but state does not persist",
        "device_info": {
          "os": "iOS",
          "os_version": "17.5",
          "device_model": "iPhone 13",
          "network": "WiFi"
        },
        "app_version": "2.3.1",
        "media_urls": [
          "https://cdn.example.com/screenshots/bug-1234.png"
        ],
        "tags": ["favorites", "ios"]
      }'
```

### Sample Response

```json
{
  "id": 42,
  "user_id": 17,
  "source": "mobile",
  "bug_type": "functionality_bug",
  "severity": "high",
  "status": "open",
  "title": "Cannot save property to favorites",
  "description": "Tap on the heart icon fails silently on listing screens.",
  "steps_to_reproduce": "1. Login\n2. Open any property\n3. Tap the heart",
  "expected_behavior": "Property should be added to favorites and icon should toggle",
  "actual_behavior": "Icon flashes but state does not persist",
  "device_info": {
    "os": "iOS",
    "os_version": "17.5",
    "device_model": "iPhone 13",
    "network": "WiFi"
  },
  "app_version": "2.3.1",
  "media_urls": [
    "https://cdn.example.com/screenshots/bug-1234.png"
  ],
  "tags": ["favorites", "ios"],
  "assigned_to": null,
  "resolution": null,
  "resolved_at": null,
  "created_at": "2024-04-16T09:25:37.311Z",
  "updated_at": null
}
```

---

## POST `/api/v1/bugs/with-media/`

Create a bug report and upload one or more supporting files in a single request. The backend uploads each file via `storage_service.upload_generic()` and stores the resulting public URLs on the bug report.

- **Auth**: required (Bearer)
- **Content-Type**: `multipart/form-data`
- **Success status**: `200 OK`
- **Response body**: Same `BugReportResponse` schema with the generated `media_urls`

### Multipart Form Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source` | text | Yes | Same as JSON endpoint. |
| `bug_type` | text | Yes | Must match enum values listed earlier. |
| `severity` | text | Yes | Must match enum values listed earlier. |
| `title` | text | Yes | Short summary. |
| `description` | text | Yes | Detailed description. |
| `steps_to_reproduce` | text | No | Optional narrative. |
| `expected_behavior` | text | No | Optional. |
| `actual_behavior` | text | No | Optional. |
| `device_info` | text | No | Provide a JSON-stringified object (e.g. `{"os": "Android", "version": "14"}`). |
| `app_version` | text | No | Optional. |
| `tags` | text | No | JSON-stringified array of strings (e.g. `["android", "payments"]`). |
| `files` | file[] | Yes | One or more files. Each file becomes a stored media URL. |

If an individual upload fails, the service logs the error, skips that file, and continues processing the remaining attachments. The request still succeeds as long as at least one file is accepted (or other payload data is valid). Failed files simply do not appear in `media_urls`.

### Sample `curl`

```bash
curl -X POST "https://api.360ghar.com/api/v1/bugs/with-media/" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "source=android" \
  -F "bug_type=crash" \
  -F "severity=critical" \
  -F "title=App crashes on launch" \
  -F "description=The agent app crashes immediately after splash screen" \
  -F "device_info={\"os\": \"Android\", \"os_version\": \"14\", \"device_model\": \"Pixel 7\"}" \
  -F "app_version=2.3.1" \
  -F "tags=[\"agent-app\", \"release-2.3\"]" \
  -F "files=@/path/to/logcat.txt" \
  -F "files=@/path/to/screenrecord.mp4"
```

### Sample Response (abbreviated)

```json
{
  "id": 87,
  "user_id": 17,
  "source": "android",
  "bug_type": "crash",
  "severity": "critical",
  "status": "open",
  "title": "App crashes on launch",
  "description": "The agent app crashes immediately after splash screen",
  "media_urls": [
    "https://cdn.360ghar.com/uploads/bugs/87/logcat.txt",
    "https://cdn.360ghar.com/uploads/bugs/87/screenrecord.mp4"
  ],
  "created_at": "2024-04-16T11:04:55.912Z",
  "updated_at": null,
  "...": "other fields omitted for brevity"
}
```

---

## Error Handling

| Status | When it occurs | Sample body |
| --- | --- | --- |
| `401 Unauthorized` | Missing/invalid bearer token. | `{ "detail": { "code": "AUTH_HEADER_MISSING", "message": "Authorization header missing" } }` |
| `403 Forbidden` | Authenticated but inactive user. | `{ "detail": { "code": "USER_INACTIVE", "message": "Inactive user" } }` |
| `422 Unprocessable Entity` | Validation error (e.g., missing required field, invalid enum, malformed JSON in `device_info`/`tags`). | Standard FastAPI validation response detailing the offending fields. |

All other failures result in structured FastAPI errors with a `detail` message. Retries are safe for idempotent submission attempts (the API does not currently deduplicate duplicate bug reports).

## Post-Submission Behavior

- New bug reports always start with `status: open`.
- `created_at` is set when the record is stored; `updated_at` remains `null` until the report is modified.
- `resolved_at` is automatically set when admins later update the report to `status = resolved`.
- Admin tooling can assign bugs to specific team members using separate update endpoints.

## Testing Tips

- For local development use `http://localhost:8000/api/v1/...` as the base URL.
- Ensure the Supabase session token used in Authorization headers is still valid.
- Verify that JSON strings included inside multipart forms are valid JSON (double-quote keys/values, escape characters as needed).
