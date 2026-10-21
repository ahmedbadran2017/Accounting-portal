"""Who may run code on the server through Claude (frappe_assistant_core MCP).

frappe_assistant_core ships `run_python_code` open to every connected user
(`requires_permission = None`). Its database handle is a read-only wrapper, but
the code still receives the whole `frappe` module, so any connected user can
call `frappe.set_user("Administrator")` and then write anything. Every other
tool checks the caller's own DocType permissions (create/update/delete/submit
call `frappe.has_permission` per document), so a read-only role is enough to
keep a user read-only there. This one tool needs a role gate.

The gate: code tools run only for Administrator, System Manager and Assistant
Admin. Everyone else does not see them in the tool list, and a direct call is
refused before the code runs.

How it attaches: `before_request` calls `apply()`, which patches the tool
classes once per worker process (gunicorn runs with --preload, so a patch made
at import time is not guaranteed to land in every worker). `BaseTool._safe_execute`
always calls `check_permission()` before `execute()`, and the registry builds
the tool list through `_check_tool_permission()`, so those two methods cover
both paths. `execute()` of the code tool is wrapped too, in case a future
version calls it directly.

Fail-closed for the code tool, fail-open for the request: if patching fails,
the request goes on and the error is logged.
"""
import frappe

CODE_TOOLS = {"run_python_code"}
CODE_ROLES = {"System Manager", "Assistant Admin"}

_applied = False


def can_run_code(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(CODE_ROLES & set(frappe.get_roles(user)))


def _refuse(tool_name):
    frappe.throw(
        f"{tool_name} is limited to System Manager / Assistant Admin. "
        "Use the read tools (list_documents, get_document, generate_report, run_database_query).",
        frappe.PermissionError,
    )


def _patch():
    from frappe_assistant_core.core.base_tool import BaseTool
    from frappe_assistant_core.core.tool_registry import ToolRegistry
    from frappe_assistant_core.plugins.data_science.tools.run_python_code import ExecutePythonCode

    if getattr(BaseTool, "_ap_guarded", False):
        return

    base_check = BaseTool.check_permission

    def check_permission(self):
        if getattr(self, "name", None) in CODE_TOOLS and not can_run_code():
            _refuse(self.name)
        return base_check(self)

    registry_check = ToolRegistry._check_tool_permission

    def _check_tool_permission(self, tool_instance, user):
        if getattr(tool_instance, "name", None) in CODE_TOOLS and not can_run_code(user):
            return False
        return registry_check(self, tool_instance, user)

    code_execute = ExecutePythonCode.execute

    def execute(self, arguments):
        if not can_run_code():
            _refuse(self.name)
        return code_execute(self, arguments)

    BaseTool.check_permission = check_permission
    ToolRegistry._check_tool_permission = _check_tool_permission
    ExecutePythonCode.execute = execute
    BaseTool._ap_guarded = True


def apply():
    """before_request hook — cheap after the first call in each worker."""
    global _applied
    if _applied:
        return
    try:
        _patch()
        _applied = True
    except ImportError:
        _applied = True  # assistant app not installed: nothing to guard
    except Exception:
        _applied = True  # log once per worker, not on every request
        frappe.log_error(title="fac_guard: could not attach", message=frappe.get_traceback())
