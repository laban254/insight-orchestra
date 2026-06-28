import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.services.export_service import ExportService
from app.services.session_manager import get_session_manager

router = APIRouter(prefix="/export", tags=["export"])
export_service = ExportService()
_session_manager = get_session_manager()


def _build_session(session_id: str) -> dict:
    """Assemble a report payload from the real session history."""
    history = _session_manager.get(session_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this session (it may have expired).",
        )

    agents = []
    messages = []
    for entry in history:
        if entry.get("role") == "analysis":
            if entry.get("narrative"):
                messages.append({"role": "assistant", "content": entry["narrative"]})
            for h in entry.get("hypotheses", []) or []:
                if h is None:
                    continue
                text = h.get("hypothesis") if isinstance(h, dict) else str(h)
                if text:
                    agents.append({"emoji": "💡", "name": "Insight", "output": text})
        elif entry.get("question"):
            messages.append({"role": "user", "content": entry.get("question", "")})
            messages.append(
                {"role": "assistant", "content": entry.get("answer", ""), "code": entry.get("code", "")}
            )

    return {
        "title": f"Analysis · {session_id}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": agents,
        "messages": messages,
        "charts": [],  # charts live client-side; the in-app HTML export embeds them
    }


@router.get("/{session_id}/html")
async def export_html(session_id: str):
    html = export_service.to_html(_build_session(session_id))
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f"attachment; filename=analysis-{session_id}.html"},
    )


@router.get("/{session_id}/markdown")
async def export_markdown(session_id: str):
    md = export_service.to_markdown(_build_session(session_id))
    return PlainTextResponse(
        content=md,
        headers={"Content-Disposition": f"attachment; filename=analysis-{session_id}.md"},
    )


@router.get("/{session_id}/csv")
async def export_qa_csv(session_id: str):
    """Export the session's question/answer/code history as CSV."""
    history = _session_manager.get(session_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this session (it may have expired).",
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["question", "answer", "code"])
    rows = 0
    for entry in history:
        if entry.get("question"):
            writer.writerow([entry.get("question", ""), entry.get("answer", ""), entry.get("code", "")])
            rows += 1
    if rows == 0:
        raise HTTPException(status_code=404, detail="No questions have been asked in this session yet.")

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=qa-{session_id}.csv"},
    )
