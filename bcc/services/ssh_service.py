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
        return client

    def test(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
    ) -> SSHResult:
        try:
            client = self.connect(host, username, port, password, key_path)
            try:
                _, stdout, _ = client.exec_command("echo BCC_OK && uname -a 2>/dev/null || ver", timeout=15)
                out = stdout.read().decode("utf-8", errors="replace")
                code = stdout.channel.recv_exit_status()
                if "BCC_OK" in out or code == 0:
                    return SSHResult(True, f"SSH OK ke {username}@{host}:{port}", 0, out)
                return SSHResult(False, f"SSH response aneh: {out[:200]}", code, out)
            finally:
                client.close()
        except (paramiko.SSHException, socket.error, OSError, TimeoutError) as e:
            return SSHResult(False, f"SSH gagal: {e}")

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
    ) -> SSHResult:
        try:
            client = self.connect(host, username, port, password, key_path)
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
                msg = "OK" if ok else f"exit {code}"
                return SSHResult(ok, msg, code, out, err)
            finally:
                client.close()
        except Exception as e:
            return SSHResult(False, str(e))

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
    ) -> SSHResult:
        """Upload mapping filename -> content or local_path text files to remote_dir via staging."""
        import tempfile
        from pathlib import Path

        try:
            client = self.connect(host, username, port, password, key_path)
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
                if not r.ok:
                    return r
                return SSHResult(True, f"Uploaded ke {remote_dir}", 0, r.stdout)
            finally:
                client.close()
        except Exception as e:
            log.exception("upload failed")
            return SSHResult(False, str(e))

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
