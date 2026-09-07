# ChatGPT Plugin + quota backend contract

**Policy version:** v3.0  
**Status:** normative development contract

This reference defines the production boundary between the ChatGPT Web skill and the read-only quota backend.

## 1. Roles

```text
CHATGPT_CONTROL_PLANE=YES
SKILL_RUNTIME=CHATGPT_WEB_ONLY
QUOTA_PLUGIN=READ_ONLY
PLUGIN_DECISION_AUTHORITY=NONE
WORK_CODEX_ROLE=EXECUTION_PLANE
```

ChatGPT owns routing, model/effort selection, quota/pace admission and project runway. The Plugin returns authenticated quota facts only.

## 2. Production path

```text
ChatGPT Web
   ↓ get_quota_snapshot()
Regulator Quota Plugin/App
   ↓ authenticated subject
server-side quota backend
   ↓ managed ChatGPT auth
official codex app-server
   ↓ account/rateLimits/read
normalized quota facts
   ↓
ChatGPT regulator
```

The path has no local user-side component.

```text
LOCAL_COMPANION_REQUIRED=NO
CODEXBAR_USER_PREREQUISITE=NO
LOCALHOST_REQUIRED=NO
OS_DEPENDENCY=NO
```

## 3. Tool surface

Canonical tool:

```text
get_quota_snapshot()
```

Input schema is an empty object. The model must never supply:

```text
email
account id
workspace id
installation id
OAuth/access/refresh token
cookie
reader token
provider credential
```

Authenticated Plugin context resolves the subject outside model arguments.

Reference schema: `plugin/get_quota_snapshot.tool.json`.

## 4. Output boundary

A successful normalized result may contain:

```text
schema_version
allowance_domain
source
snapshot_at
freshness
weekly_meter_semantics
weekly_used
weekly_reset
five_hour_used
five_hour_reset
other_windows
plan_type
ordinary_usage_allowed
credits
```

No raw provider response is returned to the model unless it has been explicitly normalized and allow-listed.

Forbidden model-visible classes:

```text
OAuth/access/refresh tokens
cookies/session material
Authorization headers
raw auth files
passwords
private prompts/chat history
unneeded PII
internal credential-store identifiers
```

## 5. Official Codex backend

The current proven backend uses official `codex app-server`.

Relevant managed-auth sequence:

```text
initialize
initialized
account/login/start
account/login/completed
account/updated
account/rateLimits/read
```

For development/P0, `chatgptDeviceCode` can establish managed ChatGPT auth. The production ChatGPT Plugin may use a different user-facing authorization UX, but the backend must preserve the same authenticated account semantics.

The backend waits for authenticated `account/updated` before reading rate limits. This is a protocol readiness rule, not a timing heuristic.

## 6. Subject-to-account binding

The Plugin subject and the OpenAI/Codex account used for quota reads must be bound explicitly and fail closed.

Required properties:

- one authenticated ChatGPT Plugin subject cannot read another subject's quota;
- account/workspace switching cannot happen silently;
- binding changes require a new explicit authorization path;
- logout/revoke invalidates the corresponding backend session;
- the model cannot choose the subject/account by passing an id to the tool.

```text
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CROSS_SUBJECT_READ=FORBIDDEN
SILENT_ACCOUNT_SWITCH=FORBIDDEN
```

## 7. Credential lifecycle

Production credential persistence is not inherited from the P0 runner.

A release-ready backend needs:

```text
CREDENTIAL_ISOLATION_AUDITED=YES
ENCRYPTION_AT_REST_REQUIRED=YES
TOKEN_REFRESH_TESTED=YES
TOKEN_REVOCATION_TESTED=YES
LOGOUT_PATH_TESTED=YES
SECRET_LOGGING=FORBIDDEN
```

Credentials are server-side implementation state. They never enter ChatGPT tool arguments or output.

## 8. Least-privilege service

The Plugin/App surface exposes quota read only. It must not expose generic Codex execution, shell, thread control, account mutation, credits purchase or paid reset endpoints to the model.

```text
PLUGIN_TOOL_ALLOWLIST=get_quota_snapshot
CREDIT_PURCHASE_TOOL=ABSENT
PAID_RESET_TOOL=ABSENT
ACCOUNT_MUTATION_TOOL=ABSENT
GENERIC_CODEX_RPC_TOOL=ABSENT
```

If the service needs internal auth maintenance, those operations stay behind the server boundary and are not model-callable.

## 9. Freshness and availability

The backend records capture time and evaluates freshness at read time. It must not preserve an old `FRESH` label indefinitely.

Possible states:

```text
FRESH
STALE
UNAVAILABLE
CONFLICT
UNKNOWN
```

Missing 5h or weekly windows remain null/unavailable. An upstream error is not converted into a zero-usage snapshot.

## 10. Rate-limit normalization

Prefer the `codex` bucket when `rateLimitsByLimitId` contains it. Do not accidentally use a different bucket such as base-model inference as Work/Codex quota.

Window classification:

```text
RATE_WINDOW_POSITION_IS_NOT_SEMANTICS
300 minutes   → FIVE_HOUR
10080 minutes → WEEKLY
other         → OTHER_WINDOW
missing       → UNAVAILABLE
```

## 11. P0 proof

The 2026-09-07 P0 established:

```text
REMOTE_HEADLESS_CODEX_AUTH=PASS
PLUS_RATE_LIMIT_READ=PASS
SANITIZED_PROOF=PASS
EPHEMERAL_AUTH_CLEANUP=PASS
```

The P0 is reproducible research evidence in `experiments/p0_headless_quota_probe.py`. It is not itself the production service.

## 12. Error behavior

Expected server-facing states should map to stable product errors rather than leaking raw exceptions or credentials.

Examples:

```text
PLUGIN_NOT_CONNECTED
AUTHORIZATION_REQUIRED
AUTHORIZATION_EXPIRED
QUOTA_SOURCE_UNAVAILABLE
QUOTA_SNAPSHOT_STALE
ACCOUNT_BINDING_CONFLICT
UPSTREAM_PROTOCOL_ERROR
```

ChatGPT can continue non-quota-sensitive work when possible. The Plugin must never fabricate a successful snapshot to keep workflow moving.

## 13. Observability

Operational logs may record:

- request correlation id;
- stable non-secret subject surrogate;
- result class;
- source latency;
- freshness age;
- upstream error category.

Logs must not record raw auth tokens, device codes, cookies, `Authorization` headers or model-visible private content.

## 14. Release gates

Before PR to `main`:

```text
CHATGPT_WEB_CONNECT_AUTH_E2E=PASS
GET_QUOTA_SNAPSHOT_E2E=PASS
PLUS_ACCOUNT_TEST=PASS
SUBJECT_ACCOUNT_BINDING_AUDITED=YES
CREDENTIAL_ISOLATION_AUDITED=YES
TOKEN_REFRESH_REVOCATION=PASS
CROSS_SUBJECT_ISOLATION=PASS
READ_ONLY_TOOL_SURFACE=PASS
FAILURE_RECOVERY=PASS
SECURITY_REVIEW=PASS
```

No local Companion or CodexBar packaging gate is part of the production release criteria.
