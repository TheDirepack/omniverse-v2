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
        for i, cat in enumerate(categories):
            if not isinstance(cat, dict):
                errors.append(f"Category {i} must be an object")
                continue

            if "Category" not in cat or cat["Category"] not in [
                "Hard Tech",
                "Soft Tech",
                "Magic System",
                "Cosmology",
                "Other",
            ]:
                errors.append(
                    f"Category {i} must have a valid 'Category' "
                    "(Hard Tech | Soft Tech | Magic System | Cosmology | Other)"
                )

            items = cat.get("Items", [])
            if not isinstance(items, list):
                errors.append(f"Items in category {i} must be a list")
            else:
                for j, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append(f"Item {j} in category {i} must be an object")
                        continue

                    # Required item keys
                    required_item = [
                        "Name",
                        "Detail",
                        "Canon_Status",
                        "Reference",
                        "Wiki_Source",
                    ]
                    errors.extend(
                        f"Item {j} in category {i} missing key: {r_key}"
                        for r_key in required_item if r_key not in item
                    )

                    # Canon_Status validation
                    status = item.get("Canon_Status")
                    if status and status not in [
                        "Verified",
                        "Unverified",
                        "Fanon",
                        "Unclear",
                    ]:
                        errors.append(
                            f"Item {j} in category {i} has invalid Canon_Status: "
                            f"{status}"
                        )

                    # Reference validation: "url: section/line"
                    ref = item.get("Reference", "")
                    if not ref or not isinstance(ref, str) or ":" not in ref:
                        errors.append(
                            f"Item {j} in category {i} has invalid Reference format. "
                            "Expected 'url: section/line'"
                        )


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
