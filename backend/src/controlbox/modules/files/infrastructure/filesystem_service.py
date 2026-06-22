import os
import shutil
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.shared.domain.base import ForbiddenError, NotFoundError, ValidationError

TEXT_EXTENSIONS = {
    ".txt", ".md", ".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".xml", ".yml", ".yaml", ".env", ".php", ".py", ".sh", ".bash",
    ".conf", ".ini", ".htaccess", ".svg", ".sql", ".vue", ".go", ".rs", ".java",
}
MAX_EDIT_SIZE = 2 * 1024 * 1024
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@dataclass
class FileEntry:
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str
    modified_at: datetime
    extension: str | None = None
    editable: bool = False


@dataclass
class BrowseResult:
    path: str
    parent: str | None
    entries: list[FileEntry]


class PathResolver:
    def __init__(self, settings: Settings) -> None:
        self._base = Path(settings.sites_base_path)

    def tenant_root(self, tenant_id: UUID) -> Path:
        root = (self._base / str(tenant_id)).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def resolve(self, tenant_id: UUID, relative_path: str = "") -> Path:
        root = self.tenant_root(tenant_id)
        clean = relative_path.replace("\\", "/").strip("/")
        if ".." in clean.split("/"):
            raise ForbiddenError("Path traversal not allowed")
        target = (root / clean).resolve() if clean else root
        if not str(target).startswith(str(root)):
            raise ForbiddenError("Access denied")
        return target

    def to_relative(self, tenant_id: UUID, absolute: Path) -> str:
        root = self.tenant_root(tenant_id)
        rel = absolute.relative_to(root)
        return "" if str(rel) == "." else str(rel).replace("\\", "/")


