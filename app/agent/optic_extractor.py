"""Targeted optic-section discovery without an LLM tree traversal.

The old agent walked every branch of a large document looking for optics.  This
module instead starts from the optic categories that the parsed linecards
actually request and finds those category headings in the document tree.
"""

import json
import os
import re
from collections.abc import Iterable

from app.utils.tree import TreeExplorer


def _canonical_name(value: str) -> str:
    """Normalize harmless spelling differences in optic category headings."""
    value = value.lower().replace("optical modules", "optical module")
    value = re.sub(r"[^a-z0-9+]", "", value)
    return value


def collect_supported_optics(
    linecards_dir: str = "app/database/linecards",
    model_names: Iterable[str] | None = None,
) -> list[str]:
    """Return distinct ``supported_optics`` values from valid linecard files.

    ``model_names`` scopes the collection to linecards produced in the current
    upload, avoiding stale files from a previous document.  Leaving it as None
    is useful for an existing on-disk linecard batch.
    """
    if not os.path.isdir(linecards_dir):
        return []

    expected_files = None
    if model_names is not None:
        expected_files = {f"{model_name}.json" for model_name in model_names}

    names = set()
    for filename in os.listdir(linecards_dir):
        if not filename.endswith(".json") or filename in {"linecard_nodes.json"}:
            continue
        if expected_files is not None and filename not in expected_files:
            continue
        try:
            with open(os.path.join(linecards_dir, filename), "r", encoding="utf-8") as file:
                linecard = json.load(file)
        except (OSError, json.JSONDecodeError):
            continue

        for config in linecard.get("port_configuration", {}).values():
            for optic_name in config.get("supported_optics", []):
                if isinstance(optic_name, str) and optic_name.strip():
                    names.add(optic_name.strip())
    return sorted(names)


def _matching_nodes(explorer: TreeExplorer, optic_name: str) -> list[dict]:
    """Find body nodes whose title is the requested optic category.

    The structure can contain a table of contents and a document body with the
    same heading.  The body occurrence has the later page number, so retain
    only candidates at the latest start page for an exact category match.
    """
    wanted = _canonical_name(optic_name)
    exact_candidates = []
    contains_candidates = []
    for node in explorer.id_map.values():
        title = node.get("title")
        if not isinstance(title, str):
            continue
        if node.get("start_index") is None or node.get("end_index") is None:
            continue
        canonical_title = _canonical_name(title)
        if canonical_title == wanted:
            exact_candidates.append(node)
        elif wanted in canonical_title:
            # This handles an intentionally broad linecard category such as
            # "CWDM Optical Module", whose document headings are speed/form
            # factor-specific. It remains a literal heading match, not fuzzy
            # similarity matching.
            contains_candidates.append(node)

    candidates = exact_candidates or contains_candidates
    if not candidates:
        return []
    # Keep the later (body) occurrence of each heading. A generic target can
    # legitimately match several different headings, e.g. 1.25G and 10G CWDM.
    latest_by_title = {}
    for node in candidates:
        title = _canonical_name(node["title"])
        previous = latest_by_title.get(title)
        if previous is None or node["start_index"] > previous["start_index"]:
            latest_by_title[title] = node
    return list(latest_by_title.values())


def find_optic_targets(json_path: str, supported_optics: Iterable[str]) -> list[dict[str, str]]:
    """Map requested optic categories to their smallest relevant PDF sections.

    A target holds the original linecard category, rather than the tree title,
    so downstream cross-checking continues to use the linecard's terminology.
    Names without an exact tree heading are deliberately skipped: broad fuzzy
    matching would select unrelated optic families and reintroduce false data.
    """
    explorer = TreeExplorer(json_path)
    targets = []
    seen = set()
    for optic_name in sorted(set(supported_optics)):
        for node in _matching_nodes(explorer, optic_name):
            target = (node["node_id"], optic_name)
            if target not in seen:
                seen.add(target)
                targets.append({"node_id": node["node_id"], "supported_optic": optic_name})
    return targets
