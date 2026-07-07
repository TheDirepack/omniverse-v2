import pytest
from app.core.validators import validate_research_json


def get_valid_data():
    return {
        "Universe_Name": "Test",
        "Source_Wikis": ["wiki1"],
        "Data_Categories": [
            {
                "Category": "Hard Tech",
                "Items": [
                    {
                        "Name": "Weapon",
                        "Detail": "A weapon",
                        "Canon_Status": "Verified",
                        "Reference": "url.com: section1",
                        "Wiki_Source": "wiki1",
                    }
                ],
            }
        ],
        "Knowledge_Graph": [
            {"Lead": "lead1", "Reason": "reason1", "Expected_Value": "value1"}
        ],
        "Missing_Info": ["info1"],
        "Provisional_Conclusions": [
            {
                "Conclusion": "conc1",
                "Reasoning": "reason",
                "Confidence": "High",
                "Verification_Need": "verify",
            }
        ],
    }


class TestValidateResearchJson:
    def test_valid_data(self):
        is_valid, errors = validate_research_json(get_valid_data())
        assert is_valid
        assert errors == []

    def test_root_not_dict(self):
        is_valid, errors = validate_research_json("not a dict")
        assert not is_valid
        assert "Root must be a JSON object" in errors

    def test_root_not_dict_list(self):
        is_valid, errors = validate_research_json([1, 2, 3])
        assert not is_valid
        assert "Root must be a JSON object" in errors

    def test_missing_root_keys(self):
        is_valid, errors = validate_research_json({"Universe_Name": "T"})
        assert not is_valid
        assert "Missing root key: Source_Wikis" in errors
        assert "Missing root key: Data_Categories" in errors
        assert "Missing root key: Knowledge_Graph" in errors
        assert "Missing root key: Missing_Info" in errors
        assert "Missing root key: Provisional_Conclusions" in errors

    def test_data_categories_not_list(self):
        data = get_valid_data()
        data["Data_Categories"] = "not a list"
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Data_Categories must be a list" in errors

    def test_category_not_dict(self):
        data = get_valid_data()
        data["Data_Categories"] = ["string", None]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Category 0 must be an object" in errors
        assert "Category 1 must be an object" in errors

    def test_category_missing_valid_category(self):
        data = get_valid_data()
        data["Data_Categories"] = [{"Items": []}]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("Category 0 must have a valid" in e for e in errors)

    def test_category_invalid_category_value(self):
        data = get_valid_data()
        data["Data_Categories"] = [{"Category": "InvalidCategory", "Items": []}]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("Category 0 must have a valid" in e for e in errors)

    def test_items_not_list(self):
        data = get_valid_data()
        data["Data_Categories"] = [{"Category": "Hard Tech", "Items": "not-list"}]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Items in category 0 must be a list" in errors

    def test_item_not_dict(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {"Category": "Hard Tech", "Items": ["string", 42]}
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Item 0 in category 0 must be an object" in errors
        assert "Item 1 in category 0 must be an object" in errors

    def test_item_missing_required_keys(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Soft Tech",
                "Items": [{"Name": "OnlyName"}],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Item 0 in category 0 missing key: Detail" in errors
        assert "Item 0 in category 0 missing key: Canon_Status" in errors
        assert "Item 0 in category 0 missing key: Reference" in errors
        assert "Item 0 in category 0 missing key: Wiki_Source" in errors

    def test_item_invalid_canon_status(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Magic System",
                "Items": [
                    {
                        "Name": "Spell",
                        "Detail": "Fireball",
                        "Canon_Status": "InvalidStatus",
                        "Reference": "url: section",
                        "Wiki_Source": "w",
                    }
                ],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("invalid Canon_Status" in e for e in errors)

    def test_item_canon_status_none(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Cosmology",
                "Items": [
                    {
                        "Name": "Realm",
                        "Detail": "Heaven",
                        "Canon_Status": None,
                        "Reference": "url: section",
                        "Wiki_Source": "w",
                    }
                ],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert is_valid
        assert errors == []

    def test_item_invalid_reference_format(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Other",
                "Items": [
                    {
                        "Name": "Thing",
                        "Detail": "stuff",
                        "Canon_Status": "Unverified",
                        "Reference": "",
                        "Wiki_Source": "w",
                    }
                ],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("invalid Reference format" in e for e in errors)

    def test_item_reference_missing_colon(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Hard Tech",
                "Items": [
                    {
                        "Name": "Gadget",
                        "Detail": "Thing",
                        "Canon_Status": "Fanon",
                        "Reference": "no-colon",
                        "Wiki_Source": "w",
                    }
                ],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("invalid Reference format" in e for e in errors)

    def test_item_reference_not_string(self):
        data = get_valid_data()
        data["Data_Categories"] = [
            {
                "Category": "Hard Tech",
                "Items": [
                    {
                        "Name": "Gadget",
                        "Detail": "Thing",
                        "Canon_Status": "Unclear",
                        "Reference": 123,
                        "Wiki_Source": "w",
                    }
                ],
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("invalid Reference format" in e for e in errors)

    def test_knowledge_graph_not_list(self):
        data = get_valid_data()
        data["Knowledge_Graph"] = "not list"
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Knowledge_Graph must be a list" in errors

    def test_knowledge_graph_item_not_dict(self):
        data = get_valid_data()
        data["Knowledge_Graph"] = ["string"]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Lead 0 in Knowledge_Graph must be an object" in errors

    def test_knowledge_graph_missing_keys(self):
        data = get_valid_data()
        data["Knowledge_Graph"] = [{"Lead": "only"}]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Lead 0 in Knowledge_Graph missing key: Reason" in errors
        assert "Lead 0 in Knowledge_Graph missing key: Expected_Value" in errors

    def test_provisional_conclusions_not_list(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = "not list"
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Provisional_Conclusions must be a list" in errors

    def test_provisional_conclusions_item_not_dict(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = [None]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Conclusion 0 in Provisional_Conclusions must be an object" in errors

    def test_provisional_conclusions_missing_keys(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = [{"Conclusion": "c"}]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Conclusion 0 in Provisional_Conclusions missing key: Reasoning" in errors
        assert "Conclusion 0 in Provisional_Conclusions missing key: Confidence" in errors
        assert "Conclusion 0 in Provisional_Conclusions missing key: Verification_Need" in errors

    def test_provisional_conclusions_invalid_confidence(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = [
            {
                "Conclusion": "c",
                "Reasoning": "r",
                "Confidence": "Invalid",
                "Verification_Need": "v",
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert any("invalid Confidence" in e for e in errors)

    def test_provisional_conclusions_confidence_none(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = [
            {
                "Conclusion": "c",
                "Reasoning": "r",
                "Confidence": None,
                "Verification_Need": "v",
            }
        ]
        is_valid, errors = validate_research_json(data)
        assert is_valid
        assert errors == []

    def test_multiple_errors_at_once(self):
        data = {
            "Universe_Name": "T",
            "Source_Wikis": "not list",  # missing Data_Categories
        }
        is_valid, errors = validate_research_json(data)
        assert not is_valid
        assert "Missing root key: Data_Categories" in errors
        assert "Missing root key: Knowledge_Graph" in errors
        assert "Missing root key: Missing_Info" in errors
        assert "Missing root key: Provisional_Conclusions" in errors

    def test_all_category_types_valid(self):
        for cat_type in ["Hard Tech", "Soft Tech", "Magic System", "Cosmology", "Other"]:
            data = get_valid_data()
            data["Data_Categories"] = [
                {
                    "Category": cat_type,
                    "Items": [
                        {
                            "Name": "X",
                            "Detail": "Y",
                            "Canon_Status": "Verified",
                            "Reference": "u: s",
                            "Wiki_Source": "w",
                        }
                    ],
                }
            ]
            is_valid, errors = validate_research_json(data)
            assert is_valid, f"Category {cat_type} should be valid"
            assert errors == []

    def test_all_canon_statuses_valid(self):
        for status in ["Verified", "Unverified", "Fanon", "Unclear"]:
            data = get_valid_data()
            data["Data_Categories"] = [
                {
                    "Category": "Hard Tech",
                    "Items": [
                        {
                            "Name": "X",
                            "Detail": "Y",
                            "Canon_Status": status,
                            "Reference": "u: s",
                            "Wiki_Source": "w",
                        }
                    ],
                }
            ]
            is_valid, errors = validate_research_json(data)
            assert is_valid, f"Canon_Status {status} should be valid"
            assert errors == []

    def test_all_confidence_levels_valid(self):
        for conf in ["Low", "Medium", "High"]:
            data = get_valid_data()
            data["Provisional_Conclusions"] = [
                {
                    "Conclusion": "c",
                    "Reasoning": "r",
                    "Confidence": conf,
                    "Verification_Need": "v",
                }
            ]
            is_valid, errors = validate_research_json(data)
            assert is_valid, f"Confidence {conf} should be valid"
            assert errors == []

    def test_empty_data_categories(self):
        data = get_valid_data()
        data["Data_Categories"] = []
        is_valid, errors = validate_research_json(data)
        assert is_valid
        assert errors == []

    def test_empty_knowledge_graph(self):
        data = get_valid_data()
        data["Knowledge_Graph"] = []
        is_valid, errors = validate_research_json(data)
        assert is_valid
        assert errors == []

    def test_empty_provisional_conclusions(self):
        data = get_valid_data()
        data["Provisional_Conclusions"] = []
        is_valid, errors = validate_research_json(data)
        assert is_valid
        assert errors == []
