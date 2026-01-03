## 3. Verifier Agent

### `backend/agents/verifier_agent.py`
"""
Verifier Agent
Validates and improves generated documentation
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, AgentStatus
from backend.models.code_component import CodeComponent
from backend.models.documentation import Documentation
from backend.models.evaluation import Issue, IssueSeverity
from backend.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class VerificationResult:
    """Result of documentation verification"""
    is_valid: bool
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    improved_documentation: Optional[Documentation] = None
    scores: Dict[str, float] = field(default_factory=dict)

class VerifierAgent(BaseAgent):
    """
    Verifier Agent validates documentation quality by:
    1. Checking completeness (all elements documented)
    2. Verifying accuracy (matches code behavior)
    3. Assessing consistency (terminology, style)
    4. Evaluating clarity (readability, usefulness)
    5. Auto-fixing issues when possible
    """
    
    def __init__(self):
        super().__init__("verifier")
        
        self.validation_rules = self.agent_config.get('validation_rules', [
            'completeness', 'accuracy', 'consistency'
        ])
        self.auto_fix = self.agent_config.get('auto_fix', True)
    
    def process(self, context: AgentContext) -> AgentResult:
        """
        Verify and improve documentation
        
        Args:
            context: Agent context with Writer output
            
        Returns:
            AgentResult with improved Documentation
        """
        try:
            component = context.component
            documentation = context.get_result('writer')
            
            if not documentation or not isinstance(documentation, Documentation):
                return AgentResult(
                    agent_name=self.agent_name,
                    status=AgentStatus.FAILED,
                    output=None,
                    error="No Writer output available"
                )
            
            self.logger.info(f"Verifying documentation for: {component.name}")
            
            # Run verification checks
            verification = self._verify_documentation(component, documentation)
            
            # If issues found and auto-fix enabled, attempt improvements
            if verification.issues and self.auto_fix:
                improved_doc = self._improve_documentation(
                    component,
                    documentation,
                    verification
                )
                verification.improved_documentation = improved_doc
            else:
                verification.improved_documentation = documentation
            
            # Calculate quality scores
            verification.scores = self._calculate_quality_scores(
                component,
                verification.improved_documentation
            )
            
            self.logger.info(
                f"Verification complete: {len(verification.issues)} issues found, "
                f"Overall score: {verification.scores.get('overall', 0):.2f}"
            )
            
            # Return improved documentation
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.SUCCESS,
                output=verification.improved_documentation,
                metadata={
                    'issues': [issue.to_dict() for issue in verification.issues],
                    'scores': verification.scores,
                    'suggestions': verification.suggestions
                }
            )
            
        except Exception as e:
            self.logger.error(f"Verifier agent error: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                output=None,
                error=str(e)
            )
    
    def _verify_documentation(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> VerificationResult:
        """Run all verification checks"""
        issues = []
        suggestions = []
        
        # 1. Completeness checks
        if 'completeness' in self.validation_rules:
            completeness_issues = self._check_completeness(component, documentation)
            issues.extend(completeness_issues)
        
        # 2. Accuracy checks
        if 'accuracy' in self.validation_rules:
            accuracy_issues = self._check_accuracy(component, documentation)
            issues.extend(accuracy_issues)
        
        # 3. Consistency checks
        if 'consistency' in self.validation_rules:
            consistency_issues = self._check_consistency(component, documentation)
            issues.extend(consistency_issues)
        
        # 4. Generate suggestions
        suggestions = self._generate_suggestions(component, documentation, issues)
        
        is_valid = len([i for i in issues if i.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL]]) == 0
        
        return VerificationResult(
            is_valid=is_valid,
            issues=issues,
            suggestions=suggestions
        )
    
    def _check_completeness(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> List[Issue]:
        """Check if documentation is complete"""
        issues = []
        
        # Check summary
        if not documentation.summary or len(documentation.summary) < 10:
            issues.append(Issue(
                component_id=component.id,
                severity=IssueSeverity.ERROR,
                category="missing_summary",
                message="Summary is missing or too short",
                suggestion="Add a clear one-line summary of what this component does"
            ))
        
        # Check description
        if not documentation.description or len(documentation.description) < 50:
            issues.append(Issue(
                component_id=component.id,
                severity=IssueSeverity.WARNING,
                category="insufficient_description",
                message="Description is too brief",
                suggestion="Expand the description to explain purpose, usage, and behavior"
            ))
        
        # Check parameters documentation
        if component.parameters:
            documented_params = {p['name'] for p in documentation.parameters_doc}
            actual_params = {p.name for p in component.parameters}
            
            missing_params = actual_params - documented_params
            if missing_params:
                issues.append(Issue(
                    component_id=component.id,
                    severity=IssueSeverity.ERROR,
                    category="missing_parameters",
                    message=f"Parameters not documented: {', '.join(missing_params)}",
                    suggestion=f"Add documentation for parameters: {', '.join(missing_params)}"
                ))
        
        # Check return documentation
        if component.return_type and component.return_type != 'None':
            if not documentation.returns_doc:
                issues.append(Issue(
                    component_id=component.id,
                    severity=IssueSeverity.WARNING,
                    category="missing_return",
                    message="Return value not documented",
                    suggestion="Describe what this function returns"
                ))
        
        # Check examples
        if not documentation.examples and component.type.value in ['function', 'method']:
            issues.append(Issue(
                component_id=component.id,
                severity=IssueSeverity.INFO,
                category="missing_examples",
                message="No usage examples provided",
                suggestion="Add at least one usage example"
            ))
        
        return issues
    
    def _check_accuracy(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> List[Issue]:
        """Check if documentation accurately describes the code"""
        issues = []
        
        # Check parameter types match
        if component.parameters:
            for param in component.parameters:
                doc_param = next(
                    (p for p in documentation.parameters_doc if p['name'] == param.name),
                    None
                )
                
                if doc_param and param.type_hint:
                    doc_type = doc_param.get('type', '').strip()
                    if doc_type and doc_type != param.type_hint:
                        issues.append(Issue(
                            component_id=component.id,
                            severity=IssueSeverity.WARNING,
                            category="type_mismatch",
                            message=f"Parameter '{param.name}' type mismatch: "
                                  f"documented as {doc_type}, actually {param.type_hint}",
                            location=f"parameter:{param.name}",
                            suggestion=f"Update type to {param.type_hint}"
                        ))
        
        # Check return type match
        if component.return_type and documentation.returns_doc:
            doc_return_type = documentation.returns_doc.get('type', '').strip()
            if doc_return_type and doc_return_type != component.return_type:
                issues.append(Issue(
                    component_id=component.id,
                    severity=IssueSeverity.WARNING,
                    category="return_type_mismatch",
                    message=f"Return type mismatch: "
                          f"documented as {doc_return_type}, actually {component.return_type}",
                    suggestion=f"Update return type to {component.return_type}"
                ))
        
        return issues
    
    def _check_consistency(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> List[Issue]:
        """Check consistency in documentation"""
        issues = []
        
        # Check if component name mentioned correctly
        if component.name.lower() not in documentation.description.lower():
            issues.append(Issue(
                component_id=component.id,
                severity=IssueSeverity.INFO,
                category="name_not_mentioned",
                message=f"Component name '{component.name}' not mentioned in description",
                suggestion="Consider mentioning the component name in the description"
            ))
        
        # Check docstring style consistency
        if documentation.docstring:
            if not self._validate_docstring_format(documentation.docstring, documentation.style):
                issues.append(Issue(
                    component_id=component.id,
                    severity=IssueSeverity.WARNING,
                    category="inconsistent_format",
                    message=f"Docstring format doesn't match {documentation.style} style",
                    suggestion=f"Reformat docstring to match {documentation.style} style"
                ))
        
        return issues
    
    def _validate_docstring_format(self, docstring: str, style: str) -> bool:
        """Validate docstring format matches style"""
        if style == "google":
            return "Args:" in docstring or "Returns:" in docstring
        elif style == "numpy":
            return "Parameters" in docstring or "Returns" in docstring
        elif style == "sphinx":
            return ":param" in docstring or ":return:" in docstring
        return True
    
    def _generate_suggestions(
        self,
        component: CodeComponent,
        documentation: Documentation,
        issues: List[Issue]
    ) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        
        # Priority suggestions based on issues
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        error_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
        
        if critical_issues:
            suggestions.append("Critical issues found - documentation requires immediate attention")
        
        if error_issues:
            suggestions.append(f"Fix {len(error_issues)} error(s) to improve documentation quality")
        
        # Specific suggestions
        if not documentation.examples:
            suggestions.append("Add usage examples to help users understand how to use this component")
        
        if len(documentation.description) < 100:
            suggestions.append("Consider expanding the description with more details about behavior and use cases")
        
        return suggestions
    
    def _improve_documentation(
        self,
        component: CodeComponent,
        documentation: Documentation,
        verification: VerificationResult
    ) -> Documentation:
        """Attempt to automatically improve documentation"""
        
        # Create a copy to modify
        improved = Documentation(
            component_id=documentation.component_id,
            component_name=documentation.component_name,
            component_type=documentation.component_type,
            summary=documentation.summary,
            description=documentation.description,
            parameters_doc=documentation.parameters_doc.copy(),
            returns_doc=documentation.returns_doc.copy() if documentation.returns_doc else None,
            raises_doc=documentation.raises_doc.copy(),
            examples=documentation.examples.copy(),
            notes=documentation.notes.copy(),
            warnings=documentation.warnings.copy(),
            style=documentation.style
        )
        
        # Fix critical issues using LLM
        critical_issues = [i for i in verification.issues 
                          if i.severity in [IssueSeverity.CRITICAL, IssueSeverity.ERROR]]
        
        if critical_issues:
            prompt = self._create_improvement_prompt(component, documentation, critical_issues)
            
            try:
                improvements = self.generate_with_llm(
                    prompt=prompt,
                    temperature=0.5,
                    max_tokens=1000
                )
                
                # Apply improvements
                improved = self._apply_improvements(improved, improvements, critical_issues)
                
            except Exception as e:
                self.logger.warning(f"Failed to generate improvements: {e}")
        
        return improved
    
    def _create_improvement_prompt(
        self,
        component: CodeComponent,
        documentation: Documentation,
        issues: List[Issue]
    ) -> str:
        """Create prompt for LLM to improve documentation"""
        prompt = f"""Improve this documentation by fixing the identified issues:

