import logging
from typing import Optional

from reqradar.agent.steps import _COMMON_SYNONYMS

logger = logging.getLogger("reqradar.synonym_resolver")


class SynonymResolver:
    HARD_CODED_SYNONYMS: dict[str, list[str]] = {}

    def __init__(self):
        if not self.HARD_CODED_SYNONYMS:
            self.HARD_CODED_SYNONYMS = dict(_COMMON_SYNONYMS) if _COMMON_SYNONYMS else {}

    def resolve(
        self,
        keywords: list[str],
        project_mappings: list[dict],
        global_mappings: list[dict],
    ) -> list[str]:
        result_set = set()
        seen_terms = set()

        project_by_term: dict[str, list[dict]] = {}
        for m in project_mappings:
            term = m["business_term"]
            project_by_term.setdefault(term, []).append(m)

        global_by_term: dict[str, list[dict]] = {}
        for m in global_mappings:
            term = m["business_term"]
            global_by_term.setdefault(term, []).append(m)

        for keyword in keywords:
            expanded = self._expand_term(keyword, project_by_term, global_by_term)
            result_set.update(expanded)
            result_set.add(keyword)
            seen_terms.add(keyword)

        return list(result_set)

    def _expand_term(
        self,
        term: str,
        project_by_term: dict[str, list[dict]],
        global_by_term: dict[str, list[dict]],
    ) -> list[str]:
        results = []
        project_entries = project_by_term.get(term, [])
        global_entries = global_by_term.get(term, [])

        if project_entries or global_entries:
            all_entries = list(project_entries)
            seen_project_terms = set()
            for entry in project_entries:
                for ct in entry.get("code_terms", []):
                    if isinstance(ct, str):
                        seen_project_terms.add(ct)

            for entry in global_entries:
                if entry.get("business_term") not in project_by_term:
                    all_entries.append(entry)

            sorted_entries = sorted(all_entries, key=lambda e: e.get("priority", 100))
            for entry in sorted_entries:
                for ct in entry.get("code_terms", []):
                    if isinstance(ct, str) and ct not in results:
                        results.append(ct)
        else:
            hard_coded = self.HARD_CODED_SYNONYMS.get(term, [])
            results.extend(hard_coded)

        return results

    def expand_keywords_with_synonyms(
        self,
        keywords: list[str],
        project_mappings: list[dict] | None = None,
        global_mappings: list[dict] | None = None,
    ) -> tuple[list[str], dict[str, list[str]]]:
        project_mappings = project_mappings or []
        global_mappings = global_mappings or []

        expanded = self.resolve(keywords, project_mappings, global_mappings)
        mapping_log = {}

        for keyword in keywords:
            expanded_for_term = self._expand_term(
                keyword,
                {m["business_term"]: [m] for m in project_mappings if m["business_term"] == keyword},
                {m["business_term"]: [m] for m in global_mappings if m["business_term"] == keyword},
            )
            if expanded_for_term:
                mapping_log[keyword] = expanded_for_term

        return expanded, mapping_log
