from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class VerificationVerdict(BaseModel):
    passed: bool
    rule: str
    details: Dict[str, Any]
    message: str


class DeterministicVerifier:
    """
    Deterministic Invariant Verifier.
    Evaluates whether an agent's answer meets explicit mathematical,
    relational, and schema constraints without relying on non-deterministic LLM-as-a-judge.
    """

    @staticmethod
    def verify_sql_result(
        candidate_result: List[Dict[str, Any]],
        expected_result: List[Dict[str, Any]],
        order_sensitive: bool = False,
    ) -> VerificationVerdict:
        if len(candidate_result) != len(expected_result):
            return VerificationVerdict(
                passed=False,
                rule="row_count_match",
                details={"candidate_rows": len(candidate_result), "expected_rows": len(expected_result)},
                message=f"Row count mismatch: expected {len(expected_result)}, got {len(candidate_result)}",
            )

        if order_sensitive:
            if candidate_result != expected_result:
                return VerificationVerdict(
                    passed=False,
                    rule="ordered_equality",
                    details={"candidate": candidate_result, "expected": expected_result},
                    message="Ordered rows do not match ground truth.",
                )
        else:
            # Sort dictionaries by values for set comparison
            def sort_key(d: Dict[str, Any]) -> str:
                return str(sorted(d.items()))

            cand_sorted = sorted(candidate_result, key=sort_key)
            exp_sorted = sorted(expected_result, key=sort_key)

            if cand_sorted != exp_sorted:
                return VerificationVerdict(
                    passed=False,
                    rule="set_equality",
                    details={"candidate": cand_sorted, "expected": exp_sorted},
                    message="Result rows do not match ground truth set.",
                )

        return VerificationVerdict(
            passed=True,
            rule="exact_data_match",
            details={"matched_rows": len(candidate_result)},
            message="Query result bitwise matches expected ground truth.",
        )

    @staticmethod
    def verify_schema(data: Any, required_fields: List[str]) -> VerificationVerdict:
        if not isinstance(data, dict):
            return VerificationVerdict(
                passed=False,
                rule="dict_type",
                details={"actual_type": type(data).__name__},
                message=f"Expected dictionary payload, got {type(data).__name__}",
            )

        missing = [f for f in required_fields if f not in data]
        if missing:
            return VerificationVerdict(
                passed=False,
                rule="required_fields",
                details={"missing_fields": missing},
                message=f"Missing required fields: {', '.join(missing)}",
            )

        return VerificationVerdict(
            passed=True,
            rule="schema_conformance",
            details={"fields": list(data.keys())},
            message="Data conforms to required schema.",
        )
