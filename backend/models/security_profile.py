"""
Security Profile Model
Stores statically-inferred security vulnerability signals for a CodeComponent.

These signals are derived purely from source-code analysis (AST, regex,
pattern matching) — no actual execution is involved — so they are safe for
arbitrary untrusted repositories.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class Severity(str, Enum):
    """Vulnerability severity levels aligned with CVSS."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityCategory(str, Enum):
    """Top-level vulnerability categories."""
    INJECTION = "injection"
    BROKEN_AUTH = "broken_authentication"
    SENSITIVE_DATA = "sensitive_data_exposure"
    XXE = "xml_external_entities"
    BROKEN_ACCESS = "broken_access_control"
    SECURITY_MISCONFIG = "security_misconfiguration"
    XSS = "cross_site_scripting"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    VULNERABLE_COMPONENTS = "vulnerable_components"
    INSUFFICIENT_LOGGING = "insufficient_logging"
    CRYPTOGRAPHIC = "cryptographic_issues"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    RESOURCE_MANAGEMENT = "resource_management"


@dataclass
class VulnerabilitySignal:
    """A single detected vulnerability signal."""

    # CWE identification
    cwe_id: str
    """Common Weakness Enumeration ID (e.g., 'CWE-89')."""

    cwe_name: str
    """Human-readable CWE name (e.g., 'SQL Injection')."""

    # Classification
    category: VulnerabilityCategory
    """Top-level vulnerability category."""

    severity: Severity
    """Severity level of the vulnerability."""

    # Description
    description: str
    """Detailed description of the vulnerability."""

    # Location
    line_number: Optional[int] = None
    """Line number where vulnerability was detected."""

    end_line_number: Optional[int] = None
    """End line number for multi-line vulnerabilities."""

    code_snippet: Optional[str] = None
    """The vulnerable code snippet."""

    # Remediation
    mitigation: str = ""
    """Recommended mitigation/fix for the vulnerability."""

    secure_alternative: Optional[str] = None
    """Example of secure code pattern to use instead."""

    # Detection metadata
    detection_method: str = "pattern"
    """How the vulnerability was detected: 'pattern', 'ast', 'dataflow'."""

    confidence: float = 0.8
    """Confidence level 0.0-1.0 of the detection."""

    # References
    references: List[str] = field(default_factory=list)
    """Links to documentation, OWASP guides, etc."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cwe_id": self.cwe_id,
            "cwe_name": self.cwe_name,
            "category": self.category.value if isinstance(self.category, VulnerabilityCategory) else self.category,
            "severity": self.severity.value if isinstance(self.severity, Severity) else self.severity,
            "description": self.description,
            "line_number": self.line_number,
            "end_line_number": self.end_line_number,
            "code_snippet": self.code_snippet,
            "mitigation": self.mitigation,
            "secure_alternative": self.secure_alternative,
            "detection_method": self.detection_method,
            "confidence": self.confidence,
            "references": self.references,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VulnerabilitySignal":
        # Handle enum conversion
        category = data.get("category")
        if isinstance(category, str):
            category = VulnerabilityCategory(category)
        severity = data.get("severity")
        if isinstance(severity, str):
            severity = Severity(severity)

        return cls(
            cwe_id=data.get("cwe_id", ""),
            cwe_name=data.get("cwe_name", ""),
            category=category,
            severity=severity,
            description=data.get("description", ""),
            line_number=data.get("line_number"),
            end_line_number=data.get("end_line_number"),
            code_snippet=data.get("code_snippet"),
            mitigation=data.get("mitigation", ""),
            secure_alternative=data.get("secure_alternative"),
            detection_method=data.get("detection_method", "pattern"),
            confidence=data.get("confidence", 0.8),
            references=data.get("references", []),
        )


@dataclass
class SecurityProfile:
    """Statically-inferred security signals for a code component.

    Aggregates all vulnerability signals and security-relevant metadata
    for a single code component (function, class, method).
    """

    # Core vulnerability data
    vulnerabilities: List[VulnerabilitySignal] = field(default_factory=list)
    """List of detected vulnerability signals."""

    # Security relevance flags
    handles_user_input: bool = False
    """Component processes external/user input."""

    handles_authentication: bool = False
    """Component involved in authentication logic."""

    handles_authorization: bool = False
    """Component involved in authorization/access control."""

    handles_cryptography: bool = False
    """Component performs cryptographic operations."""

    handles_sensitive_data: bool = False
    """Component processes sensitive data (PII, credentials, etc.)."""

    handles_file_operations: bool = False
    """Component performs file system operations."""

    handles_network: bool = False
    """Component makes network requests."""

    handles_database: bool = False
    """Component interacts with databases."""

    handles_subprocess: bool = False
    """Component spawns subprocesses or executes commands."""

    # Data flow hints
    input_sources: List[str] = field(default_factory=list)
    """Where data comes from (e.g., 'request.args', 'user_input', 'file')."""

    output_sinks: List[str] = field(default_factory=list)
    """Where data goes (e.g., 'database', 'response', 'file', 'subprocess')."""

    tainted_variables: List[str] = field(default_factory=list)
    """Variables that may contain untrusted data."""

    # Security patterns detected
    security_patterns: List[str] = field(default_factory=list)
    """Positive security patterns found (e.g., 'uses_parameterized_queries')."""

    # Aggregate metrics
    risk_score: float = 0.0
    """Aggregate risk score 0.0-10.0 based on vulnerabilities and context."""

    confidence: float = 0.0
    """Overall confidence of the security analysis 0.0-1.0."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """True when no security signal was extracted."""
        return not any([
            self.vulnerabilities,
            self.handles_user_input,
            self.handles_authentication,
            self.handles_authorization,
            self.handles_cryptography,
            self.handles_sensitive_data,
            self.handles_file_operations,
            self.handles_network,
            self.handles_database,
            self.handles_subprocess,
            self.input_sources,
            self.output_sinks,
            self.security_patterns,
        ])

    @property
    def is_security_relevant(self) -> bool:
        """True if the component has any security-relevant operations."""
        return any([
            self.handles_user_input,
            self.handles_authentication,
            self.handles_authorization,
            self.handles_cryptography,
            self.handles_sensitive_data,
            self.handles_file_operations,
            self.handles_network,
            self.handles_database,
            self.handles_subprocess,
        ])

    @property
    def has_vulnerabilities(self) -> bool:
        """True if any vulnerabilities were detected."""
        return len(self.vulnerabilities) > 0

    @property
    def critical_count(self) -> int:
        """Count of critical severity vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high severity vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        """Count of medium severity vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        """Count of low severity vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.LOW)

    def calculate_risk_score(self) -> float:
        """Calculate aggregate risk score based on vulnerabilities."""
        if not self.vulnerabilities:
            return 0.0

        severity_weights = {
            Severity.CRITICAL: 10.0,
            Severity.HIGH: 7.5,
            Severity.MEDIUM: 5.0,
            Severity.LOW: 2.5,
            Severity.INFO: 0.5,
        }

        total_score = sum(
            severity_weights.get(v.severity, 0) * v.confidence
            for v in self.vulnerabilities
        )

        # Normalize to 0-10 scale
        self.risk_score = min(10.0, total_score)
        return self.risk_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "handles_user_input": self.handles_user_input,
            "handles_authentication": self.handles_authentication,
            "handles_authorization": self.handles_authorization,
            "handles_cryptography": self.handles_cryptography,
            "handles_sensitive_data": self.handles_sensitive_data,
            "handles_file_operations": self.handles_file_operations,
            "handles_network": self.handles_network,
            "handles_database": self.handles_database,
            "handles_subprocess": self.handles_subprocess,
            "input_sources": self.input_sources,
            "output_sinks": self.output_sinks,
            "tainted_variables": self.tainted_variables,
            "security_patterns": self.security_patterns,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            # Computed properties
            "is_security_relevant": self.is_security_relevant,
            "has_vulnerabilities": self.has_vulnerabilities,
            "vulnerability_counts": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityProfile":
        vulnerabilities = [
            VulnerabilitySignal.from_dict(v)
            for v in data.get("vulnerabilities", [])
        ]

        profile = cls(
            vulnerabilities=vulnerabilities,
            handles_user_input=data.get("handles_user_input", False),
            handles_authentication=data.get("handles_authentication", False),
            handles_authorization=data.get("handles_authorization", False),
            handles_cryptography=data.get("handles_cryptography", False),
            handles_sensitive_data=data.get("handles_sensitive_data", False),
            handles_file_operations=data.get("handles_file_operations", False),
            handles_network=data.get("handles_network", False),
            handles_database=data.get("handles_database", False),
            handles_subprocess=data.get("handles_subprocess", False),
            input_sources=data.get("input_sources", []),
            output_sinks=data.get("output_sinks", []),
            tainted_variables=data.get("tainted_variables", []),
            security_patterns=data.get("security_patterns", []),
            risk_score=data.get("risk_score", 0.0),
            confidence=data.get("confidence", 0.0),
        )
        return profile

    def merge(self, other: "SecurityProfile") -> "SecurityProfile":
        """Merge another security profile into this one."""
        self.vulnerabilities.extend(other.vulnerabilities)
        self.handles_user_input = self.handles_user_input or other.handles_user_input
        self.handles_authentication = self.handles_authentication or other.handles_authentication
        self.handles_authorization = self.handles_authorization or other.handles_authorization
        self.handles_cryptography = self.handles_cryptography or other.handles_cryptography
        self.handles_sensitive_data = self.handles_sensitive_data or other.handles_sensitive_data
        self.handles_file_operations = self.handles_file_operations or other.handles_file_operations
        self.handles_network = self.handles_network or other.handles_network
        self.handles_database = self.handles_database or other.handles_database
        self.handles_subprocess = self.handles_subprocess or other.handles_subprocess
        self.input_sources = list(set(self.input_sources + other.input_sources))
        self.output_sinks = list(set(self.output_sinks + other.output_sinks))
        self.tainted_variables = list(set(self.tainted_variables + other.tainted_variables))
        self.security_patterns = list(set(self.security_patterns + other.security_patterns))
        self.confidence = max(self.confidence, other.confidence)
        self.calculate_risk_score()
        return self
