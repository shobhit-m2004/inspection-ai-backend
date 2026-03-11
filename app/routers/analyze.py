"""
Compliance Analysis Router

Analyzes SOP vs Log compliance using dynamic parameter extraction.
"""

import re
import numpy as np
from collections import defaultdict
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session
from typing import Any, List

from app.db.session import get_db
from app.models import SOP, Log, SOPChunk, LogChunk, ComplianceResult, User
from app.schemas import AnalyzeResponse, AnalyzeRequest
from app.utils.security import get_current_user_optional
from app.services.faiss_store import search
from app.services.report_llm import generate_report
from app.core.exceptions import BadRequestException
from app.core.logging_config import get_logger

router = APIRouter(prefix="/analyze", tags=["Compliance Analysis"])
logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.70


class DynamicParameterExtractor:
    """
    Extract ANY parameters dynamically from SOP/Log documents.
    No hardcoded parameters - works for any SOP with any parameters.
    """
    
    VALUE_UNIT_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*'
        r'(°C|°F|celsius|fahrenheit|psi|bar|pa|kpa|mpa|atm|'
        r'minutes?|mins?|hours?|hrs?|seconds?|secs?|rpm|rps|'
        r'mg|g|kg|grams?|kilograms?|ml|l|liters?|'
        r'%|percent|ph|fold|times|x|microns?|volts?|amps?|lux|degrees?|deg|°)?',
        re.IGNORECASE
    )
    
    UNIT_MAP = {
        '°c': '°C', 'celsius': '°C', '°f': '°F', 'fahrenheit': '°F',
        'min': 'minutes', 'mins': 'minutes', 'hr': 'hours', 'hrs': 'hours',
        'sec': 'seconds', 'secs': 'seconds', 'ml': 'mL', 'l': 'L',
        'mg': 'mg', 'g': 'g', 'kg': 'kg', 'psi': 'psi', 'bar': 'bar',
        'rpm': 'rpm', 'rps': 'rps', '%': '%', 'percent': '%', 'ph': 'pH',
    }
    
    PARAM_KEYWORDS = {
        'Temperature': ['temperature', 'temp', 'heat', 'cool', 'thermal'],
        'Pressure': ['pressure', 'press', 'psi', 'bar'],
        'Time': ['time', 'duration', 'for', 'mix', 'stir', 'hold', 'wait'],
        'Speed': ['speed', 'rpm', 'rps', 'stir', 'mix', 'rotate'],
        'pH Level': ['ph', 'acidity', 'alkaline'],
        'Volume': ['volume', 'dissolve', 'add', 'ml', 'liter'],
        'Weight': ['weight', 'add', 'mg', 'gram', 'kg'],
        'Humidity': ['humidity', 'rh', 'moisture'],
    }
    
    def extract_from_sop(self, text: str) -> List[dict]:
        """Extract EXPECTED parameters from SOP."""
        sentences = self._split_sentences(text)
        params = []
        
        for sentence in sentences:
            matches = list(self.VALUE_UNIT_PATTERN.finditer(sentence))
            for match in matches:
                value = match.group(1)
                unit_raw = match.group(2) or ""
                unit = self.UNIT_MAP.get(unit_raw.lower(), unit_raw)
                name = self._extract_name(sentence, match)
                
                params.append({
                    "name": name,
                    "expected": f"{value} {unit}".strip(),
                    "actual": "",
                    "unit": unit,
                    "value": value,
                    "status": "pending",
                    "sop_context": sentence.strip()[:200]
                })
        return params
    
    def extract_from_log(self, text: str) -> List[dict]:
        """Extract ACTUAL parameters from Log."""
        sentences = self._split_sentences(text)
        params = []
        
        for sentence in sentences:
            matches = list(self.VALUE_UNIT_PATTERN.finditer(sentence))
            for match in matches:
                value = match.group(1)
                unit_raw = match.group(2) or ""
                unit = self.UNIT_MAP.get(unit_raw.lower(), unit_raw)
                name = self._extract_name(sentence, match)
                
                params.append({
                    "name": name,
                    "expected": "",
                    "actual": f"{value} {unit}".strip(),
                    "unit": unit,
                    "value": value,
                    "status": "pending",
                    "log_context": sentence.strip()[:200]
                })
        return params
    
    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'[.!?;]\s*', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10 and re.search(r'\d', s)]
    
    def _extract_name(self, sentence: str, match: re.Match) -> str:
        context = sentence.lower()[max(0, match.start()-60):match.start()]
        for name, keywords in self.PARAM_KEYWORDS.items():
            if any(kw in context for kw in keywords):
                return name
        words = context.split()[-3:-1] if len(context.split()) > 3 else context.split()[-2:]
        return ' '.join(words).strip(' ,.:-').title() if words else "Parameter"


