"""Menu UI (Lot 6) — make the system usable without memorising the CLI.

`agentic` with no subcommand shows a numbered menu: available workflows,
existing sessions (current state + journal integrity) and the actions
each supports. Rendering and mapping are pure and tested; only the
interactive loop touches stdin.

Listing logic:

- workflows: scan workflows/v<N>/*.yaml, newest version first, sorted
  by id. Each entry carries the id and the version directory.
- sessions: scan sessions/<id>/session.jsonl; current state is the last
  block's ``to_state``, integrity is ok/invalid (load_journal raises).
  A corrupted session is flagged, never fatal to the menu.
"""

from __future__ import annotations

from pathlib import Path

from agentic_suite.loader import load_workflow
from agentic_suite.session import SessionIntegrityViolation, load_journal

SESSIONS_DIR = "sessions"
WORKFLOWS_DIR = "workflows"


def build_menu(project_root: Path) -> dict:
    """Collect workflows and sessions under *project_root*."""
    workflows = _list_workflows(project_root)
    sessions = _list_sessions(project_root)
    return {"workflows": workflows, "sessions": sessions}


def _list_workflows(project_root: Path) -> list[dict]:
    """workflows/v<N>/<id>.yaml entries, newest version first, ids sorted."""
    vdir = project_root / WORKFLOWS_DIR
    entries: list[dict] = []
    if not vdir.is_dir():
        return entries
    for version_dir in sorted(vdir.iterdir(), reverse=True):
        if not (version_dir.is_dir() and version_dir.name.startswith("v")):
            continue
        for wf_file in sorted(version_dir.glob("*.yaml")):
            try:
                wf = load_workflow(wf_file)
            except Exception:
                continue  # unparsable workflow: skip, do not crash the menu
            wf_id = wf.get("id") or wf_file.stem
            entries.append({
                "id": wf_id,
                "version": wf.get("version", 1),
                "path": str(wf_file),
                "initial_state": wf.get("initial_state", ""),
            })
    return entries


def _list_sessions(project_root: Path) -> list[dict]:
    """sessions/<id>/session.jsonl entries, newest mtime first."""
    sdir = project_root / SESSIONS_DIR
    entries: list[dict] = []
    if not sdir.is_dir():
        return entries
    for session_dir in sorted(sdir.iterdir(), key=lambda p: p.stat().st_mtime,
                               reverse=True):
        if not session_dir.is_dir():
            continue
        jp = session_dir / "session.jsonl"
        if not jp.is_file():
            continue
        entries.append(_session_entry(session_dir.name, jp))
    return entries


def _session_entry(session_id: str, jp: Path) -> dict:
    try:
        journal = load_journal(jp)
        integrity = "ok"
    except SessionIntegrityViolation:
        integrity = "invalid"
        journal = None
    state = journal[-1].get("to_state", "?") if journal else "?"
    last_seq = journal[-1].get("seq", 0) if journal else 0
    return {
        "id": session_id,
        "state": state,
        "blocks": last_seq + 1,
        "integrity": integrity,
    }


def render_menu(menu: dict) -> str:
    """Plain-text numbered menu (no dependencies, CI-testable)."""
    lines: list[str] = []
    lines.append("Agentic Suite — sessions et workflows")
    lines.append("")
    workflows = menu["workflows"]
    sessions = menu["sessions"]
    offset = len(workflows)
    if workflows:
        lines.append("Workflows :")
        for i, wf in enumerate(workflows, start=1):
            lines.append(
                f"  {i:>2}  {wf['id']} (v{wf['version']})"
                f" — entre sur {wf['initial_state']}"
            )
    else:
        lines.append("Workflows : (aucun)")
    lines.append("")
    if sessions:
        lines.append("Sessions :")
        for i, session in enumerate(sessions, start=offset + 1):
            integrity = "" if session["integrity"] == "ok" else " [journal invalide]"
            lines.append(
                f"  {i:>2}  {session['id']} — {session['state']}"
                f" ({session['blocks']} blocs){integrity}"
            )
    else:
        lines.append("Sessions : (aucune)")
    lines.append("")
    lines.append("0  quitter")
    return "\n".join(lines)


def action_from_menu(menu: dict, choice: int) -> dict | None:
    """Map a numbered choice to a workflow or session action.

    Workflows are numbered 1..N, sessions N+1..N+M. Returns None for an
    out-of-range choice (including 0 = quit).
    """
    workflows = menu["workflows"]
    sessions = menu["sessions"]
    if 1 <= choice <= len(workflows):
        return {"kind": "workflow", "id": workflows[choice - 1]["id"]}
    if len(workflows) < choice <= len(workflows) + len(sessions):
        return {"kind": "session", "id": sessions[choice - len(workflows) - 1]["id"]}
    return None