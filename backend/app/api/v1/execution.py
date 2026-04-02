from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.execution_job import ExecutionJob
from backend.app.models.execution_result import ExecutionResult
from backend.app.models.generation_job import GenerationJob
from backend.app.models.testcase import Testcase
from backend.app.schemas.execution import ExecutionJobCreate, ExecutionJobOut, ExecutionResultOut
from backend.app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/execution/jobs", tags=["用例执行"])


async def _run_execution(job_id: int):
    """后台执行测试用例"""
    from backend.database import async_session
    from backend.app.core.executor.engine import ExecutionEngine

    async with async_session() as db:
        engine = ExecutionEngine(db)
        await engine.run(job_id)


@router.post("/", response_model=ApiResponse[ExecutionJobOut])
async def create_execution_job(
    data: ExecutionJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # 校验生成任务存在且为接口测试类型
    gen_job = await db.get(GenerationJob, data.generation_job_id)
    if not gen_job:
        raise HTTPException(status_code=404, detail=f"生成任务 {data.generation_job_id} 不存在")
    if gen_job.job_type != "api":
        raise HTTPException(status_code=400, detail="仅支持接口测试类型的生成任务")
    if gen_job.status != "success":
        raise HTTPException(status_code=400, detail="生成任务尚未成功完成，无法执行")

    # 查找该生成任务下所有的 api 测试用例
    stmt = (
        select(Testcase)
        .where(Testcase.generation_job_id == data.generation_job_id)
        .where(Testcase.case_type == "api")
        .order_by(Testcase.id)
    )
    result = await db.execute(stmt)
    testcases = list(result.scalars().all())

    if not testcases:
        raise HTTPException(status_code=400, detail="该生成任务下没有接口测试用例")

    job = ExecutionJob(
        name=data.name,
        generation_job_id=data.generation_job_id,
        execution_mode=data.execution_mode,
        env_config=data.env_config,
        total_cases=len(testcases),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 为每个 testcase 创建执行结果记录（按 ID 顺序，保证与 pytest 脚本函数顺序一致）
    for tc in testcases:
        result = ExecutionResult(execution_job_id=job.id, testcase_id=tc.id, status="pending")
        db.add(result)
    await db.commit()

    # 后台异步执行
    background_tasks.add_task(_run_execution, job.id)

    return ApiResponse(data=ExecutionJobOut.model_validate(job))


@router.get("/", response_model=ApiResponse[PageResult[ExecutionJobOut]])
async def list_execution_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ExecutionJob)
    count_query = select(func.count(ExecutionJob.id))

    if status:
        query = query.where(ExecutionJob.status == status)
        count_query = count_query.where(ExecutionJob.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(ExecutionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [ExecutionJobOut.model_validate(j) for j in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/{job_id}", response_model=ApiResponse[ExecutionJobOut])
async def get_execution_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ExecutionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="执行任务不存在")
    return ApiResponse(data=ExecutionJobOut.model_validate(job))


@router.get("/{job_id}/results", response_model=ApiResponse[PageResult[ExecutionResultOut]])
async def list_execution_results(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ExecutionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="执行任务不存在")

    query = select(ExecutionResult).where(ExecutionResult.execution_job_id == job_id)
    count_query = select(func.count(ExecutionResult.id)).where(ExecutionResult.execution_job_id == job_id)

    if status:
        query = query.where(ExecutionResult.status == status)
        count_query = count_query.where(ExecutionResult.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(ExecutionResult.id).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    exec_results = list(result.scalars().all())

    # 批量获取关联的 testcase title
    tc_ids = [r.testcase_id for r in exec_results]
    tc_map: dict[int, str] = {}
    if tc_ids:
        tc_stmt = select(Testcase.id, Testcase.title).where(Testcase.id.in_(tc_ids))
        tc_result = await db.execute(tc_stmt)
        tc_map = {row[0]: row[1] for row in tc_result.all()}

    items = []
    for r in exec_results:
        out = ExecutionResultOut.model_validate(r)
        out.testcase_title = tc_map.get(r.testcase_id)
        items.append(out)

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/{job_id}/report")
async def get_execution_report(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ExecutionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="执行任务不存在")
    if not job.report_path:
        raise HTTPException(status_code=400, detail="执行报告尚未生成")

    from pathlib import Path
    from fastapi.responses import FileResponse
    file_path = Path(job.report_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="报告文件未找到")

    return FileResponse(path=str(file_path), filename=file_path.name, media_type="text/html")


@router.get("/{job_id}/pytest-script")
async def get_pytest_script(job_id: int, db: AsyncSession = Depends(get_db)):
    """获取执行任务关联的 pytest 脚本内容"""
    job = await db.get(ExecutionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="执行任务不存在")

    # 直接通过 generation_job_id 查找脚本
    if job.generation_job_id:
        gen_job = await db.get(GenerationJob, job.generation_job_id)
        if gen_job and gen_job.pytest_script_content:
            return ApiResponse(data={
                "script_content": gen_job.pytest_script_content,
                "script_path": gen_job.pytest_script_path,
                "generation_job_id": gen_job.id,
            })

    # 兜底: 通过 ExecutionResult -> Testcase -> GenerationJob 查找（兼容旧数据）
    stmt = (
        select(GenerationJob)
        .join(Testcase, Testcase.generation_job_id == GenerationJob.id)
        .join(ExecutionResult, ExecutionResult.testcase_id == Testcase.id)
        .where(ExecutionResult.execution_job_id == job_id)
        .where(GenerationJob.pytest_script_content.is_not(None))
        .limit(1)
    )
    result = await db.execute(stmt)
    gen_job = result.scalar_one_or_none()

    if not gen_job or not gen_job.pytest_script_content:
        raise HTTPException(status_code=404, detail="未找到 pytest 脚本")

    return ApiResponse(data={
        "script_content": gen_job.pytest_script_content,
        "script_path": gen_job.pytest_script_path,
        "generation_job_id": gen_job.id,
    })


@router.get("/{job_id}/pytest-script/download")
async def download_pytest_script(job_id: int, db: AsyncSession = Depends(get_db)):
    """下载 pytest 脚本文件"""
    job = await db.get(ExecutionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="执行任务不存在")

    script_content = None

    # 直接通过 generation_job_id 查找
    if job.generation_job_id:
        gen_job = await db.get(GenerationJob, job.generation_job_id)
        if gen_job:
            script_content = gen_job.pytest_script_content

    # 兜底: 通过关系链查找（兼容旧数据）
    if not script_content:
        stmt = (
            select(GenerationJob.pytest_script_content)
            .join(Testcase, Testcase.generation_job_id == GenerationJob.id)
            .join(ExecutionResult, ExecutionResult.testcase_id == Testcase.id)
            .where(ExecutionResult.execution_job_id == job_id)
            .where(GenerationJob.pytest_script_content.is_not(None))
            .limit(1)
        )
        result = await db.execute(stmt)
        script_content = result.scalar_one_or_none()

    if not script_content:
        raise HTTPException(status_code=404, detail="未找到 pytest 脚本")

    return Response(
        content=script_content,
        media_type="text/x-python",
        headers={
            "Content-Disposition": f'attachment; filename="test_execution_{job_id}.py"'
        },
    )
