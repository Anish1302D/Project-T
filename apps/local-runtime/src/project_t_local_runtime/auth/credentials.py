"""Per-installation CSPRNG bearer token and OS credential store management."""

from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

_KEYRING_SERVICE = "project-t-local-runtime"
_KEYRING_TOKEN_USER = "installation_bearer_token"


@dataclass(frozen=True, slots=True)
class InstallationCredentials:
    """Installation identity and bearer authentication token."""

    installation_id: str
    bearer_token: str
    storage_backend: str


def _write_restricted_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Windows POSIX mode bits are advisory; best-effort only.
        pass


class CredentialStore:
    """
    Manages the per-installation ID and cryptographically random bearer token.

    Prefers the OS credential store (via keyring if installed and functional),
    falling back safely to an owner-restricted local file inside data_dir.
    """

    def __init__(self, data_dir: Path, *, use_os_keyring: bool = True) -> None:
        self._data_dir = data_dir
        self._use_os_keyring = use_os_keyring
        self._id_file = data_dir / "installation_id"
        self._token_file = data_dir / "auth_token"

    def _try_keyring_get(self, key: str) -> str | None:
        if not self._use_os_keyring:
            return None
        try:
            import keyring  # type: ignore[import-not-found]

            return keyring.get_password(_KEYRING_SERVICE, key)
        except Exception:
            return None

    def _try_keyring_set(self, key: str, value: str) -> bool:
        if not self._use_os_keyring:
            return False
        try:
            import keyring  # type: ignore[import-not-found]

            keyring.set_password(_KEYRING_SERVICE, key, value)
            return True
        except Exception:
            return False

    def load_or_create(self) -> InstallationCredentials:
        self._data_dir.mkdir(parents=True, exist_ok=True)

        if self._id_file.exists():
            installation_id = self._id_file.read_text(encoding="utf-8").strip()
        else:
            installation_id = f"inst_{uuid.uuid4().hex[:16]}"
            _write_restricted_file(self._id_file, installation_id)

        keyring_key = f"{_KEYRING_TOKEN_USER}:{installation_id}"
        token = self._try_keyring_get(keyring_key)
        if token:
            return InstallationCredentials(
                installation_id=installation_id,
                bearer_token=token,
                storage_backend="os_keyring",
            )

        if self._token_file.exists():
            file_token = self._token_file.read_text(encoding="utf-8").strip()
            if file_token:
                return InstallationCredentials(
                    installation_id=installation_id,
                    bearer_token=file_token,
                    storage_backend="restricted_file",
                )

        new_token = secrets.token_urlsafe(32)
        if self._try_keyring_set(keyring_key, new_token):
            backend = "os_keyring"
        else:
            _write_restricted_file(self._token_file, new_token)
            backend = "restricted_file"

        return InstallationCredentials(
            installation_id=installation_id,
            bearer_token=new_token,
            storage_backend=backend,
        )

    def rotate_token(self) -> InstallationCredentials:
        creds = self.load_or_create()
        new_token = secrets.token_urlsafe(32)
        keyring_key = f"{_KEYRING_TOKEN_USER}:{creds.installation_id}"
        if self._try_keyring_set(keyring_key, new_token):
            backend = "os_keyring"
            if self._token_file.exists():
                self._token_file.unlink()
        else:
            _write_restricted_file(self._token_file, new_token)
            backend = "restricted_file"

        return InstallationCredentials(
            installation_id=creds.installation_id,
            bearer_token=new_token,
            storage_backend=backend,
        )
