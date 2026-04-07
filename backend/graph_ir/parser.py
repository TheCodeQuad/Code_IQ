"""
AST Parser for Python Code

This module parses Python source files using the ast module and builds
the Intermediate Representation (IR) for further analysis.
"""

import ast
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

from .models import (
    IRStatement, StatementType, Variable, FunctionCall, Import,
    ParameterInfo, FunctionIR, ClassIR, ModuleIR, RepositoryIR,
    ComponentType, SourceLocation
)


def generate_id(prefix: str, *parts: str) -> str:
    """Generate a unique ID from parts"""
    content = ":".join(str(p) for p in parts)
    hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{prefix}_{hash_val}"


class VariableVisitor(ast.NodeVisitor):
    """Extracts variable definitions and uses from an AST node"""

    def __init__(self):
        self.definitions: List[Variable] = []
        self.uses: List[Variable] = []
        self._in_target = False

    def visit_Name(self, node: ast.Name):
        var = Variable(
            name=node.id,
            line=node.lineno,
            is_definition=isinstance(node.ctx, ast.Store),
            is_use=isinstance(node.ctx, (ast.Load, ast.Del))
        )
        if var.is_definition:
            self.definitions.append(var)
        if var.is_use:
            self.uses.append(var)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # For attribute access like self.x, record as use
        if isinstance(node.ctx, ast.Load):
            # Build full attribute path
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            full_name = ".".join(parts)
            self.uses.append(Variable(
                name=full_name,
                line=node.lineno,
                is_use=True
            ))
        elif isinstance(node.ctx, ast.Store):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            full_name = ".".join(parts)
            self.definitions.append(Variable(
                name=full_name,
                line=node.lineno,
                is_definition=True
            ))
        self.generic_visit(node)


class CallVisitor(ast.NodeVisitor):
    """Extracts function calls from an AST node"""

    def __init__(self):
        self.calls: List[FunctionCall] = []

    def visit_Call(self, node: ast.Call):
        call = self._extract_call(node)
        if call:
            self.calls.append(call)
        self.generic_visit(node)

    def _extract_call(self, node: ast.Call) -> Optional[FunctionCall]:
        func = node.func
        name = ""
        module = None
        receiver = None
        is_method = False

        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
            is_method = True
            # Get receiver
            if isinstance(func.value, ast.Name):
                receiver = func.value.id
            elif isinstance(func.value, ast.Attribute):
                # Chain like os.path.join
                parts = []
                current = func.value
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                parts.reverse()
                module = ".".join(parts)
                receiver = module
        else:
            return None

        # Extract argument names (simplified)
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                args.append(arg.id)
            elif isinstance(arg, ast.Constant):
                args.append(repr(arg.value)[:20])
            else:
                args.append("<expr>")

        kwargs = []
        for kw in node.keywords:
            if kw.arg:
                kwargs.append(kw.arg)

        return FunctionCall(
            name=name,
            module=module,
            args=args,
            kwargs=kwargs,
            line=node.lineno,
            is_method=is_method,
            receiver=receiver
        )


