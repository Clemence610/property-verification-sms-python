import argparse
import json

from src.property_verification import (
    InfraiSmsClient,
    InspectionReminder,
    MaintenanceRequest,
    TenantDocument,
    VerificationRequest,
    resend_if_stuck,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resend a stuck property verification code")
    parser.add_argument("message_id")
    parser.add_argument("tenant_id")
    parser.add_argument("phone")
    args = parser.parse_args()
    request = VerificationRequest(
        message_id=args.message_id,
        tenant_id=args.tenant_id,
        phone=args.phone,
        maintenance=MaintenanceRequest("maint-104", "4B", "Leaking kitchen tap"),
        document=TenantDocument("doc-22", args.tenant_id, "lease"),
        inspection=InspectionReminder("inspect-9", "4B", "2026-11-02"),
    )
    print(json.dumps(resend_if_stuck(request, InfraiSmsClient()), indent=2))


if __name__ == "__main__":
    main()
