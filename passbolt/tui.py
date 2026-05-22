"""Textual TUI for Passbolt password lookup"""

import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

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

from passbolt.client import PassboltClient
from passbolt.config import PassboltConfig


class ResourceDetail(Static):
    """Widget to display resource details"""

    resource: reactive[Optional[Dict[str, Any]]] = reactive(None)

    def watch_resource(self, resource: Optional[Dict[str, Any]]) -> None:
        """Update display when resource changes"""
        if resource is None:
            self.update(
                "[#888888 italic]Select a password entry to view details[/]"
            )
            return

        lines: List[str] = []
        lines.append(f"[b]{self._escape(resource.get('name', 'Unknown'))}[/b]\n")

        username = resource.get('username')
        if username:
            lines.append(f"[dim]Username:[/dim]    {self._escape(username)}")

        uri = resource.get('uri')
        if uri:
            lines.append(f"[dim]URI:[/dim]        {self._escape(uri)}")

        description = resource.get('description')
        if description:
            lines.append(f"[dim]Description:[/dim] {self._escape(description)}")

        resource_id = resource.get('id')
        if resource_id:
            lines.append(f"[dim]ID:[/dim]          {self._escape(resource_id)}")

        self.update("\n".join(lines))

    @staticmethod
    def _escape(text: str) -> str:
        """Escape rich markup in text"""
        return text.replace("[", "\\[").replace("]", "\\]")


class SecretDialog(Static):
    """Modal-like widget to display a secret password"""

    def __init__(self, password: str, username: str = "", uri: str = "") -> None:
        super().__init__()
        self.password = password
        self.username = username
        self.uri = uri

    def compose(self) -> ComposeResult:
        lines: List[str] = []
        lines.append("[b]Password[/b]")
        lines.append(f"[reverse]{self.password}[/reverse]\n")

        if self.username:
            lines.append(f"[dim]Username:[/dim] {self.username}")
        if self.uri:
            lines.append(f"[dim]URI:[/dim]      {self.uri}")

        yield Label("\n".join(lines))
        yield Label("[dim]Press [b]Esc[/b] or [b]q[/b] to close[/dim]", classes="center")


