# Non-Frontend Team Handoff (Consolidated)

## Why this is needed
Frontend now supports receipt evidence display and approval workflows, but several behaviors still require backend/OCR enforcement and persistence to prevent bypasses and complete the intended product flow.

## Backend team TODO

1. Guarantee first-signup bootstrap contract
- Keep/signup behavior should always create:
  - one new company
  - one admin user
  - company currency derived from selected country
- Add automated tests for this flow to prevent regressions.

2. Enforce admin-only user governance
- Validate only admins can create/update users.
- Validate manager relationship rules server-side:
  - employees can have manager_id
  - managers/admin should generally not have manager_id (or enforce policy)

3. Persist uploaded receipt files and store URL
- Accept and store employee receipt upload in durable storage (local media folder or object storage).
- Save generated URL/path into `expenses.receipt_url`.
- Ensure this works even when employee uses OCR upload flow without manually entering a link.

4. Expose receipt evidence in approval queue payload
- Include `receipt_url` in `/approvals/queue` response so approvers can access evidence directly from queue table.
- Include `amount_in_base` in `/approvals/queue` so managers see company-currency amount directly without frontend fallback.

5. Enforce server-side receipt proof rule
- In expense creation, reject submission unless one of these is provided:
  - `receipt_url`
  - uploaded receipt reference stored by backend
- Keep this validation server-side so API clients cannot bypass frontend checks.

6. Approval-rule execution engine completion
- Ensure rule processing supports:
  - percentage rule (e.g., 60%)
  - specific approver short-circuit approval
  - hybrid rule (percentage OR specific approver)
  - optional manager-first sequencing + multi-step approvers
- Add integration tests for each mode and mixed scenarios.

7. Admin permissions coverage endpoints
- Confirm/expand endpoints for:
  - view all expenses
  - override approvals with reason
  - read/create/update approval rules

8. Add audit trace for receipt metadata
- Optionally store file name, uploader, and upload timestamp for compliance and dispute resolution.

## OCR team TODO

1. Return attachment metadata after OCR scan
- OCR response should include metadata for the uploaded file (e.g., `file_name`, `mime_type`, `stored_receipt_url` if available).

2. Integrate OCR scan and receipt storage
- OCR pipeline should not only extract fields, but also return/stitch the stored receipt location that backend can persist.

3. Improve extraction quality fields
- Keep returning `amount`, `date`, `vendor`, `description`, `currency`.
- Add confidence scores per field so UI can highlight low-confidence values for user verification.

4. Standardize OCR response contract
- Keep amount/date/vendor/description/currency and add stable metadata fields for file identity.

## Contract suggestion
Use a shared response shape for receipt-aware OCR:

```json
{
  "amount": 123.45,
  "date": "2026-03-29",
  "description": "Business lunch",
  "vendor": "Cafe XYZ",
  "currency": "INR",
  "file_name": "receipt_123.jpg",
  "mime_type": "image/jpeg",
  "stored_receipt_url": "https://.../receipt_123.jpg",
  "confidence": {
    "amount": 0.92,
    "date": 0.81,
    "vendor": 0.74
  }
}
```

## Latest Verified Findings (March 29, 2026)

1. Receipt enforcement gap in backend expense creation
- Verified by API test: expense can still be created without `receipt_url` and without any uploaded file reference.
- Impact: frontend validation can be bypassed by direct API clients.
- Required fix: enforce server-side validation in `/expenses` create endpoint:
  - require one of: `receipt_url` OR persisted uploaded receipt reference.

2. Unexpected immediate approval status observed
- In OCR integration sanity test, a newly created expense returned `approved` directly instead of expected `pending` workflow progression.
- Impact: approval workflow may be skipped under certain rule states.
- Required fix: review approval engine defaults and rule fallback path; add regression tests for "no rule", "manager-first", and "hybrid" scenarios to confirm intended status transitions.

3. OCR endpoint contract itself is healthy
- Verified:
  - image upload returns HTTP 200 with expected OCR fields
  - PDF upload returns HTTP 200 with expected OCR fields
  - unsupported MIME returns HTTP 400
- No immediate router/service crash found during runtime checks.
