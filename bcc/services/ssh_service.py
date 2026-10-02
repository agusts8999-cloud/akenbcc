"""SSH helpers via Paramiko."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from typing import Optional

import paramiko
from paramiko import AutoAddPolicy, SSHClient

log = logging.getLogger(__name__)


@dataclass
class SSHResult:
    ok: bool
    message: str
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    host_used: str = ""


def lan_then_tailscale(lan_host: str, tailscale_host: str) -> tuple[list[str], list[int]]:
    """LAN first with a short timeout, then Tailscale. Never stick to the last path."""
    hosts: list[str] = []
    timeouts: list[int] = []
    lan = (lan_host or "").strip()
    remote = (tailscale_host or "").strip()
    if lan:
        hosts.append(lan)
        timeouts.append(3)
    if remote and remote not in hosts:
        hosts.append(remote)
        timeouts.append(20)
    return hosts, timeouts


def target_route(target: dict) -> dict:
    """SSH kwargs for a backup target: LAN probe, then Tailscale."""
    hosts, timeouts = lan_then_tailscale(target.get("lan_host") or "", target.get("host") or "")
    if not hosts:
        return {}
    return {"hosts": hosts, "connect_timeouts": timeouts}


def ordered_hosts(host: str, alt_host: str = "", last_host: str = "") -> list[str]:
    """Last successful address first, then primary, then alternate. No duplicates."""
    order: list[str] = []
    for item in (last_host, host, alt_host):
        item = (item or "").strip()
        if item and item not in order:
            order.append(item)
    return order


class SSHService:
    def connect(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        timeout: int = 20,
    ) -> SSHClient:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_path:
            kwargs["key_filename"] = key_path
            kwargs["look_for_keys"] = True
        if password:
            kwargs["password"] = password
        client.connect(**kwargs)
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        return client

    def _host_list(self, host: str, hosts: Optional[list[str]]) -> list[str]:
        if hosts:
            return [h.strip() for h in hosts if h and h.strip()]
        return [host] if host else []

    def _open_first(
        self,
        hosts: list[str],
        username: str,
        port: int,
        password: str,
        key_path: str,
        timeout: int,
        timeouts: Optional[list[int]] = None,
    ) -> tuple[Optional[SSHClient], str, list[str]]:
        errors: list[str] = []
        for index, candidate in enumerate(hosts):
            wait = timeouts[index] if timeouts and index < len(timeouts) else timeout
            try:
                return self.connect(candidate, username, port, password, key_path, wait), candidate, errors
            except (paramiko.SSHException, socket.error, OSError, TimeoutError) as e:
                errors.append(f"{candidate}: {e}")
        return None, "", errors

    @staticmethod
    def _fail_note(errors: list[str]) -> str:
        if not errors:
            return ""
        return " | pindah jalur, gagal sebelumnya: " + "; ".join(errors)

    def test(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        hosts: Optional[list[str]] = None,
        connect_timeouts: Optional[list[int]] = None,
    ) -> SSHResult:
        order = self._host_list(host, hosts)
        client, used, errors = self._open_first(
            order, username, port, password, key_path, 20, connect_timeouts
        )
        if client is None:
            return SSHResult(False, "SSH gagal: " + "; ".join(errors))
        try:
            _, stdout, _ = client.exec_command("echo BCC_OK && uname -a 2>/dev/null || ver", timeout=15)
            out = stdout.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            note = self._fail_note(errors)
            if "BCC_OK" in out or code == 0:
                return SSHResult(True, f"SSH OK ke {username}@{used}:{port}{note}", 0, out, host_used=used)
            return SSHResult(False, f"SSH response aneh: {out[:200]}{note}", code, out, host_used=used)
        except (paramiko.SSHException, socket.error, OSError, TimeoutError) as e:
            return SSHResult(False, f"SSH gagal di {used}: {e}", host_used=used)
        finally:
            client.close()

    def run(
        self,
        host: str,
        username: str,
        command: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        timeout: int = 120,
        sudo_password: str = "",
        hosts: Optional[list[str]] = None,
        connect_timeouts: Optional[list[int]] = None,
    ) -> SSHResult:
        order = self._host_list(host, hosts)
        client, used, errors = self._open_first(
            order, username, port, password, key_path, 20, connect_timeouts
        )
        if client is None:
            return SSHResult(False, "SSH gagal: " + "; ".join(errors))
        try:
            cmd = command
            if sudo_password:
                esc = sudo_password.replace("'", "'\\''")
                cmd = f"echo '{esc}' | sudo -S -p '' bash -lc {self._shell_quote(command)}"
            _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=bool(sudo_password))
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            ok = code == 0
            msg = ("OK" if ok else f"exit {code}") + self._fail_note(errors)
            return SSHResult(ok, msg, code, out, err, host_used=used)
        except Exception as e:
            text = str(e).strip() or "SSH terputus"
            return SSHResult(False, f"{used}: {text}", host_used=used)
        finally:
            client.close()

    def upload_dir_files(
        self,
        host: str,
        username: str,
        local_files: dict[str, str],
        remote_dir: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        sudo_password: str = "",
        hosts: Optional[list[str]] = None,
        connect_timeouts: Optional[list[int]] = None,
    ) -> SSHResult:
        """Upload mapping filename -> content or local_path text files to remote_dir via staging."""
        import tempfile
        from pathlib import Path

        order = self._host_list(host, hosts)
        client, used, errors = self._open_first(
            order, username, port, password, key_path, 20, connect_timeouts
        )
        if client is None:
            return SSHResult(False, "SSH gagal: " + "; ".join(errors))
        try:
            try:
                staging = f"/tmp/bcc_upload_{os_getpid()}"
                self._exec(client, f"rm -rf {staging} && mkdir -p {staging}")
                sftp = client.open_sftp()
                try:
                    for name, content in local_files.items():
                        remote = f"{staging}/{name}"
                        if "\n" not in content and Path(content).is_file():
                            sftp.put(content, remote)
                        else:
                            with sftp.file(remote, "w") as f:
                                data = content if isinstance(content, str) else str(content)
                                f.write(data.replace("\r\n", "\n"))
                finally:
                    sftp.close()

                # move to target (maybe needs sudo)
                if sudo_password:
                    esc = sudo_password.replace("'", "'\\''")
                    cmd = (
                        f"echo '{esc}' | sudo -S -p '' bash -c "
                        f"'mkdir -p {remote_dir} && cp -a {staging}/. {remote_dir}/ "
                        f"&& chown -R root:root {remote_dir} 2>/dev/null || true "
                        f"&& chmod 700 {remote_dir}/*.sh 2>/dev/null || true "
                        f"&& chmod 600 {remote_dir}/config.sh 2>/dev/null || true "
                        f"&& sed -i \"s/\\r$//\" {remote_dir}/*.sh {remote_dir}/config.sh {remote_dir}/lib.sh 2>/dev/null || true'"
                    )
                else:
                    cmd = (
                        f"mkdir -p {remote_dir} && cp -a {staging}/. {remote_dir}/ "
                        f"&& chmod 700 {remote_dir}/*.sh 2>/dev/null || true "
                        f"&& chmod 600 {remote_dir}/config.sh 2>/dev/null || true"
                    )
                r = self._exec(client, cmd, timeout=120)
                self._exec(client, f"rm -rf {staging}", timeout=30)
                note = self._fail_note(errors)
                if not r.ok:
                    r.host_used = used
                    r.message = (r.message or "") + note
                    return r
                return SSHResult(True, f"Uploaded ke {remote_dir} via {used}{note}", 0, r.stdout, host_used=used)
            finally:
                client.close()
        except Exception as e:
            log.exception("upload failed")
            text = str(e).strip() or "SSH terputus"
            return SSHResult(False, f"{used}: {text}", host_used=used)

    def _exec(self, client: SSHClient, cmd: str, timeout: int = 60) -> SSHResult:
        _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return SSHResult(code == 0, "OK" if code == 0 else f"exit {code}", code, out, err)

    @staticmethod
    def _shell_quote(s: str) -> str:
        return "'" + s.replace("'", "'\"'\"'") + "'"


def os_getpid() -> int:
    import os

    return os.getpid()