class StatementVisitor(ast.NodeVisitor):
    """Builds IRStatements from AST nodes"""

    def __init__(self, source_lines: List[str], file_path: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.statements: List[IRStatement] = []
        self._stmt_counter = 0

    def _next_id(self) -> str:
        self._stmt_counter += 1
        return f"stmt_{self._stmt_counter}"

    def _get_source(self, node: ast.AST) -> str:
        """Extract source code for a node"""
        try:
            start_line = node.lineno - 1
            end_line = getattr(node, 'end_lineno', node.lineno)
            if end_line is None:
                end_line = node.lineno
            lines = self.source_lines[start_line:end_line]
            return "\n".join(lines).strip()[:200]  # Limit length
        except Exception:
            return ""

    def _extract_vars(self, node: ast.AST) -> Tuple[List[Variable], List[Variable]]:
        """Extract variable definitions and uses from a node"""
        visitor = VariableVisitor()
        visitor.visit(node)
        return visitor.definitions, visitor.uses

    def _extract_calls(self, node: ast.AST) -> List[FunctionCall]:
        """Extract function calls from a node"""
        visitor = CallVisitor()
        visitor.visit(node)
        return visitor.calls

    def create_statement(
        self,
        node: ast.AST,
        stmt_type: StatementType,
        **kwargs
    ) -> IRStatement:
        """Create an IRStatement from an AST node"""
        defs, uses = self._extract_vars(node)
        calls = self._extract_calls(node)

        return IRStatement(
            id=self._next_id(),
            type=stmt_type,
            line=node.lineno,
            end_line=getattr(node, 'end_lineno', node.lineno),
            code=self._get_source(node),
            definitions=defs,
            uses=uses,
            calls=calls,
            **kwargs
        )

    def visit_Assign(self, node: ast.Assign) -> IRStatement:
        stmt = self.create_statement(node, StatementType.ASSIGNMENT)
        self.statements.append(stmt)
        return stmt

    def visit_AugAssign(self, node: ast.AugAssign) -> IRStatement:
        stmt = self.create_statement(node, StatementType.ASSIGNMENT)
        self.statements.append(stmt)
        return stmt

    def visit_AnnAssign(self, node: ast.AnnAssign) -> IRStatement:
        stmt = self.create_statement(node, StatementType.ASSIGNMENT)
        self.statements.append(stmt)
        return stmt

    def visit_Expr(self, node: ast.Expr) -> IRStatement:
        # Check if it's a call expression
        if isinstance(node.value, ast.Call):
            stmt = self.create_statement(node, StatementType.CALL)
        else:
            stmt = self.create_statement(node, StatementType.EXPRESSION)
        self.statements.append(stmt)
        return stmt

    def visit_Return(self, node: ast.Return) -> IRStatement:
        stmt = self.create_statement(node, StatementType.RETURN)
        self.statements.append(stmt)
        return stmt

    def visit_If(self, node: ast.If) -> IRStatement:
        condition = self._get_source(node.test) if node.test else ""
        stmt = self.create_statement(
            node,
            StatementType.IF,
            condition=condition,
            is_branch=True
        )
        self.statements.append(stmt)
        return stmt

    def visit_For(self, node: ast.For) -> IRStatement:
        target = ast.unparse(node.target) if hasattr(ast, 'unparse') else str(node.target)
        iter_expr = self._get_source(node.iter) if node.iter else ""
        condition = f"{target} in {iter_expr}"
        stmt = self.create_statement(
            node,
            StatementType.FOR,
            condition=condition,
            is_branch=True,
            is_loop_header=True
        )
        self.statements.append(stmt)
        return stmt

    def visit_While(self, node: ast.While) -> IRStatement:
        condition = self._get_source(node.test) if node.test else ""
        stmt = self.create_statement(
            node,
            StatementType.WHILE,
            condition=condition,
            is_branch=True,
            is_loop_header=True
        )
        self.statements.append(stmt)
        return stmt

    def visit_Try(self, node: ast.Try) -> IRStatement:
        stmt = self.create_statement(node, StatementType.TRY)
        self.statements.append(stmt)
        return stmt

    def visit_With(self, node: ast.With) -> IRStatement:
        stmt = self.create_statement(node, StatementType.WITH)
        self.statements.append(stmt)
        return stmt

    def visit_Raise(self, node: ast.Raise) -> IRStatement:
        stmt = self.create_statement(node, StatementType.RAISE)
        self.statements.append(stmt)
        return stmt

    def visit_Assert(self, node: ast.Assert) -> IRStatement:
        stmt = self.create_statement(node, StatementType.ASSERT)
        self.statements.append(stmt)
        return stmt

    def visit_Pass(self, node: ast.Pass) -> IRStatement:
        stmt = self.create_statement(node, StatementType.PASS)
        self.statements.append(stmt)
        return stmt

    def visit_Break(self, node: ast.Break) -> IRStatement:
        stmt = self.create_statement(node, StatementType.BREAK)
        self.statements.append(stmt)
        return stmt

    def visit_Continue(self, node: ast.Continue) -> IRStatement:
        stmt = self.create_statement(node, StatementType.CONTINUE)
        self.statements.append(stmt)
        return stmt

    def visit_Yield(self, node: ast.Yield) -> IRStatement:
        stmt = self.create_statement(node, StatementType.YIELD)
        self.statements.append(stmt)
        return stmt

    def visit_YieldFrom(self, node: ast.YieldFrom) -> IRStatement:
        stmt = self.create_statement(node, StatementType.YIELD)
        self.statements.append(stmt)
        return stmt

    def visit_Await(self, node: ast.Await) -> IRStatement:
        stmt = self.create_statement(node, StatementType.AWAIT)
        self.statements.append(stmt)
        return stmt


class FunctionVisitor(ast.NodeVisitor):
    """Extracts complete function IR including all statements"""

    def __init__(self, source_lines: List[str], file_path: str, module_name: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.module_name = module_name
        self.functions: Dict[str, FunctionIR] = {}
        self.current_class: Optional[str] = None

    def _get_docstring(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
        """Extract docstring from function"""
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value
        return None

    def _get_decorators(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extract decorator names"""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)
        return decorators

    def _get_parameters(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[ParameterInfo]:
        """Extract function parameters"""
        params = []
        args = node.args

        # Regular args
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            default = None
            if i >= defaults_offset:
                default_node = args.defaults[i - defaults_offset]
                if isinstance(default_node, ast.Constant):
                    default = repr(default_node.value)
                elif isinstance(default_node, ast.Name):
                    default = default_node.id

            annotation = None
            if arg.annotation:
                try:
                    annotation = ast.unparse(arg.annotation)
                except Exception:
                    pass

            params.append(ParameterInfo(
                name=arg.arg,
                annotation=annotation,
                default=default
            ))

        # *args
        if args.vararg:
            params.append(ParameterInfo(
                name=args.vararg.arg,
                is_args=True
            ))

        # **kwargs
        if args.kwarg:
            params.append(ParameterInfo(
                name=args.kwarg.arg,
                is_kwargs=True
            ))

        return params

    def _collect_statements(self, body: List[ast.stmt]) -> List[IRStatement]:
        """Recursively collect all statements from a function body"""
        statements = []

        def process_body(nodes: List[ast.stmt], depth: int = 0):
            visitor = StatementVisitor(self.source_lines, self.file_path)

            for idx, node in enumerate(nodes):
                # Skip docstring expression at the top of a function.
                # We already extract it separately into FunctionIR.docstring.
                if (
                    depth == 0
                    and idx == 0
                    and isinstance(node, ast.Expr)
                    and isinstance(getattr(node, "value", None), ast.Constant)
                    and isinstance(getattr(node.value, "value", None), str)
                ):
                    continue
                # Process the node
                if isinstance(node, ast.If):
                    stmt = visitor.visit_If(node)
                    statements.append(stmt)
                    # Process if body
                    process_body(node.body, depth + 1)
                    # Process else body
                    if node.orelse:
                        # Check if it's elif or else
                        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                            # It's an elif
                            process_body(node.orelse, depth)
                        else:
                            # It's else
                            else_stmt = IRStatement(
                                id=f"stmt_else_{node.lineno}",
                                type=StatementType.ELSE,
                                line=node.orelse[0].lineno if node.orelse else node.lineno,
                                code="else:",
                                definitions=[],
                                uses=[]
                            )
                            statements.append(else_stmt)
                            process_body(node.orelse, depth + 1)

                elif isinstance(node, ast.For):
                    stmt = visitor.visit_For(node)
                    statements.append(stmt)
                    process_body(node.body, depth + 1)
                    if node.orelse:
                        process_body(node.orelse, depth + 1)

                elif isinstance(node, ast.While):
                    stmt = visitor.visit_While(node)
                    statements.append(stmt)
                    process_body(node.body, depth + 1)
                    if node.orelse:
                        process_body(node.orelse, depth + 1)

                elif isinstance(node, ast.Try):
                    stmt = visitor.visit_Try(node)
                    statements.append(stmt)
                    process_body(node.body, depth + 1)
                    for handler in node.handlers:
                        except_stmt = IRStatement(
                            id=f"stmt_except_{handler.lineno}",
                            type=StatementType.EXCEPT,
                            line=handler.lineno,
                            code=f"except {handler.type.id if handler.type and isinstance(handler.type, ast.Name) else ''}:",
                            definitions=[Variable(name=handler.name, is_definition=True)] if handler.name else [],
                            uses=[]
                        )
                        statements.append(except_stmt)
                        process_body(handler.body, depth + 1)
                    if node.finalbody:
                        finally_stmt = IRStatement(
                            id=f"stmt_finally_{node.lineno}",
                            type=StatementType.FINALLY,
                            line=node.finalbody[0].lineno,
                            code="finally:",
                            definitions=[],
                            uses=[]
                        )
                        statements.append(finally_stmt)
                        process_body(node.finalbody, depth + 1)

                elif isinstance(node, ast.With):
                    stmt = visitor.visit_With(node)
                    statements.append(stmt)
                    process_body(node.body, depth + 1)

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Nested function - create a statement for it
                    nested_stmt = IRStatement(
                        id=f"stmt_nested_func_{node.lineno}",
                        type=StatementType.FUNCTION_DEF,
                        line=node.lineno,
                        end_line=node.end_lineno,
                        code=f"def {node.name}(...):",
                        definitions=[Variable(name=node.name, is_definition=True)],
                        uses=[]
                    )
                    statements.append(nested_stmt)

                elif isinstance(node, ast.ClassDef):
                    # Nested class
                    nested_stmt = IRStatement(
                        id=f"stmt_nested_class_{node.lineno}",
                        type=StatementType.CLASS_DEF,
                        line=node.lineno,
                        end_line=node.end_lineno,
                        code=f"class {node.name}:",
                        definitions=[Variable(name=node.name, is_definition=True)],
                        uses=[]
                    )
                    statements.append(nested_stmt)

                elif isinstance(node, ast.Assign):
                    statements.append(visitor.visit_Assign(node))
                elif isinstance(node, ast.AugAssign):
                    statements.append(visitor.visit_AugAssign(node))
                elif isinstance(node, ast.AnnAssign):
                    statements.append(visitor.visit_AnnAssign(node))
                elif isinstance(node, ast.Expr):
                    statements.append(visitor.visit_Expr(node))
                elif isinstance(node, ast.Return):
                    statements.append(visitor.visit_Return(node))
                elif isinstance(node, ast.Raise):
                    statements.append(visitor.visit_Raise(node))
                elif isinstance(node, ast.Assert):
                    statements.append(visitor.visit_Assert(node))
                elif isinstance(node, ast.Pass):
                    statements.append(visitor.visit_Pass(node))
                elif isinstance(node, ast.Break):
                    statements.append(visitor.visit_Break(node))
                elif isinstance(node, ast.Continue):
                    statements.append(visitor.visit_Continue(node))
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Skip imports in function body
                    pass
                elif isinstance(node, ast.Global):
                    pass  # Global statement
                elif isinstance(node, ast.Nonlocal):
                    pass  # Nonlocal statement

        process_body(body)
        return statements

    def _collect_function_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[FunctionCall]:
        """Collect all function calls in a function"""
        visitor = CallVisitor()
        visitor.visit(node)
        return visitor.calls

    def _collect_local_vars(self, statements: List[IRStatement]) -> List[str]:
        """Get list of local variable names"""
        vars_set = set()
        for stmt in statements:
            for defn in stmt.definitions:
                if "." not in defn.name:  # Skip attribute assignments
                    vars_set.add(defn.name)
        return list(vars_set)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node)
        self.generic_visit(node)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """Process a function definition"""
        # Build qualified name
        if self.current_class:
            qualified_name = f"{self.module_name}.{self.current_class}.{node.name}"
            comp_type = ComponentType.METHOD
        else:
            qualified_name = f"{self.module_name}.{node.name}"
            comp_type = ComponentType.FUNCTION

        func_id = generate_id("func", self.file_path, qualified_name)

        decorators = self._get_decorators(node)

        statements = self._collect_statements(node.body)

        func_ir = FunctionIR(
            id=func_id,
            name=node.name,
            qualified_name=qualified_name,
            type=comp_type,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parameters=self._get_parameters(node),
            return_annotation=ast.unparse(node.returns) if node.returns else None,
            decorators=decorators,
            docstring=self._get_docstring(node),
            statements=statements,
            parent_class=self.current_class,
            is_static="staticmethod" in decorators,
            is_classmethod="classmethod" in decorators,
            is_property="property" in decorators,
            calls=self._collect_function_calls(node),
            local_variables=self._collect_local_vars(statements)
        )

        self.functions[func_id] = func_ir

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class to process methods"""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class


class ClassVisitor(ast.NodeVisitor):
    """Extracts class IR"""

    def __init__(self, source_lines: List[str], file_path: str, module_name: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.module_name = module_name
        self.classes: Dict[str, ClassIR] = {}

    def _get_docstring(self, node: ast.ClassDef) -> Optional[str]:
        """Extract docstring from class"""
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value
        return None

    def _get_bases(self, node: ast.ClassDef) -> List[str]:
        """Get base class names"""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    bases.append(base.attr)
        return bases

    def _get_decorators(self, node: ast.ClassDef) -> List[str]:
        """Extract decorator names"""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
        return decorators

    def _get_class_variables(self, node: ast.ClassDef) -> List[Variable]:
        """Get class-level variable assignments"""
        vars = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        vars.append(Variable(
                            name=target.id,
                            line=stmt.lineno,
                            is_definition=True,
                            scope="class"
                        ))
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    vars.append(Variable(
                        name=stmt.target.id,
                        line=stmt.lineno,
                        is_definition=True,
                        scope="class"
                    ))
        return vars

    def _get_instance_attributes(self, node: ast.ClassDef) -> List[str]:
        """Get instance attributes from __init__"""
        attrs = []
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == "__init__":
                for init_stmt in ast.walk(stmt):
                    if isinstance(init_stmt, ast.Assign):
                        for target in init_stmt.targets:
                            if isinstance(target, ast.Attribute):
                                if isinstance(target.value, ast.Name) and target.value.id == "self":
                                    attrs.append(target.attr)
                    elif isinstance(init_stmt, ast.AnnAssign):
                        if isinstance(init_stmt.target, ast.Attribute):
                            if isinstance(init_stmt.target.value, ast.Name) and init_stmt.target.value.id == "self":
                                attrs.append(init_stmt.target.attr)
        return attrs

    def _get_method_ids(self, node: ast.ClassDef) -> List[str]:
        """Get IDs of methods in the class"""
        method_ids = []
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = f"{self.module_name}.{node.name}.{stmt.name}"
                method_id = generate_id("func", self.file_path, qualified_name)
                method_ids.append(method_id)
        return method_ids

    def visit_ClassDef(self, node: ast.ClassDef):
        qualified_name = f"{self.module_name}.{node.name}"
        class_id = generate_id("class", self.file_path, qualified_name)

        class_ir = ClassIR(
            id=class_id,
            name=node.name,
            qualified_name=qualified_name,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            bases=self._get_bases(node),
            decorators=self._get_decorators(node),
            docstring=self._get_docstring(node),
            methods=self._get_method_ids(node),
            class_variables=self._get_class_variables(node),
            instance_attributes=self._get_instance_attributes(node)
        )

        self.classes[class_id] = class_ir
        self.generic_visit(node)


class ModuleVisitor(ast.NodeVisitor):
    """Extracts module-level IR"""

    def __init__(self, source_lines: List[str], file_path: str, module_name: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.module_name = module_name
        self.imports: List[Import] = []
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.module_variables: List[Variable] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(Import(
                module=alias.name,
                alias=alias.asname,
                line=node.lineno,
                is_from=False
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        names = [alias.name for alias in node.names]
        self.imports.append(Import(
            module=node.module or "",
            names=names,
            line=node.lineno,
            is_from=True
        ))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qualified_name = f"{self.module_name}.{node.name}"
        func_id = generate_id("func", self.file_path, qualified_name)
        self.functions.append(func_id)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        qualified_name = f"{self.module_name}.{node.name}"
        func_id = generate_id("func", self.file_path, qualified_name)
        self.functions.append(func_id)

    def visit_ClassDef(self, node: ast.ClassDef):
        qualified_name = f"{self.module_name}.{node.name}"
        class_id = generate_id("class", self.file_path, qualified_name)
        self.classes.append(class_id)

    def visit_Assign(self, node: ast.Assign):
        # Only top-level assignments (check column offset)
        if node.col_offset == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.module_variables.append(Variable(
                        name=target.id,
                        line=node.lineno,
                        is_definition=True,
                        scope="module"
                    ))


class RepositoryParser:
    """
    Main parser class that processes an entire repository.
    """

    def __init__(self, root_path: str, exclude_patterns: Optional[List[str]] = None):
        self.root_path = os.path.abspath(root_path)
        self.exclude_patterns = exclude_patterns or [
            "__pycache__", ".git", ".venv", "venv", "node_modules",
            ".pytest_cache", ".mypy_cache", "dist", "build", ".egg-info"
        ]
        self.ir = RepositoryIR(root_path=self.root_path)
        self.errors: List[str] = []

    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded"""
        for pattern in self.exclude_patterns:
            if pattern in path:
                return True
        return False

    def _get_module_name(self, file_path: str) -> str:
        """Get module name from file path"""
        rel_path = os.path.relpath(file_path, self.root_path)
        module_name = rel_path.replace(os.sep, ".").replace("/", ".")
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        return module_name

    def parse_file(self, file_path: str) -> Optional[ModuleIR]:
        """Parse a single Python file"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
                source_lines = source.splitlines()

            tree = ast.parse(source, filename=file_path)
            module_name = self._get_module_name(file_path)

            # Extract functions
            func_visitor = FunctionVisitor(source_lines, file_path, module_name)
            func_visitor.visit(tree)
            for func_id, func_ir in func_visitor.functions.items():
                self.ir.functions[func_id] = func_ir
                self.ir.function_to_file[func_id] = file_path

            # Extract classes
            class_visitor = ClassVisitor(source_lines, file_path, module_name)
            class_visitor.visit(tree)
            for class_id, class_ir in class_visitor.classes.items():
                self.ir.classes[class_id] = class_ir
                self.ir.class_to_file[class_id] = file_path

            # Extract module-level info
            module_visitor = ModuleVisitor(source_lines, file_path, module_name)
            module_visitor.visit(tree)

            module_id = generate_id("module", file_path)
            module_ir = ModuleIR(
                id=module_id,
                file_path=file_path,
                module_name=module_name,
                imports=module_visitor.imports,
                functions=module_visitor.functions,
                classes=module_visitor.classes,
                module_variables=module_visitor.module_variables
            )

            self.ir.modules[module_id] = module_ir
            self.ir.file_to_module[file_path] = module_id

            return module_ir

        except SyntaxError as e:
            self.errors.append(f"Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            self.errors.append(f"Error parsing {file_path}: {e}")
            return None

    def parse_repository(self) -> RepositoryIR:
        """Parse all Python files in the repository"""
        for root, dirs, files in os.walk(self.root_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(d)]

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    if not self._should_exclude(file_path):
                        self.parse_file(file_path)

        return self.ir

    def parse_single_file(self, file_path: str) -> RepositoryIR:
        """Parse just a single file (for testing)"""
        self.parse_file(os.path.abspath(file_path))
        return self.ir


def parse_repository(root_path: str, exclude_patterns: Optional[List[str]] = None) -> RepositoryIR:
    """Convenience function to parse a repository"""
    parser = RepositoryParser(root_path, exclude_patterns)
    return parser.parse_repository()


def parse_file(file_path: str) -> RepositoryIR:
    """Convenience function to parse a single file"""
    parser = RepositoryParser(os.path.dirname(file_path))
    return parser.parse_single_file(file_path)
