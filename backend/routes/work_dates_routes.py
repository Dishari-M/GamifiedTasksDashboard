from fastapi import APIRouter, Depends, HTTPException, status

from schemas.work_dates import WorkingTodayRequest
from services.user_context import current_oracle_user_id
from services.work_dates_service import (
    RowVersionConflictError,
    TaskNotFoundError,
    WorkDateDatabaseError,
    set_working_today,
)


router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.put("/{task_id}/today", status_code=status.HTTP_200_OK)
def update_working_today(task_id: int, payload: WorkingTodayRequest, user_id: int = Depends(current_oracle_user_id)):
    try:
        return {
            "data": set_working_today(
                task_id=task_id,
                is_working_today=payload.is_working_today,
                row_version=payload.row_version,
                user_id=user_id,
            )
        }
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task was not found.") from exc
    except RowVersionConflictError as exc:
        raise HTTPException(status_code=409, detail="Task was updated by another request.") from exc
    except WorkDateDatabaseError as exc:
        raise HTTPException(status_code=503, detail="Working-today storage is unavailable.") from exc
