from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.testcase import Testcase
from backend.app.schemas.testcase import TestcaseCreate, TestcaseUpdate, TestcaseOut
from backend.app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/testcases", tags=["用例管理"])


@router.post("/", response_model=ApiResponse[TestcaseOut])
async def create_testcase(data: TestcaseCreate, db: AsyncSession = Depends(get_db)):
    tc = Testcase(**data.model_dump())
    db.add(tc)
    await db.commit()
    await db.refresh(tc)
    return ApiResponse(data=TestcaseOut.model_validate(tc))


@router.get("/", response_model=ApiResponse[PageResult[TestcaseOut]])
async def list_testcases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    case_type: str | None = None,
    requirement_id: int | None = None,
    generation_job_id: int | None = None,
    priority: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Testcase)
    count_query = select(func.count(Testcase.id))

    filters = []
    if case_type:
        filters.append(Testcase.case_type == case_type)
    if requirement_id:
        filters.append(Testcase.requirement_id == requirement_id)
    if generation_job_id:
        filters.append(Testcase.generation_job_id == generation_job_id)
    if priority:
        filters.append(Testcase.priority == priority)
    if status:
        filters.append(Testcase.status == status)
    if keyword:
        filters.append(Testcase.title.contains(keyword))

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Testcase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [TestcaseOut.model_validate(tc) for tc in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/export")
async def export_testcases(
    case_type: str | None = None,
    requirement_id: int | None = None,
    generation_job_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import PlainTextResponse

    query = select(Testcase)
    if case_type:
        query = query.where(Testcase.case_type == case_type)
    if requirement_id:
        query = query.where(Testcase.requirement_id == requirement_id)
    if generation_job_id:
        query = query.where(Testcase.generation_job_id == generation_job_id)

    result = await db.execute(query.order_by(Testcase.id))
    testcases = result.scalars().all()

    md_parts = ["# 测试用例导出\n"]
    for tc in testcases:
        if tc.content_md:
            md_parts.append(tc.content_md)
        else:
            md_parts.append(f"## {tc.title}\n- 类型: {tc.case_type}\n- 优先级: {tc.priority}\n")
        md_parts.append("\n---\n")

    return PlainTextResponse(content="\n".join(md_parts), media_type="text/markdown")


@router.get("/{tc_id}", response_model=ApiResponse[TestcaseOut])
async def get_testcase(tc_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(Testcase, tc_id)
    if not tc:
        raise HTTPException(status_code=404, detail="用例不存在")
    return ApiResponse(data=TestcaseOut.model_validate(tc))


@router.put("/{tc_id}", response_model=ApiResponse[TestcaseOut])
async def update_testcase(tc_id: int, data: TestcaseUpdate, db: AsyncSession = Depends(get_db)):
    tc = await db.get(Testcase, tc_id)
    if not tc:
        raise HTTPException(status_code=404, detail="用例不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(tc, key, value)
    await db.commit()
    await db.refresh(tc)
    return ApiResponse(data=TestcaseOut.model_validate(tc))


@router.delete("/{tc_id}", response_model=ApiResponse)
async def delete_testcase(tc_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(Testcase, tc_id)
    if not tc:
        raise HTTPException(status_code=404, detail="用例不存在")
    await db.delete(tc)
    await db.commit()
    return ApiResponse(message="删除成功")
