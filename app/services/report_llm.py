import json
import os
import re
from typing import Any, Dict, List
from datetime import datetime

import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-1.5-flash")


def _extract_json(text: str) -> Dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _infer_param_name(rule_text: str, fallback: str) -> str:
    """Infer a readable parameter name from SOP text."""
    if not rule_text:
        return fallback

    text = rule_text.lower()
    keyword_map = {
        "Temperature": ["temperature", "temp", "thermal", "heat", "cool"],
        "Pressure": ["pressure", "press", "psi", "bar", "kpa", "mpa", "atm"],
        "Time": ["time", "duration", "minutes", "hours", "seconds", "mins", "hrs", "secs"],
        "Speed": ["speed", "rpm", "rps", "stir", "mix", "rotate"],
        "pH Level": ["ph", "acidity", "alkaline"],
        "Volume": ["volume", "ml", "mL", "l", "liter", "liters"],
        "Weight": ["weight", "mg", "g", "kg", "gram", "grams", "kilogram"],
        "Humidity": ["humidity", "rh", "moisture"],
    }
    for name, keywords in keyword_map.items():
        if any(k in text for k in keywords):
            return name

    # Try to use the first short phrase before a comma/colon/semicolon
    short = re.split(r"[,;:]", rule_text)[0].strip()
    words = short.split()
    if 2 <= len(words) <= 8:
        return " ".join(words).strip(" .,-").title()

    return fallback


