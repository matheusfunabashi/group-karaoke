"""HTTP layer for the recordings domain. Thin: parse request, call service, return response."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from karaoke.db import get_conn
from karaoke.recordings import service

router = APIRouter()


@router.post("", status_code=201)
def upload_recording(
    request: Request,
    turn_id: int = Form(...),
    clip: UploadFile = File(...),
    conn=Depends(get_conn),
):
    # Read at most one byte over the limit, so a huge upload is rejected without
    # loading all of it into memory.
    data = clip.file.read(service.MAX_BYTES + 1)
    media_dir = request.app.state.settings.media_dir
    try:
        return service.save_recording(conn, media_dir, turn_id, clip.content_type or "", data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except service.TurnNotOpen as e:
        raise HTTPException(status_code=409, detail=str(e))
