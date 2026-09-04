import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from rules_engine import compare_field, run_business_rules, decide_outcome

router = APIRouter(prefix="/api/verification", tags=["verification"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_lrms_property(property_id: str):
    for record in load_json("synthetic_lrms.json"):
        if record["property_id"] == property_id:
            return record
    return None


def find_mutation(property_id: str):
    for record in load_json("synthetic_mutation.json"):
        if record["property_id"] == property_id:
            return record
    return None


def find_registration(registration_no: str):
    for record in load_json("synthetic_registration.json"):
        if record["registration_no"] == registration_no:
            return record
    return None


def find_encumbrance(property_id: str):
    for record in load_json("synthetic_encumbrance.json"):
        if record["property_id"] == property_id:
            active = any(e["status"] == "ACTIVE" for e in record.get("encumbrances", []))
            return active
    return False


class ExtractedFields(BaseModel):
    property_id: str
    owner_name: Optional[str] = None
    survey_no: Optional[str] = None
    area: Optional[float] = None
    village: Optional[str] = None
    registration_no: Optional[str] = None


@router.post("/document")
def verify_document(fields: ExtractedFields):
    lrms_record = find_lrms_property(fields.property_id)

    if lrms_record is None:
        raise HTTPException(status_code=404, detail="Property not found in LRMS — cannot verify")

    lrms_owner_name = lrms_record["owners"][0]["name"] if lrms_record.get("owners") else None

    field_results = [
        compare_field("owner_name", fields.owner_name, lrms_owner_name),
        compare_field("survey_no", fields.survey_no, lrms_record.get("survey_no")),
        compare_field("area", fields.area, lrms_record.get("area"), tolerance=0.01),
        compare_field("village", fields.village, lrms_record.get("village")),
    ]

    # Registration check — only run if the caller actually provided one
    if fields.registration_no:
        registration_record = find_registration(fields.registration_no)
        field_results.append(
            compare_field(
                "registration_no",
                fields.registration_no,
                registration_record["registration_no"] if registration_record else None
            )
        )

    mutation_record = find_mutation(fields.property_id)
    mutation_status = mutation_record["status"] if mutation_record else None

    encumbrance_active = find_encumbrance(fields.property_id)

    flags = run_business_rules(field_results, encumbrance_active=encumbrance_active, mutation_status=mutation_status)
    outcome = decide_outcome(flags, field_results)

    return {
        "property_id": fields.property_id,
        "fields": field_results,
        "mutation_status": mutation_status,
        "encumbrance_active": encumbrance_active,
        "flags": flags,
        "decision": outcome["decision"],
        "review_reason": outcome["reason"]
    }