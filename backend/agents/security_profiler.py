"""
Static Security Profiler

Pattern-based vulnerability scanner that analyzes source code to detect
potential security issues. Uses AST analysis and regex patterns - no LLM
calls required.

Supported languages: Python (primary), JavaScript/TypeScript (basic)
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.models.code_component import CodeComponent, ComponentType
from backend.models.security_profile import (
    SecurityProfile,
    VulnerabilitySignal,
    VulnerabilityCategory,
    Severity,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ======================================================================
# Vulnerability Pattern Definitions
# ======================================================================

@dataclass
class VulnerabilityPattern:
    """Definition of a vulnerability detection pattern."""
    cwe_id: str
    cwe_name: str
    category: VulnerabilityCategory
    severity: Severity
    description: str
    mitigation: str
    patterns: List[str]  # Regex patterns
    ast_check: Optional[str] = None  # Name of AST check method
    secure_alternative: Optional[str] = None
    references: List[str] = field(default_factory=list)
    confidence: float = 0.8


# SQL Injection patterns
SQL_INJECTION_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-89",
    cwe_name="SQL Injection",
    category=VulnerabilityCategory.INJECTION,
    severity=Severity.CRITICAL,
    description="User-controlled input is concatenated into SQL queries, allowing attackers to execute arbitrary SQL commands.",
    mitigation="Use parameterized queries or prepared statements. Never concatenate user input directly into SQL strings.",
    patterns=[
        r'execute\s*\(\s*["\'].*%[sd].*["\'].*%',  # execute("SELECT... %s" % var)
        r'execute\s*\(\s*["\'].*\.format\s*\(',    # execute("SELECT...".format())
        r'execute\s*\(\s*f["\']',                   # execute(f"SELECT...")
        r'executemany\s*\(\s*["\'].*%[sd]',
        r'cursor\.execute\s*\([^,)]*\+',            # cursor.execute(sql + var)
        r'raw\s*\(\s*["\'].*%[sd]',                 # Django raw() with formatting
        r'extra\s*\(\s*where\s*=.*%[sd]',           # Django extra() with formatting
    ],
    secure_alternative='cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
    references=[
        "https://owasp.org/www-community/attacks/SQL_Injection",
        "https://cwe.mitre.org/data/definitions/89.html",
    ],
)

# Command Injection patterns
COMMAND_INJECTION_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-78",
    cwe_name="OS Command Injection",
    category=VulnerabilityCategory.COMMAND_INJECTION,
    severity=Severity.CRITICAL,
    description="User-controlled input is passed to system command execution functions, allowing arbitrary command execution.",
    mitigation="Avoid shell=True. Use subprocess with a list of arguments. Validate and sanitize all inputs.",
    patterns=[
        r'os\.system\s*\(',
        r'os\.popen\s*\(',
        r'subprocess\.\w+\s*\([^)]*shell\s*=\s*True',
        r'subprocess\.call\s*\(\s*["\']',           # shell command as string
        r'subprocess\.run\s*\(\s*["\']',
        r'commands\.getoutput\s*\(',
        r'commands\.getstatusoutput\s*\(',
        r'popen\s*\(',
    ],
    secure_alternative='subprocess.run(["ls", "-la", directory], shell=False, check=True)',
    references=[
        "https://owasp.org/www-community/attacks/Command_Injection",
        "https://cwe.mitre.org/data/definitions/78.html",
    ],
)

# Code Injection (eval/exec)
CODE_INJECTION_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-94",
    cwe_name="Code Injection",
    category=VulnerabilityCategory.INJECTION,
    severity=Severity.CRITICAL,
    description="Dynamic code execution functions are used with potentially untrusted input.",
    mitigation="Avoid eval() and exec() entirely. Use ast.literal_eval() for safe literal evaluation if needed.",
    patterns=[
        r'\beval\s*\(',
        r'\bexec\s*\(',
        r'compile\s*\([^)]*,[^)]*,\s*["\']exec["\']',
        r'__import__\s*\(',
        r'importlib\.import_module\s*\([^)]*\+',    # Dynamic imports with concat
    ],
    secure_alternative='import ast; ast.literal_eval(user_input)  # Only for literal structures',
    references=[
        "https://owasp.org/www-community/attacks/Code_Injection",
        "https://cwe.mitre.org/data/definitions/94.html",
    ],
)

# Path Traversal patterns
PATH_TRAVERSAL_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-22",
    cwe_name="Path Traversal",
    category=VulnerabilityCategory.PATH_TRAVERSAL,
    severity=Severity.HIGH,
    description="User-controlled input is used in file path operations without proper validation, allowing access to arbitrary files.",
    mitigation="Validate and sanitize file paths. Use os.path.basename() or pathlib to ensure paths stay within allowed directories.",
    patterns=[
        r'open\s*\([^)]*\+',                        # open(base + user_input)
        r'open\s*\(\s*f["\']',                      # open(f"{path}")
        r'Path\s*\([^)]*\+',
        r'os\.path\.join\s*\([^)]*request\.',       # join with request data
        r'send_file\s*\([^)]*\+',                   # Flask send_file with concat
        r'send_from_directory\s*\([^)]*\+',
        r'shutil\.(copy|move|rmtree)\s*\([^)]*\+',
    ],
    secure_alternative='safe_path = os.path.join(BASE_DIR, os.path.basename(user_filename))',
    references=[
        "https://owasp.org/www-community/attacks/Path_Traversal",
        "https://cwe.mitre.org/data/definitions/22.html",
    ],
)

# Hardcoded Secrets patterns
HARDCODED_SECRETS_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-798",
    cwe_name="Hardcoded Credentials",
    category=VulnerabilityCategory.SENSITIVE_DATA,
    severity=Severity.HIGH,
    description="Credentials, API keys, or secrets are hardcoded in source code.",
    mitigation="Use environment variables or secure secret management (e.g., AWS Secrets Manager, HashiCorp Vault).",
    patterns=[
        r'(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',
        r'(api_key|apikey|api_secret)\s*=\s*["\'][^"\']{8,}["\']',
        r'(secret_key|secretkey|secret)\s*=\s*["\'][^"\']{8,}["\']',
        r'(access_key|accesskey)\s*=\s*["\'][^"\']{8,}["\']',
        r'(auth_token|authtoken|bearer)\s*=\s*["\'][^"\']{8,}["\']',
        r'(private_key|privatekey)\s*=\s*["\']-----BEGIN',
        r'AKIA[0-9A-Z]{16}',                        # AWS Access Key ID
        r'["\'][a-zA-Z0-9+/]{40}["\']',             # Base64-ish secrets
    ],
    secure_alternative='api_key = os.environ.get("API_KEY")',
    references=[
        "https://cwe.mitre.org/data/definitions/798.html",
        "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/04-Review_Old_Backup_and_Unreferenced_Files_for_Sensitive_Information",
    ],
    confidence=0.7,
)

# Insecure Deserialization patterns
INSECURE_DESERIALIZATION_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-502",
    cwe_name="Insecure Deserialization",
    category=VulnerabilityCategory.INSECURE_DESERIALIZATION,
    severity=Severity.HIGH,
    description="Untrusted data is deserialized using unsafe methods, potentially leading to remote code execution.",
    mitigation="Use safe serialization formats like JSON. If pickle is required, only deserialize trusted data with HMAC verification.",
    patterns=[
        r'pickle\.loads?\s*\(',
        r'cPickle\.loads?\s*\(',
        r'_pickle\.loads?\s*\(',
        r'marshal\.loads?\s*\(',
        r'shelve\.open\s*\(',
        r'yaml\.load\s*\([^)]*\)',                  # yaml.load without SafeLoader
        r'yaml\.unsafe_load\s*\(',
        r'jsonpickle\.decode\s*\(',
    ],
    secure_alternative='import json; data = json.loads(user_input)  # or yaml.safe_load()',
    references=[
        "https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/15-Testing_for_HTTP_Incoming_Requests",
        "https://cwe.mitre.org/data/definitions/502.html",
    ],
)

# Weak Cryptography patterns
WEAK_CRYPTO_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-327",
    cwe_name="Use of Broken Cryptographic Algorithm",
    category=VulnerabilityCategory.CRYPTOGRAPHIC,
    severity=Severity.MEDIUM,
    description="Weak or broken cryptographic algorithms are used (MD5, SHA1 for security, DES, etc.).",
    mitigation="Use strong algorithms: SHA-256+ for hashing, AES-256 for encryption, bcrypt/argon2 for passwords.",
    patterns=[
        r'hashlib\.md5\s*\(',
        r'hashlib\.sha1\s*\(',
        r'MD5\.new\s*\(',
        r'SHA\.new\s*\(',                           # PyCrypto SHA1
        r'DES\.new\s*\(',
        r'Blowfish\.new\s*\(',
        r'RC4\.new\s*\(',
        r'ARC4\.new\s*\(',
        r'\.setPassword\s*\([^)]+\).*md5',
    ],
    secure_alternative='from hashlib import sha256; hashed = sha256(data).hexdigest()',
    references=[
        "https://cwe.mitre.org/data/definitions/327.html",
    ],
    confidence=0.9,
)

# XSS patterns (for Python web frameworks)
XSS_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-79",
    cwe_name="Cross-site Scripting (XSS)",
    category=VulnerabilityCategory.XSS,
    severity=Severity.HIGH,
    description="User input is rendered in HTML without proper escaping, allowing script injection.",
    mitigation="Always escape user input before rendering. Use framework auto-escaping features. Apply Content-Security-Policy headers.",
    patterns=[
        r'Markup\s*\([^)]*\+',                      # Flask Markup with concat
        r'\|safe\b',                                # Jinja2 safe filter
        r'mark_safe\s*\(',                          # Django mark_safe
        r'format_html\s*\([^)]*{.*}',               # Django format_html misuse
        r'render_template_string\s*\([^)]*\+',      # Flask template string
        r'\.innerHTML\s*=',                         # JS innerHTML
        r'document\.write\s*\(',                    # JS document.write
    ],
    secure_alternative='from markupsafe import escape; return escape(user_input)',
    references=[
        "https://owasp.org/www-community/attacks/xss/",
        "https://cwe.mitre.org/data/definitions/79.html",
    ],
)

# SSRF patterns
SSRF_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-918",
    cwe_name="Server-Side Request Forgery (SSRF)",
    category=VulnerabilityCategory.INJECTION,
    severity=Severity.HIGH,
    description="User-controlled URLs are used in server-side HTTP requests, potentially allowing access to internal services.",
    mitigation="Validate and whitelist allowed URLs/domains. Block internal IP ranges. Use URL parsing to validate schemes.",
    patterns=[
        r'requests\.(get|post|put|delete|patch|head)\s*\([^)]*\+',
        r'urllib\.request\.urlopen\s*\([^)]*\+',
        r'urllib\.urlopen\s*\([^)]*\+',
        r'httpx\.\w+\s*\([^)]*\+',
        r'aiohttp\.\w+\s*\([^)]*\+',
        r'http\.client\.HTTP\w*Connection\s*\([^)]*\+',
    ],
    secure_alternative='# Validate URL against allowlist before making request',
    references=[
        "https://owasp.org/www-community/attacks/Server_Side_Request_Forgery",
        "https://cwe.mitre.org/data/definitions/918.html",
    ],
)

# XXE patterns
XXE_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-611",
    cwe_name="XML External Entity (XXE)",
    category=VulnerabilityCategory.XXE,
    severity=Severity.HIGH,
    description="XML parser processes external entity references, potentially allowing file disclosure or SSRF.",
    mitigation="Disable external entity processing. Use defusedxml library for safe XML parsing.",
    patterns=[
        r'xml\.etree\.ElementTree\.parse\s*\(',
        r'xml\.etree\.ElementTree\.fromstring\s*\(',
        r'lxml\.etree\.parse\s*\(',
        r'lxml\.etree\.fromstring\s*\(',
        r'xml\.dom\.minidom\.parse\s*\(',
        r'xml\.sax\.parse\s*\(',
        r'xmlrpc\.',
    ],
    secure_alternative='import defusedxml.ElementTree as ET; tree = ET.parse(file)',
    references=[
        "https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing",
        "https://cwe.mitre.org/data/definitions/611.html",
    ],
    confidence=0.6,  # Lower confidence - may be used safely
)

# Insecure Random patterns
INSECURE_RANDOM_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-330",
    cwe_name="Use of Insufficiently Random Values",
    category=VulnerabilityCategory.CRYPTOGRAPHIC,
    severity=Severity.MEDIUM,
    description="Insecure random number generator used for security-sensitive operations.",
    mitigation="Use secrets module for security-sensitive random values. Use os.urandom() for cryptographic randomness.",
    patterns=[
        r'random\.random\s*\(',
        r'random\.randint\s*\(',
        r'random\.choice\s*\(',
        r'random\.randrange\s*\(',
        r'random\.shuffle\s*\(',
    ],
    secure_alternative='import secrets; token = secrets.token_urlsafe(32)',
    references=[
        "https://cwe.mitre.org/data/definitions/330.html",
    ],
    confidence=0.5,  # Only a problem if used for security
)

# Debug/Development patterns left in production
DEBUG_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-489",
    cwe_name="Active Debug Code",
    category=VulnerabilityCategory.SECURITY_MISCONFIG,
    severity=Severity.MEDIUM,
    description="Debug or development code is present that may expose sensitive information or functionality.",
    mitigation="Remove debug code before production. Use proper logging with appropriate levels.",
    patterns=[
        r'DEBUG\s*=\s*True',
        r'app\.debug\s*=\s*True',
        r'app\.run\s*\([^)]*debug\s*=\s*True',
        r'\.set_trace\s*\(',                        # pdb
        r'import\s+pdb',
        r'breakpoint\s*\(',
        r'print\s*\([^)]*password',
        r'print\s*\([^)]*secret',
        r'print\s*\([^)]*token',
    ],
    secure_alternative='DEBUG = os.environ.get("DEBUG", "false").lower() == "true"',
    references=[
        "https://cwe.mitre.org/data/definitions/489.html",
    ],
    confidence=0.7,
)

# LDAP Injection patterns
LDAP_INJECTION_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-90",
    cwe_name="LDAP Injection",
    category=VulnerabilityCategory.INJECTION,
    severity=Severity.HIGH,
    description="User input is concatenated into LDAP queries without proper escaping.",
    mitigation="Use LDAP escape functions for user input. Validate input against expected patterns.",
    patterns=[
        r'ldap\.search\s*\([^)]*%[sd]',
        r'ldap\.search_s\s*\([^)]*%[sd]',
        r'ldap3\.search\s*\([^)]*%[sd]',
        r'search_filter\s*=.*\+',
        r'ldap_filter\s*=.*\+',
    ],
    secure_alternative='from ldap3.utils.conv import escape_filter_chars; safe_input = escape_filter_chars(user_input)',
    references=[
        "https://owasp.org/www-community/attacks/LDAP_Injection",
        "https://cwe.mitre.org/data/definitions/90.html",
    ],
)

# Regex DoS patterns
REGEX_DOS_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-1333",
    cwe_name="Regular Expression Denial of Service (ReDoS)",
    category=VulnerabilityCategory.RESOURCE_MANAGEMENT,
    severity=Severity.MEDIUM,
    description="Regular expressions with nested quantifiers can cause catastrophic backtracking on malicious input.",
    mitigation="Avoid nested quantifiers. Use possessive quantifiers or atomic groups. Set regex timeouts.",
    patterns=[
        r're\.compile\s*\([^)]*\([^)]*\*\)[^)]*\*',       # (a*)*
        r're\.compile\s*\([^)]*\([^)]*\+\)[^)]*\+',       # (a+)+
        r're\.compile\s*\([^)]*\([^)]*\*\)[^)]*\+',       # (a*)+
        r're\.compile\s*\([^)]*\[[^\]]*\]\*[^)]*\*',      # [abc]*.*
    ],
    secure_alternative='import regex; pattern = regex.compile(r"pattern", timeout=5)',
    references=[
        "https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS",
        "https://cwe.mitre.org/data/definitions/1333.html",
    ],
    confidence=0.5,
)

# Timing Attack patterns
TIMING_ATTACK_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-208",
    cwe_name="Observable Timing Discrepancy",
    category=VulnerabilityCategory.CRYPTOGRAPHIC,
    severity=Severity.LOW,
    description="String comparisons for secrets use timing-vulnerable operations.",
    mitigation="Use constant-time comparison functions like hmac.compare_digest() or secrets.compare_digest().",
    patterns=[
        r'(password|token|secret|key)\s*==\s*',
        r'==\s*(password|token|secret|key)',
        r'(password|token|secret|key)\s*!=\s*',
        r'\.verify.*==',
    ],
    secure_alternative='import hmac; hmac.compare_digest(provided_token, expected_token)',
    references=[
        "https://cwe.mitre.org/data/definitions/208.html",
    ],
    confidence=0.6,
)

# Open Redirect patterns
OPEN_REDIRECT_PATTERNS = VulnerabilityPattern(
    cwe_id="CWE-601",
    cwe_name="Open Redirect",
    category=VulnerabilityCategory.BROKEN_ACCESS,
    severity=Severity.MEDIUM,
    description="User-controlled input is used in redirect URLs without validation.",
    mitigation="Validate redirect URLs against an allowlist. Use relative URLs where possible.",
    patterns=[
        r'redirect\s*\(\s*request\.',
        r'redirect\s*\([^)]*\+',
        r'HttpResponseRedirect\s*\(\s*request\.',
        r'Location\s*:\s*.*\+',
        r'return\s+redirect\s*\(.*url.*\)',
    ],
    secure_alternative='if url in ALLOWED_REDIRECTS: return redirect(url)',
    references=[
        "https://cwe.mitre.org/data/definitions/601.html",
        "https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html",
    ],
)

# All vulnerability patterns
ALL_VULNERABILITY_PATTERNS = [
    SQL_INJECTION_PATTERNS,
    COMMAND_INJECTION_PATTERNS,
    CODE_INJECTION_PATTERNS,
    PATH_TRAVERSAL_PATTERNS,
    HARDCODED_SECRETS_PATTERNS,
    INSECURE_DESERIALIZATION_PATTERNS,
    WEAK_CRYPTO_PATTERNS,
    XSS_PATTERNS,
    SSRF_PATTERNS,
    XXE_PATTERNS,
    INSECURE_RANDOM_PATTERNS,
    DEBUG_PATTERNS,
    LDAP_INJECTION_PATTERNS,
    REGEX_DOS_PATTERNS,
    TIMING_ATTACK_PATTERNS,
    OPEN_REDIRECT_PATTERNS,
]

# Security context detection patterns
SECURITY_CONTEXT_PATTERNS = {
    "handles_user_input": [
        r'request\.(args|form|data|json|files|values|params)',
        r'request\.get\s*\(',
        r'flask\.request\.',
        r'argv\b',
        r'sys\.stdin',
        r'input\s*\(',
        r'raw_input\s*\(',
        r'@app\.route',
        r'@api_view',
        r'@blueprint\.route',
    ],
    "handles_authentication": [
        r'(login|logout|authenticate|auth)\s*\(',
        r'session\[',
        r'@login_required',
        r'@requires_auth',
        r'check_password',
        r'verify_password',
        r'jwt\.',
        r'oauth',
        r'current_user',
    ],
    "handles_authorization": [
        r'@requires_role',
        r'@permission_required',
        r'\.has_perm\s*\(',
        r'user\.is_superuser',
        r'user\.is_staff',
        r'check_permission',
        r'authorize',
        r'access_control',
    ],
    "handles_cryptography": [
        r'from\s+cryptography',
        r'import\s+hashlib',
        r'from\s+Crypto',
        r'\.encrypt\s*\(',
        r'\.decrypt\s*\(',
        r'\.sign\s*\(',
        r'\.verify\s*\(',
        r'hmac\.',
        r'fernet',
        r'bcrypt',
        r'argon2',
    ],
    "handles_sensitive_data": [
        r'(password|passwd|pwd|secret|token|key|credential|ssn|credit_card)',
        r'(email|phone|address|birth)',
        r'PII',
        r'sensitive',
        r'confidential',
    ],
    "handles_file_operations": [
        r'\bopen\s*\(',
        r'pathlib\.Path',
        r'os\.path\.',
        r'shutil\.',
        r'with\s+open',
        r'\.read\s*\(',
        r'\.write\s*\(',
        r'os\.remove',
        r'os\.unlink',
    ],
    "handles_network": [
        r'requests\.',
        r'urllib',
        r'httpx\.',
        r'aiohttp\.',
        r'socket\.',
        r'http\.client',
        r'\.get\s*\(\s*["\']http',
        r'\.post\s*\(\s*["\']http',
        r'fetch\s*\(',
    ],
    "handles_database": [
        r'cursor\.',
        r'\.execute\s*\(',
        r'\.executemany\s*\(',
        r'sqlalchemy',
        r'django\.db',
        r'pymongo',
        r'redis\.',
        r'\.query\s*\(',
        r'SELECT\s+.*FROM',
        r'INSERT\s+INTO',
        r'UPDATE\s+.*SET',
        r'DELETE\s+FROM',
    ],
    "handles_subprocess": [
        r'subprocess\.',
        r'os\.system\s*\(',
        r'os\.popen',
        r'Popen\s*\(',
        r'\.run\s*\([^)]*shell',
        r'commands\.',
    ],
}

# Input sources patterns
INPUT_SOURCE_PATTERNS = {
    "request.args": r'request\.args',
    "request.form": r'request\.form',
    "request.json": r'request\.json',
    "request.data": r'request\.data',
    "request.files": r'request\.files',
    "sys.argv": r'sys\.argv',
    "stdin": r'sys\.stdin|\.read\s*\(\s*\)',
    "input()": r'\binput\s*\(',
    "environment": r'os\.environ',
    "file": r'open\s*\([^)]*\)\.read',
}

# Output sinks patterns
OUTPUT_SINK_PATTERNS = {
    "database": r'\.execute|\.executemany|\.query',
    "file": r'\.write\s*\(|open\s*\([^)]*["\']w',
    "response": r'return.*Response|make_response|jsonify|render_template',
    "subprocess": r'subprocess\.|os\.system|os\.popen',
    "network": r'requests\.\w+|urllib\.request|httpx\.|\.send\s*\(',
    "logging": r'logger?\.\w+\s*\(|print\s*\(',
}


# ======================================================================
# Static Security Profiler
# ======================================================================

class StaticSecurityProfiler:
    """
    Static code analyzer for security vulnerabilities.

    Uses pattern matching and AST analysis to detect potential security
    issues in source code without execution.
    """

    def __init__(self, repo_path: str):
        """Initialize the security profiler.

        Args:
            repo_path: Path to the repository root.
        """
        self.repo_path = Path(repo_path).resolve()
        self.logger = logger

    def profile_components(
        self,
        components: Dict[str, CodeComponent],
    ) -> Dict[str, SecurityProfile]:
        """Profile all components for security issues.

        Args:
            components: Dictionary of component ID to CodeComponent.

        Returns:
            Dictionary of component ID to SecurityProfile.
        """
        profiles: Dict[str, SecurityProfile] = {}
        total = len(components)

        for idx, (cid, component) in enumerate(components.items(), 1):
            try:
                self.logger.debug(
                    f"[{idx}/{total}] Security profiling: {component.name}"
                )
                profile = self.profile_component(component)
                profiles[cid] = profile

                if profile.has_vulnerabilities:
                    self.logger.info(
                        f"Found {len(profile.vulnerabilities)} vulnerabilities in {component.name}"
                    )

            except Exception as e:
                self.logger.warning(
                    f"Security profiling failed for {component.name}: {e}"
                )
                profiles[cid] = SecurityProfile()

        # Log summary
        total_vulns = sum(len(p.vulnerabilities) for p in profiles.values())
        components_with_vulns = sum(1 for p in profiles.values() if p.has_vulnerabilities)
        self.logger.info(
            f"Security profiling complete: {total_vulns} vulnerabilities "
            f"in {components_with_vulns}/{total} components"
        )

        return profiles

    def profile_component(self, component: CodeComponent) -> SecurityProfile:
        """Profile a single component for security issues.

        Args:
            component: The code component to analyze.

        Returns:
            SecurityProfile with detected vulnerabilities and context.
        """
        source = component.source_code or ""
        if not source.strip():
            return SecurityProfile()

        profile = SecurityProfile()

        # Detect security context
        self._detect_security_context(source, profile)

        # Detect vulnerabilities using patterns
        vulnerabilities = self._detect_pattern_vulnerabilities(source, component)
        profile.vulnerabilities.extend(vulnerabilities)

        # Python-specific AST analysis
        if component.language == "python":
            ast_vulns = self._detect_ast_vulnerabilities(source, component)
            profile.vulnerabilities.extend(ast_vulns)

        # Detect input sources and output sinks
        self._detect_data_flow(source, profile)

        # Detect positive security patterns
        self._detect_security_patterns(source, profile)

        # Calculate risk score
        profile.calculate_risk_score()

        # Set confidence based on analysis depth
        profile.confidence = 0.7 if component.language == "python" else 0.5

        return profile

    def _detect_security_context(
        self,
        source: str,
        profile: SecurityProfile,
    ) -> None:
        """Detect security-relevant context flags."""
        for flag, patterns in SECURITY_CONTEXT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, source, re.IGNORECASE):
                    setattr(profile, flag, True)
                    break

    def _detect_pattern_vulnerabilities(
        self,
        source: str,
        component: CodeComponent,
    ) -> List[VulnerabilitySignal]:
        """Detect vulnerabilities using regex patterns."""
        vulnerabilities = []
        lines = source.splitlines()

        for vuln_pattern in ALL_VULNERABILITY_PATTERNS:
            for pattern in vuln_pattern.patterns:
                try:
                    for match in re.finditer(pattern, source, re.IGNORECASE):
                        # Find line number
                        match_start = match.start()
                        line_num = source[:match_start].count('\n') + 1

                        # Get code snippet
                        if 0 < line_num <= len(lines):
                            snippet = lines[line_num - 1].strip()
                        else:
                            snippet = match.group(0)

                        vuln = VulnerabilitySignal(
                            cwe_id=vuln_pattern.cwe_id,
                            cwe_name=vuln_pattern.cwe_name,
                            category=vuln_pattern.category,
                            severity=vuln_pattern.severity,
                            description=vuln_pattern.description,
                            line_number=line_num,
                            code_snippet=snippet[:200],
                            mitigation=vuln_pattern.mitigation,
                            secure_alternative=vuln_pattern.secure_alternative,
                            detection_method="pattern",
                            confidence=vuln_pattern.confidence,
                            references=vuln_pattern.references,
                        )
                        vulnerabilities.append(vuln)

                except re.error as e:
                    self.logger.warning(f"Regex error for pattern {pattern}: {e}")
                    continue

        # Deduplicate by (cwe_id, line_number)
        seen = set()
        unique_vulns = []
        for v in vulnerabilities:
            key = (v.cwe_id, v.line_number)
            if key not in seen:
                seen.add(key)
                unique_vulns.append(v)

        return unique_vulns

    def _detect_ast_vulnerabilities(
        self,
        source: str,
        component: CodeComponent,
    ) -> List[VulnerabilitySignal]:
        """Detect vulnerabilities using Python AST analysis."""
        vulnerabilities = []

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return vulnerabilities

        for node in ast.walk(tree):
            # Check for assert statements (security issue in production)
            if isinstance(node, ast.Assert):
                # Check if it's used for security checks
                if self._is_security_assert(node):
                    vulnerabilities.append(VulnerabilitySignal(
                        cwe_id="CWE-617",
                        cwe_name="Reachable Assertion",
                        category=VulnerabilityCategory.SECURITY_MISCONFIG,
                        severity=Severity.LOW,
                        description="Assert statements can be disabled with -O flag, bypassing security checks.",
                        line_number=node.lineno,
                        mitigation="Use explicit if/raise for security checks, not assert.",
                        detection_method="ast",
                        confidence=0.6,
                    ))

            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                vulnerabilities.append(VulnerabilitySignal(
                    cwe_id="CWE-396",
                    cwe_name="Catching Overly Broad Exception",
                    category=VulnerabilityCategory.SECURITY_MISCONFIG,
                    severity=Severity.LOW,
                    description="Bare except clause may hide security-relevant exceptions.",
                    line_number=node.lineno,
                    mitigation="Catch specific exceptions instead of using bare except.",
                    detection_method="ast",
                    confidence=0.5,
                ))

            # Check for string formatting in dangerous functions
            if isinstance(node, ast.Call):
                vulns = self._check_dangerous_call(node, source)
                vulnerabilities.extend(vulns)

        return vulnerabilities

    def _is_security_assert(self, node: ast.Assert) -> bool:
        """Check if an assert statement is used for security."""
        if node.test:
            # Convert to string and check for security keywords
            try:
                source_seg = ast.unparse(node.test)
                security_keywords = ['auth', 'permission', 'role', 'user', 'valid', 'allowed']
                return any(kw in source_seg.lower() for kw in security_keywords)
            except Exception:
                pass
        return False

    def _check_dangerous_call(
        self,
        node: ast.Call,
        source: str,
    ) -> List[VulnerabilitySignal]:
        """Check if a function call is dangerous with user input."""
        vulnerabilities = []

        # Get function name
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # Check for format strings in SQL execute
        if func_name in ('execute', 'executemany'):
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):  # f-string
                    vulnerabilities.append(VulnerabilitySignal(
                        cwe_id="CWE-89",
                        cwe_name="SQL Injection",
                        category=VulnerabilityCategory.INJECTION,
                        severity=Severity.CRITICAL,
                        description="F-string used in SQL query - potential SQL injection.",
                        line_number=node.lineno,
                        mitigation="Use parameterized queries with placeholders.",
                        detection_method="ast",
                        confidence=0.95,
                    ))
                elif isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod)):
                    vulnerabilities.append(VulnerabilitySignal(
                        cwe_id="CWE-89",
                        cwe_name="SQL Injection",
                        category=VulnerabilityCategory.INJECTION,
                        severity=Severity.CRITICAL,
                        description="String concatenation/formatting in SQL query.",
                        line_number=node.lineno,
                        mitigation="Use parameterized queries with placeholders.",
                        detection_method="ast",
                        confidence=0.9,
                    ))

        return vulnerabilities

    def _detect_data_flow(
        self,
        source: str,
        profile: SecurityProfile,
    ) -> None:
        """Detect input sources and output sinks."""
        for source_name, pattern in INPUT_SOURCE_PATTERNS.items():
            if re.search(pattern, source, re.IGNORECASE):
                profile.input_sources.append(source_name)

        for sink_name, pattern in OUTPUT_SINK_PATTERNS.items():
            if re.search(pattern, source, re.IGNORECASE):
                profile.output_sinks.append(sink_name)

    def _detect_security_patterns(
        self,
        source: str,
        profile: SecurityProfile,
    ) -> None:
        """Detect positive security patterns (good practices)."""
        positive_patterns = {
            "uses_parameterized_queries": r'execute\s*\([^)]*,\s*\(',
            "uses_csrf_protection": r'@csrf_protect|csrf_token|CSRFProtect',
            "uses_rate_limiting": r'@ratelimit|@limiter|RateLimiter',
            "uses_input_validation": r'@validates|validator|Schema\(',
            "uses_output_encoding": r'escape\(|html\.escape|markupsafe\.escape',
            "uses_secure_headers": r'Strict-Transport-Security|Content-Security-Policy|X-Frame-Options',
            "uses_constant_time_compare": r'compare_digest|constant_time_compare|secure_compare',
            "uses_secrets_module": r'secrets\.(token|choice|randbelow)',
            "uses_safe_yaml": r'yaml\.safe_load|SafeLoader',
            "uses_defusedxml": r'defusedxml',
        }

        for pattern_name, pattern in positive_patterns.items():
            if re.search(pattern, source, re.IGNORECASE):
                profile.security_patterns.append(pattern_name)


# ======================================================================
# Convenience function
# ======================================================================

def profile_repository_security(repo_path: str) -> Dict[str, SecurityProfile]:
    """Profile all components in a repository for security issues.

    Convenience function that creates a profiler and runs analysis.

    Args:
        repo_path: Path to the repository.

    Returns:
        Dictionary of component ID to SecurityProfile.
    """
    profiler = StaticSecurityProfiler(repo_path)

    # Import here to avoid circular imports
    from backend.navigator.core.repository_parser import RepositoryParser

    parser = RepositoryParser(repo_path)
    components = parser.parse()

    return profiler.profile_components(components)
