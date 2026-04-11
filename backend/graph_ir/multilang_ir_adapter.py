"""Multi-language statement-level IR adapter.

Navigator already extracts multi-language *components* (functions/classes/methods)
using tree-sitter. The CFG/PDG/HPG builders in `backend.graph_ir` require a
statement-level IR (`FunctionIR` containing ordered `IRStatement`s with def/use
info).

This module provides a best-effort adapter that converts a Navigator
`CodeComponent` into a `FunctionIR` by:
- using the component snippet + source location
- extracting coarse-grained statements from the snippet
- approximating definitions/uses/calls

Notes / limitations
- This is intentionally conservative and heuristic-based.
- It will not be as precise as a full language-specific CFG/PDG implementation.
- It is good enough to visualize control constructs + basic data-flow edges.
"""

from __future__ import annotations

from dataclasses import asdict
import re
from typing import List, Optional, Sequence, Tuple

from backend.models.code_component import CodeComponent

from .models import (
    FunctionIR,
    ParameterInfo,
    IRStatement,
    StatementType,
    Variable,
    FunctionCall,
    ComponentType,
)


_JS_LIKE_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "return",
    "try",
    "catch",
    "finally",
    "throw",
    "new",
    "class",
    "function",
    "const",
    "let",
    "var",
    "import",
    "from",
    "export",
    "extends",
    "this",
    "super",
    "true",
    "false",
    "null",
    "undefined",
}

_JAVA_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "return",
    "try",
    "catch",
    "finally",
    "throw",
    "new",
    "class",
    "interface",
    "enum",
    "extends",
    "implements",
    "this",
    "super",
    "true",
    "false",
    "null",
    "public",
    "private",
    "protected",
    "static",
    "final",
    "void",
    "int",
    "long",
    "double",
    "float",
    "boolean",
    "char",
    "byte",
    "short",
    "String",
}


def _strip_strings_and_comments(line: str) -> str:
    # Remove // comments
    line = re.sub(r"//.*$", "", line)
    # Remove /* */ on same line
    line = re.sub(r"/\*.*?\*/", "", line)
    # Remove single/double quoted strings (simple)
    line = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", line)
    line = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', line)
    return line


def _extract_paren_condition(text: str) -> Optional[str]:
    # Extract condition inside first balanced (...)
    start = text.find("(")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i].strip() or None
    return None


def _find_block_end_line(lines: Sequence[str], start_idx_1based: int) -> int:
    """Find matching brace end line for a block starting at/after start_idx.

    Returns 1-based end line index relative to `lines`.
    If no brace block is found, returns start_idx.
    """
    i0 = max(start_idx_1based - 1, 0)
    depth = 0
    started = False
    for j in range(i0, len(lines)):
        cleaned = _strip_strings_and_comments(lines[j])
        for ch in cleaned:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                if started:
                    depth -= 1
                    if depth <= 0:
                        return j + 1
    return start_idx_1based


def _identifier_tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", text)


def _make_var(name: str, line: int, is_def: bool = False, is_use: bool = False) -> Variable:
    return Variable(name=name, line=line, is_definition=is_def, is_use=is_use)


def _parse_call(text: str, line: int) -> Optional[FunctionCall]:
    # crude: capture receiver.name or name
    m = re.search(r"([A-Za-z_$][A-Za-z0-9_$]*)(?:\.([A-Za-z_$][A-Za-z0-9_$]*))?\s*\(", text)
    if not m:
        return None
    head = m.group(1)
    tail = m.group(2)
    if tail:
        return FunctionCall(name=tail, receiver=head, line=line, is_method=True)
    return FunctionCall(name=head, line=line)


