from __future__ import annotations

"""Command implementations for Passbolt CLI"""

import sys
import os
import subprocess
import shutil
from typing import Any

from passbolt.client import PassboltClient
from passbolt.config import PassboltConfig


def copy_password(client: PassboltClient, password_name: str, config: PassboltConfig | None = None) -> None:
    """Copy a password to the clipboard"""
    # Find the resource (by UUID or name)
    resource: dict[str, Any] | None = client.find_resource_by_name_or_id(password_name)
    
    if not resource:
        print(f"Error: Password '{password_name}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Get the secret
    try:
        resource_id: str = resource['id']
        secret: str = client.get_secret(resource_id)
        
        # Parse secret if it's JSON
        try:
            secret_data = eval(secret) if isinstance(secret, str) else secret
            if isinstance(secret_data, dict) and 'password' in secret_data:
                password: str = secret_data['password']
            else:
                password = secret
        except Exception:
            password = secret
        
        # Copy to clipboard using system clipboard tools
        # Try different clipboard mechanisms in order of preference
        clipboard_cmd: list[str] | None = None
        
        # Check for Wayland (wl-copy) - only if actually in Wayland session
        if os.environ.get('WAYLAND_DISPLAY') and shutil.which('wl-copy'):
            clipboard_cmd = ['wl-copy']
        # Check for X11 (xclip or xsel)
        elif os.environ.get('DISPLAY'):
            if shutil.which('xclip'):
                clipboard_cmd = ['xclip', '-selection', 'clipboard', '-i']
            elif shutil.which('xsel'):
                clipboard_cmd = ['xsel', '--clipboard', '--input']
        # Check for macOS (pbcopy)
        elif shutil.which('pbcopy'):
            clipboard_cmd = ['pbcopy']
        
        if not clipboard_cmd:
            print("Error: No clipboard tool found (install xclip, xsel, wl-clipboard, or pbcopy)", file=sys.stderr)
            sys.exit(1)
        
        try:
            # xclip/xsel need to stay running to serve clipboard content
            # Use Popen to fork them to background
            if clipboard_cmd[0] in ['xclip', 'xsel']:
                proc = subprocess.Popen(
                    clipboard_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.stdin.write(password.encode('utf-8'))
                proc.stdin.close()
                # Don't wait for the process - let it run in background
                
                # Start background process to clear clipboard after timeout
                if config and config.clipboard_timeout > 0:
                    # Use a simple approach: just clear after timeout without checking content
                    # This avoids exposing the password in process list
                    clear_script = f'''import time, subprocess
time.sleep({config.clipboard_timeout})
subprocess.run({repr(clipboard_cmd)}, input='', text=True, stdout=subprocess.devnull if hasattr(subprocess, 'devnull') else None, stderr=subprocess.devnull if hasattr(subprocess, 'devnull') else None)
'''
                    subprocess.Popen(
                        [sys.executable, '-c', clear_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
            else:
                result = subprocess.run(
                    clipboard_cmd,
                    input=password,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                if result.returncode != 0:
                    print(f"Error copying to clipboard: {result.stderr}", file=sys.stderr)
                    sys.exit(1)
        except Exception as e:
            print(f"Error copying to clipboard: {e}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Password for '{resource['name']}' copied to clipboard")
        
    except Exception as e:
        print(f"Error retrieving password: {e}", file=sys.stderr)
        sys.exit(1)


def search_passwords(client: PassboltClient, query: str) -> None:
    """Search for passwords matching the query"""
    try:
        results: list[dict[str, Any]] = client.search_resources(query)
        
        if not results:
            print(f"No passwords found matching '{query}'")
            return
        
        print(f"Found {len(results)} password(s):\n")
        
        for resource in results:
            name = resource.get('name', 'Unknown')
            resource_id = resource.get('id', '')
            username = resource.get('username', '')
            uri = resource.get('uri', '')
            description = resource.get('description', '')
            
            print(f"  • {name}")
            print(f"    ID: {resource_id}")
            if username:
                print(f"    Username: {username}")
            if uri:
                print(f"    URI: {uri}")
            if description:
                print(f"    Description: {description}")
            print()
            
    except Exception as e:
        print(f"Error searching passwords: {e}", file=sys.stderr)
        sys.exit(1)


def export_password(client: PassboltClient, password_name: str, pass_path: str) -> None:
    """Export a password to password-store (pass)"""
    # Find the resource (by UUID or name)
    resource: dict[str, Any] | None = client.find_resource_by_name_or_id(password_name)
    
    if not resource:
        print(f"Error: Password '{password_name}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Get the secret
    try:
        resource_id = resource['id']
        secret = client.get_secret(resource_id)
        
        # Parse secret if it's JSON
        try:
            secret_data = eval(secret) if isinstance(secret, str) else secret
            if isinstance(secret_data, dict):
                password = secret_data.get('password', secret)
                username = resource.get('username', '')
                uri = resource.get('uri', '')
                
                # Build multiline pass entry
                pass_content = password
                if username or uri:
                    pass_content += '\n'
                if username:
                    pass_content += f'username: {username}\n'
                if uri:
                    pass_content += f'url: {uri}\n'
            else:
                pass_content = secret
        except Exception:
            pass_content = secret
        
        # Insert into pass
        result = subprocess.run(
            ['pass', 'insert', '-m', pass_path],
            input=pass_content,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"Password exported to pass as '{pass_path}'")
        else:
            print(f"Error exporting to pass: {result.stderr}", file=sys.stderr)
            sys.exit(1)
            
    except FileNotFoundError:
        print("Error: 'pass' (password-store) is not installed", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error exporting password: {e}", file=sys.stderr)
        sys.exit(1)


def show_password(client: PassboltClient, password_name: str) -> None:
    """Display password on stdout"""
    # Find the resource (by UUID or name)
    resource: dict[str, Any] | None = client.find_resource_by_name_or_id(password_name)
    
    if not resource:
        print(f"Error: Password '{password_name}' not found", file=sys.stderr)
        sys.exit(1)
    
    # Get the secret
    try:
        resource_id = resource['id']
        secret = client.get_secret(resource_id)
        
        # Parse secret if it's JSON
        try:
            secret_data = eval(secret) if isinstance(secret, str) else secret
            if isinstance(secret_data, dict):
                password = secret_data.get('password', secret)
                username = resource.get('username', '')
                uri = resource.get('uri', '')
                
                # Build output in pass format
                output = password
                if username or uri:
                    output += '\n'
                if username:
                    output += f'username: {username}\n'
                if uri:
                    output += f'url: {uri}\n'
                print(output, end='')
            else:
                print(secret)
        except Exception:
            print(secret)
            
    except Exception as e:
        print(f"Error retrieving password: {e}", file=sys.stderr)
        sys.exit(1)