class FileSystemService:
    def __init__(self, settings: Settings) -> None:
        self._resolver = PathResolver(settings)

    def browse(self, tenant_id: UUID, path: str = "") -> BrowseResult:
        target = self._resolver.resolve(tenant_id, path)
        if not target.exists():
            raise NotFoundError("Path not found")
        if not target.is_dir():
            raise ValidationError("Path is not a directory")

        entries: list[FileEntry] = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append(self._to_entry(tenant_id, item))

        parent = self._resolver.to_relative(tenant_id, target.parent)
        if parent == "" and str(target) == str(self._resolver.tenant_root(tenant_id)):
            parent = None

        return BrowseResult(
            path=self._resolver.to_relative(tenant_id, target),
            parent=parent if parent != self._resolver.to_relative(tenant_id, target) else None,
            entries=entries,
        )

    def read_content(self, tenant_id: UUID, path: str) -> tuple[str, str]:
        target = self._resolver.resolve(tenant_id, path)
        if not target.is_file():
            raise NotFoundError("File not found")
        if target.stat().st_size > MAX_EDIT_SIZE:
            raise ValidationError("File too large to edit")
        ext = target.suffix.lower()
        if ext not in TEXT_EXTENSIONS and target.name != ".htaccess":
            raise ValidationError("File type is not editable")
        return target.read_text(encoding="utf-8", errors="replace"), ext

    def get_entry(self, tenant_id: UUID, path: str) -> FileEntry:
        target = self._resolver.resolve(tenant_id, path)
        if not target.exists():
            raise NotFoundError("Path not found")
        return self._to_entry(tenant_id, target)

    def write_content(self, tenant_id: UUID, path: str, content: str) -> FileEntry:
        target = self._resolver.resolve(tenant_id, path)
        ext = target.suffix.lower()
        if ext not in TEXT_EXTENSIONS and target.name != ".htaccess":
            raise ValidationError("File type is not editable")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return self._to_entry(tenant_id, target)

    def upload(self, tenant_id: UUID, directory: str, filename: str, data: bytes) -> FileEntry:
        if len(data) > MAX_UPLOAD_SIZE:
            raise ValidationError("File exceeds maximum upload size")
        safe_name = Path(filename).name
        if not safe_name or safe_name in (".", ".."):
            raise ValidationError("Invalid filename")
        dest_dir = self._resolver.resolve(tenant_id, directory)
        if not dest_dir.is_dir():
            dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / safe_name
        dest.write_bytes(data)
        return self._to_entry(tenant_id, dest)

    def mkdir(self, tenant_id: UUID, path: str) -> FileEntry:
        target = self._resolver.resolve(tenant_id, path)
        target.mkdir(parents=True, exist_ok=False)
        return self._to_entry(tenant_id, target)

    def rename(self, tenant_id: UUID, path: str, new_name: str) -> FileEntry:
        target = self._resolver.resolve(tenant_id, path)
        if not target.exists():
            raise NotFoundError("Path not found")
        safe_name = Path(new_name).name
        if not safe_name:
            raise ValidationError("Invalid name")
        dest = target.parent / safe_name
        if dest.exists():
            raise ValidationError("Destination already exists")
        target.rename(dest)
        return self._to_entry(tenant_id, dest)

    def delete(self, tenant_id: UUID, path: str) -> None:
        target = self._resolver.resolve(tenant_id, path)
        root = self._resolver.tenant_root(tenant_id)
        if target == root:
            raise ForbiddenError("Cannot delete root directory")
        if not target.exists():
            raise NotFoundError("Path not found")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def compress(self, tenant_id: UUID, paths: list[str], archive_name: str, dest_dir: str = "") -> FileEntry:
        if not archive_name.endswith(".zip"):
            archive_name = f"{archive_name}.zip"
        safe_name = Path(archive_name).name
        out_dir = self._resolver.resolve(tenant_id, dest_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        archive_path = out_dir / safe_name
        if archive_path.exists():
            raise ValidationError("Archive already exists")

        root = self._resolver.tenant_root(tenant_id)
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in paths:
                source = self._resolver.resolve(tenant_id, rel)
                if not source.exists():
                    continue
                if source.is_file():
                    arcname = self._resolver.to_relative(tenant_id, source)
                    zf.write(source, arcname)
                else:
                    for file_path in source.rglob("*"):
                        if file_path.is_file():
                            arcname = str(file_path.relative_to(root)).replace("\\", "/")
                            zf.write(file_path, arcname)
        return self._to_entry(tenant_id, archive_path)

    def extract(self, tenant_id: UUID, archive_path: str, dest_dir: str = "") -> BrowseResult:
        archive = self._resolver.resolve(tenant_id, archive_path)
        if not archive.is_file() or archive.suffix.lower() != ".zip":
            raise ValidationError("Only .zip archives are supported")
        out_dir = self._resolver.resolve(tenant_id, dest_dir or str(Path(archive_path).parent))
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "r") as zf:
            for member in zf.namelist():
                if ".." in member.replace("\\", "/"):
                    raise ForbiddenError("Unsafe archive entry")
            zf.extractall(out_dir)
        return self.browse(tenant_id, self._resolver.to_relative(tenant_id, out_dir))

    def get_permissions(self, tenant_id: UUID, path: str) -> dict:
        target = self._resolver.resolve(tenant_id, path)
        if not target.exists():
            raise NotFoundError("Path not found")
        mode = target.stat().st_mode
        return {
            "path": self._resolver.to_relative(tenant_id, target),
            "mode": oct(stat.S_IMODE(mode)),
            "readable": os.access(target, os.R_OK),
            "writable": os.access(target, os.W_OK),
            "executable": os.access(target, os.X_OK),
        }

    def set_permissions(self, tenant_id: UUID, path: str, mode: str) -> dict:
        target = self._resolver.resolve(tenant_id, path)
        if not target.exists():
            raise NotFoundError("Path not found")
        try:
            if mode.startswith("0o") or mode.startswith("0"):
                octal_mode = int(mode, 8)
            else:
                octal_mode = int(mode, 8)
            if octal_mode < 0 or octal_mode > 0o7777:
                raise ValueError
        except ValueError as exc:
            raise ValidationError("Invalid permission mode") from exc
        os.chmod(target, octal_mode)
        return self.get_permissions(tenant_id, path)

    def resolve_download(self, tenant_id: UUID, path: str) -> Path:
        target = self._resolver.resolve(tenant_id, path)
        if not target.is_file():
            raise NotFoundError("File not found")
        return target

    def _to_entry(self, tenant_id: UUID, path: Path) -> FileEntry:
        st = path.stat()
        ext = path.suffix.lower() if path.is_file() else None
        editable = path.is_file() and (ext in TEXT_EXTENSIONS or path.name == ".htaccess")
        return FileEntry(
            name=path.name,
            path=self._resolver.to_relative(tenant_id, path),
            is_dir=path.is_dir(),
            size=st.st_size if path.is_file() else 0,
            permissions=oct(stat.S_IMODE(st.st_mode)),
            modified_at=datetime.fromtimestamp(st.st_mtime),
            extension=ext,
            editable=editable,
        )
