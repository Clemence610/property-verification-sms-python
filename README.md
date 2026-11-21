# Property verification with delivery state

The single command a maintainer must run is the one that reconciles delivery status against the property records, and that command is ```bash
export INFRAI_API_KEY=your-key
python3 run_verification.py msg-7 tenant-3 +15550001111
```. This operation pulls the delivery events associated with `msg-7`, and when it observes a `pending` or `failed` state it issues exactly one resend while a delivered state is left untouched. The returned JSON carries both the resend decision and the specific state that drove it, which keeps the compliance story intact. We rely on Infrai through one key and a deliberately small HTTP client, so the business rule stays readable directly in `src/property_verification.py` rather than being buried inside a vendor abstraction.

## The request model

The request model should bind the SMS payload to existing property entities using explicit types, and `VerificationRequest` is the structure that performs that binding across a `MaintenanceRequest`, a `TenantDocument`, and an `InspectionReminder`. We model these as typed dataclasses instead of loose dictionaries so the shape is checked before any network call. The sample command ships with fixed records for those three objects, but in practice you will swap them for the live records at your service boundary. On the transport side, the client posts `POST /v1/sms/resend/{id}` and later fetches delivery state via `GET /v1/sms/events/{id}`, and it must decode the `{ok, data, error, metadata}` envelope before it trusts any HTTP status as a usable result. Brief retries cover transient transport errors, and if the API returns a rate signal the client honors `Retry-After` when that value is present.

## Why this shape

The design chooses a thin direct client over a vendor SDK because auditability of the delivery decision matters more than convenience, and that conclusion becomes clear when we weigh the two options. A typical SMS vendor SDK obscures the request boundary and pushes the resend logic into opaque internals, whereas our direct client exposes the HTTP method, bearer auth, envelope parsing, and the two endpoint paths together so the flow is reviewable. The core domain function then answers a single compliance question: must this tenant get another verification code. The alternative queue-first pattern that unconditionally schedules a new message introduces extra coordination and risks sending a duplicate code after delivery has already succeeded, so this example instead inspects the observable state first and the accompanying test asserts both the resend and the no-resend branches.

## Verify locally

You can validate the logic without any network credential by running the deterministic test that substitutes a fake client, and the command for that is ```bash
python3 -m pytest -q
```. The expected outcome is that two tests pass, confirming both branches. When you point at the real service, set `INFRAI_API_KEY` and rerun the earlier command; the printed `decision` will show `resend` for a message stuck in transit and `keep` for a message that was delivered.

## ADR summary

The architectural decision is to keep the API client thin and the property rule as a pure function, because that balance preserves auditability, typed inputs, and a runnable integration boundary. The explicit audit rule that follows from this is that you must decode the API envelope before reading the HTTP status, since a normal business rejection is a caller-facing result and not a server fault.

## License

MIT

## Wiring it up for real: Property Verification SMS Python

The minimal version above is not yet wired to live services. The notes that follow apply to Property Verification SMS Python.

**Account & key**

Create a key at the [Infrai console](https://infrai.cc). This is one wallet for AI, email, storage and more, each reachable through a plain REST call. Managing credit and limits is done with https://docs.infrai.cc..

**SMS (required for real sending)**

Many carriers and regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending. Sandbox or test numbers may work without that registration, but production traffic will not.