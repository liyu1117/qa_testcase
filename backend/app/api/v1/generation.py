from datetime import datetime

import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.app.models.generation_job import GenerationJob
from backend.app.models.requirement import Requirement
from backend.app.schemas.generation import GenerationJobCreate, GenerationJobOut
from backend.app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/generation/jobs", tags=["用例生成"])


async def _run_generation_pipeline(job_id: int):
    """后台执行生成 pipeline"""
    from backend.database import async_session
    from backend.app.core.pipeline.functional_pipeline import FunctionalPipeline
    from backend.app.core.pipeline.ui_pipeline import UIPipeline
    from backend.app.core.pipeline.api_pipeline import ApiPipeline

    async with async_session() as db:
        job = await db.get(GenerationJob, job_id)
        if not job:
            return

        pipeline_map = {
            "functional": FunctionalPipeline,
            "ui": UIPipeline,
            "api": ApiPipeline,
        }
        pipeline_cls = pipeline_map.get(job.job_type)
        if not pipeline_cls:
            job.status = "failed"
            job.error_message = f"不支持的任务类型: {job.job_type}"
            await db.commit()
            return

        pipeline = pipeline_cls(db)
        await pipeline.run(job_id)


@router.post("/", response_model=ApiResponse[GenerationJobOut])
async def create_generation_job(
    data: GenerationJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # 校验需求存在
    req = await db.get(Requirement, data.requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    job = GenerationJob(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 后台异步执行 pipeline
    background_tasks.add_task(_run_generation_pipeline, job.id)

    return ApiResponse(data=GenerationJobOut.model_validate(job))


@router.get("/", response_model=ApiResponse[PageResult[GenerationJobOut]])
async def list_generation_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job_type: str | None = None,
    status: str | None = None,
    requirement_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(GenerationJob)
    count_query = select(func.count(GenerationJob.id))

    filters = []
    if job_type:
        filters.append(GenerationJob.job_type == job_type)
    if status:
        filters.append(GenerationJob.status == status)
    if requirement_id:
        filters.append(GenerationJob.requirement_id == requirement_id)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(GenerationJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [GenerationJobOut.model_validate(j) for j in result.scalars().all()]

    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.get("/{job_id}", response_model=ApiResponse[GenerationJobOut])
async def get_generation_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return ApiResponse(data=GenerationJobOut.model_validate(job))


# @router.get("/{job_id}/download")
# async def download_generation_result(
#     job_id: int,
#     format: str = Query("md", description="下载格式: md 或 xmind"),
#     db: AsyncSession = Depends(get_db),
# ):
#     if format not in ("md", "xmind"):
#         raise HTTPException(status_code=400, detail="不支持的格式，可选: md, xmind")
#
#     job = await db.get(GenerationJob, job_id)
#     if not job:
#         raise HTTPException(status_code=404, detail="生成任务不存在")
#     if not job.result_file_path:
#         raise HTTPException(status_code=400, detail="生成结果文件不存在")
#
#     from pathlib import Path
#     file_path = Path(job.result_file_path)
#     if not file_path.exists():
#         raise HTTPException(status_code=404, detail="文件未找到")
#
#     if format == "xmind":
#         from backend.app.core.xmind_converter import convert_md_to_xmind
#         md_content = file_path.read_text(encoding="utf-8")
#         xmind_bytes = convert_md_to_xmind(md_content, job.job_type or "functional", job.name or "测试用例")
#         filename = file_path.stem + ".xmind"
#         return Response(
#             content=xmind_bytes,
#             media_type="application/octet-stream",
#             headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#         )
#
#     return FileResponse(
#         path=str(file_path),
#         filename=file_path.name,
#         media_type="text/markdown",
#     )


from pathlib import Path

def _build_export_content(job: GenerationJob, format: str) -> tuple[bytes, str, str]:
    file_path = Path(job.result_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件未找到")

    if format == "xmind":
        from backend.app.core.xmind_converter import convert_md_to_xmind

        md_content = file_path.read_text(encoding="utf-8")
        xmind_bytes = convert_md_to_xmind(
            md_content,
            job.job_type or "functional",
            job.name or "测试用例",
        )
        filename = file_path.stem + ".xmind"
        return xmind_bytes, filename, "application/octet-stream"

    return file_path.read_bytes(), file_path.name, "text/markdown"


@router.get("/{job_id}/download")
async def download_generation_result(
    job_id: int,
    format: str = Query("md", description="下载格式: md 或 xmind"),
    db: AsyncSession = Depends(get_db),
):
    if format not in ("md", "xmind"):
        raise HTTPException(status_code=400, detail="不支持的格式，可选: md, xmind")

    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    if not job.result_file_path:
        raise HTTPException(status_code=400, detail="生成结果文件不存在")

    content_bytes, filename, media_type = _build_export_content(job, format)

    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.post("/{job_id}/upload")
async def upload_generation_result_to_dingtalk(
    job_id: int,
    format: str = Query("md", description="上传格式: md 或 xmind"),
    db: AsyncSession = Depends(get_db),
):
    if format not in ("md", "xmind"):
        raise HTTPException(status_code=400, detail="不支持的格式，可选: md, xmind")

    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    if not job.result_file_path:
        raise HTTPException(status_code=400, detail="生成结果文件不存在")

    from pathlib import Path
    file_path = Path(job.result_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件未找到")

    from backend.app.core.doc_reader.dingtalk_mcp_uploader import DingtalkMCPUploader

    uploader = DingtalkMCPUploader()

    try:
        if format == "xmind":
            content_bytes, filename, _ = _build_export_content(job, "xmind")
            dingtalk_url = await uploader.upload_file(filename, content_bytes)
        else:
            content_bytes, filename, _ = _build_export_content(job, "md")
            md_text = content_bytes.decode("utf-8")
            dingtalk_url = await uploader.upload_markdown_as_doc(filename, md_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传到钉钉失败: {str(e)}")

    if not dingtalk_url:
        raise HTTPException(status_code=500, detail="上传到钉钉失败：未返回文档链接")

    # 上传成功后发送钉钉通知
    try:
        from backend.app.core.notifier.dingtalk import DingtalkNotifier

        notifier = DingtalkNotifier(db)
        await notifier.notify_upload_done(
                job_name=job.name,
                job_id=job.id,
                dingtalk_url=dingtalk_url,
                upload_format=format,
                job_type=job.job_type or "",
        )
    except Exception as notify_err:
        logger.warning(f"上传成功通知发送失败: {notify_err}")

    return ApiResponse(data={
        "success": True,
        "file_name": filename,
        "format": format,
        "dingtalk_url": dingtalk_url,
    })