def _fallback_report(rule_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a detailed fallback report with parameter-level comparison."""
    if not rule_matches:
        return {
            "overall_score": 0.0,
            "severity": "High",
            "severity_confidence": 0.9,
            "summary": "No SOP rules or log evidence found.",
            "gaps": [],
            "comparison_data": [],
            "parameter_comparison": [],
            "missing_parameters": [],
            "chart": {"type": "bar", "labels": ["Matched", "Missing"], "values": [0, 0]},
        }

    matched = sum(1 for r in rule_matches if r.get("score", 0) >= 0.7)
    total = len(rule_matches)
    missing = total - matched
    overall_score = round(sum(r.get("score", 0) for r in rule_matches) / max(1, total), 4)
    severity = "Low" if overall_score >= 0.85 else "Medium" if overall_score >= 0.6 else "High"

    # Build detailed parameter comparison
    parameter_comparison = []
    missing_parameters = []
    
    for i, r in enumerate(rule_matches[:20]):
        rule_text = r.get("rule", "")
        log_text = r.get("log_excerpt", "")
        score = r.get("score", 0)
        
        # Extract parameter name from rule (keywords or short phrase)
        param_name = _infer_param_name(rule_text, f"Parameter {i+1}")
        expected_value = "Not specified"
        actual_value = "Not found"
        status = "missing"
        
        # Try to extract numerical values from rule
        numbers_in_rule = re.findall(r'\d+(?:\.\d+)?(?:\s*(?:°C|°F|psi|bar|Pa|minutes?|hours?|hrs?|mins?|mg|g|kg|mL|L|%)?)?', rule_text, re.IGNORECASE)
        numbers_in_log = re.findall(r'\d+(?:\.\d+)?(?:\s*(?:°C|°F|psi|bar|Pa|minutes?|hours?|hrs?|mins?|mg|g|kg|mL|L|%)?)?', log_text, re.IGNORECASE)
        
        if numbers_in_rule:
            expected_value = numbers_in_rule[0]
            param_name = _infer_param_name(rule_text, param_name)
        if numbers_in_log:
            actual_value = numbers_in_log[0]
        
        if score >= 0.7:
            status = "compliant"
        elif score >= 0.4:
            status = "deviation"
        else:
            status = "missing"
            missing_parameters.append({
                "parameter": param_name,
                "expected": expected_value,
                "reason": "No matching log entry found"
            })
        
        parameter_comparison.append({
            "parameter": param_name,
            "expected": expected_value,
            "actual": actual_value,
            "score": round(score, 4),
            "status": status,
            "rule_text": rule_text[:200] if len(rule_text) > 200 else rule_text,
            "log_text": log_text[:200] if len(log_text) > 200 else log_text,
        })

    return {
        "overall_score": overall_score,
        "severity": severity,
        "severity_confidence": 0.6,
        "summary": f"Detected {missing} missing steps out of {total}. Compliance score: {overall_score*100:.1f}%",
        "gaps": [
            {
                "expected": r.get("rule", ""),
                "observed": r.get("log_excerpt", ""),
                "severity": "High" if r.get("score", 0) < 0.6 else "Medium",
                "recommendation": "Verify this SOP step in the operational log.",
                "score": round(r.get("score", 0), 4),
            }
            for r in rule_matches[:10]
        ],
        "comparison_data": [
            {
                "parameter": item["parameter"],
                "expected": 1.0 if item["status"] == "compliant" else 0.0,
                "actual": item["score"]
            }
            for i, item in enumerate(parameter_comparison[:10])
        ],
        "parameter_comparison": parameter_comparison,
        "missing_parameters": missing_parameters,
        "chart": {"type": "bar", "labels": ["Matched", "Missing"], "values": [matched, missing]},
        "generated_at": datetime.utcnow().isoformat(),
        "total_parameters": total,
        "compliant_parameters": matched,
        "deviation_parameters": sum(1 for r in rule_matches if 0.4 <= r.get("score", 0) < 0.7),
    }


def _build_enhanced_prompt(sop_title: str, log_title: str, parameter_comparison: List[Dict]) -> str:
    """Build enhanced LLM prompt for professional compliance report."""
    return f"""
================================================================================
PHARMACEUTICAL COMPLIANCE AUDIT REPORT
================================================================================

ROLE: Expert pharmaceutical compliance auditor (20+ years GMP experience).

TASK: Analyze SOP vs Log parameter comparison and generate comprehensive audit report.

================================================================================
INPUT DATA
================================================================================

SOP DOCUMENT: {sop_title}
LOG DOCUMENT: {log_title}

PARAMETER COMPARISON (Expected vs Actual):
{json.dumps(parameter_comparison, indent=2)}

================================================================================
REPORT REQUIREMENTS
================================================================================

Generate JSON report with EXACT structure:

{{
  "overall_score": <float 0-1>,
  "severity": "<Low|Medium|High>",
  "severity_confidence": <float 0-1>,
  "summary": "<string - mention specific deviations>",
  "gaps": [
    {{
      "expected": "<string - SOP requirement>",
      "observed": "<string - Log value or 'Not recorded'>",
      "severity": "<Low|Medium|High>",
      "recommendation": "<string - corrective action>",
      "parameter_name": "<string>",
      "deviation_amount": "<string - e.g., '-2°C' or '5% lower'>"
    }}
  ],
  "comparison_data": [
    {{"parameter": "<string>", "expected": <float 0-1>, "actual": <float 0-1>}}
  ],
  "chart": {{
    "type": "bar",
    "labels": ["Compliant", "Deviation", "Missing"],
    "values": [<int>, <int>, <int>]
  }}
}}

================================================================================
ANALYSIS RULES
================================================================================

1. OVERALL SCORE: compliant_count ÷ total_parameters

2. SEVERITY:
   - Low: score >= 0.8 (80%+ compliant)
   - Medium: score 0.5-0.8 (50-80% compliant)
   - High: score < 0.5 (<50% compliant)

3. SUMMARY must include:
   - Total parameters analyzed
   - Count: compliant, deviations, missing
   - Highlight critical deviations (temperature, pressure, pH)
   - Example: "Analyzed 10 parameters: 7 compliant, 2 deviations, 1 missing. Critical temperature deviation (expected 30°C, actual 25°C)."

4. GAPS - For EACH non-compliant parameter:
   - expected: Quote SOP requirement
   - observed: Quote Log value or "Not recorded in log"
   - severity: High for critical (temp/pressure/pH), Medium otherwise
   - recommendation: Specific corrective action
   - parameter_name: Name of parameter
   - deviation_amount: Calculate difference (e.g., "-5°C", "10 min short")

5. MISSING PARAMETERS:
   - Clearly state which SOP parameters NOT in logs
   - Mark High severity if critical

6. TONE: Professional, objective, factual, no blame language

================================================================================
EXAMPLE OUTPUT
================================================================================

{{
  "overall_score": 0.7,
  "severity": "Medium",
  "severity_confidence": 0.85,
  "summary": "Analyzed 10 parameters: 7 compliant, 2 deviations, 1 missing. Critical temperature deviation (expected 30°C, actual 25°C). pH not recorded.",
  "gaps": [
    {{
      "expected": "Maintain temperature at 30°C",
      "observed": "Temperature recorded at 25°C",
      "severity": "High",
      "recommendation": "Investigate heating system. Implement temperature alarm.",
      "parameter_name": "Temperature",
      "deviation_amount": "-5°C (16.7% below setpoint)"
    }}
  ],
  "comparison_data": [
    {{"parameter": "Temperature", "expected": 1.0, "actual": 0.0}},
    {{"parameter": "Mixing Time", "expected": 1.0, "actual": 1.0}}
  ],
  "chart": {{
    "type": "bar",
    "labels": ["Compliant", "Deviation", "Missing"],
    "values": [7, 2, 1]
  }}
}}

================================================================================
Return ONLY valid JSON - no markdown, no explanations.
================================================================================

Generate compliance report:
"""


def generate_report(
    sop_title: str,
    log_title: str,
    parameter_comparison: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate compliance report using LLM with enhanced prompt.
    
    parameter_comparison: list of {parameter, expected, actual, status, score, ...}
    """
    if not GEMINI_API_KEY:
        return _fallback_report(parameter_comparison)

    # Use enhanced prompt
    prompt = _build_enhanced_prompt(sop_title, log_title, parameter_comparison)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TEXT_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(url, json=payload, timeout=45)
        if resp.status_code != 200:
            return _fallback_report(parameter_comparison)
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        parsed = _extract_json(text)
        if parsed:
            # Merge with structured data
            parsed["parameter_comparison"] = parameter_comparison
            parsed["missing_parameters"] = [
                {"parameter": p["parameter"], "expected": p["expected"], "reason": "Not found in log"}
                for p in parameter_comparison if p.get("status") == "missing"
            ]
            parsed["generated_at"] = datetime.utcnow().isoformat()
            parsed["total_parameters"] = len(parameter_comparison)
            parsed["compliant_parameters"] = sum(1 for p in parameter_comparison if p.get("status") == "compliant")
            parsed["deviation_parameters"] = sum(1 for p in parameter_comparison if p.get("status") == "deviation")
            return parsed
        return _fallback_report(parameter_comparison)
    except Exception:
        return _fallback_report(parameter_comparison)
