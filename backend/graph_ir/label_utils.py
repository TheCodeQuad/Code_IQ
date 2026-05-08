import re
from typing import Optional
from backend.graph_ir.models import IRStatement, StatementType


def _tokenize_label(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    # Keep parenthetical and bracketed chunks intact so semantic fragments stay together.
    return re.findall(r"\[[^\]]+\]|\([^\)]+\)|[^\s]+", normalized)


def _wrap_tokens(tokens: list[str], max_chars: int) -> list[str]:
    lines: list[str] = []
    current_line = ""

    for token in tokens:
        if not current_line:
            current_line = token
            continue

        candidate = f"{current_line} {token}"
        if len(candidate) <= max_chars:
            current_line = candidate
        else:
            lines.append(current_line)
            current_line = token

    if current_line:
        lines.append(current_line)

    return lines


def _append_line_suffix(label: str, line: Optional[int]) -> str:
    if not line:
        return label
    suffix = f"[L{line}]"
    if label.endswith(suffix):
        return label
    return f"{label} {suffix}" if label else suffix


def _finalize_label(label: str, line: Optional[int], wrap: bool) -> str:
    with_line = _append_line_suffix(label, line)
    return wrap_semantic_label(with_line) if wrap else with_line


def wrap_semantic_label(text: str, max_lines: int = 3) -> str:
    """Insert manual line breaks into a semantic label without splitting words."""
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return ""

    if "\n" in text:
        return "\n".join(part.strip() for part in text.splitlines() if part.strip())

    tokens = _tokenize_label(normalized)
    if not tokens:
        return normalized

    # Search for a width that yields 2-3 balanced lines when possible.
    best_lines: list[str] = [normalized]
    best_score: tuple[int, int, int] = (99, 99, 99)

    for max_chars in range(16, 25):
        lines = _wrap_tokens(tokens, max_chars)

        while len(lines) > max_lines:
            best_pair_index = 0
            best_pair_score = 10**9
            for index in range(len(lines) - 1):
                pair_score = len(lines[index]) + len(lines[index + 1])
                if pair_score < best_pair_score:
                    best_pair_score = pair_score
                    best_pair_index = index
            merged = f"{lines[best_pair_index]} {lines[best_pair_index + 1]}".strip()
            lines = lines[:best_pair_index] + [merged] + lines[best_pair_index + 2 :]

        line_count = len(lines)
        if line_count > max_lines:
            continue

        balance = max(len(line) for line in lines) - min(len(line) for line in lines) if line_count > 1 else 0
        score = (abs(line_count - 2), balance, max_chars)
        if score < best_score:
            best_score = score
            best_lines = lines

    if len(best_lines) == 1 and len(tokens) > 1:
        best_lines = _wrap_tokens(tokens, 18)

    return "\n".join(best_lines)


def format_semantic_label(text: str, max_lines: int = 3) -> str:
    """Public wrapper for semantic label formatting used across graph builders."""
    return wrap_semantic_label(text, max_lines=max_lines)


def get_semantic_label(stmt: IRStatement, mode: str = "compact", wrap: bool = True) -> str:
    """
    Generate a clean semantic action-based label for a statement.
    Format: <Action Verb> + <Meaningful Object>
    Line numbers are NOT included in the title (moved to metadata).
    """
    code = (stmt.code or "").strip()
    clean_code = code.rstrip(';')
    
    # 1. Security-sensitive functions
    if "strcpy" in clean_code:
        label = "Unsafe buffer copy (strcpy)"
        return _finalize_label(label, stmt.line, wrap)
    if "gets" in clean_code:
        label = "Unsafe input function (gets)"
        return _finalize_label(label, stmt.line, wrap)
    if "sprintf" in clean_code:
        label = "Unsafe formatted write"
        return _finalize_label(label, stmt.line, wrap)
    if "memcpy" in clean_code:
        label = "Memory copy operation"
        return _finalize_label(label, stmt.line, wrap)
        
    # 2. Returns
    if stmt.type == StatementType.RETURN:
        rest = clean_code[len("return"):].strip()
        if rest in ("0", "NULL", "true", "0;"):
            label = "Return success"
        elif rest:
            label = f"Return {rest}" if mode == "verbose" else "Return value"
        else:
            label = "Return"
        return _finalize_label(label, stmt.line, wrap)
        
    # 3. Conditions & Loops
    if stmt.type == StatementType.IF:
        cond = stmt.condition
        if not cond and clean_code.startswith("if"):
            cond = clean_code[2:].strip()
        if not cond:
            cond = "..."
        # Strip parentheses if present
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1].strip()
        label = f"Condition: {cond}"
        return _finalize_label(label, stmt.line, wrap)
        
    if stmt.type == StatementType.WHILE:
        cond = stmt.condition
        if not cond and clean_code.startswith("while"):
            cond = clean_code[5:].strip()
        if not cond:
            cond = "..."
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1].strip()
        label = f"Loop condition: {cond}"
        return _finalize_label(label, stmt.line, wrap)
        
    if stmt.type == StatementType.FOR:
        cond = stmt.condition
        if not cond and clean_code.startswith("for"):
            cond = clean_code[3:].strip()
        if not cond:
            cond = "..."
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1].strip()
            
        # Try to parse "item in items"
        match = re.match(r'^(\w+)\s+in\s+(.+)$', cond)
        if match:
            label = f"Iterate {match.group(2)}"
            return _finalize_label(label, stmt.line, wrap)
        label = f"Iterate over {cond}"
        return _finalize_label(label, stmt.line, wrap)
        
    # 4. Break / Continue
    if stmt.type == StatementType.BREAK:
        label = "Exit loop"
        return _finalize_label(label, stmt.line, wrap)
    if stmt.type == StatementType.CONTINUE:
        label = "Continue loop"
        return _finalize_label(label, stmt.line, wrap)
        
    # 5. Context Managers (With)
    if clean_code.startswith("with "):
        if "open(" in clean_code:
            label = "Open file"
        else:
            label = "Enter context"
        return _finalize_label(label, stmt.line, wrap)
        
    # 6. Declarations & Assignments
    # char dest[5] -> Declare destination buffer
    match = re.match(r'^(?:char|int|float|double)\s+(\w+)\[\d+\]', clean_code)
    if match:
        label = f"Declare {match.group(1)} buffer"
        return _finalize_label(label, stmt.line, wrap)
        
    # char source[] = "..." -> Initialize source buffer
    match = re.match(r'^(?:char|int|float|double)\s+(\w+)\[\]\s*=', clean_code)
    if match:
        label = f"Initialize {match.group(1)} buffer"
        return _finalize_label(label, stmt.line, wrap)
        
    # trigger = 5 or int trigger = 5 -> Initialize trigger = 5
    match = re.match(r'^(?:(?:char|int|float|double)\s+)?(\w+)\s*=\s*(.+)$', clean_code)
    if match:
        var_name = match.group(1)
        val = match.group(2)
        if val in ("[]", "list()"):
            label = f"Create {var_name} list"
            return _finalize_label(label, stmt.line, wrap)
        if val in ("{}", "dict()"):
            label = f"Create {var_name} dict"
            return _finalize_label(label, stmt.line, wrap)
        if mode == "verbose":
            label = f"Initialize {var_name} = {val}"
        else:
            label = f"Initialize {var_name}"
        return _finalize_label(label, stmt.line, wrap)

    if stmt.type == StatementType.ASSIGNMENT:
        defs = [v.name for v in stmt.definitions]
        if defs:
            label = f"Assign {defs[0]}"
        else:
            label = "Assignment"
        return _finalize_label(label, stmt.line, wrap)

    # 7. Calls
    if stmt.type == StatementType.CALL:
        if stmt.calls:
            call = stmt.calls[0]
            if "append" in call.name:
                label = "Append item"
                return _finalize_label(label, stmt.line, wrap)
            if call.receiver:
                label = f"Call {call.receiver}.{call.name}"
            else:
                label = f"Call {call.name}"
            return _finalize_label(label, stmt.line, wrap)
        label = "Call"
        return _finalize_label(label, stmt.line, wrap)

    if stmt.type == StatementType.EXPRESSION:
        label = clean_code[:30] if clean_code else "Expression"
        return _finalize_label(label, stmt.line, wrap)

    if stmt.type == StatementType.PASS:
        label = "Pass"
        return _finalize_label(label, stmt.line, wrap)

    # Default fallback
    label = stmt.type.value.replace("_", " ").capitalize()
    return _finalize_label(label, stmt.line, wrap)
