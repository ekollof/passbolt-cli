"""Textual TUI for Passbolt password lookup"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from passbolt.clipboard import (
    clear_clipboard_if_unchanged,
    copy_to_clipboard,
    get_clipboard_cmd,
)
from passbolt.client import PassboltClient
from passbolt.config import PassboltConfig
from passbolt.resources import filter_resources_by_query, sanitize_resource_for_display
from passbolt.secret import (
    extract_totp,
    generate_totp,
    get_password_field,
    get_totp_for_resource,
    has_totp,
)
from passbolt.theme import load_wallust_theme

COLUMN_LIMITS = {"name": 32, "username": 24, "uri": 36}


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _row_key(resource: dict[str, Any], index: int) -> str:
    """Return a stable DataTable row key for a resource."""
    resource_id = resource.get("id")
    if resource_id:
        return str(resource_id)
    return f"__row_{index}"


def _totp_progress(remaining: int, period: int, width: int = 10) -> str:
    elapsed = max(0, period - remaining)
    filled = round((elapsed / period) * width) if period else 0
    filled = min(width, max(0, filled))
    return "█" * filled + "░" * (width - filled)


class ResourceDetail(Static):
    """Widget to display resource details"""

    resource: reactive[dict[str, Any] | None] = reactive(None)
    totp_display: reactive[str] = reactive("")
    totp_progress: reactive[str] = reactive("")

    def watch_resource(self, resource: dict[str, Any] | None) -> None:
        """Update display when resource changes"""
        if resource is None:
            self.update("[#888888 italic]Select a password entry to view details[/]")
            return

        lines: list[str] = []
        lines.append(f"[b]{self._escape(resource.get('name', 'Unknown'))}[/b]\n")

        username = resource.get("username")
        if username:
            lines.append(f"[dim]Username:[/dim]    {self._escape(username)}")

        uri = resource.get("uri")
        if uri:
            lines.append(f"[dim]URI:[/dim]        {self._escape(uri)}")

        description = resource.get("description")
        if description:
            lines.append(f"[dim]Description:[/dim] {self._escape(description)}")

        resource_id = resource.get("id")
        if resource_id:
            lines.append(f"[dim]ID:[/dim]          {self._escape(resource_id)}")

        if has_totp(resource):
            if self.totp_display:
                lines.append(
                    f"[dim]TOTP:[/dim]        [green]{self.totp_display}[/green]"
                )
                if self.totp_progress:
                    lines.append(f"[dim]         [/dim] [green]{self.totp_progress}[/green]")
            else:
                lines.append(
                    "[dim]TOTP:[/dim]        [green]Available[/green] (press [b]t[/b] to copy)"
                )

        self.update("\n".join(lines))

    def watch_totp_display(self, _value: str) -> None:
        """Refresh detail panel when the live TOTP display changes."""
        self.watch_resource(self.resource)

    def watch_totp_progress(self, _value: str) -> None:
        """Refresh detail panel when the TOTP progress bar changes."""
        self.watch_resource(self.resource)

    @staticmethod
    def _escape(text: str) -> str:
        """Escape rich markup in text"""
        return text.replace("[", "\\[").replace("]", "\\]")


class PassboltTUI(App[None]):
    """Passbolt Terminal User Interface"""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "copy_password", "Copy Password"),
        Binding("t", "copy_totp", "Copy TOTP"),
        Binding("u", "copy_username", "Copy Username"),
        Binding("o", "copy_uri", "Copy URI"),
        Binding("s", "show_secret", "Show Secret"),
        Binding("r", "refresh_resources", "Refresh"),
        Binding("enter", "copy_password", "Copy", show=False),
        Binding("slash", "focus_search", "Search"),
        Binding("tab", "cycle_focus", "Focus"),
        Binding("escape", "clear_search", "Clear"),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
    ]

    CSS = """
    Screen {
        align: center middle;
    }

    .main-container {
        width: 100%;
        height: 100%;
    }

    .top-bar {
        height: auto;
        padding: 0 1;
    }

    .search-input {
        width: 100%;
        margin: 1 0 0 0;
    }

    .status-bar {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    .content-area {
        height: 1fr;
    }

    .resource-list {
        width: 2fr;
        height: 100%;
        border: solid $primary;
    }

    .detail-panel {
        width: 1fr;
        height: 100%;
        padding: 1 2;
        border: solid $primary;
    }

    DataTable {
        width: 100%;
        height: 100%;
    }

    DataTable > .datatable--cursor {
        background: $accent 40%;
    }

    .loading {
        text-align: center;
        color: $text-muted;
    }

    Footer {
        background: $surface-darken-1;
    }
    """

    resources: reactive[list[dict[str, Any]]] = reactive([])
    selected_resource: reactive[dict[str, Any] | None] = reactive(None)

    def __init__(self, client: PassboltClient, config: PassboltConfig) -> None:
        super().__init__()
        self.client = client
        self.config = config
        self._all_resources: list[dict[str, Any]] = []
        self._secret_cache: dict[str, str] = {}
        self._totp_cache: dict[str, dict[str, Any]] = {}
        self._clipboard_clear_generation: int = 0
        self._last_clipboard_text: str = ""
        self._clipboard_clear_deadline: float | None = None
        self._loading: bool = False
        self._wal_path = Path.home() / ".cache" / "wal" / "colors.json"
        self._wal_mtime: float = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(classes="main-container"):
            with Horizontal(classes="top-bar"):
                yield Input(
                    placeholder="Search passwords... (/ focus, Tab switch, Enter/Esc results)",
                    classes="search-input",
                    id="search",
                )

            yield Label("Loading resources...", classes="status-bar", id="status-bar")

            with Horizontal(classes="content-area"):
                with Vertical(classes="resource-list"):
                    table = DataTable(
                        id="resource-table",
                        cursor_type="row",
                        zebra_stripes=True,
                    )
                    table.add_columns("Name", "Username", "URI", "TOTP")
                    yield table

                with Vertical(classes="detail-panel"):
                    yield Label(
                        "Loading resources...", classes="loading", id="loading-label"
                    )
                    yield ResourceDetail(id="detail")

        yield Footer()

    def on_mount(self) -> None:
        """Load resources and theme when app mounts"""
        wallust_theme = load_wallust_theme()
        if wallust_theme:
            self.register_theme(wallust_theme)
            self.theme = "wallust"
            try:
                self._wal_mtime = self._wal_path.stat().st_mtime
            except OSError:
                self._wal_mtime = 0.0
            self.set_interval(2, self._check_wallust_theme)

        self.set_interval(1, self._tick_totp_display)
        self.set_interval(1, self._update_clipboard_footer)

        self.query_one("#loading-label", Label).styles.display = "block"
        self.query_one("#detail", ResourceDetail).styles.display = "none"
        self.load_all_resources()

    @work(thread=True)
    def load_all_resources(self) -> None:
        """Load the full resource list from Passbolt in a background thread."""
        self.call_from_thread(self._set_loading, True)
        try:
            results = self.client.list_resources()
            self.call_from_thread(self._on_resources_loaded, results)
        except Exception as e:
            self.call_from_thread(self.show_error, f"Error loading resources: {e}")
        finally:
            self.call_from_thread(self._set_loading, False)

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._update_status_bar()

    def _on_resources_loaded(self, results: list[dict[str, Any]]) -> None:
        """Store fetched resources and apply the current search filter."""
        self._all_resources = [
            sanitize_resource_for_display(resource) for resource in results
        ]
        search = self.query_one("#search", Input)
        self._apply_search_filter(search.value)

    def _apply_search_filter(self, query: str) -> None:
        """Filter the cached resource list locally and refresh the table."""
        filtered = filter_resources_by_query(self._all_resources, query)
        preserve_id = (self.selected_resource or {}).get("id")
        self.set_resources(filtered, select_id=preserve_id)
        self._update_status_bar(query=query)

    def set_resources(
        self,
        results: list[dict[str, Any]],
        *,
        select_id: str | None = None,
    ) -> None:
        """Set resources and update table"""
        self.resources = results
        table = self.query_one("#resource-table", DataTable)
        table.clear()

        loading = self.query_one("#loading-label", Label)
        loading.styles.display = "none"
        self.query_one("#detail", ResourceDetail).styles.display = "block"

        if not results:
            loading.update("No resources found.")
            loading.styles.display = "block"
            self.query_one("#detail", ResourceDetail).styles.display = "none"
            self.selected_resource = None
            return

        for index, resource in enumerate(results):
            name = _truncate(resource.get("name"), COLUMN_LIMITS["name"])
            username = _truncate(resource.get("username"), COLUMN_LIMITS["username"])
            uri = _truncate(resource.get("uri"), COLUMN_LIMITS["uri"])
            totp_marker = "●" if has_totp(resource) else ""
            table.add_row(
                name,
                username,
                uri,
                totp_marker,
                key=_row_key(resource, index),
            )

        selected_index = 0
        if select_id:
            for index, resource in enumerate(results):
                if resource.get("id") == select_id:
                    selected_index = index
                    break

        if table.row_count > 0:
            table.move_cursor(row=selected_index)
            self.selected_resource = results[selected_index]

    def _update_status_bar(self, query: str | None = None) -> None:
        """Update the status line above the resource table."""
        status = self.query_one("#status-bar", Label)
        if query is None:
            query = self.query_one("#search", Input).value

        if self._loading:
            status.update("[dim]Loading resources from server...[/dim]")
            return

        total = len(self._all_resources)
        shown = len(self.resources)
        if query:
            status.update(f"Showing {shown} of {total} — filter: {query}")
        else:
            noun = "resource" if total == 1 else "resources"
            status.update(f"{total} {noun}")

    def show_error(self, message: str) -> None:
        """Show an error message"""
        loading = self.query_one("#loading-label", Label)
        loading.update(f"[red]{message}[/red]")
        loading.styles.display = "block"
        self.query_one("#detail", ResourceDetail).styles.display = "none"
        self.query_one("#status-bar", Label).update("[red]Failed to load resources[/red]")

    @on(DataTable.RowSelected)
    @on(DataTable.RowHighlighted)
    def on_row_selected(
        self, event: DataTable.RowSelected | DataTable.RowHighlighted
    ) -> None:
        """Handle row selection/highlight"""
        row_key = event.row_key.value
        resource = next((r for r in self.resources if r.get("id") == row_key), None)
        self.selected_resource = resource

    def watch_selected_resource(self, resource: dict[str, Any] | None) -> None:
        """Update detail panel when selection changes"""
        detail = self.query_one("#detail", ResourceDetail)
        detail.resource = resource
        detail.totp_display = ""
        detail.totp_progress = ""
        if resource and has_totp(resource):
            self._refresh_totp_display()

    def _tick_totp_display(self) -> None:
        """Refresh live TOTP display every second for the selected resource."""
        if self.selected_resource and has_totp(self.selected_resource):
            self._refresh_totp_display()

    def _refresh_totp_display(self) -> None:
        """Compute and display the current TOTP code with countdown."""
        resource = self.selected_resource
        if not resource or not has_totp(resource):
            return

        resource_id = resource.get("id")
        if not resource_id:
            return

        totp_params = self._get_totp_params(resource_id)
        if totp_params is None:
            return

        code = generate_totp(
            secret_key=totp_params["secret_key"],
            algorithm=totp_params["algorithm"],
            digits=totp_params["digits"],
            period=totp_params["period"],
        )
        remaining = totp_params["period"] - (int(time.time()) % totp_params["period"])
        display = f"{code} ({remaining}s)"
        progress = _totp_progress(remaining, totp_params["period"])

        detail = self.query_one("#detail", ResourceDetail)
        if self.selected_resource is resource:
            detail.totp_display = display
            detail.totp_progress = progress

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with instant local filtering."""
        self._apply_search_filter(event.value)

    def action_focus_search(self) -> None:
        """Focus the search input"""
        self.query_one("#search", Input).focus()

    def action_cycle_focus(self) -> None:
        """Switch focus between the search box and results table."""
        search = self.query_one("#search", Input)
        table = self.query_one("#resource-table", DataTable)
        if search.has_focus:
            table.focus()
        else:
            search.focus()

    def action_defocus_search(self) -> None:
        """Move focus from search to the results table."""
        search = self.query_one("#search", Input)
        search.blur()
        self.query_one("#resource-table", DataTable).focus()

    def action_clear_search(self) -> None:
        """Clear the search filter and refocus the results table."""
        search = self.query_one("#search", Input)
        if search.value:
            search.value = ""
            self._apply_search_filter("")
        self.action_defocus_search()

    def action_refresh_resources(self) -> None:
        """Reload resources from the server"""
        self._clear_sensitive_caches()
        self.load_all_resources()
        self.notify("Refreshing resources...", severity="information")

    @on(Input.Submitted, "#search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """Pressing Enter in the search box moves focus to the table"""
        self.action_defocus_search()

    def action_cursor_up(self) -> None:
        """Move cursor up in table"""
        table = self.query_one("#resource-table", DataTable)
        table.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move cursor down in table"""
        table = self.query_one("#resource-table", DataTable)
        table.action_cursor_down()

    def action_copy_password(self) -> None:
        """Copy selected resource's password to clipboard"""
        if self.focused == self.query_one("#search", Input):
            return

        resource = self.selected_resource
        if not resource:
            self.notify("No resource selected", severity="warning")
            return

        resource_id = resource.get("id")
        if not resource_id:
            return

        self._copy_secret(resource_id, resource.get("name", "Unknown"))

    @work(thread=True)
    def _copy_secret(self, resource_id: str, resource_name: str) -> None:
        """Copy secret password to clipboard in background thread"""
        try:
            password = self._get_password(resource_id)
            success, result = self._do_clipboard_copy(password)
            if success:
                self.call_from_thread(
                    self._on_clipboard_copy_success,
                    result,
                    password,
                    f"Password for '{resource_name}' copied to clipboard",
                    f"Password for '{resource_name}'",
                )
            else:
                self.call_from_thread(self.notify, result, severity="error")
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to copy password: {e}", severity="error"
            )

    @work(thread=True)
    def _copy_text_to_clipboard(self, text: str, description: str) -> None:
        """Copy arbitrary text to clipboard in background thread"""
        try:
            success, result = self._do_clipboard_copy(text)
            if success:
                self.call_from_thread(
                    self._on_clipboard_copy_success,
                    result,
                    text,
                    f"{description} copied to clipboard",
                    description,
                )
            else:
                self.call_from_thread(self.notify, result, severity="error")
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to copy {description}: {e}", severity="error"
            )

    def _get_password(self, resource_id: str) -> str:
        """Get password for a resource, using cache if available"""
        if resource_id in self._secret_cache:
            return self._secret_cache[resource_id]

        secret = self.client.get_secret(resource_id)
        password = get_password_field(secret)
        self._secret_cache[resource_id] = password
        return password

    def _get_totp_params(self, resource_id: str) -> dict[str, Any] | None:
        """Get cached TOTP parameters for a resource."""
        if resource_id in self._totp_cache:
            return self._totp_cache[resource_id]

        secret = self.client.get_secret(resource_id)
        totp_params = extract_totp(secret)
        if totp_params is not None:
            self._totp_cache[resource_id] = totp_params
        return totp_params

    def _evict_secret_cache(self, resource_id: str) -> None:
        """Overwrite and remove a single cached password."""
        if resource_id in self._secret_cache:
            self._secret_cache[resource_id] = "x" * len(self._secret_cache[resource_id])
            del self._secret_cache[resource_id]
        if resource_id in self._totp_cache:
            params = self._totp_cache[resource_id]
            secret_key = params.get("secret_key")
            if isinstance(secret_key, str):
                params["secret_key"] = "x" * len(secret_key)
            del self._totp_cache[resource_id]

    def _clear_secret_cache(self) -> None:
        """Overwrite and clear cached passwords from memory"""
        for key in list(self._secret_cache.keys()):
            self._secret_cache[key] = "x" * len(self._secret_cache[key])
        self._secret_cache.clear()

    def _clear_totp_cache(self) -> None:
        """Overwrite and clear cached TOTP secrets from memory."""
        for resource_id in list(self._totp_cache.keys()):
            params = self._totp_cache[resource_id]
            secret_key = params.get("secret_key")
            if isinstance(secret_key, str):
                params["secret_key"] = "x" * len(secret_key)
            del self._totp_cache[resource_id]

    def _clear_sensitive_caches(self) -> None:
        self._clear_secret_cache()
        self._clear_totp_cache()

    def on_unmount(self) -> None:
        """Clean up sensitive data when app is shutting down"""
        self._clear_sensitive_caches()

    @staticmethod
    def _do_clipboard_copy(text: str) -> tuple[bool, str | list[str]]:
        """Copy text to clipboard. Returns (success, clipboard_cmd)."""
        clipboard_cmd = get_clipboard_cmd()

        if not clipboard_cmd:
            return (
                False,
                "No clipboard tool found (install xclip, xsel, wl-clipboard, or pbcopy)",
            )

        try:
            copy_to_clipboard(text, clipboard_cmd)
            return True, clipboard_cmd
        except Exception as e:
            return False, f"Clipboard error: {e}"

    def _on_clipboard_copy_success(
        self,
        clipboard_cmd: list[str],
        copied_text: str,
        textual_message: str,
        desktop_message: str,
    ) -> None:
        """Handle successful clipboard copy on main thread"""
        self.notify(textual_message, severity="information")
        self._send_desktop_notification("Passbolt", desktop_message)
        self._last_clipboard_text = copied_text

        if self.config.clipboard_timeout > 0:
            self._clipboard_clear_generation += 1
            generation = self._clipboard_clear_generation
            self._clipboard_clear_deadline = time.time() + self.config.clipboard_timeout
            self.set_timer(
                self.config.clipboard_timeout,
                lambda gen=generation: self._clear_clipboard_if_current(
                    clipboard_cmd, desktop_message, copied_text, gen
                ),
            )
            self._update_clipboard_footer()

    def _update_clipboard_footer(self) -> None:
        """Show clipboard clear countdown in the footer."""
        footer = self.query_one(Footer)
        if self._clipboard_clear_deadline is None:
            footer.sub_title = ""
            return

        remaining = int(self._clipboard_clear_deadline - time.time())
        if remaining <= 0:
            self._clipboard_clear_deadline = None
            footer.sub_title = ""
            return

        footer.sub_title = f"Clipboard clears in {remaining}s"

    def _clear_clipboard_if_current(
        self,
        clipboard_cmd: list[str],
        description: str,
        expected_text: str,
        generation: int,
    ) -> None:
        """Clear clipboard only if no newer copy replaced the scheduled one."""
        if generation != self._clipboard_clear_generation:
            return
        self._clear_clipboard(clipboard_cmd, description, expected_text)

    @work(thread=True)
    def _clear_clipboard(
        self,
        clipboard_cmd: list[str],
        description: str,
        expected_text: str,
    ) -> None:
        """Clear clipboard in background thread if unchanged."""
        try:
            if not clear_clipboard_if_unchanged(clipboard_cmd, expected_text):
                return

            self._clipboard_clear_deadline = None
            self.call_from_thread(self._update_clipboard_footer)
            self.call_from_thread(
                self.notify,
                f"Clipboard cleared ({description})",
                severity="information",
            )
            self._send_desktop_notification(
                "Passbolt", f"Clipboard cleared ({description})"
            )
        except Exception:
            pass

    @staticmethod
    def _send_desktop_notification(title: str, message: str) -> None:
        """Send a desktop notification using notify-send if available"""
        if shutil.which("notify-send"):
            try:
                subprocess.run(
                    ["notify-send", title, message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            except Exception:
                pass

    def action_copy_username(self) -> None:
        """Copy selected resource's username to clipboard"""
        resource = self.selected_resource
        if not resource:
            self.notify("No resource selected", severity="warning")
            return

        username = resource.get("username")
        if not username:
            self.notify("No username for this resource", severity="warning")
            return

        self._copy_text_to_clipboard(
            username, f"Username for '{resource.get('name', '')}'"
        )

    def action_copy_uri(self) -> None:
        """Copy selected resource's URI to clipboard"""
        resource = self.selected_resource
        if not resource:
            self.notify("No resource selected", severity="warning")
            return

        uri = resource.get("uri")
        if not uri:
            self.notify("No URI for this resource", severity="warning")
            return

        self._copy_text_to_clipboard(uri, f"URI for '{resource.get('name', '')}'")

    @work(thread=True)
    def action_copy_totp(self) -> None:
        """Generate and copy TOTP code for selected resource"""
        resource = self.selected_resource
        if not resource:
            self.notify("No resource selected", severity="warning")
            return

        if not has_totp(resource):
            self.notify("No TOTP for this resource", severity="warning")
            return

        resource_id = resource.get("id")
        if not resource_id:
            return

        try:
            totp_params = self._get_totp_params(resource_id)
            if totp_params is None:
                self.call_from_thread(
                    self.notify, "Could not extract TOTP data", severity="error"
                )
                return
            totp_code = generate_totp(
                secret_key=totp_params["secret_key"],
                algorithm=totp_params["algorithm"],
                digits=totp_params["digits"],
                period=totp_params["period"],
            )
            success, result = self._do_clipboard_copy(totp_code)
            if success:
                self.call_from_thread(
                    self._on_clipboard_copy_success,
                    result,
                    totp_code,
                    f"TOTP for '{resource.get('name', '')}' copied to clipboard",
                    f"TOTP for '{resource.get('name', '')}'",
                )
            else:
                self.call_from_thread(self.notify, result, severity="error")
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to generate TOTP: {e}", severity="error"
            )

    def action_show_secret(self) -> None:
        """Show secret password in a dialog"""
        resource = self.selected_resource
        if not resource:
            self.notify("No resource selected", severity="warning")
            return

        resource_id = resource.get("id")
        if not resource_id:
            return

        self._show_secret_dialog(resource_id, resource)

    @work(thread=True)
    def _show_secret_dialog(self, resource_id: str, resource: dict[str, Any]) -> None:
        """Fetch and show secret in background thread"""
        try:
            password = self._get_password(resource_id)
            totp_params = self._get_totp_params(resource_id) if has_totp(resource) else None
            totp_code = (
                generate_totp(
                    secret_key=totp_params["secret_key"],
                    algorithm=totp_params["algorithm"],
                    digits=totp_params["digits"],
                    period=totp_params["period"],
                )
                if totp_params
                else None
            )
            self.call_from_thread(
                self._push_secret_screen,
                password,
                resource,
                totp_code,
                totp_params,
                resource_id,
            )
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to retrieve password: {e}", severity="error"
            )

    def _push_secret_screen(
        self,
        password: str,
        resource: dict[str, Any],
        totp_code: str | None,
        totp_params: dict[str, Any] | None,
        resource_id: str,
    ) -> None:
        """Push a screen showing the secret"""
        app = self

        class SecretScreen(Screen[None]):
            """Screen to display a secret"""

            BINDINGS = [
                Binding("q", "app.pop_screen", "Close"),
                Binding("escape", "app.pop_screen", "Close"),
                Binding("c", "copy_password", "Copy Password"),
                Binding("t", "copy_totp", "Copy TOTP"),
                Binding("u", "copy_username", "Copy Username"),
                Binding("o", "copy_uri", "Copy URI"),
            ]

            totp_code_display: reactive[str] = reactive("")

            def __init__(
                self,
                password: str,
                resource: dict[str, Any],
                totp_code: str | None,
                totp_params: dict[str, Any] | None,
                resource_id: str,
            ) -> None:
                super().__init__()
                self.password = password
                self.resource = resource
                self.totp_code = totp_code
                self.totp_params = totp_params
                self.resource_id = resource_id

            def compose(self) -> ComposeResult:
                yield Static(self._render_content(), id="secret-content")
                yield Label(
                    "[dim]c password · t TOTP · u username · o URI · Esc close[/dim]",
                    classes="center",
                )

            def _render_content(self) -> str:
                lines: list[str] = []
                lines.append(f"[b]{self.resource.get('name', 'Unknown')}[/b]\n")
                lines.append("[b]Password[/b]")
                lines.append(f"[reverse]{self.password}[/reverse]\n")

                if self.totp_code or self.totp_params:
                    lines.append("[b]TOTP[/b]")
                    lines.append(
                        f"[reverse]{self.totp_code_display or self.totp_code or '...'}[/reverse]"
                    )
                    if self.totp_params:
                        remaining = self.totp_params["period"] - (
                            int(time.time()) % self.totp_params["period"]
                        )
                        lines.append(
                            f"[dim]{_totp_progress(remaining, self.totp_params['period'])}[/dim]\n"
                        )
                    else:
                        lines.append("")

                username = self.resource.get("username")
                if username:
                    lines.append(f"[dim]Username:[/dim] {username}")

                uri = self.resource.get("uri")
                if uri:
                    lines.append(f"[dim]URI:[/dim]      {uri}")

                description = self.resource.get("description")
                if description:
                    lines.append(f"[dim]Description:[/dim] {description}")

                return "\n".join(lines)

            def on_mount(self) -> None:
                if self.totp_params:
                    self.set_interval(1, self._update_totp)
                    self._update_totp()

            def _update_totp(self) -> None:
                if not self.totp_params:
                    return
                code = generate_totp(
                    secret_key=self.totp_params["secret_key"],
                    algorithm=self.totp_params["algorithm"],
                    digits=self.totp_params["digits"],
                    period=self.totp_params["period"],
                )
                remaining = self.totp_params["period"] - (
                    int(time.time()) % self.totp_params["period"]
                )
                self.totp_code_display = f"{code} ({remaining}s)"
                self.query_one("#secret-content", Static).update(self._render_content())

            def action_copy_password(self) -> None:
                app._copy_secret(
                    self.resource_id,
                    self.resource.get("name", "Unknown"),
                )

            def action_copy_totp(self) -> None:
                app.action_copy_totp()

            def action_copy_username(self) -> None:
                app.action_copy_username()

            def action_copy_uri(self) -> None:
                app.action_copy_uri()

            def on_unmount(self) -> None:
                app._evict_secret_cache(self.resource_id)

        self.push_screen(
            SecretScreen(password, resource, totp_code, totp_params, resource_id)
        )

    def _check_wallust_theme(self) -> None:
        """Poll wallust colors.json and refresh theme if it changed."""
        try:
            mtime = self._wal_path.stat().st_mtime
        except OSError:
            return
        if mtime == self._wal_mtime:
            return
        self._wal_mtime = mtime
        new_theme = load_wallust_theme()
        if new_theme:
            self.register_theme(new_theme)
            if self.theme == "wallust":
                self.refresh_css(animate=False)


def run_tui(client: PassboltClient, config: PassboltConfig) -> None:
    """Run the Passbolt TUI"""
    import os
    import signal

    app = PassboltTUI(client, config)

    def _sigint_handler(sig: int, frame: Any) -> None:
        nonlocal app
        if app._is_running:
            app.exit()
        else:
            os._exit(130)

    original_handler = signal.signal(signal.SIGINT, _sigint_handler)
    try:
        app.run()
    finally:
        signal.signal(signal.SIGINT, original_handler)