class PassboltTUI(App[None]):
    """Passbolt Terminal User Interface"""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "copy_password", "Copy Password"),
        Binding("u", "copy_username", "Copy Username"),
        Binding("o", "copy_uri", "Copy URI"),
        Binding("s", "show_secret", "Show Secret"),
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

    SecretDialog {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    SecretDialog .center {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }

    Footer {
        background: $surface-darken-1;
    }
    """

    resources: reactive[List[Dict[str, Any]]] = reactive([])
    selected_resource: reactive[Optional[Dict[str, Any]]] = reactive(None)

    def __init__(self, client: PassboltClient, config: PassboltConfig) -> None:
        super().__init__()
        self.client = client
        self.config = config
        self._secret_cache: Dict[str, str] = {}

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
                    table.add_columns("Name", "Username", "URI")
                    yield table

                with Vertical(classes="detail-panel"):
                    yield Label("Loading resources...", classes="loading", id="loading-label")
                    yield ResourceDetail(id="detail")

        yield Footer()

    def on_mount(self) -> None:
        """Load resources when app mounts"""
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

    def set_resources(self, results: List[Dict[str, Any]]) -> None:
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
            table.add_row(name, username, uri, key=resource.get("id", ""))

        # Select first row if available
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
    def on_row_selected(self, event: DataTable.RowSelected | DataTable.RowHighlighted) -> None:
        """Handle row selection/highlight"""
        row_key = event.row_key.value
        resource = next((r for r in self.resources if r.get("id") == row_key), None)
        self.selected_resource = resource

    def watch_selected_resource(self, resource: Optional[Dict[str, Any]]) -> None:
        """Update detail panel when selection changes"""
        detail = self.query_one("#detail", ResourceDetail)
        detail.resource = resource

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debounce"""
        self.load_resources(event.value)

    def action_focus_search(self) -> None:
        """Focus the search input"""
        self.query_one("#search", Input).focus()

    def action_defocus_or_clear(self) -> None:
        """Defocus search and move focus to the results table"""
        search = self.query_one("#search", Input)
        search.blur()
        self.query_one("#resource-table", DataTable).focus()

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
        password = self._parse_password(secret)
        self._secret_cache[resource_id] = password
        return password

    @staticmethod
    def _parse_password(secret: str) -> str:
        """Parse password from secret string"""
        try:
            secret_data = json.loads(secret) if isinstance(secret, str) else secret
            if isinstance(secret_data, dict) and "password" in secret_data:
                return str(secret_data["password"])
        except Exception:
            pass
        return secret

    @staticmethod
    def _do_clipboard_copy(text: str) -> tuple[bool, str | List[str]]:
        """Copy text to clipboard. Returns (success, clipboard_cmd)."""
        import os

        clipboard_cmd: Optional[List[str]] = None
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            clipboard_cmd = ["wl-copy"]
        elif os.environ.get("DISPLAY"):
            if shutil.which("xclip"):
                clipboard_cmd = ["xclip", "-selection", "clipboard", "-i"]
            elif shutil.which("xsel"):
                clipboard_cmd = ["xsel", "--clipboard", "--input"]
        elif shutil.which("pbcopy"):
            clipboard_cmd = ["pbcopy"]

        if not clipboard_cmd:
            return False, "No clipboard tool found (install xclip, xsel, wl-clipboard, or pbcopy)"

        try:
            # Use Popen for all clipboard tools. Some (wl-copy, xclip, xsel)
            # stay running to serve clipboard content; waiting for them to exit
            # would hang the application on shutdown.
            proc = subprocess.Popen(
                clipboard_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if proc.stdin is not None:
                proc.stdin.write(text.encode("utf-8"))
                proc.stdin.close()

            # Wait briefly to catch immediate errors, but don't block
            # on clipboard daemons that stay alive.
            try:
                proc.wait(timeout=0.5)
                if proc.returncode != 0:
                    return False, f"Clipboard error (exit {proc.returncode})"
            except subprocess.TimeoutExpired:
                pass  # Daemon-style clipboard tool, expected

            return True, clipboard_cmd
        except Exception as e:
            return False, f"Clipboard error: {e}"

    def _on_clipboard_copy_success(
        self,
        clipboard_cmd: List[str],
        textual_message: str,
        desktop_message: str,
    ) -> None:
        """Handle successful clipboard copy on main thread"""
        self.notify(textual_message, severity="information")
        self._send_desktop_notification("Passbolt", desktop_message)

        if self.config.clipboard_timeout > 0:
            self.set_timer(
                self.config.clipboard_timeout,
                lambda: self._clear_clipboard(clipboard_cmd, desktop_message),
            )

    @work(thread=True)
    def _clear_clipboard(self, clipboard_cmd: List[str], description: str) -> None:
        """Clear clipboard in background thread"""
        try:
            # Use Popen for all clipboard tools so we don't block on
            # daemon-style tools (wl-copy, xclip, xsel) that stay running.
            proc = subprocess.Popen(
                clipboard_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if proc.stdin is not None:
                proc.stdin.close()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass  # Expected for daemon-style clipboard tools

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
    def _show_secret_dialog(self, resource_id: str, resource: Dict[str, Any]) -> None:
        """Fetch and show secret in background thread"""
        try:
            password = self._get_password(resource_id)
            self.call_from_thread(
                self._push_secret_screen, password, resource
            )
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Failed to retrieve password: {e}", severity="error"
            )

    def _push_secret_screen(self, password: str, resource: Dict[str, Any]) -> None:
        """Push a screen showing the secret"""

        class SecretScreen(Screen[None]):
            """Screen to display a secret"""

            BINDINGS = [
                Binding("q", "app.pop_screen", "Close"),
                Binding("escape", "app.pop_screen", "Close"),
            ]

            def __init__(self, password: str, resource: Dict[str, Any]) -> None:
                super().__init__()
                self.password = password
                self.resource = resource

            def compose(self) -> ComposeResult:
                lines: List[str] = []
                lines.append(f"[b]{resource.get('name', 'Unknown')}[/b]\n")
                lines.append("[b]Password[/b]")
                lines.append(f"[reverse]{password}[/reverse]\n")

                username = resource.get("username")
                if username:
                    lines.append(f"[dim]Username:[/dim] {username}")

                uri = resource.get("uri")
                if uri:
                    lines.append(f"[dim]URI:[/dim]      {uri}")

                description = resource.get("description")
                if description:
                    lines.append(f"[dim]Description:[/dim] {description}")

                yield Static("\n".join(lines))
                yield Label(
                    "[dim]Press [b]Esc[/b] or [b]q[/b] to close[/dim]",
                    classes="center",
                )

        self.push_screen(SecretScreen(password, resource))


def run_tui(client: PassboltClient, config: PassboltConfig) -> None:
    """Run the Passbolt TUI"""
    app = PassboltTUI(client, config)
    app.run()
    sys.exit(0)
