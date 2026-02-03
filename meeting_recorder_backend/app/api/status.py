from fastapi import APIRouter
from celery.result import AsyncResult
from app.celery_app import celery_app

router = APIRouter(prefix="/status", tags=["Status"])

@router.get("/{task_id}")
def get_task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return {"status": "processing"}

    if task.state == "STARTED":
        return {"status": "transcribing"}

    if task.state == "SUCCESS":
        return {
            "status": "completed",
            "result": task.result
        }

    if task.state == "FAILURE":
        return {
            "status": "failed",
            "error": str(task.info)
        }

    return {"status": task.state}
