import pytest

from app.core.validation import audit_success


@pytest.mark.parametrize("input_str, expected", [
    ('{"Verification_Status": "SUCCESS"}', True),
    ('{"Verification_Status": "Revision_Required"}', False),
    ("STATUS: SUCCESS", True),
    ("STATUS: VERIFIED", True),
    ("STATUS: ANOMALY", False),
    ("This is a SUCCESS story", False),
    # Should be False because it doesn't start with SUCCESS/VERIFIED
    ("SUCCESS: The data is correct", True),
    ("VERIFIED: and accurate", True),
    ("REVISION_REQUIRED: fix the citations", False),
    ("Random text with no status", False),
    ("", False),
    (None, False),
])
def test_audit_success_variations(input_str, expected):
    assert audit_success(input_str) == expected
