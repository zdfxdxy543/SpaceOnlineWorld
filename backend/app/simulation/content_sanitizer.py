from __future__ import annotations

import re


PROMPT_LINE_PATTERNS = [
    re.compile(r"^生成一个.+", re.IGNORECASE),
    re.compile(r"^请生成.+", re.IGNORECASE),
    re.compile(r"^请写一个.+", re.IGNORECASE),
    re.compile(r"^你是.+", re.IGNORECASE),
    re.compile(r"^你需要.+", re.IGNORECASE),
    re.compile(r"^请扮演.+", re.IGNORECASE),
    re.compile(r"^输出(json|JSON).*$"),
    re.compile(r"^返回(json|JSON).*$"),
    re.compile(r"^不要输出.+", re.IGNORECASE),
    re.compile(r"^只输出.+", re.IGNORECASE),
    re.compile(r"^根据以上.+", re.IGNORECASE),
    re.compile(r"^基于以上.+", re.IGNORECASE),
    re.compile(r"^下面是.+提示词.*$", re.IGNORECASE),
]


def sanitize_forum_title(title: str) -> str:
    cleaned = _sanitize_text(title, allow_multiline=False)
    if cleaned:
        return cleaned[:120]
    return "论坛记录"


def sanitize_forum_content(content: str) -> str:
    cleaned = _sanitize_text(content, allow_multiline=True)
    if cleaned:
        return cleaned[:4000]
    return "今天整理了一些信息，先把已经确认的内容记录在这里。"


def _sanitize_text(text: str, *, allow_multiline: bool) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    normalized = normalized.replace("```json", "").replace("```", "")

    lines = [line.strip() for line in normalized.split("\n")]
    kept_lines: list[str] = []
    for line in lines:
        if not line:
            if allow_multiline and kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        if _looks_like_prompt_instruction(line):
            continue
        kept_lines.append(line)

    result = "\n".join(kept_lines).strip() if allow_multiline else " ".join(kept_lines).strip()
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip(" :-")


def _looks_like_prompt_instruction(line: str) -> bool:
    return any(pattern.match(line) for pattern in PROMPT_LINE_PATTERNS)
