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
from textual.timer import Timer
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
from passbolt.secret import (
    extract_totp,
    generate_totp,
    get_password_field,
    get_totp_for_resource,
    has_totp,
)
from passbolt.theme import load_wallust_theme

SEARCH_DEBOUNCE_SECONDS = 0.3


class ResourceDetail(Static):
    """Widget to display resource details"""

    resource: reactive[dict[str, Any] | None] = reactive(None)
    totp_display: reactive[str] = reactive("")

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
                lines.append(f"[dim]TOTP:[/dim]        [green]{self.totp_display}[/green]")
            else:
                lines.append(
                    "[dim]TOTP:[/dim]        [green]Available[/green] (press [b]t[/b] to copy)"
                )

        self.update("\n".join(lines))

    def watch_totp_display(self, _value: str) -> None:
        """Refresh detail panel when the live TOTP display changes."""
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
        Binding("escape", "defocus_or_clear", "Results"),
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
        margin: 1 0;
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
        self._secret_cache: dict[str, str] = {}
        self._clipboard_clear_generation: int = 0
        self._last_clipboard_text: str = ""
        self._clipboard_clear_deadline: float | None = None
        self._search_debounce_timer: Timer | None = None
        self._pending_search_query: str = ""
        self._wal_path = Path.home() / ".cache" / "wal" / "colors.json"
        self._wal_mtime: float = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(classes="main-container"):
            with Horizontal(classes="top-bar"):
                yield Input(
                    placeholder="Search passwords... (press / to focus, Enter/Esc to results)",
                    classes="search-input",
                    id="search",
                )

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
        self.load_resources()

    @work(thread=True)
    def load_resources(self, query: str = "") -> None:
        """Load resources from Passbolt in a background thread"""
        try:
            results = self.client.search_resources(query)
            self.call_from_thread(self.set_resources, results)
        except Exception as e:
            self.call_from_thread(self.show_error, f"Error loading resources: {e}")

    def set_resources(self, results: list[dict[str, Any]]) -> None:
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
            return

        for resource in results:
            name = resource.get("name", "Unknown")
            username = resource.get("username", "")
            uri = resource.get("uri", "")
            totp_marker = "●" if has_totp(resource) else ""
            table.add_row(name, username, uri, totp_marker, key=resource.get("id", ""))

        if table.row_count > 0:
            table.move_cursor(row=0)

    def show_error(self, message: str) -> None:
        """Show an error message"""
        loading = self.query_one("#loading-label", Label)
        loading.update(f"[red]{message}[/red]")
        loading.styles.display = "block"
        self.query_one("#detail", ResourceDetail).styles.display = "none"

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
        if resource and has_totp(resource):
            self._refresh_totp_display()

    def _tick_totp_display(self) -> None:
        """Refresh live TOTP display every second for the selected resource."""
        if self.selected_resource and has_totp(self.selected_resource):
            self._refresh_totp_display()

    @work(thread=True)
    def _refresh_totp_display(self) -> None:
        """Compute and display the current TOTP code with countdown."""
        resource = self.selected_resource
        if not resource or not has_totp(resource):
            return

        resource_id = resource.get("id")
        if not resource_id:
            return

        try:
            secret = self.client.get_secret(resource_id)
            totp_params = extract_totp(secret)
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

            def _update() -> None:
                detail = self.query_one("#detail", ResourceDetail)
                if self.selected_resource is resource:
                    detail.totp_display = display

            self.call_from_thread(_update)
        except Exception:
            pass

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debounce"""
        self._pending_search_query = event.value
        if self._search_debounce_timer is not None:
            self._search_debounce_timer.stop()
        self._search_debounce_timer = self.set_timer(
            SEARCH_DEBOUNCE_SECONDS,
            self._run_debounced_search,
        )

    def _run_debounced_search(self) -> None:
        """Run the pending search after debounce."""
        self.load_resources(self._pending_search_query)

    def action_focus_search(self) -> None:
        """Focus the search input"""
        self.query_one("#search", Input).focus()

    def action_defocus_or_clear(self) -> None:
        """Defocus search and move focus to the results table"""
        search = self.query_one("#search", Input)
        search.blur()
        self.query_one("#resource-table", DataTable).focus()

    def action_refresh_resources(self) -> None:
        """Reload resources from the server"""
        search = self.query_one("#search", Input)
        self.load_resources(search.value)
        self.notify("Resources refreshed", severity="information")

    @on(Input.Submitted, "#search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """Pressing Enter in the search box moves focus to the table"""
        self.action_defocus_or_clear()

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

    def _evict_secret_cache(self, resource_id: str) -> None:
        """Overwrite and remove a single cached password."""
        if resource_id in self._secret_cache:
            self._secret_cache[resource_id] = "x" * len(self._secret_cache[resource_id])
            del self._secret_cache[resource_id]

    def _clear_secret_cache(self) -> None:
        """Overwrite and clear cached passwords from memory"""
        for key in list(self._secret_cache.keys()):
            self._secret_cache[key] = "x" * len(self._secret_cache[key])
        self._secret_cache.clear()

    def on_unmount(self) -> None:
        """Clean up sensitive data when app is shutting down"""
        self._clear_secret_cache()

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
            secret = self.client.get_secret(resource_id)
            totp_code = get_totp_for_resource(secret)
            if totp_code is None:
                self.call_from_thread(
                    self.notify, "Could not extract TOTP data", severity="error"
                )
                return
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
            totp_code: str | None = None
            totp_params = None
            if has_totp(resource):
                secret = self.client.get_secret(resource_id)
                totp_params = extract_totp(secret)
                totp_code = get_totp_for_resource(secret)
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
                lines: list[str] = []
                lines.append(f"[b]{resource.get('name', 'Unknown')}[/b]\n")
                lines.append("[b]Password[/b]")
                lines.append(f"[reverse]{password}[/reverse]\n")

                if totp_code or totp_params:
                    lines.append("[b]TOTP[/b]")
                    lines.append(f"[reverse]{self.totp_code_display or totp_code or '...'}[/reverse]\n")

                username = resource.get("username")
                if username:
                    lines.append(f"[dim]Username:[/dim] {username}")

                uri = resource.get("uri")
                if uri:
                    lines.append(f"[dim]URI:[/dim]      {uri}")

                description = resource.get("description")
                if description:
                    lines.append(f"[dim]Description:[/dim] {description}")

                yield Static("\n".join(lines), id="secret-content")
                yield Label(
                    "[dim]Press [b]c[/b] to copy, [b]Esc[/b] or [b]q[/b] to close[/dim]",
                    classes="center",
                )

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
                content = self.query_one("#secret-content", Static)
                lines: list[str] = []
                lines.append(f"[b]{self.resource.get('name', 'Unknown')}[/b]\n")
                lines.append("[b]Password[/b]")
                lines.append(f"[reverse]{self.password}[/reverse]\n")
                lines.append("[b]TOTP[/b]")
                lines.append(f"[reverse]{self.totp_code_display}[/reverse]\n")
                username = self.resource.get("username")
                if username:
                    lines.append(f"[dim]Username:[/dim] {username}")
                uri = self.resource.get("uri")
                if uri:
                    lines.append(f"[dim]URI:[/dim]      {uri}")
                description = self.resource.get("description")
                if description:
                    lines.append(f"[dim]Description:[/dim] {description}")
                content.update("\n".join(lines))

            def action_copy_password(self) -> None:
                app._copy_secret(
                    self.resource_id,
                    self.resource.get("name", "Unknown"),
                )

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