def extract_statements_from_snippet(
    snippet: str,
    language: str,
    start_line: int,
) -> List[IRStatement]:
    """Extract a coarse list of IRStatements from a function snippet."""
    lines = snippet.splitlines()
    stmts: List[IRStatement] = []

    keywords = _JS_LIKE_KEYWORDS if language in {"javascript", "typescript"} else _JAVA_KEYWORDS

    # Skip leading signature line if it looks like a function header.
    signature_skip = False
    if lines:
        first = lines[0].strip()
        if language in {"javascript", "typescript"} and ("function" in first or first.endswith("{") or first.startswith("(")):
            signature_skip = True
        if language == "java" and (first.endswith("{") or re.search(r"\)\s*\{\s*$", first)):
            signature_skip = True

    for idx, raw in enumerate(lines, start=1):
        if signature_skip and idx == 1:
            continue

        stripped = raw.strip()
        if not stripped:
            continue

        abs_line = start_line + idx - 1
        cleaned = _strip_strings_and_comments(stripped).strip()
        if not cleaned:
            continue

        # Normalize common patterns like "} else {" so we can detect else blocks.
        normalized = cleaned
        if normalized.startswith("}"):
            normalized = normalized.lstrip("}").strip()

        # Ignore lines that are only structural delimiters.
        # Example: "}", "{", "};", "}," etc.
        if re.fullmatch(r"[{}();,]+", cleaned):
            continue

        stype = StatementType.EXPRESSION
        condition: Optional[str] = None
        end_line: Optional[int] = None

        # Control constructs
        if re.match(r"^if\b", normalized):
            stype = StatementType.IF
            condition = _extract_paren_condition(normalized)
            end_rel = _find_block_end_line(lines, idx)
            end_line = start_line + end_rel - 1
        elif re.match(r"^else\b", normalized):
            stype = StatementType.ELSE
            end_rel = _find_block_end_line(lines, idx)
            end_line = start_line + end_rel - 1
        elif re.match(r"^for\b", normalized):
            stype = StatementType.FOR
            condition = _extract_paren_condition(normalized)
            end_rel = _find_block_end_line(lines, idx)
            end_line = start_line + end_rel - 1
        elif re.match(r"^while\b", normalized):
            stype = StatementType.WHILE
            condition = _extract_paren_condition(normalized)
            end_rel = _find_block_end_line(lines, idx)
            end_line = start_line + end_rel - 1
        elif re.match(r"^try\b", normalized):
            stype = StatementType.TRY
            end_rel = _find_block_end_line(lines, idx)
            end_line = start_line + end_rel - 1
        elif re.match(r"^(catch|except)\b", normalized):
            stype = StatementType.EXCEPT
        elif re.match(r"^finally\b", normalized):
            stype = StatementType.FINALLY
        elif re.match(r"^return\b", normalized):
            stype = StatementType.RETURN
        elif re.match(r"^break\b", normalized):
            stype = StatementType.BREAK
        elif re.match(r"^continue\b", normalized):
            stype = StatementType.CONTINUE
        elif re.match(r"^(throw|raise)\b", normalized):
            stype = StatementType.RAISE

        # Data-ish statements
        definitions: List[Variable] = []
        uses: List[Variable] = []
        calls: List[FunctionCall] = []

        # Assignment heuristics (exclude ==, <=, etc.)
        if stype == StatementType.EXPRESSION:
            has_assign = "=" in normalized and not re.search(r"==|!=|<=|>=|===|!==", normalized)
            if has_assign:
                # JS: (const|let|var)? name = ...
                m = re.match(r"^(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", normalized)
                if not m:
                    # plain assignment or field assignment
                    m = re.match(r"^([A-Za-z_$][A-Za-z0-9_$.]*)\s*=", normalized)
                if not m and language == "java":
                    # Java: Type name = ...
                    m = re.match(r"^[A-Za-z_$][A-Za-z0-9_$.<>\[\]]*\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", normalized)

                if m:
                    stype = StatementType.ASSIGNMENT
                    lhs = m.group(1)
                    definitions.append(_make_var(lhs, abs_line, is_def=True))

                    rhs = normalized.split("=", 1)[1]
                    for tok in _identifier_tokens(rhs):
                        if tok in keywords:
                            continue
                        if tok == lhs:
                            continue
                        uses.append(_make_var(tok, abs_line, is_use=True))

        # Call heuristics
        if stype in (StatementType.EXPRESSION, StatementType.ASSIGNMENT) and re.search(r"\w\s*\(", normalized):
            call = _parse_call(normalized, abs_line)
            if call:
                calls.append(call)
                # Mark as CALL if it's not already a control/return.
                if stype == StatementType.EXPRESSION:
                    stype = StatementType.CALL

        # If/for/while conditions contribute uses
        if stype in (StatementType.IF, StatementType.FOR, StatementType.WHILE) and condition:
            for tok in _identifier_tokens(condition):
                if tok in keywords:
                    continue
                uses.append(_make_var(tok, abs_line, is_use=True))

        # Return expressions contribute uses
        if stype == StatementType.RETURN:
            rest = normalized[len("return"):]
            for tok in _identifier_tokens(rest):
                if tok in keywords:
                    continue
                uses.append(_make_var(tok, abs_line, is_use=True))

        stmt = IRStatement(
            id=f"stmt_{abs_line}_{len(stmts) + 1}",
            type=stype,
            line=abs_line,
            end_line=end_line,
            code=stripped,
            definitions=definitions,
            uses=uses,
            condition=condition,
            calls=calls,
        )
        stmts.append(stmt)

    return stmts


def _coerce_parameters(comp: CodeComponent) -> List[ParameterInfo]:
    params = getattr(comp, "parameters", None) or []
    out: List[ParameterInfo] = []

    for p in params:
        if isinstance(p, dict):
            out.append(ParameterInfo(
                name=str(p.get("name")),
                annotation=p.get("type_hint"),
                default=p.get("default_value"),
                is_args=False,
                is_kwargs=False,
            ))
            continue

        # dataclass Parameter
        try:
            d = asdict(p)
            out.append(ParameterInfo(
                name=str(d.get("name")),
                annotation=d.get("type_hint"),
                default=d.get("default_value"),
                is_args=False,
                is_kwargs=False,
            ))
        except Exception:
            # fallback
            name = getattr(p, "name", None)
            if name:
                out.append(ParameterInfo(name=str(name)))

    return out


def function_ir_from_code_component(comp: CodeComponent) -> FunctionIR:
    """Convert a Navigator CodeComponent into a graph-ir FunctionIR."""

    lang = (getattr(comp, "language", "python") or "python").lower()

    raw_type = getattr(comp.type, "value", comp.type)
    if raw_type in ("method", "constructor"):
        ctype = ComponentType.METHOD
        parent_class = str(comp.id).split(".")[-2] if "." in str(comp.id) else None
    else:
        ctype = ComponentType.FUNCTION
        parent_class = None

    start_line = comp.location.start_line
    end_line = comp.location.end_line

    statements = extract_statements_from_snippet(
        comp.source_code or "",
        language=lang,
        start_line=start_line,
    )

    local_vars = sorted({v.name for s in statements for v in s.definitions if v.name and "." not in v.name})

    return FunctionIR(
        id=str(comp.id),
        name=str(comp.name),
        qualified_name=str(comp.id),
        type=ctype,
        file_path=str(comp.location.file_path),
        start_line=start_line,
        end_line=end_line,
        parameters=_coerce_parameters(comp),
        return_annotation=getattr(comp, "return_type", None),
        decorators=getattr(comp, "decorators", []) or [],
        docstring=getattr(comp, "existing_docstring", None),
        statements=statements,
        parent_class=parent_class,
        calls=[],
        local_variables=local_vars,
        global_variables=[],
        closure_variables=[],
    )
