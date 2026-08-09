"""
Build Backup Control Center one-file EXE:
  dist/BackupControlCenter-{version}-{build}.exe
  + desktop shortcut with logo icon
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bcc.version import executable_basename, file_version_tuple, full_version  # noqa: E402


def ensure_ico() -> Path:
    from PIL import Image

    assets = ROOT / "bcc" / "assets"
    png = assets / "logo.png"
    ico = assets / "logo.ico"
    if not png.is_file():
        raise SystemExit(f"Logo PNG missing: {png}")
    img = Image.open(png).convert("RGBA")
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico, format="ICO", sizes=sizes)
    print(f"[OK] ICO: {ico}")
    return ico


def write_version_file(path: Path) -> None:
    maj, mino, patch, build = file_version_tuple()
    # PyInstaller version file format
    content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({maj}, {mino}, {patch}, {build}),
    prodvers=({maj}, {mino}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'BCC'),
        StringStruct(u'FileDescription', u'Backup Control Center'),
        StringStruct(u'FileVersion', u'{full_version()}'),
        StringStruct(u'InternalName', u'BackupControlCenter'),
        StringStruct(u'LegalCopyright', u''),
        StringStruct(u'OriginalFilename', u'{executable_basename()}.exe'),
        StringStruct(u'ProductName', u'Backup Control Center'),
        StringStruct(u'ProductVersion', u'{full_version()}')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"[OK] version file: {path}")


def main() -> int:
    print(f"=== Building BCC {full_version()} ===")
    ico = ensure_ico()
    basename = executable_basename()
    version_file = ROOT / "bcc_version_info.txt"
    write_version_file(version_file)

    # Clean previous one-file with same name
    dist = ROOT / "dist"
    build_dir = ROOT / "build"
    dist.mkdir(exist_ok=True)

    # Windows pathsep for --add-data is ;
    sep = ";" if sys.platform.startswith("win") else ":"
    add_templates = f"{ROOT / 'bcc' / 'templates'}{sep}bcc/templates"
    add_assets = f"{ROOT / 'bcc' / 'assets'}{sep}bcc/assets"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        f"--name={basename}",
        f"--icon={ico}",
        f"--version-file={version_file}",
        f"--add-data={add_templates}",
        f"--add-data={add_assets}",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=customtkinter",
        str(ROOT / "run_bcc.py"),
    ]
    print("Running:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        return r.returncode

    exe = dist / f"{basename}.exe"
    if not exe.is_file():
        print(f"[ERROR] EXE not found: {exe}")
        return 1
    print(f"[OK] EXE: {exe} ({exe.stat().st_size // 1024} KB)")

    # Copy ico next to exe for shortcut icon convenience
    shutil.copy2(ico, dist / "logo.ico")

    # Create desktop shortcut
    ps1 = ROOT / "scripts" / "create_shortcut.ps1"
    if ps1.is_file():
        sc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1),
                "-ExePath",
                str(exe),
                "-IconPath",
                str(dist / "logo.ico"),
            ],
            cwd=str(ROOT),
        )
        if sc.returncode != 0:
            print("[WARN] shortcut script exit", sc.returncode)
        else:
            print("[OK] Desktop shortcut created")

    print("=== Build selesai ===")
    print(f"Artifact: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
