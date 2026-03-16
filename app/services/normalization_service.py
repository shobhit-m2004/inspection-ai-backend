from __future__ import annotations

from rapidfuzz import fuzz


DEFAULT_ALIAS_MAP: dict[str, list[str]] = {
    'temperature': ['temperature', 'temp', 'product temp', 'mix temp', 'room temp'],
    'viscosity': ['viscosity', 'visc'],
    'pH': ['ph', 'pH', 'acidity'],
    'rpm': ['rpm', 'agitator speed', 'stirrer speed', 'mixing speed'],
    'pressure': ['pressure', 'bar', 'psi'],
    'line clearance': ['line clearance', 'clearance', 'area clearance'],
    'supervisor signature': ['supervisor sign', 'approved by supervisor', 'supervisor initials'],
    'time': ['time', 'minutes', 'min', 'hours', 'hr'],
    'quantity': ['quantity', 'qty', 'amount'],
}


class NormalizationService:
    def __init__(self, alias_map: dict[str, list[str]] | None = None):
        self.alias_map = alias_map or DEFAULT_ALIAS_MAP
        self._reverse_alias: dict[str, str] = {}
        for canonical, aliases in self.alias_map.items():
            self._reverse_alias[canonical.lower()] = canonical
            for alias in aliases:
                self._reverse_alias[alias.lower()] = canonical

    def predefined_parameters(self) -> list[str]:
        return sorted(self.alias_map.keys())

    def aliases(self) -> dict[str, list[str]]:
        return self.alias_map

    def normalize_parameter(self, term: str | None) -> str | None:
        if not term:
            return None

        normalized = term.strip().lower()
        if normalized in self._reverse_alias:
            return self._reverse_alias[normalized]

        best_param = None
        best_score = 0
        for alias, canonical in self._reverse_alias.items():
            score = fuzz.ratio(normalized, alias)
            if score > best_score:
                best_score = score
                best_param = canonical

        if best_param and best_score >= 85:
            return best_param
        return term.strip()

    def normalize_selected_parameters(self, selected: list[str] | None) -> list[str]:
        if not selected:
            return []

        output: list[str] = []
        for item in selected:
            canonical = self.normalize_parameter(item)
            if canonical and canonical not in output:
                output.append(canonical)
        return output

    def match_parameter_tokens(self, text: str) -> tuple[str | None, list[str]]:
        lowered = text.lower()
        hits: list[tuple[str, str]] = []
        for canonical, aliases in self.alias_map.items():
            all_terms = [canonical, *aliases]
            for alias in all_terms:
                if alias.lower() in lowered:
                    hits.append((canonical, alias))

        if not hits:
            return None, []

        canonical = hits[0][0]
        aliases = sorted({alias for param, alias in hits if param == canonical})
        return canonical, aliases

    def is_in_selected(self, parameter: str | None, selected: list[str]) -> bool:
        if not selected:
            return True
        if not parameter:
            return False
        canonical = self.normalize_parameter(parameter)
        return canonical in selected


normalization_service = NormalizationService()
