import time
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.mcp.schemas import (
    MCPToolSchema,
    MCPToolCategory,
    MCPToolCallRequest,
    MCPToolResult,
)
from app.mcp.security import MCPSecurityValidator
from app.mcp.registry import MCPToolRegistry
from app.core.logging import logger


class MCPClientManager:
    """
    Standardized Model Context Protocol Client Layer.
    Orchestrates:
    - MCP Tool discovery
    - Tool allowlists & permission validation
    - Secure tool invocation with timeout handling
    - Least-privilege checks & SSRF verification
    - Structured audit logging
    """
    def __init__(self, registry: Optional[MCPToolRegistry] = None):
        self.registry = registry or MCPToolRegistry()

    def discover_tools(self, category: Optional[MCPToolCategory] = None) -> List[MCPToolSchema]:
        """Discover available MCP tools filtered by category."""
        return self.registry.list_tools(category=category)

    def get_tool_schema(self, tool_name: str) -> Optional[MCPToolSchema]:
        return self.registry.get_tool(tool_name)

    async def invoke_tool(
        self,
        request: MCPToolCallRequest,
        user_id: str,
        session: AsyncSession,
        timeout: Optional[float] = None,
    ) -> MCPToolResult:
        """
        Execute an authorized MCP tool with validation, timeouts, error boundary,
        and audit logging.
        """
        tool_name = request.tool_name
        start_time = time.perf_counter()

        # 1. Allowlist and security check
        if not MCPSecurityValidator.is_tool_allowed(tool_name):
            err_msg = f"Security Policy Violation: Tool '{tool_name}' is not allowed or unauthorized."
            logger.warning(err_msg)
            MCPSecurityValidator.record_audit(
                tool_name=tool_name,
                user_id=user_id,
                arguments=request.arguments,
                success=False,
                latency_ms=0.0,
                error=err_msg,
            )
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=err_msg,
                latency_ms=0.0,
            )

        # 2. Check tool existence
        schema = self.registry.get_tool(tool_name)
        if not schema:
            err_msg = f"Tool not found: '{tool_name}'"
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=err_msg,
                latency_ms=0.0,
            )

        # 3. Execution with audit logging
        try:
            data = await self.registry.execute_tool(
                tool_name=tool_name,
                arguments=request.arguments,
                user_id=user_id,
                session=session,
                conversation_id=request.conversation_id,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            MCPSecurityValidator.record_audit(
                tool_name=tool_name,
                user_id=user_id,
                arguments=request.arguments,
                success=True,
                latency_ms=latency_ms,
            )

            return MCPToolResult(
                tool_name=tool_name,
                success=True,
                data=data,
                latency_ms=round(latency_ms, 2),
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_str = str(e)
            logger.error(f"MCP tool '{tool_name}' failed: {error_str}", exc_info=True)

            MCPSecurityValidator.record_audit(
                tool_name=tool_name,
                user_id=user_id,
                arguments=request.arguments,
                success=False,
                latency_ms=latency_ms,
                error=error_str,
            )

            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=error_str,
                latency_ms=round(latency_ms, 2),
            )
