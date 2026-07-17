from typing import Any


def validate_research_json(data: Any) -> tuple[bool, list[str]]:
    """
    Validates research JSON against expected schema and checks for required fields.
    Returns (is_valid, errors).
    """
    if not isinstance(data, dict):
        return False, ["Root must be a JSON object"]

    errors = []

    # Required root keys
    required_root = [
        "Universe_Name",
        "Source_Wikis",
        "Data_Categories",
        "Knowledge_Graph",
        "Missing_Info",
        "Provisional_Conclusions",
    ]
    errors.extend(
        f"Missing root key: {key}" for key in required_root if key not in data
    )

    # Validate Data_Categories
    categories = data.get("Data_Categories", [])
    if not isinstance(categories, list):
        errors.append("Data_Categories must be a list")
    else:
        valid_categories = ["Hard Tech", "Soft Tech", "Magic System", "Cosmology", "Other"]
        valid_canon_statuses = ["Verified", "Unverified", "Fanon", "Unclear", None]
        for i, cat in enumerate(categories):
            if not isinstance(cat, dict):
                errors.append(f"Category {i} must be an object")
                continue

            cat_name = cat.get("Category")
            if not cat_name or cat_name not in valid_categories:
                errors.append(f"Category {i} must have a valid category name")

            items = cat.get("Items")
            if not isinstance(items, list):
                errors.append(f"Items in category {i} must be a list")
                continue

            for j, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"Item {j} in category {i} must be an object")
                    continue

                item_required = ["Name", "Detail", "Canon_Status", "Reference", "Wiki_Source"]
                errors.extend(
                    f"Item {j} in category {i} missing key: {rk}"
                    for rk in item_required if rk not in item
                )

                canon = item.get("Canon_Status")
                if canon is not None and canon not in valid_canon_statuses:
                    errors.append(f"Item {j} in category {i} has invalid Canon_Status: {canon}")

                ref = item.get("Reference")
                if not isinstance(ref, str) or not ref or ":" not in ref:
                    errors.append(f"Item {j} in category {i} has invalid Reference format")

    # Validate Knowledge_Graph

    graph = data.get("Knowledge_Graph", [])
    if not isinstance(graph, list):
        errors.append("Knowledge_Graph must be a list")
    else:
        for i, lead in enumerate(graph):
            if not isinstance(lead, dict):
                errors.append(f"Lead {i} in Knowledge_Graph must be an object")
                continue
            errors.extend(
                f"Lead {i} in Knowledge_Graph missing key: {r_key}"
                for r_key in ["Lead", "Reason", "Expected_Value"]
                if r_key not in lead
            )
            # Evidence Verification: Every lead must have a way to be verified
            if not lead.get("URL") and not lead.get("Reference"):
                 errors.append(f"Lead {i} in Knowledge_Graph missing reference/URL evidence")

    # Validate Provisional_Conclusions
    conclusions = data.get("Provisional_Conclusions", [])
    if not isinstance(conclusions, list):
        errors.append("Provisional_Conclusions must be a list")
    else:
        for i, conc in enumerate(conclusions):
            if not isinstance(conc, dict):
                errors.append(
                    f"Conclusion {i} in Provisional_Conclusions must be an object"
                )
                continue

            errors.extend(
                f"Conclusion {i} in Provisional_Conclusions missing key: {r_key}"
                for r_key in [
                    "Conclusion", "Reasoning", "Confidence", "Verification_Need"
                ]
                if r_key not in conc
            )

            conf = conc.get("Confidence")
            if conf and conf not in ["Low", "Medium", "High"]:
                errors.append(
                    f"Conclusion {i} in Provisional_Conclusions has "
                    f"invalid Confidence: {conf}"
                )



    return len(errors) == 0, errors
