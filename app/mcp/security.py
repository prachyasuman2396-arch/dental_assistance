import ipaddress
import re
import urllib.parse
from typing import Dict, Any, List, Optional
from collections import deque
from app.mcp.schemas import MCPAuditLog
from app.core.logging import logger

# Configurable Allowlist of Permitted MCP Tools
DEFAULT_ALLOWED_TOOLS = {
    "web_search",
    "fetch_web_page",
    "get_source_metadata",
    "pubmed_search",
    "crossref_metadata",
    "europe_pmc_search",
    "generate_quiz",
    "generate_flashcards",
    "generate_study_plan",
    "generate_revision_summary",
    "get_study_notes",
    "search_documents",
    "search_study_memories",
    "get_conversation_context",
}

# In-memory circular buffer for tool audit logs (last 1000 executions)
_GLOBAL_AUDIT_LOGS = deque(maxlen=1000)


class MCPSecurityValidator:
    """
    Enforces least-privilege tool execution, SSRF validation,
    input sanitization, prompt injection defense, and auditing.
    """

    @staticmethod
    def is_tool_allowed(tool_name: str, allowed_tools: Optional[set] = None) -> bool:
        allowlist = allowed_tools or DEFAULT_ALLOWED_TOOLS
        return tool_name in allowlist

    @staticmethod
    def validate_url_safe(url: str) -> bool:
        """
        SSRF Protection: Ensure URL is standard HTTP(S) and does not point to
        internal/loopback addresses, metadata services (AWS 169.254.169.254), or local networks.
        """
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            # Disallow localhost and special hostnames
            if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
                return False

            # Check if IP address is private/reserved
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
            except ValueError:
                # Hostname is a domain name, not an IP literal
                pass

            return True
        except Exception:
            return False

    @staticmethod
    def sanitize_output(text: str) -> str:
        """
        Sanitize tool text output to mitigate prompt injection and credential leakage.
        """
        if not text:
            return ""

        # Remove API keys or tokens if accidentally exposed
        sanitized = re.sub(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]+['\"]", "[REDACTED_CREDENTIAL]", text)

        # Neutralize common instruction-override vectors
        sanitized = re.sub(
            r"(?i)(ignore previous instructions|you are now a|system override:|disregard the above)",
            "[REDACTED_PROMPT_INJECTION_ATTEMPT]",
            sanitized,
        )
        return sanitized

    @staticmethod
    def redact_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive keys from tool call argument logs."""
        sensitive_keys = {"password", "token", "secret", "api_key", "authorization"}
        redacted = {}
        for k, v in args.items():
            if any(s in k.lower() for s in sensitive_keys):
                redacted[k] = "******"
            elif isinstance(v, str) and len(v) > 200:
                redacted[k] = v[:200] + "... [truncated]"
            else:
                redacted[k] = v
        return redacted

    @classmethod
    def record_audit(
        cls,
        tool_name: str,
        user_id: str,
        arguments: Dict[str, Any],
        success: bool,
        latency_ms: float,
        error: Optional[str] = None,
    ) -> MCPAuditLog:
        """Log tool execution to structured audit memory."""
        redacted = cls.redact_arguments(arguments)
        entry = MCPAuditLog(
            tool_name=tool_name,
            user_id=user_id,
            arguments_redacted=redacted,
            success=success,
            error=error,
            latency_ms=round(latency_ms, 2),
        )
        _GLOBAL_AUDIT_LOGS.append(entry)
        logger.info(
            f"MCP Audit: user={user_id} tool={tool_name} success={success} latency={latency_ms:.2f}ms"
        )
        return entry

    @staticmethod
    def get_audit_logs(user_id: Optional[str] = None, limit: int = 50) -> List[MCPAuditLog]:
        logs = list(_GLOBAL_AUDIT_LOGS)
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        return logs[-limit:]
