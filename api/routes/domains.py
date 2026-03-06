"""
Domain config CRUD endpoints.
"""
import uuid
from fastapi import APIRouter, HTTPException

from api.db import get_domain, list_domains, insert_domain
from api.models import DomainCreate, DomainResponse

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=list[DomainResponse])
def get_domains():
    """List all available domain configs (presets + custom)."""
    return list_domains()


@router.get("/{domain_id}", response_model=DomainResponse)
def get_domain_by_id(domain_id: str):
    domain = get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    return domain


@router.post("", response_model=DomainResponse, status_code=201)
def create_domain(body: DomainCreate):
    """Create a custom domain config."""
    domain_id = body.name.lower().replace(" ", "_")
    if get_domain(domain_id):
        raise HTTPException(status_code=409, detail=f"Domain '{domain_id}' already exists")
    insert_domain(domain_id, body.name, body.aspects, body.description)
    return get_domain(domain_id)
