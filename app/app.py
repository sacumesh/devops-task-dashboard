# app.py
import streamlit as st
import api

st.set_page_config(page_title="Task Manager", layout="centered")
st.title("Task Manager", text_alignment="center")


def show_error(message: str):
    if message:
        st.error(message)


def show_success(message: str):
    if message:
        st.success(message)


def invalidate_tasks_cache():
    # Make sure the list fragment sees fresh data after mutations
    try:
        api.get_tasks.clear()
    except Exception:
        pass


def ensure_editing_valid():
    """Clear editing state if the task no longer exists."""
    editing = st.session_state.get("editing") or {}
    if not editing:
        return
    edit_id, _ = next(iter(editing.items()))
    try:
        tasks, err = api.get_tasks()
    except Exception:
        tasks, err = [], "Unexpected error while validating edit state."
    if err:
        st.session_state["editing"] = {}
        return
    if not any(str(t.get("id", "")) == str(edit_id) for t in tasks):
        st.session_state["editing"] = {}


if "editing" not in st.session_state:
    st.session_state["editing"] = {}


@st.fragment
def task_list_fragment():
    with st.spinner("Loading tasks..."):
        tasks, err = api.get_tasks()
    if err:
        show_error(err)
        tasks = []

    ensure_editing_valid()

    if not tasks:
        st.info("No tasks found.")
        return

    status_counts = {"TODO": 0, "IN_PROGRESS": 0, "DONE": 0}
    for t in tasks:
        s = t.get("status", "TODO")
        status_counts[s] = status_counts.get(s, 0) + 1
    st.caption(
        f"Total: {len(tasks)} • TODO: {status_counts.get('TODO', 0)} • "
        f"IN_PROGRESS: {status_counts.get('IN_PROGRESS', 0)} • "
        f"DONE: {status_counts.get('DONE', 0)}"
    )

    current_edit = st.session_state.get("editing") or {}
    current_edit_id = next(iter(current_edit.keys()), None)

    emoji_map = {"TODO": "📝", "IN_PROGRESS": "🚧", "DONE": "✅"}

    for t in tasks:
        tid = str(t.get("id", ""))
        title = t.get("title", "<no title>")
        status = t.get("status", "TODO")
        desc = t.get("description", "")

        is_editing = current_edit_id == tid

        with st.container(border=True):

            st.caption(f"Task Id: {tid}")
            status_label = status.replace("_", " ").title()
            status_str = f"{emoji_map.get(status, '')} {status_label}"
            if is_editing:
                st.markdown(f"**Editing:** {title} • {status_str}")
            else:
                st.markdown(f"**{title}** • {status_str}")

            if is_editing:
                with st.form(f"edit_form_{tid}"):
                    e_title = st.text_input("Title", value=t.get("title", ""))
                    e_description = st.text_area(
                        "Description", value=t.get("description", ""))
                    status_values = ["TODO", "IN_PROGRESS", "DONE"]
                    try:
                        idx = status_values.index(t.get("status", "TODO"))
                    except ValueError:
                        idx = 0
                    e_status = st.selectbox("Status", status_values, index=idx)
                    c1, c2 = st.columns([1, 1])
                    save = c1.form_submit_button("Save")
                    cancel = c2.form_submit_button("Cancel")

                    if cancel:
                        st.session_state["editing"] = {}
                        st.rerun()

                    if save:
                        if not e_title.strip():
                            show_error("Title is required")
                        else:
                            _, uerr = api.update_task(
                                tid, e_title.strip(), e_description.strip(), e_status)
                            if uerr:
                                show_error(uerr)
                            else:
                                # Close the editor on successful save
                                st.session_state["editing"] = {}
                                invalidate_tasks_cache()
                                show_success("Task updated")
                            st.rerun()
            else:
                if desc.strip():
                    st.write(desc)
                else:
                    st.caption("No description")

                if not is_editing:
                    # Streamlit doesn't support placing buttons side-by-side without using columns.
                    # Keeping a minimal two-column layout is the simplest way to achieve horizontal buttons.
                    c_edit, c_del = st.columns(2)
                    if c_edit.button("Edit", key=f"edit-{tid}", width="stretch"):
                        st.session_state["editing"] = {tid: t}
                        st.rerun()
                    if c_del.button("Delete", key=f"del-{tid}", width="stretch"):
                        _, derr = api.delete_task(tid)
                        if derr:
                            show_error(derr)
                        else:
                            if current_edit_id == tid:
                                st.session_state["editing"] = {}
                            invalidate_tasks_cache()
                            show_success("Deleted")
                        st.rerun()


@st.fragment
def create_task_fragment():
    with st.form("create_form", clear_on_submit=True):
        title = st.text_input("Title")
        description = st.text_area("Description")
        status_opt = st.selectbox(
            "Status (optional, defaults to TODO)",
            ["", "TODO", "IN_PROGRESS", "DONE"],
        )
        submitted = st.form_submit_button("Create Task")
        if submitted:
            if not title.strip():
                show_error("Title is required")
            else:
                status_value = status_opt if status_opt else None
                _, cerr = api.create_task(
                    title.strip(), description.strip(), status_value)
                if cerr:
                    show_error(cerr)
                else:
                    invalidate_tasks_cache()
                    show_success("Task created")
                    st.rerun()


task_list_fragment()
create_task_fragment()
