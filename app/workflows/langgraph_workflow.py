from __future__ import annotations

import copy
import re
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.models.enums import DocumentType
from app.services.extraction_service import extraction_service
from app.services.normalization_service import normalization_service


class ReviewState(TypedDict, total=False):
    document_type: Literal['SOP', 'LOG']
    raw_text: str
    current_json: dict[str, Any]
    selected_parameters: list[str]
    user_message: str
    assistant_message: str
    updated_json: dict[str, Any] | None
    changed: bool
    approved: bool


def extraction_node(state: ReviewState) -> ReviewState:
    doc_type = DocumentType(state['document_type'])
    extracted, _ = extraction_service.extract_structured(
        document_type=doc_type,
        raw_text=state.get('raw_text', ''),
        selected_parameters=state.get('selected_parameters', []),
        mode='manual' if state.get('selected_parameters') else 'auto',
    )
    return {'current_json': extracted, 'updated_json': extracted, 'changed': True}


def explanation_node(state: ReviewState) -> ReviewState:
    message = state.get('user_message', '')
    current_json = state.get('current_json') or {}
    raw_text = state.get('raw_text', '')
    selected = state.get('selected_parameters') or []

    focus_param = _guess_parameter_from_message(message)
    evidence_in_text = _find_evidence_line(raw_text, focus_param) if focus_param else None
    container_key = 'rules' if state['document_type'] == 'SOP' else 'observations'
    items = current_json.get(container_key, [])

    if focus_param:
        present = any(normalization_service.normalize_parameter(i.get('parameter')) == focus_param for i in items)
        if present:
            assistant_message = (
                f"{focus_param} appears in the extracted JSON because matching evidence was found in the source text."
            )
        elif evidence_in_text:
            assistant_message = (
                f"{focus_param} is currently missing in JSON, but I found likely evidence in source text: '{evidence_in_text}'. "
                'You can ask me to add it and I will apply an evidence-backed correction.'
            )
        else:
            assistant_message = (
                f"{focus_param} is not visible because I could not find clear evidence in the uploaded text. "
                'To avoid hallucination, extraction keeps it out unless text evidence exists.'
            )
    else:
        mode_hint = 'manual parameter mode' if selected else 'auto mode'
        assistant_message = (
            f'I reviewed the extraction context using {mode_hint}. '
            'If you name a specific parameter, I can explain exactly why it was included or missing.'
        )

    return {'assistant_message': assistant_message, 'updated_json': None, 'changed': False}


def correction_node(state: ReviewState) -> ReviewState:
    message = state.get('user_message', '')
    doc_type = DocumentType(state['document_type'])
    raw_text = state.get('raw_text', '')
    selected = state.get('selected_parameters') or []

    container_key = 'rules' if doc_type == DocumentType.SOP else 'observations'
    current_json = copy.deepcopy(state.get('current_json') or {container_key: []})
    items = current_json.get(container_key, [])

    changed = False
    updates: list[str] = []

    only_params = _parse_only_extract(message)
    if only_params:
        normalized = normalization_service.normalize_selected_parameters(only_params)
        filtered_items = [
            item
            for item in items
            if normalization_service.normalize_parameter(item.get('parameter')) in normalized
        ]
        if len(filtered_items) != len(items):
            current_json[container_key] = _reindex_items(filtered_items, doc_type)
            items = current_json[container_key]
            changed = True
            updates.append(f'filtered output to only {normalized}')

    remove_param = _parse_action_parameter(message, ['remove', 'delete', 'drop'])
    if remove_param:
        target = normalization_service.normalize_parameter(remove_param)
        filtered_items = [
            item for item in items if normalization_service.normalize_parameter(item.get('parameter')) != target
        ]
        if len(filtered_items) != len(items):
            current_json[container_key] = _reindex_items(filtered_items, doc_type)
            items = current_json[container_key]
            changed = True
            updates.append(f'removed {target}')

    add_param = _parse_action_parameter(message, ['add', 'include', 'recheck'])
    if add_param:
        target = normalization_service.normalize_parameter(add_param)
        extracted, _ = extraction_service.extract_structured(
            document_type=doc_type,
            raw_text=raw_text,
            selected_parameters=[target],
            mode='manual',
        )
        candidates = extracted.get(container_key, [])
        existing_pairs = {(i.get('parameter'), i.get('source_text')) for i in items}
        new_items = [
            i for i in candidates if (i.get('parameter'), i.get('source_text')) not in existing_pairs
        ]
        if new_items:
            current_json[container_key] = _reindex_items(items + new_items, doc_type)
            items = current_json[container_key]
            changed = True
            updates.append(f'added {target} from source evidence')
        else:
            updates.append(f'no evidence found to add {target}')

    mandatory_param = _parse_action_parameter(message, ['mandatory'])
    if mandatory_param and doc_type == DocumentType.SOP:
        target = normalization_service.normalize_parameter(mandatory_param)
        toggled = 0
        for item in items:
            if normalization_service.normalize_parameter(item.get('parameter')) == target:
                if not item.get('mandatory'):
                    item['mandatory'] = True
                    toggled += 1
        if toggled > 0:
            changed = True
            updates.append(f'marked {target} as mandatory')

    if doc_type == DocumentType.SOP and ('range not exact' in message.lower() or 'should be range' in message.lower()):
        focus = _guess_parameter_from_message(message)
        for item in items:
            if item.get('rule_type') == 'exact_value' and (
                not focus or normalization_service.normalize_parameter(item.get('parameter')) == focus
            ):
                target = item.get('target_value')
                if isinstance(target, (int, float)):
                    item['rule_type'] = 'range'
                    item['min_value'] = target - 1
                    item['max_value'] = target + 1
                    changed = True
        if changed:
            updates.append('converted exact_value to range where applicable')

    if not updates:
        updates.append('no deterministic correction pattern matched your request')

    assistant_message = (
        'I applied evidence-based corrections: ' + '; '.join(updates)
        if changed
        else 'I reviewed your request but did not change JSON because evidence was insufficient or no matching pattern was found.'
    )

    # Keep selected-parameter context aligned if user asks for strict filter.
    effective_selected = selected
    if only_params:
        effective_selected = normalization_service.normalize_selected_parameters(only_params)

    return {
        'assistant_message': assistant_message,
        'updated_json': current_json,
        'changed': changed,
        'selected_parameters': effective_selected,
    }


