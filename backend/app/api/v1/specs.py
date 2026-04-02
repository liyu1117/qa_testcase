from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.testcase_spec import TestcaseSpec
from backend.app.schemas.testcase import TestcaseSpecCreate, TestcaseSpecUpdate, TestcaseSpecOut
from backend.app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/specs", tags=["用例规范"])


@router.post("/", response_model=ApiResponse[TestcaseSpecOut])
async def create_spec(data: TestcaseSpecCreate, db: AsyncSession = Depends(get_db)):
    # 如果设为默认，先将同类型其他规范的 is_default 置为 False
    if data.is_default:
        stmt = select(TestcaseSpec).where(
            TestcaseSpec.spec_type == data.spec_type,
            TestcaseSpec.is_default == True,
        )
        result = await db.execute(stmt)
        for spec in result.scalars().all():
            spec.is_default = False

    spec = TestcaseSpec(**data.model_dump())
    db.add(spec)
    await db.commit()
    await db.refresh(spec)
    return ApiResponse(data=TestcaseSpecOut.model_validate(spec))


@router.get("/", response_model=ApiResponse[PageResult[TestcaseSpecOut]])
async def list_specs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    spec_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(TestcaseSpec)
    count_query = select(func.count(TestcaseSpec.id))

    if spec_type:
        query = query.where(TestcaseSpec.spec_type == spec_type)
        count_query = count_query.where(TestcaseSpec.spec_type == spec_type)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(TestcaseSpec.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [TestcaseSpecOut.model_validate(s) for s in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/{spec_id}", response_model=ApiResponse[TestcaseSpecOut])
async def get_spec(spec_id: int, db: AsyncSession = Depends(get_db)):
    spec = await db.get(TestcaseSpec, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="规范不存在")
    return ApiResponse(data=TestcaseSpecOut.model_validate(spec))


@router.put("/{spec_id}", response_model=ApiResponse[TestcaseSpecOut])
async def update_spec(spec_id: int, data: TestcaseSpecUpdate, db: AsyncSession = Depends(get_db)):
    spec = await db.get(TestcaseSpec, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="规范不存在")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default"):
        spec_type = update_data.get("spec_type", spec.spec_type)
        stmt = select(TestcaseSpec).where(
            TestcaseSpec.spec_type == spec_type,
            TestcaseSpec.is_default == True,
            TestcaseSpec.id != spec_id,
        )
        result = await db.execute(stmt)
        for s in result.scalars().all():
            s.is_default = False

    for key, value in update_data.items():
        setattr(spec, key, value)
    await db.commit()
    await db.refresh(spec)
    return ApiResponse(data=TestcaseSpecOut.model_validate(spec))


@router.delete("/{spec_id}", response_model=ApiResponse)
async def delete_spec(spec_id: int, db: AsyncSession = Depends(get_db)):
    spec = await db.get(TestcaseSpec, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="规范不存在")
    await db.delete(spec)
    await db.commit()
    return ApiResponse(message="删除成功")
