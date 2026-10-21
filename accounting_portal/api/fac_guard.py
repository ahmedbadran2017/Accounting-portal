"""Who may run code or raw SQL on the server through Claude (frappe_assistant_core MCP).

frappe_assistant_core ships every tool open to every connected user
(`requires_permission = None`). Most tools check the caller's own DocType
permissions (create/update/delete/submit call `frappe.has_permission` per
document), so a read-only role keeps a user read-only there. Two do not:

- `run_python_code` hands the code the whole `frappe` module, so any connected
  user can call `frappe.set_user("Administrator")` and then write anything.
- `run_database_query` runs raw SELECTs, which skip DocType permissions, so a
  user limited to accounting could still read salaries or any other table.

The gate: those tools run only for Administrator, System Manager and Assistant
Admin. Everyone else does not see them in the tool list, and a direct call is
refused before anything runs.

How it attaches: `before_request` and `before_job` call `apply()`, which patches
the classes once per process (gunicorn runs with --preload, so a patch made at
import time is not guaranteed to land in every worker). `BaseTool._safe_execute`
always calls `check_permission()` before `execute()`, and the registry builds
the tool list through `_check_tool_permission()`; those two cover both paths.
`execute()` of the code tool is wrapped too, in case a future version calls it
directly — that wrap is optional and its absence is logged, not fatal.

Fail loudly: if the assistant app is installed but its classes moved (an
upgrade), nothing is patched and an Error Log entry says so, once per process.
"""
import frappe

GATED_TOOLS = {"run_python_code", "run_database_query"}
GATED_ROLES = {"System Manager", "Assistant Admin"}

_applied = False


def can_use_gated_tools(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(GATED_ROLES & set(frappe.get_roles(user)))


def _refuse(tool_name):
    frappe.throw(
        f"{tool_name} is limited to System Manager / Assistant Admin. "
        "Use the read tools (list_documents, get_document, generate_report).",
        frappe.PermissionError,
    )


def _patch_core():
    from frappe_assistant_core.core.base_tool import BaseTool
    from frappe_assistant_core.core.tool_registry import ToolRegistry

    if getattr(BaseTool, "_ap_guarded", False):
        return

    base_check = BaseTool.check_permission

    def check_permission(self):
        if getattr(self, "name", None) in GATED_TOOLS and not can_use_gated_tools():
            _refuse(self.name)
        return base_check(self)

    registry_check = ToolRegistry._check_tool_permission

    def _check_tool_permission(self, tool_instance, user):
        if getattr(tool_instance, "name", None) in GATED_TOOLS and not can_use_gated_tools(user):
            return False
        return registry_check(self, tool_instance, user)

    BaseTool.check_permission = check_permission
    ToolRegistry._check_tool_permission = _check_tool_permission
    BaseTool._ap_guarded = True


def _patch_code_tool():
    """Belt and braces: refuse inside execute() as well."""
    from frappe_assistant_core.plugins.data_science.tools.run_python_code import ExecutePythonCode

    if getattr(ExecutePythonCode, "_ap_guarded", False):
        return
    code_execute = ExecutePythonCode.execute

    def execute(self, arguments):
        if not can_use_gated_tools():
            _refuse(self.name)
        return code_execute(self, arguments)

    ExecutePythonCode.execute = execute
    ExecutePythonCode._ap_guarded = True


def apply(*args, **kwargs):
    """before_request / before_job hook (before_job passes method/kwargs; ignored) — cheap after the first call in each process."""
    global _applied
    if _applied:
        return
    _applied = True  # one attempt (and at most one log entry) per process
    if "frappe_assistant_core" not in frappe.get_installed_apps():
        return
    try:
        _patch_core()
    except Exception:
        frappe.log_error(title="fac_guard: gate NOT attached — run_python_code/run_database_query are open",
                         message=frappe.get_traceback())
        return
    try:
        _patch_code_tool()
    except Exception:
        frappe.log_error(title="fac_guard: execute() wrap not attached (core gate is active)",
                         message=frappe.get_traceback())
