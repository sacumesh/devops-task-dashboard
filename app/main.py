# app.py
from __future__ import annotations

import typing as t
from enum import Enum

import streamlit as st
import api


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


# --- Constants / helpers ---
EMOJI_MAP: dict[str, str] = {
    TaskStatus.TODO.value: "📝",
    TaskStatus.IN_PROGRESS.value: "🚧",
    TaskStatus.COMPLETED.value: "✅",
    TaskStatus.CANCELLED.value: "❌",
    TaskStatus.FAILED.value: "❗",
}
STATUS_VALUES: list[str] = [s.value for s in TaskStatus]


def normalize_status(value: t.Optional[str]) -> str:
    """Normalize status to a valid TaskStatus value."""
    if not value:
        return TaskStatus.TODO.value
    s = value.strip().upper()
    return s if s in STATUS_VALUES else TaskStatus.TODO.value


def show_error(message: t.Optional[str]) -> None:
    if message:
        st.error(message)


def show_success(message: t.Optional[str]) -> None:
    if message:
        st.success(message)


def invalidate_tasks_cache() -> None:
    """Ensure task list shows fresh data after mutations."""
    try:
        api.get_tasks.clear()
    except Exception:
        pass


def get_tasks_safe() -> tuple[list[dict], t.Optional[str]]:
    """Get tasks with basic protection."""
    try:
        tasks, err = api.get_tasks()
    except Exception:
        return [], "Unexpected error while loading tasks."
    return (tasks or []), err


def ensure_editing_valid() -> None:
    """Clear editing state if the task no longer exists."""
    editing: dict[str, dict] = st.session_state.get("editing") or {}
    if not editing:
        return
    edit_id = next(iter(editing.keys()), None)
    if not edit_id:
        st.session_state["editing"] = {}
        return
    tasks, err = get_tasks_safe()
    if err:
        st.session_state["editing"] = {}
        return
    if not any(str(t.get("id", "")) == str(edit_id) for t in tasks):
        st.session_state["editing"] = {}


def set_editing(task_id: str, task: dict | None = None) -> None:
    st.session_state["editing"] = {task_id: (task or {})}


def clear_editing() -> None:
    st.session_state["editing"] = {}


# --- Health check ---
def check_health() -> tuple[bool, str | None]:
    """Ping backend /health; return (ok, message)."""
    try:
        ok, msg = api.health()
        return bool(ok), msg
    except Exception:
        return False, "Failed to reach backend health endpoint."


@st.fragment
def task_list_fragment() -> None:
    with st.spinner("Loading tasks..."):
        tasks, err = get_tasks_safe()
    if err:
        show_error(err)
        tasks = []

    ensure_editing_valid()

    if not tasks:
        st.info("No tasks found.")
        return

    # Build counts from the TaskStatus enum
    status_counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
    for t in tasks:
        s = normalize_status(t.get("status"))
        status_counts[s] = status_counts.get(s, 0) + 1

    # Display totals using the enum order
    parts = [f"Total: {len(tasks)}"] + [
        f"{status.value}: {status_counts.get(status.value, 0)}" for status in TaskStatus
    ]
    st.caption(" • ".join(parts))

    current_edit: dict[str, dict] = st.session_state.get("editing") or {}
    current_edit_id: str | None = next(iter(current_edit.keys()), None)

    for t in tasks:
        tid = str(t.get("id", ""))
        title = (t.get("title") or "").strip() or "<no title>"
        status = normalize_status(t.get("status"))
        desc = (t.get("description") or "").strip()

        is_editing = current_edit_id == tid

        with st.container(border=True):
            st.caption(f"Task Id: {tid}")
            status_label = status.replace("_", " ").title()
            status_str = f"{EMOJI_MAP.get(status, '')} {status_label}"

            if is_editing:
                st.markdown(f"**Editing:** {title} • {status_str}")
            else:
                st.markdown(f"**{title}** • {status_str}")

            if is_editing:
                with st.form(f"edit_form_{tid}"):
                    e_title = st.text_input("Title", value=title)
                    e_description = st.text_area("Description", value=desc)

                    try:
                        idx = STATUS_VALUES.index(status)
                    except ValueError:
                        idx = 0
                    e_status = st.selectbox("Status", STATUS_VALUES, index=idx)

                    c1, c2 = st.columns([1, 1])
                    save = c1.form_submit_button("Save", width="stretch")
                    cancel = c2.form_submit_button("Cancel", width="stretch")

                    if cancel:
                        clear_editing()
                        st.rerun()

                    if save:
                        title_clean = e_title.strip()
                        desc_clean = e_description.strip()
                        if not title_clean:
                            show_error("Title is required")
                        else:
                            _, uerr = api.update_task(tid, title_clean, desc_clean, e_status)
                            if uerr:
                                show_error(uerr)
                            else:
                                clear_editing()
                                invalidate_tasks_cache()
                                show_success("Task updated")
                            st.rerun()
            else:
                if desc:
                    st.write(desc)
                else:
                    st.caption("No description")

                # Buttons side-by-side; keep layout unchanged
                c_edit, c_del = st.columns(2)
                if c_edit.button("Edit", key=f"edit-{tid}", width="stretch"):
                    set_editing(tid, t)
                    st.rerun()
                if c_del.button("Delete", key=f"del-{tid}", width="stretch"):
                    _, derr = api.delete_task(tid)
                    if derr:
                        show_error(derr)
                    else:
                        if current_edit_id == tid:
                            clear_editing()
                        invalidate_tasks_cache()
                        show_success("Deleted")
                    st.rerun()


@st.fragment
def create_task_fragment() -> None:
    with st.form("create_form", clear_on_submit=True):
        title = st.text_input("Title")
        description = st.text_area("Description")
        submitted = st.form_submit_button("Create Task")
        if submitted:
            title_clean = (title or "").strip()
            description_clean = (description or "").strip()
            if not title_clean:
                show_error("Title is required")
            else:
                _, cerr = api.create_task(title_clean, description_clean, None)
                if cerr:
                    show_error(cerr)
                else:
                    invalidate_tasks_cache()
                    show_success("Task created")
                    st.rerun()


def main() -> None:
    # --- Streamlit app setup ---
    st.set_page_config(page_title="Task Manager", layout="centered")
    st.title("Task Manager", text_alignment="center")

    # Initialize session state only when healthy
    ok, hmsg = check_health()
    if not ok:
        show_error(hmsg or "Service unavailable")
        st.stop()

    if "editing" not in st.session_state:
        st.session_state["editing"] = {}

    task_list_fragment()
    st.markdown("---")
    create_task_fragment()


if __name__ == "__main__":
    main()
