"""HTTP layer for the sessions domain. Thin: parse request, call service, return response."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from karaoke.db import get_conn
from karaoke.sessions import service

router = APIRouter()


class CreateSessionBody(BaseModel):
    song_id: int
    host_name: str


class JoinBody(BaseModel):
    display_name: str


class ClaimBody(BaseModel):
    participant_id: int


def _call(fn, *args):
    """Run a service function and turn its exceptions into HTTP errors."""
    try:
        return fn(*args)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except service.Conflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/songs")
def list_songs(conn=Depends(get_conn)):
    return service.list_songs(conn)


@router.post("", status_code=201)
def create_session(body: CreateSessionBody, conn=Depends(get_conn)):
    return _call(service.create_session, conn, body.song_id, body.host_name)


@router.get("/{session_id}")
def get_session(session_id: str, conn=Depends(get_conn)):
    return _call(service.get_session, conn, session_id)


@router.post("/{session_id}/participants", status_code=201)
def join_session(session_id: str, body: JoinBody, conn=Depends(get_conn)):
    return _call(service.join_session, conn, session_id, body.display_name)


@router.post("/{session_id}/turns/{turn_id}/claim")
def claim_turn(session_id: str, turn_id: int, body: ClaimBody, conn=Depends(get_conn)):
    return _call(service.claim_turn, conn, session_id, turn_id, body.participant_id)
