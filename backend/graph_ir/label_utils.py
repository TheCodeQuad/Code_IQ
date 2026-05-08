import re
from typing import Optional
from backend.graph_ir.models import IRStatement, StatementType

def get_semantic_label(stmt: IRStatement, mode: str = "compact") -> str:
    """
    Generate a clean semantic action-based label for a statement.
    Format: <Action Verb> + <Meaningful Object>
    Line numbers are NOT included in the title (moved to metadata).
    """
    code = (stmt.code or "").strip()
    clean_code = code.rstrip(';')
    
    # 1. Security-sensitive functions
    if "strcpy" in clean_code:
        return "Unsafe buffer copy (strcpy)"
    if "gets" in clean_code:
        return "Unsafe input function (gets)"
    if "sprintf" in clean_code:
        return "Unsafe formatted write"
    if "memcpy" in clean_code:
        return "Memory copy operation"
        
    # 2. Returns
    if stmt.type == StatementType.RETURN:
        rest = clean_code[len("return"):].strip()
        if rest in ("0", "NULL", "true", "0;"):
            return "Return success"
        elif rest:
            return f"Return {rest}" if mode == "verbose" else "Return value"
        return "Return"
        
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
        return f"Check if {cond}"
        
    if stmt.type == StatementType.WHILE:
        cond = stmt.condition
        if not cond and clean_code.startswith("while"):
            cond = clean_code[5:].strip()
        if not cond:
            cond = "..."
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1].strip()
        return f"Loop while {cond}"
        
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
            return f"Iterate {match.group(2)}"
        return f"Iterate over {cond}"
        
    # 4. Break / Continue
    if stmt.type == StatementType.BREAK:
        return "Exit loop"
    if stmt.type == StatementType.CONTINUE:
        return "Continue loop"
        
    # 5. Context Managers (With)
    if clean_code.startswith("with "):
        if "open(" in clean_code:
            return "Open file"
        return "Enter context"
        
    # 6. Declarations & Assignments
    # char dest[5] -> Declare destination buffer
    match = re.match(r'^(?:char|int|float|double)\s+(\w+)\[\d+\]', clean_code)
    if match:
        return f"Declare {match.group(1)} buffer"
        
    # char source[] = "..." -> Initialize source buffer
    match = re.match(r'^(?:char|int|float|double)\s+(\w+)\[\]\s*=', clean_code)
    if match:
        return f"Initialize {match.group(1)} buffer"
        
    # trigger = 5 or int trigger = 5 -> Initialize trigger = 5
    match = re.match(r'^(?:(?:char|int|float|double)\s+)?(\w+)\s*=\s*(.+)$', clean_code)
    if match:
        var_name = match.group(1)
        val = match.group(2)
        if val in ("[]", "list()"):
            return f"Create {var_name} list"
        if val in ("{}", "dict()"):
            return f"Create {var_name} dict"
        if mode == "verbose":
            return f"Initialize {var_name} = {val}"
        return f"Initialize {var_name}"

    if stmt.type == StatementType.ASSIGNMENT:
        defs = [v.name for v in stmt.definitions]
        if defs:
            return f"Assign {defs[0]}"
        return "Assignment"

    # 7. Calls
    if stmt.type == StatementType.CALL:
        if stmt.calls:
            call = stmt.calls[0]
            if "append" in call.name:
                return "Append item"
            if call.receiver:
                return f"Call {call.receiver}.{call.name}"
            return f"Call {call.name}"
        return "Call"

    if stmt.type == StatementType.EXPRESSION:
        return clean_code[:30] if clean_code else "Expression"

    if stmt.type == StatementType.PASS:
        return "Pass"

    # Default fallback
    return stmt.type.value.replace("_", " ").capitalize()