def approval_node(state: ReviewState) -> ReviewState:
    return {
        'assistant_message': 'JSON has been finalized for approval. You can now save the approved version.',
        'updated_json': state.get('current_json'),
        'changed': False,
        'approved': True,
    }


def analysis_assist_node(state: ReviewState) -> ReviewState:
    return {
        'assistant_message': 'For unclear findings, compare source_text and matched observations, then confirm unit/time alignment.',
        'changed': False,
        'updated_json': None,
    }


def route_intent(state: ReviewState) -> str:
    message = state.get('user_message', '').lower()
    if any(token in message for token in ['approve', 'finalize']):
        return 'approval'
    if any(token in message for token in ['add', 'remove', 'delete', 'correct', 'recheck', 'mandatory', 'only extract']):
        return 'correction'
    if any(token in message for token in ['analysis', 'unclear finding']):
        return 'analysis_assist'
    return 'explanation'


def build_review_graph():
    graph = StateGraph(ReviewState)
    graph.add_node('extraction_node', extraction_node)
    graph.add_node('explanation_node', explanation_node)
    graph.add_node('correction_node', correction_node)
    graph.add_node('approval_node', approval_node)
    graph.add_node('analysis_assist_node', analysis_assist_node)

    graph.add_conditional_edges(
        START,
        route_intent,
        {
            'explanation': 'explanation_node',
            'correction': 'correction_node',
            'approval': 'approval_node',
            'analysis_assist': 'analysis_assist_node',
        },
    )
    graph.add_edge('explanation_node', END)
    graph.add_edge('correction_node', END)
    graph.add_edge('approval_node', END)
    graph.add_edge('analysis_assist_node', END)
    return graph.compile()


review_graph = build_review_graph()


def run_review_graph(state: ReviewState) -> ReviewState:
    return review_graph.invoke(state)


def _guess_parameter_from_message(message: str) -> str | None:
    normalized_message = message.lower()
    for parameter in normalization_service.predefined_parameters():
        if parameter.lower() in normalized_message:
            return parameter
        for alias in normalization_service.aliases().get(parameter, []):
            if alias.lower() in normalized_message:
                return parameter
    return None


def _find_evidence_line(raw_text: str, parameter: str | None) -> str | None:
    if not parameter:
        return None
    aliases = [parameter, *normalization_service.aliases().get(parameter, [])]
    for line in raw_text.splitlines():
        lowered = line.lower()
        if any(alias.lower() in lowered for alias in aliases):
            return line.strip()
    return None


def _parse_action_parameter(message: str, verbs: list[str]) -> str | None:
    for verb in verbs:
        pattern = re.compile(rf'{verb}\s+([a-zA-Z\s]+)')
        match = pattern.search(message.lower())
        if match:
            candidate = match.group(1).strip(' .')
            return candidate.split(' and ')[0].strip()
    return None


def _parse_only_extract(message: str) -> list[str]:
    lowered = message.lower()
    if 'only extract' not in lowered:
        return []
    segment = lowered.split('only extract', 1)[1]
    segment = segment.split('.', 1)[0]
    parts = [p.strip() for p in re.split(r',|and', segment) if p.strip()]
    return parts


def _reindex_items(items: list[dict[str, Any]], doc_type: DocumentType) -> list[dict[str, Any]]:
    id_key = 'rule_id' if doc_type == DocumentType.SOP else 'observation_id'
    prefix = 'R' if doc_type == DocumentType.SOP else 'O'
    for index, item in enumerate(items, start=1):
        item[id_key] = f'{prefix}{index}'
    return items
