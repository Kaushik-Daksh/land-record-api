from typing import Optional


def compare_field(field_name: str, extracted_value, authoritative_value, tolerance: float = 0.0) -> dict:
    """
    Compares a single extracted field against its authoritative counterpart.
    Returns a structured result: MATCH, MISMATCH, or MISSING.
    """
    if extracted_value is None or extracted_value == "":
        return {
            "field": field_name,
            "extracted": extracted_value,
            "authoritative": authoritative_value,
            "status": "MISSING"
        }

    if authoritative_value is None:
        return {
            "field": field_name,
            "extracted": extracted_value,
            "authoritative": authoritative_value,
            "status": "NOT_FOUND"
        }

    # Numeric fields (like area) get a tolerance-based comparison
    if isinstance(extracted_value, (int, float)) and isinstance(authoritative_value, (int, float)):
        if abs(extracted_value - authoritative_value) <= tolerance:
            status = "MATCH"
        else:
            status = "MISMATCH"
    else:
        # Text fields — simple case-insensitive exact match for now
        if str(extracted_value).strip().lower() == str(authoritative_value).strip().lower():
            status = "MATCH"
        else:
            status = "MISMATCH"

    return {
        "field": field_name,
        "extracted": extracted_value,
        "authoritative": authoritative_value,
        "status": status
    }


def run_business_rules(field_results: list, encumbrance_active: bool = False, mutation_status: Optional[str] = None) -> list:
    """
    Applies deterministic business rules on top of field comparison results.
    Returns a list of flags (issues that require attention).
    """
    flags = []

    for result in field_results:
        if result["status"] == "MISMATCH":
            flags.append(f"{result['field'].upper()}_MISMATCH")
        elif result["status"] == "MISSING":
            flags.append(f"{result['field'].upper()}_MISSING")
        elif result["status"] == "NOT_FOUND":
            flags.append(f"{result['field'].upper()}_NOT_FOUND")

    if encumbrance_active:
        flags.append("ACTIVE_ENCUMBRANCE")

    if mutation_status == "PENDING":
        flags.append("MUTATION_PENDING")

    return flags


def decide_outcome(flags: list, field_results: list) -> dict:
    """
    Given the flags and field-level results, decides the final outcome:
    AUTO_APPROVE, HUMAN_REVIEW, or REJECTED.
    """
    if not flags:
        return {
            "decision": "AUTO_APPROVE",
            "reason": []
        }

    # Hard-stop conditions — always require human review, never auto-approve
    critical_flags = [
        f for f in flags
        if "MISMATCH" in f or "NOT_FOUND" in f or f == "ACTIVE_ENCUMBRANCE"
    ]

    if critical_flags:
        return {
            "decision": "HUMAN_REVIEW",
            "reason": flags
        }

    # Softer flags (like pending mutation) still get flagged, but might be
    # a lower-severity review case — for MVP we'll route these to review too
    return {
        "decision": "HUMAN_REVIEW",
        "reason": flags
    }