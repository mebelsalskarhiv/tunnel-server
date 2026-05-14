"""
TunnelFlow API - Tunnel Management Routes
Create, update, delete, and manage tunnels.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..db.database import get_db_session
from ..db.models import User, Tunnel, UsageLog
from ..core.tunnel_manager import tunnel_manager
from .auth import get_current_user, TokenData

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])


class TunnelCreate(BaseModel):
    subdomain: str = Field(..., min_length=3, max_length=63)
    custom_domain: Optional[str] = None
    target_port: int = Field(default=80, ge=1, le=65535)
    protocol: str = Field(default="http", pattern="^(http|https|tls)$")


class TunnelResponse(BaseModel):
    id: str
    user_id: str
    subdomain: str
    custom_domain: Optional[str] = None
    target_port: int
    protocol: str
    is_active: bool
    public_url: str
    active_connections: int
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[TunnelResponse])
async def list_tunnels(
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Get all tunnels for the current user"""
    tunnels = tunnel_manager.get_user_tunnels(current_user.user_id)
    
    # If no tunnels in memory, fetch from database
    if not tunnels:
        db_tunnels = db.query(Tunnel).filter(
            Tunnel.user_id == current_user.user_id
        ).all()
        
        # Sync with tunnel manager
        for db_tunnel in db_tunnels:
            if db_tunnel.id not in tunnel_manager.tunnels:
                # Reconstruct tunnel in memory
                tunnel = tunnel_manager.tunnels.get(db_tunnel.id)
                if not tunnel:
                    continue
        
        tunnels = tunnel_manager.get_user_tunnels(current_user.user_id)
    
    return tunnels


@router.post("", response_model=TunnelResponse, status_code=status.HTTP_201_CREATED)
async def create_tunnel(
    tunnel_data: TunnelCreate,
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Create a new tunnel"""
    # Check user's plan limits
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = user.plan
    user_tunnel_count = len(tunnel_manager.get_user_tunnels(current_user.user_id))
    
    if user_tunnel_count >= plan.max_tunnels:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limit reached: maximum {plan.max_tunnels} tunnels"
        )
    
    # Validate subdomain format
    if not tunnel_data.subdomain.replace('-', '').replace('_', '').isalnum():
        raise HTTPException(
            status_code=400,
            detail="Subdomain can only contain letters, numbers, hyphens, and underscores"
        )
    
    try:
        # Create tunnel in tunnel manager
        tunnel = await tunnel_manager.create_tunnel(
            user_id=current_user.user_id,
            subdomain=tunnel_data.subdomain,
            custom_domain=tunnel_data.custom_domain,
            target_port=tunnel_data.target_port,
            protocol=tunnel_data.protocol
        )
        
        # Save to database
        db_tunnel = Tunnel(
            id=tunnel.id,
            user_id=current_user.user_id,
            subdomain=tunnel_data.subdomain,
            custom_domain=tunnel_data.custom_domain,
            target_port=tunnel_data.target_port,
            protocol=tunnel_data.protocol,
            token=tunnel.id  # Use tunnel ID as token for simplicity
        )
        db.add(db_tunnel)
        db.commit()
        db.refresh(db_tunnel)
        
        # Log creation
        usage_log = UsageLog(
            user_id=current_user.user_id,
            tunnel_id=tunnel.id,
            action="tunnel_created",
            details={"subdomain": tunnel_data.subdomain}
        )
        db.add(usage_log)
        db.commit()
        
        return tunnel
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tunnel_id}", response_model=TunnelResponse)
async def get_tunnel(
    tunnel_id: str,
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Get a specific tunnel by ID"""
    tunnel = tunnel_manager.tunnels.get(tunnel_id)
    
    if not tunnel:
        # Try database
        db_tunnel = db.query(Tunnel).filter(
            Tunnel.id == tunnel_id,
            Tunnel.user_id == current_user.user_id
        ).first()
        
        if not db_tunnel:
            raise HTTPException(status_code=404, detail="Tunnel not found")
        
        raise HTTPException(status_code=404, detail="Tunnel exists but is not active")
    
    if tunnel.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return tunnel


@router.delete("/{tunnel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tunnel(
    tunnel_id: str,
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Delete a tunnel"""
    tunnel = tunnel_manager.tunnels.get(tunnel_id)
    
    if not tunnel:
        db_tunnel = db.query(Tunnel).filter(
            Tunnel.id == tunnel_id,
            Tunnel.user_id == current_user.user_id
        ).first()
        
        if not db_tunnel:
            raise HTTPException(status_code=404, detail="Tunnel not found")
        
        # Delete from database
        db.delete(db_tunnel)
        db.commit()
        return
    
    if tunnel.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete from tunnel manager (this will close all connections)
    await tunnel_manager.delete_tunnel(tunnel_id)
    
    # Delete from database
    db_tunnel = db.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
    if db_tunnel:
        db.delete(db_tunnel)
        db.commit()
    
    # Log deletion
    usage_log = UsageLog(
        user_id=current_user.user_id,
        tunnel_id=tunnel_id,
        action="tunnel_deleted"
    )
    db.add(usage_log)
    db.commit()


@router.post("/{tunnel_id}/regenerate-token")
async def regenerate_token(
    tunnel_id: str,
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Regenerate tunnel authentication token"""
    tunnel = tunnel_manager.tunnels.get(tunnel_id)
    
    if not tunnel or tunnel.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Tunnel not found")
    
    # Generate new token
    import secrets
    new_token = secrets.token_urlsafe(32)
    
    # Update in database
    db_tunnel = db.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
    if db_tunnel:
        db_tunnel.token = new_token
        db.commit()
    
    # Log regeneration
    usage_log = UsageLog(
        user_id=current_user.user_id,
        tunnel_id=tunnel_id,
        action="token_regenerated"
    )
    db.add(usage_log)
    db.commit()
    
    return {"token": new_token}


@router.get("/{tunnel_id}/stats")
async def get_tunnel_stats(
    tunnel_id: str,
    current_user: TokenData = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Get statistics for a specific tunnel"""
    tunnel = tunnel_manager.tunnels.get(tunnel_id)
    
    if not tunnel or tunnel.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Tunnel not found")
    
    # Get stats from tunnel
    total_bytes_sent = sum(c.bytes_sent for c in tunnel.connections.values())
    total_bytes_received = sum(c.bytes_received for c in tunnel.connections.values())
    total_requests = sum(c.requests_count for c in tunnel.connections.values())
    
    # Get historical stats from database
    logs = db.query(UsageLog).filter(
        UsageLog.tunnel_id == tunnel_id
    ).order_by(UsageLog.timestamp.desc()).limit(100).all()
    
    return {
        "tunnel_id": tunnel_id,
        "is_active": tunnel.is_active,
        "active_connections": tunnel.active_connections,
        "current_session": {
            "bytes_sent": total_bytes_sent,
            "bytes_received": total_bytes_received,
            "requests": total_requests
        },
        "recent_activity": [
            {
                "timestamp": log.timestamp,
                "action": log.action,
                "details": log.details
            }
            for log in logs
        ]
    }
