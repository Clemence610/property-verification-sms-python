from src.property_verification import (
    InspectionReminder,
    MaintenanceRequest,
    TenantDocument,
    VerificationRequest,
    resend_if_stuck,
)


class FakeClient:
    def __init__(self, state):
        self.state = state
        self.resends = []

    def delivery_events(self, message_id):
        return {"ok": True, "data": {"status": self.state}}

    def resend_verification(self, message_id):
        self.resends.append(message_id)
        return {"ok": True, "data": {"message_id": message_id}}


def request():
    return VerificationRequest(
        "msg-7",
        "tenant-3",
        "+15550001111",
        MaintenanceRequest("m-1", "4B", "Tap"),
        TenantDocument("d-1", "tenant-3", "lease"),
        InspectionReminder("i-1", "4B", "2026-11-02"),
    )


def test_pending_delivery_is_resent_and_state_is_reported():
    client = FakeClient("pending")
    result = resend_if_stuck(request(), client)
    assert result["decision"] == "resend"
    assert result["delivery_state"] == "pending"
    assert client.resends == ["msg-7"]


def test_delivered_code_is_kept():
    client = FakeClient("delivered")
    result = resend_if_stuck(request(), client)
    assert result["decision"] == "keep"
    assert client.resends == []
