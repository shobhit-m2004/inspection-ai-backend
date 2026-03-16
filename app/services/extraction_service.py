from __future__ import annotations

import re
from typing import Any

from app.models.enums import DocumentType
from app.services.normalization_service import normalization_service
from app.utils.llm import try_llm_json


class ExtractionService:
    RANGE_BETWEEN_PATTERN = re.compile(
        r'(?P<parameter>[A-Za-z\s]+?)\s*(?:should|must|shall|is to be|to be)?\s*(?:maintained|kept)?\s*(?:between|from)\s*(?P<min>-?\d+(?:\.\d+)?)\s*(?:to|and|-)\s*(?P<max>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%/.\u00b0]+)?',
        re.IGNORECASE,
    )
    RANGE_PLUS_MINUS_PATTERN = re.compile(
        r'(?P<parameter>[A-Za-z\s]+?)\s*(?:should|must|shall|is to be|to be)?\s*(?:maintained|kept|at)?\s*(?P<target>-?\d+(?:\.\d+)?)\s*(?:\u00b1|\\+/-)\s*(?P<tolerance>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%/.\u00b0]+)?',
        re.IGNORECASE,
    )
    EXACT_VALUE_PATTERN = re.compile(
        r'(?P<parameter>[A-Za-z\s]+?)\s*(?:should|must|shall|to be|is)\s*(?:maintained at|set at|at)?\s*(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%/.\u00b0]+)?',
        re.IGNORECASE,
    )
    FREQUENCY_PATTERN = re.compile(
        r'(?P<parameter>[A-Za-z\s]+?)\s*(?:record|check|inspect|verify|sample)\w*\s*(?:every|each)\s*(?P<freq_value>\d+)\s*(?P<freq_unit>minutes?|mins?|hours?|hrs?|batches?)',
        re.IGNORECASE,
    )
    NUMERIC_PATTERN = re.compile(r'(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z%/.\u00b0]+)?')
    ISO_TIMESTAMP_PATTERN = re.compile(r'\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?\b')

    def extract_structured(
        self,
        document_type: DocumentType,
        raw_text: str,
        selected_parameters: list[str] | None = None,
        mode: str = 'auto',
    ) -> tuple[dict[str, Any], list[str]]:
        selected = normalization_service.normalize_selected_parameters(selected_parameters)
        warnings: list[str] = []

        if document_type == DocumentType.SOP:
            deterministic = self.extract_sop_rules(raw_text, selected)
            target_key = 'rules'
        else:
            deterministic = self.extract_log_observations(raw_text, selected)
            target_key = 'observations'

        llm_candidate = self._llm_refine(
            document_type=document_type,
            raw_text=raw_text,
            deterministic_json=deterministic,
            selected_parameters=selected,
            mode=mode,
        )

        if llm_candidate and isinstance(llm_candidate.get(target_key), list):
            merged = llm_candidate
        else:
            merged = deterministic
            if llm_candidate is None:
                warnings.append('LLM refinement not applied; deterministic extraction used.')
            else:
                warnings.append('LLM output was invalid for expected schema; deterministic extraction used.')

        return merged, warnings

    def extract_sop_rules(self, raw_text: str, selected: list[str]) -> dict[str, Any]:
        rules: list[dict[str, Any]] = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        current_section = 'General'

        for line in lines:
            if len(line) < 4:
                continue

            if line.endswith(':') and len(line.split()) <= 8:
                current_section = line.rstrip(':')
                continue

            canonical_param, aliases = normalization_service.match_parameter_tokens(line)
            if selected and not normalization_service.is_in_selected(canonical_param, selected):
                continue

            if ' if ' in f' {line.lower()} ' and ' then ' in f' {line.lower()} ':
                condition_text = line
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=canonical_param or 'conditional check',
                        aliases=aliases,
                        rule_type='conditional',
                        expected_action='verify condition outcome',
                        condition=condition_text,
                        source_text=line,
                        mandatory=True,
                    )
                )
                continue

            if ' before ' in f' {line.lower()} ' or ' after ' in f' {line.lower()} ':
                relation = 'before' if ' before ' in f' {line.lower()} ' else 'after'
                sequence_target = line.lower().split(relation, 1)[1].strip()
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=canonical_param or 'sequence check',
                        aliases=aliases,
                        rule_type='sequence',
                        expected_action='follow sequence',
                        sequence_before=sequence_target if relation == 'before' else None,
                        condition=f'performed {relation} {sequence_target}',
                        source_text=line,
                        mandatory=True,
                    )
                )
                continue

            match = self.RANGE_BETWEEN_PATTERN.search(line)
            if match:
                parameter = normalization_service.normalize_parameter(match.group('parameter')) or canonical_param
                if selected and not normalization_service.is_in_selected(parameter, selected):
                    continue
                min_value = float(match.group('min'))
                max_value = float(match.group('max'))
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=parameter or canonical_param or 'unknown',
                        aliases=aliases,
                        rule_type='range',
                        expected_action='maintain',
                        min_value=min_value,
                        max_value=max_value,
                        target_value=round((min_value + max_value) / 2, 3),
                        unit=self._sanitize_unit(match.group('unit')),
                        source_text=line,
                    )
                )
                continue

            plus_minus = self.RANGE_PLUS_MINUS_PATTERN.search(line)
            if plus_minus:
                parameter = normalization_service.normalize_parameter(plus_minus.group('parameter')) or canonical_param
                if selected and not normalization_service.is_in_selected(parameter, selected):
                    continue
                target = float(plus_minus.group('target'))
                tolerance = float(plus_minus.group('tolerance'))
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=parameter or canonical_param or 'unknown',
                        aliases=aliases,
                        rule_type='range',
                        expected_action='maintain',
                        min_value=target - tolerance,
                        max_value=target + tolerance,
                        target_value=target,
                        unit=self._sanitize_unit(plus_minus.group('unit')),
                        source_text=line,
                    )
                )
                continue

            frequency = self.FREQUENCY_PATTERN.search(line)
            if frequency:
                parameter = normalization_service.normalize_parameter(frequency.group('parameter')) or canonical_param
                if selected and not normalization_service.is_in_selected(parameter, selected):
                    continue
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=parameter or canonical_param or 'unknown',
                        aliases=aliases,
                        rule_type='frequency',
                        expected_action='record',
                        frequency=f"every {frequency.group('freq_value')} {frequency.group('freq_unit')}",
                        source_text=line,
                    )
                )
                continue

            exact = self.EXACT_VALUE_PATTERN.search(line)
            if exact:
                parameter = normalization_service.normalize_parameter(exact.group('parameter')) or canonical_param
                if selected and not normalization_service.is_in_selected(parameter, selected):
                    continue
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=parameter or canonical_param or 'unknown',
                        aliases=aliases,
                        rule_type='exact_value',
                        expected_action='match',
                        target_value=float(exact.group('value')),
                        unit=self._sanitize_unit(exact.group('unit')),
                        source_text=line,
                    )
                )
                continue

            if any(token in line.lower() for token in ['must', 'shall', 'required', 'completed', 'signed']):
                if not canonical_param:
                    continue
                rules.append(
                    self._make_sop_rule(
                        rule_id=f'R{len(rules) + 1}',
                        section=current_section,
                        parameter=canonical_param,
                        aliases=aliases,
                        rule_type='presence',
                        expected_action='present',
                        source_text=line,
                    )
                )

        return {'rules': rules}

    def extract_log_observations(self, raw_text: str, selected: list[str]) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        current_page = 'page_1'

        for line in lines:
            page_match = re.match(r'^\[page_(\d+)\]$', line.lower())
            if page_match:
                current_page = f'page_{page_match.group(1)}'
                continue

            canonical_param, aliases = normalization_service.match_parameter_tokens(line)
            if selected and not normalization_service.is_in_selected(canonical_param, selected):
                continue
            if not canonical_param:
                continue

            numeric_match = self.NUMERIC_PATTERN.search(line)
            timestamp_match = self.ISO_TIMESTAMP_PATTERN.search(line)
            status = 'recorded' if numeric_match else 'present'

            if any(word in line.lower() for word in ['missing', 'not done', 'not recorded']):
                status = 'missing'

            value = float(numeric_match.group('value')) if numeric_match else None
            unit = self._sanitize_unit(numeric_match.group('unit')) if numeric_match else None

            confidence = 0.94 if numeric_match else 0.87
            if status == 'missing':
                confidence = 0.8

            observations.append(
                {
                    'observation_id': f'O{len(observations) + 1}',
                    'timestamp': timestamp_match.group(0).replace(' ', 'T') if timestamp_match else None,
                    'parameter': canonical_param,
                    'aliases_detected': aliases,
                    'normalized_value': value,
                    'unit': unit,
                    'status': status,
                    'raw_text': line,
                    'source_location': current_page,
                    'confidence': confidence,
                }
            )

        return {'observations': observations}

    def _llm_refine(
        self,
        document_type: DocumentType,
        raw_text: str,
        deterministic_json: dict[str, Any],
        selected_parameters: list[str],
        mode: str,
    ) -> dict[str, Any] | None:
        schema_key = 'rules' if document_type == DocumentType.SOP else 'observations'
        prompt = f"""
You are improving deterministic extraction for compliance review.

Document type: {document_type.value}
Mode: {mode}
Selected parameters: {selected_parameters}

Constraints:
- Keep only evidence-backed items from the raw text.
- Do not invent fields or values.
- Preserve IDs when possible.
- Return JSON with top-level key '{schema_key}'.

Current deterministic JSON:
{deterministic_json}

Raw text:
{raw_text[:14000]}
"""
        return try_llm_json(prompt)

    @staticmethod
    def _sanitize_unit(unit: str | None) -> str | None:
        if not unit:
            return None
        cleaned = unit.strip().replace('\u00b0', '')
        return cleaned if cleaned else None

    @staticmethod
    def _make_sop_rule(
        rule_id: str,
        section: str,
        parameter: str,
        aliases: list[str],
        rule_type: str,
        expected_action: str,
        min_value: float | None = None,
        max_value: float | None = None,
        target_value: float | None = None,
        unit: str | None = None,
        frequency: str | None = None,
        mandatory: bool = True,
        condition: str | None = None,
        sequence_before: str | None = None,
        source_text: str = '',
    ) -> dict[str, Any]:
        return {
            'rule_id': rule_id,
            'section': section,
            'parameter': parameter,
            'aliases': aliases,
            'rule_type': rule_type,
            'expected_action': expected_action,
            'min_value': min_value,
            'max_value': max_value,
            'target_value': target_value,
            'unit': unit,
            'frequency': frequency,
            'mandatory': mandatory,
            'condition': condition,
            'sequence_before': sequence_before,
            'source_text': source_text,
        }


extraction_service = ExtractionService()

