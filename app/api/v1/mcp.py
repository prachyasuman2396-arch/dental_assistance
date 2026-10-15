from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.mcp.schemas import (
    MCPToolSchema,
    MCPToolCategory,
    MCPToolCallRequest,
    MCPToolResult,
    MCPAuditLog,
)
from app.mcp.client import MCPClientManager
from app.mcp.security import MCPSecurityValidator

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])
mcp_client = MCPClientManager()


@router.get("/tools", response_model=List[MCPToolSchema])
async def list_mcp_tools(
    category: Optional[MCPToolCategory] = Query(None, description="Filter by tool category"),
    current_user: User = Depends(get_current_user),
):
    """
    Discover all available MCP tools, input schemas, and permission requirements.
    """
    return mcp_client.discover_tools(category=category)


@router.post("/execute", response_model=MCPToolResult)
async def execute_mcp_tool(
    request: MCPToolCallRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Execute a permitted MCP tool with input validation, SSRF defense,
    least-privilege checks, and structured audit logging.
    """
    result = await mcp_client.invoke_tool(
        request=request,
        user_id=current_user.id,
        session=session,
    )
    if not result.success and "Security Policy Violation" in (result.error or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.error,
        )
    return result


@router.get("/audit", response_model=List[MCPAuditLog])
async def get_mcp_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve security audit logs for MCP tool executions for the current user.
    """
    return MCPSecurityValidator.get_audit_logs(user_id=current_user.id, limit=limit)