class ParameterComparator:
    """Compare Expected (SOP) vs Actual (Log) parameters."""
    
    TOLERANCE = {'Temperature': 2.0, 'Pressure': 5.0, 'Time': 5.0, 'Speed': 10.0, 'pH Level': 0.2, 'default': 5.0}
    
    def compare(self, sop_params: List[dict], log_params: List[dict]) -> List[dict]:
        """Compare SOP vs Log parameters."""
        results = []
        log_map = {p["name"].lower(): p for p in log_params}
        
        for sop in sop_params:
            key = sop["name"].lower()
            if key in log_map:
                log = log_map[key]
                status = self._check_status(sop, log)
                results.append({
                    "parameter": sop["name"],
                    "expected": sop["expected"],
                    "actual": log["actual"],
                    "status": status,
                    "score": 1.0 if status == "compliant" else 0.5 if status == "deviation" else 0.0,
                    "sop_context": sop.get("sop_context", ""),
                    "log_context": log.get("log_context", "")
                })
            else:
                results.append({
                    "parameter": sop["name"],
                    "expected": sop["expected"],
                    "actual": "Not found",
                    "status": "missing",
                    "score": 0.0,
                    "sop_context": sop.get("sop_context", ""),
                    "log_context": ""
                })
        return results
    
    def _check_status(self, expected: dict, actual: dict) -> str:
        try:
            exp = float(expected["value"])
            act = float(actual["value"])
            tol = self.TOLERANCE.get(expected["name"], self.TOLERANCE["default"])
            dev = abs(act - exp) / exp * 100
            if dev <= tol: return "compliant"
            if dev <= tol * 2: return "deviation"
            return "missing"
        except:
            return "compliant" if expected["value"] == actual["value"] else "deviation"


def _calculate_temporal_consistency(matched_indices: List[int]) -> float:
    """Calculate how well log events follow the SOP order."""
    if len(matched_indices) < 2:
        return 1.0

    inversions = 0
    for i in range(len(matched_indices) - 1):
        if matched_indices[i] > matched_indices[i + 1]:
            inversions += 1

    max_inversions = len(matched_indices) - 1
    return 1.0 - (inversions / max_inversions) if max_inversions > 0 else 1.0


def _gap_summary(matched: int, total: int, avg_score: float, temporal: float) -> str:
    """Generate a human-readable gap summary."""
    if total == 0:
        return "No SOP steps found."
    
    coverage = matched / total

    reasons = []
    if coverage < 0.8:
        reasons.append(f"Missing {total - matched} steps")
    if avg_score < 0.8:
        reasons.append("Low step similarity")
    if temporal < 0.7:
        reasons.append("Out-of-order execution detected")

    if not reasons:
        return "Operational logs fully align with SOP requirements."

    return "Gaps identified: " + "; ".join(reasons) + "."


def _pick_best_log(
    log_scores: dict, log_indices: dict
) -> tuple:
    """Select the best matching log based on combined score."""
    best_log = None
    best_avg = -1.0
    best_temporal = 0.0
    best_std = 0.0

    for log_id, scores in log_scores.items():
        avg = sum(scores) / max(1, len(scores))
        std = float(np.std(scores)) if len(scores) > 1 else 0.05
        temporal = _calculate_temporal_consistency(log_indices[log_id])

        combined = (avg * 0.6) + (temporal * 0.4)
        if combined > (best_avg * 0.6 + best_temporal * 0.4):
            best_avg = avg
            best_log = log_id
            best_temporal = temporal
            best_std = std

    return best_log, best_avg, best_temporal, best_std


