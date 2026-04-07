from __future__ import annotations

import json


def parse_json_content(raw_content: str | dict) -> dict | None:
    if isinstance(raw_content, dict):
        return raw_content
    if not isinstance(raw_content, str):
        return None

    text = raw_content.strip()
    if not text:
        return None

    candidates = [text]

    stripped_fences = text.replace("```json", "```").replace("```JSON", "```")
    if "```" in stripped_fences:
        fenced_parts = [part.strip() for part in stripped_fences.split("```") if part.strip()]
        candidates.extend(fenced_parts)

    object_candidate = _extract_first_json_object(text)
    if object_candidate is not None:
        candidates.append(object_candidate)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            parsed = json.loads(normalized)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None
