from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.requirement import Requirement
from backend.app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementOut
from backend.app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/requirements", tags=["需求管理"])


@router.post("/", response_model=ApiResponse[RequirementOut])
async def create_requirement(data: RequirementCreate, db: AsyncSession = Depends(get_db)):
    req = Requirement(**data.model_dump())
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return ApiResponse(data=RequirementOut.model_validate(req))


@router.get("/", response_model=ApiResponse[PageResult[RequirementOut]])
async def list_requirements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Requirement)
    count_query = select(func.count(Requirement.id))

    if status:
        query = query.where(Requirement.status == status)
        count_query = count_query.where(Requirement.status == status)
    if keyword:
        query = query.where(Requirement.title.contains(keyword))
        count_query = count_query.where(Requirement.title.contains(keyword))

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Requirement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [RequirementOut.model_validate(r) for r in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/{req_id}", response_model=ApiResponse[RequirementOut])
async def get_requirement(req_id: int, db: AsyncSession = Depends(get_db)):
    req = await db.get(Requirement, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")
    return ApiResponse(data=RequirementOut.model_validate(req))


@router.put("/{req_id}", response_model=ApiResponse[RequirementOut])
async def update_requirement(req_id: int, data: RequirementUpdate, db: AsyncSession = Depends(get_db)):
    req = await db.get(Requirement, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(req, key, value)
    await db.commit()
    await db.refresh(req)
    return ApiResponse(data=RequirementOut.model_validate(req))


@router.delete("/{req_id}", response_model=ApiResponse)
async def delete_requirement(req_id: int, db: AsyncSession = Depends(get_db)):
    req = await db.get(Requirement, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")
    await db.delete(req)
    await db.commit()
    return ApiResponse(message="删除成功")