@router.post(
    "",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze compliance",
    description="Analyze compliance between SOPs and operational logs",
    responses={
        400: {"description": "No SOPs or logs found"},
    },
)
def analyze(
    payload: AnalyzeRequest = Body(default=AnalyzeRequest()),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Perform compliance analysis between SOPs and operational logs.
    
    This endpoint:
    1. Retrieves all SOPs and their chunks
    2. Searches for matching log chunks using FAISS
    3. Calculates similarity scores and temporal consistency
    4. Predicts severity of any gaps found
    5. Stores and returns compliance results
    """
    sops_query = db.query(SOP)
    logs_query = db.query(Log)

    if payload.sop_id:
        sops_query = sops_query.filter(SOP.id == payload.sop_id)
    if payload.log_id:
        logs_query = logs_query.filter(Log.id == payload.log_id)

    sops = sops_query.all()
    logs = logs_query.all()
    
    if not sops:
        raise BadRequestException(detail="No SOPs found. Please upload SOP documents first.")
    
    if not logs:
        raise BadRequestException(detail="No logs found. Please upload operational logs first.")
    
    logger.info(
        "Compliance analysis started",
        user_id=getattr(current_user, "id", None),
        sop_count=len(sops),
        log_count=len(logs),
    )
    
    results = []

    for sop in sops:
        sop_chunks = (
            db.query(SOPChunk)
            .filter(SOPChunk.sop_id == sop.id)
            .order_by(SOPChunk.chunk_index)
            .all()
        )
        
        if not sop_chunks:
            continue

        log_scores = defaultdict(list)
        log_indices = defaultdict(list)
        rule_matches = []
        matched_chunks = 0

        for chunk in sop_chunks:
            if not chunk.embedding_vector:
                continue
            
            matches = search("log_chunk", chunk.embedding_vector, top_k=5)
            if not matches:
                continue

            for match_id, score in matches:
                log_chunk = db.query(LogChunk).filter(LogChunk.id == match_id).first()
                if log_chunk:
                    if payload.log_id and log_chunk.log_id != payload.log_id:
                        continue
                    log_scores[log_chunk.log_id].append(score)
                    log_indices[log_chunk.log_id].append(log_chunk.chunk_index)
                    if score >= SIMILARITY_THRESHOLD:
                        matched_chunks += 1
                    rule_matches.append({
                        "rule": chunk.content,
                        "log_excerpt": log_chunk.content,
                        "score": round(float(score), 4),
                    })
                    break

        if not log_scores:
            continue

        if payload.log_id:
            best_log_id = payload.log_id
            scores = log_scores.get(payload.log_id, [])
            avg_score = sum(scores) / max(1, len(scores))
            temporal = _calculate_temporal_consistency(log_indices.get(payload.log_id, []))
        else:
            best_log_id, avg_score, temporal, _ = _pick_best_log(log_scores, log_indices)
        coverage = matched_chunks / max(1, len(sop_chunks))

        log_title = ""
        if best_log_id:
            best_log = db.query(Log).filter(Log.id == best_log_id).first()
            log_title = best_log.title if best_log else ""

        report = generate_report(sop.title, log_title, rule_matches)
        severity = report.get("severity", "Medium")
        severity_conf = float(report.get("severity_confidence", 0.6))
        gap_summary = report.get("summary") or _gap_summary(matched_chunks, len(sop_chunks), avg_score, temporal)
        overall_score = float(report.get("overall_score", avg_score))

        result = ComplianceResult(
            sop_id=sop.id,
            log_id=best_log_id,
            similarity_score=overall_score,
            gap_summary=f"{gap_summary} (Severity: {severity})",
        )
        db.add(result)
        db.commit()
        db.refresh(result)

        results.append({
            "id": result.id,
            "sop_id": sop.id,
            "log_id": best_log_id,
            "similarity_score": round(overall_score, 4),
            "gap_summary": gap_summary,
            "matched_chunks": matched_chunks,
            "total_chunks": len(sop_chunks),
            "coverage": round(coverage, 4),
            "temporal_consistency": round(temporal, 4),
            "severity": severity,
            "severity_confidence": round(severity_conf, 4),
            "analyzed_at": result.analyzed_at,
        })

    logger.info(
        "Compliance analysis completed",
        results_count=len(results),
    )

    return {
        "results": results,
        "total_sops": len(sops),
        "total_logs": len(logs),
    }


@router.post(
    "/dynamic",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze compliance with dynamic parameter extraction",
    description="Analyze compliance using dynamic parameter extraction (Expected vs Actual)",
)
def analyze_dynamic(
    payload: AnalyzeRequest = Body(default=AnalyzeRequest()),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Analyze compliance using DYNAMIC parameter extraction.
    
    FLOW:
    1. Extract EXPECTED parameters from SOP (any parameters, not hardcoded)
    2. Extract ACTUAL parameters from Log (any parameters, not hardcoded)
    3. Compare Expected vs Actual dynamically
    4. Generate report with LLM showing deviations and missing parameters
    5. Return results with full report data for frontend display
    """
    sops_query = db.query(SOP)
    logs_query = db.query(Log)
    
    if payload.sop_id:
        sops_query = sops_query.filter(SOP.id == payload.sop_id)
    if payload.log_id:
        logs_query = logs_query.filter(Log.id == payload.log_id)
    
    sops = sops_query.all()
    logs = logs_query.all()
    
    if not sops:
        raise BadRequestException(detail="No SOPs found. Please upload SOP documents first.")
    if not logs:
        raise BadRequestException(detail="No logs found. Please upload operational logs first.")
    
    logger.info("Dynamic compliance analysis started", sop_count=len(sops), log_count=len(logs))
    
    # Initialize extractors and comparator
    sop_extractor = DynamicParameterExtractor()
    log_extractor = DynamicParameterExtractor()
    comparator = ParameterComparator()
    
    results = []
    
    for sop in sops:
        for log in logs:
            # STEP 1: Extract EXPECTED parameters from SOP
            sop_params = sop_extractor.extract_from_sop(sop.content)
            
            # STEP 2: Extract ACTUAL parameters from Log
            log_params = log_extractor.extract_from_log(log.content)
            
            # STEP 3: Compare Expected vs Actual
            compared = comparator.compare(sop_params, log_params)
            
            # STEP 4: Generate report with LLM
            report = generate_report(sop.title, log.title, compared)
            
            # STEP 5: Save results
            result = ComplianceResult(
                sop_id=sop.id, log_id=log.id,
                similarity_score=report.get("overall_score", 0),
                gap_summary=report.get("summary", ""),
            )
            db.add(result)
            db.commit()
            
            results.append({
                "id": result.id,
                "sop_id": sop.id,
                "log_id": log.id,
                "similarity_score": round(report.get("overall_score", 0), 4),
                "gap_summary": report.get("summary", ""),
                "report_json": report,  # Full report for frontend
            })
    
    logger.info("Dynamic compliance analysis completed", results_count=len(results))
    
    return {"results": results, "total_sops": len(sops), "total_logs": len(logs)}

