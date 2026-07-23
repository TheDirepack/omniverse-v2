import json


def audit_success(audit_result: str | dict | None) -> bool:
    """
    Classifies an audit result as success or revision-required.
    Expects a JSON response or a plain text status.
    """
    if not audit_result:
        return False

    if isinstance(audit_result, dict):
        status = str(audit_result.get("Verification_Status", "")).strip().upper()
        return status == "SUCCESS"

    try:
        parsed = json.loads(audit_result)
        status = str(parsed.get("Verification_Status", "")).strip().upper()
        if status:
            return status == "SUCCESS"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    for pattern in ("REVISION_REQUIRED", "REVISION REQUIRED"):
        if pattern in audit_result.upper():
            return False

    upper = audit_result.upper()
    lines = upper.splitlines()
    for line in lines:
        line = line.strip()
        if (
            line.startswith("SUCCESS")
            or line.startswith("VERIFIED")
            or line.startswith("STATUS: SUCCESS")
            or line.startswith("STATUS: VERIFIED")
        ):
            return True

    return False
