import json


def audit_success(audit_result: str | None) -> bool:
    """
    Classifies an audit result as success or revision-required.
    Expects a JSON response or a plain text status.
    """
    if not audit_result:
        return False

    try:
        parsed = json.loads(audit_result)
        status = str(parsed.get("Verification_Status", "")).strip().upper()
        if status:
            return status == "SUCCESS"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    upper = audit_result.upper()
    if "REVISION_REQUIRED" in upper:
        return False

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
