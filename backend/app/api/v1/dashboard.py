from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.requirement import Requirement
from backend.app.models.testcase import Testcase
from backend.app.models.generation_job import GenerationJob
from backend.app.models.execution_job import ExecutionJob
from backend.app.schemas.common import ApiResponse

from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


class DashboardStats(BaseModel):
    total_requirements: int
    total_testcases: int
    testcases_by_type: dict[str, int]
    testcases_by_priority: dict[str, int]
    total_generation_jobs: int
    generation_jobs_by_status: dict[str, int]
    total_execution_jobs: int
    execution_pass_rate: float | None
    recent_generation_jobs: list[dict]
    recent_execution_jobs: list[dict]


@router.get("/stats", response_model=ApiResponse[DashboardStats])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # 需求总数
    total_req = (await db.execute(select(func.count(Requirement.id)))).scalar() or 0

    # 用例总数
    total_tc = (await db.execute(select(func.count(Testcase.id)))).scalar() or 0

    # 用例按类型分布
    tc_by_type = {}
    for case_type in ["functional", "ui", "api"]:
        count = (await db.execute(
            select(func.count(Testcase.id)).where(Testcase.case_type == case_type)
        )).scalar() or 0
        tc_by_type[case_type] = count

    # 用例按优先级分布
    tc_by_priority = {}
    for priority in ["P0", "P1", "P2", "P3"]:
        count = (await db.execute(
            select(func.count(Testcase.id)).where(Testcase.priority == priority)
        )).scalar() or 0
        tc_by_priority[priority] = count

    # 生成任务统计
    total_gen = (await db.execute(select(func.count(GenerationJob.id)))).scalar() or 0
    gen_by_status = {}
    for status in ["pending", "running", "success", "failed"]:
        count = (await db.execute(
            select(func.count(GenerationJob.id)).where(GenerationJob.status == status)
        )).scalar() or 0
        gen_by_status[status] = count

    # 执行任务统计
    total_exec = (await db.execute(select(func.count(ExecutionJob.id)))).scalar() or 0

    # 执行通过率
    exec_pass_rate = None
    result = await db.execute(
        select(func.sum(ExecutionJob.passed), func.sum(ExecutionJob.total_cases))
    )
    row = result.one_or_none()
    if row and row[1] and row[1] > 0:
        exec_pass_rate = round(row[0] / row[1] * 100, 2)

    # 最近生成任务
    recent_gen = await db.execute(
        select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(5)
    )
    recent_gen_list = [
        {"id": j.id, "name": j.name, "job_type": j.job_type, "status": j.status, "progress": j.progress}
        for j in recent_gen.scalars().all()
    ]

    # 最近执行任务
    recent_exec = await db.execute(
        select(ExecutionJob).order_by(ExecutionJob.created_at.desc()).limit(5)
    )
    recent_exec_list = [
        {
            "id": j.id, "name": j.name, "status": j.status,
            "total_cases": j.total_cases, "passed": j.passed, "failed": j.failed,
        }
        for j in recent_exec.scalars().all()
    ]

    return ApiResponse(data=DashboardStats(
        total_requirements=total_req,
        total_testcases=total_tc,
        testcases_by_type=tc_by_type,
        testcases_by_priority=tc_by_priority,
        total_generation_jobs=total_gen,
        generation_jobs_by_status=gen_by_status,
        total_execution_jobs=total_exec,
        execution_pass_rate=exec_pass_rate,
        recent_generation_jobs=recent_gen_list,
        recent_execution_jobs=recent_exec_list,
    ))