Component: {component.name}
Type: {component.type.value}

Current Documentation:
Summary: {documentation.summary}
Description: {documentation.description}

Issues Found:
"""
        
        for issue in issues:
            prompt += f"- {issue.category}: {issue.message}\n"
            if issue.suggestion:
                prompt += f"  Suggestion: {issue.suggestion}\n"
        
        prompt += """
Provide improved versions of:
1. Summary (if needed)
2. Description (if needed)
3. Any missing parameter descriptions

Format your response as:
SUMMARY: <improved summary>
DESCRIPTION: <improved description>
PARAMETER <name>: <improved description>
"""
        
        return prompt
    
    def _apply_improvements(
        self,
        documentation: Documentation,
        improvements: str,
        issues: List[Issue]
    ) -> Documentation:
        """Apply improvements from LLM response"""
        lines = improvements.strip().split('\n')
        
        for line in lines:
            if line.startswith('SUMMARY:'):
                documentation.summary = line.replace('SUMMARY:', '').strip()
            elif line.startswith('DESCRIPTION:'):
                documentation.description = line.replace('DESCRIPTION:', '').strip()
            elif line.startswith('PARAMETER'):
                # Parse parameter improvement
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    param_name = parts[1].strip()
                    param_desc = parts[2].strip()
                    
                    # Update or add parameter
                    found = False
                    for p in documentation.parameters_doc:
                        if p['name'] == param_name:
                            p['description'] = param_desc
                            found = True
                            break
                    
                    if not found:
                        documentation.parameters_doc.append({
                            'name': param_name,
                            'type': '',
                            'description': param_desc
                        })
        
        return documentation
    
    def _calculate_quality_scores(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> Dict[str, float]:
        """Calculate quality scores for documentation"""
        scores = {}
        
        # Completeness score
        scores['completeness'] = self._score_completeness(component, documentation)
        
        # Clarity score (based on length and structure)
        scores['clarity'] = self._score_clarity(documentation)
        
        # Consistency score
        scores['consistency'] = self._score_consistency(documentation)
        
        # Overall score (weighted average)
        scores['overall'] = (
            scores['completeness'] * 0.4 +
            scores['clarity'] * 0.3 +
            scores['consistency'] * 0.3
        )
        
        return scores
    
    def _score_completeness(
        self,
        component: CodeComponent,
        documentation: Documentation
    ) -> float:
        """Score documentation completeness (0-100)"""
        score = 0
        total_checks = 0
        
        # Has summary
        total_checks += 1
        if documentation.summary and len(documentation.summary) >= 10:
            score += 20
        
        # Has description
        total_checks += 1
        if documentation.description and len(documentation.description) >= 50:
            score += 20
        
        # Parameters documented
        if component.parameters:
            total_checks += 1
            documented = len(documentation.parameters_doc)
            expected = len(component.parameters)
            if expected > 0:
                score += (documented / expected) * 20
        
        # Return documented
        if component.return_type and component.return_type != 'None':
            total_checks += 1
            if documentation.returns_doc:
                score += 20
        
        # Has examples
        total_checks += 1
        if documentation.examples:
            score += 20
        
        return min(score, 100)
    
    def _score_clarity(self, documentation: Documentation) -> float:
        """Score documentation clarity (0-100)"""
        score = 0
        
        # Description length (sweet spot: 100-500 chars)
        desc_len = len(documentation.description)
        if 100 <= desc_len <= 500:
            score += 40
        elif 50 <= desc_len < 100 or 500 < desc_len <= 1000:
            score += 20
        elif desc_len > 0:
            score += 10
        
        # Has structured sections
        if documentation.parameters_doc:
            score += 20
        
        if documentation.returns_doc:
            score += 20
        
        if documentation.examples:
            score += 20
        
        return min(score, 100)
    
    def _score_consistency(self, documentation: Documentation) -> float:
        """Score documentation consistency (0-100)"""
        score = 100  # Start at perfect, deduct for issues
        
        # Check if docstring matches claimed style
        if documentation.docstring:
            if not self._validate_docstring_format(documentation.docstring, documentation.style):
                score -= 30
        
        # Check parameter consistency
        for param in documentation.parameters_doc:
            if not param.get('description'):
                score -= 10
        
        return max(score, 0)