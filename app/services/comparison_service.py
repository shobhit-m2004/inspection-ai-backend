from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.services.normalization_service import normalization_service


class ComparisonService:
    ALLOWED_STATUSES = {'compliant', 'missing', 'deviation', 'partial', 'unclear'}

    def compare(self, sop_json: dict[str, Any], log_json: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
        rules = sop_json.get('rules', [])
        observations = log_json.get('observations', [])

        findings: list[dict[str, Any]] = []
        for rule in rules:
            findings.append(self._evaluate_rule(rule, observations))

        counts = Counter(finding['status'] for finding in findings)
        summary = {
            'total_rules': len(rules),
            'compliant': counts.get('compliant', 0),
            'missing': counts.get('missing', 0),
            'deviation': counts.get('deviation', 0),
            'partial': counts.get('partial', 0),
            'unclear': counts.get('unclear', 0),
        }

        return findings, summary

    def _evaluate_rule(self, rule: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
        parameter = normalization_service.normalize_parameter(rule.get('parameter')) or (rule.get('parameter') or 'unknown')
        matched = self._match_observations(rule, observations)
        matched_ids = [obs.get('observation_id', '?') for obs in matched]
        rule_type = rule.get('rule_type', 'presence')
        mandatory = bool(rule.get('mandatory', True))

        status = 'unclear'
        explanation = 'Insufficient signal to evaluate this rule.'

        if rule_type == 'presence':
            if matched and any(obs.get('status') in {'present', 'recorded'} for obs in matched):
                status = 'compliant'
                explanation = 'Required evidence is present in execution logs.'
            else:
                status = 'missing'
                explanation = 'Required presence evidence was not found in logs.'

        elif rule_type == 'range':
            if not matched:
                status = 'missing'
                explanation = 'No matching observation found for range rule.'
            else:
                numeric_obs = [obs for obs in matched if isinstance(obs.get('normalized_value'), (int, float))]
                if not numeric_obs:
                    status = 'partial'
                    explanation = 'Matching records exist but no numeric value was captured for range check.'
                else:
                    min_value = rule.get('min_value')
                    max_value = rule.get('max_value')
                    offending = [
                        obs
                        for obs in numeric_obs
                        if (min_value is not None and obs['normalized_value'] < min_value)
                        or (max_value is not None and obs['normalized_value'] > max_value)
                    ]
                    if offending:
                        obs = offending[0]
                        status = 'deviation'
                        explanation = (
                            f"Observed value {obs['normalized_value']} {obs.get('unit') or ''} violates allowed range "
                            f"{min_value} to {max_value}."
                        ).strip()
                    else:
                        status = 'compliant'
                        explanation = 'Observed value(s) are within the expected range.'

        elif rule_type == 'exact_value':
            expected = rule.get('target_value')
            if not matched:
                status = 'missing'
                explanation = 'No observation found for exact-value rule.'
            else:
                numeric_obs = [obs for obs in matched if isinstance(obs.get('normalized_value'), (int, float))]
                if expected is None or not numeric_obs:
                    status = 'partial'
                    explanation = 'Rule or log lacks numeric value needed for exact comparison.'
                elif any(obs['normalized_value'] != expected for obs in numeric_obs):
                    obs = next(obs for obs in numeric_obs if obs['normalized_value'] != expected)
                    status = 'deviation'
                    explanation = f"Observed value {obs['normalized_value']} does not match expected {expected}."
                else:
                    status = 'compliant'
                    explanation = 'Observed value matches exact expected value.'

        elif rule_type == 'frequency':
            if not matched:
                status = 'missing'
                explanation = 'No log evidence found for required frequency rule.'
            else:
                minimum_count = self._extract_frequency_minimum(rule.get('frequency'))
                if minimum_count is None:
                    status = 'unclear'
                    explanation = 'Could not parse required frequency into a deterministic minimum count.'
                elif len(matched) >= minimum_count:
                    status = 'compliant'
                    explanation = f'Frequency satisfied: {len(matched)} occurrences recorded (required >= {minimum_count}).'
                elif len(matched) > 0:
                    status = 'partial'
                    explanation = f'Only {len(matched)} occurrences found (required >= {minimum_count}).'

        elif rule_type == 'sequence':
            status, explanation = self._evaluate_sequence(rule, observations, matched)

        elif rule_type == 'conditional':
            status, explanation = self._evaluate_conditional(rule, observations)

        if status not in self.ALLOWED_STATUSES:
            status = 'unclear'

        severity = self._severity_for(status, mandatory)

        return {
            'rule_id': rule.get('rule_id', 'unknown'),
            'parameter': parameter,
            'status': status,
            'matched_observations': matched_ids,
            'explanation': explanation,
            'severity': severity,
        }

    def _match_observations(self, rule: dict[str, Any], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rule_parameter = normalization_service.normalize_parameter(rule.get('parameter'))
        rule_aliases = {a.lower() for a in rule.get('aliases', [])}
        if rule_parameter:
            rule_aliases.add(rule_parameter.lower())

        matches: list[dict[str, Any]] = []
        for obs in observations:
            obs_parameter = normalization_service.normalize_parameter(obs.get('parameter'))
            obs_aliases = {a.lower() for a in obs.get('aliases_detected', [])}
            if obs_parameter:
                obs_aliases.add(obs_parameter.lower())

            if rule_parameter and obs_parameter and rule_parameter == obs_parameter:
                matches.append(obs)
                continue

            if rule_aliases.intersection(obs_aliases):
                matches.append(obs)

        return matches

    def _evaluate_sequence(
        self,
        rule: dict[str, Any],
        observations: list[dict[str, Any]],
        matched: list[dict[str, Any]],
    ) -> tuple[str, str]:
        target_text = (rule.get('sequence_before') or '').strip()
        if not matched:
            return 'missing', 'No primary sequence observation found.'
        if not target_text:
            return 'unclear', 'Sequence target missing in rule configuration.'

        target_param = normalization_service.normalize_parameter(target_text)
        target_obs = [
            obs
            for obs in observations
            if normalization_service.normalize_parameter(obs.get('parameter')) == target_param
        ]
        if not target_obs:
            return 'partial', 'Primary step found, but target step for sequence comparison is missing.'

        first_primary = self._safe_timestamp(matched[0].get('timestamp'))
        first_target = self._safe_timestamp(target_obs[0].get('timestamp'))
        if not first_primary or not first_target:
            return 'partial', 'Sequence evidence exists, but timestamp precision is insufficient.'

        if first_primary <= first_target:
            return 'compliant', 'Sequence order is correct based on timestamps.'
        return 'deviation', 'Sequence order is incorrect; primary step occurred after required next step.'

    def _evaluate_conditional(self, rule: dict[str, Any], observations: list[dict[str, Any]]) -> tuple[str, str]:
        condition = (rule.get('condition') or '').lower()
        if 'if' not in condition or 'then' not in condition:
            return 'unclear', 'Conditional rule text could not be deterministically parsed.'

        parts = condition.split('then', 1)
        trigger_text = parts[0].replace('if', '', 1).strip()
        response_text = parts[1].strip()

        trigger_param = normalization_service.normalize_parameter(trigger_text)
        response_param = normalization_service.normalize_parameter(response_text)

        trigger_present = any(
            normalization_service.normalize_parameter(obs.get('parameter')) == trigger_param for obs in observations
        )
        response_present = any(
            normalization_service.normalize_parameter(obs.get('parameter')) == response_param for obs in observations
        )

        if not trigger_present:
            return 'unclear', 'Trigger condition not observed, so conditional requirement is not activated.'
        if trigger_present and response_present:
            return 'compliant', 'Condition occurred and required follow-up evidence is present.'
        return 'deviation', 'Condition occurred but required follow-up evidence is missing.'

    @staticmethod
    def _extract_frequency_minimum(frequency: str | None) -> int | None:
        if not frequency:
            return None
        match = re.search(r'(\d+)', frequency)
        return int(match.group(1)) if match else None

    @staticmethod
    def _safe_timestamp(raw_timestamp: str | None) -> datetime | None:
        if not raw_timestamp:
            return None
        try:
            return datetime.fromisoformat(raw_timestamp.replace('Z', '+00:00'))
        except ValueError:
            return None

    @staticmethod
    def _severity_for(status: str, mandatory: bool) -> str:
        if status == 'deviation':
            return 'high'
        if status == 'missing':
            return 'high' if mandatory else 'medium'
        if status == 'partial':
            return 'medium'
        if status == 'unclear':
            return 'medium'
        return 'low'


comparison_service = ComparisonService()
