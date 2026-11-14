"""Create a named Modal Secret and a private local handoff, without printing it.

Run once using the Modal-authenticated Python environment. No .env is read or
changed. The generated key never appears in argv, stdout, or the repository.
"""

import os
from pathlib import Path
import secrets
import tempfile

import modal

from llm_server import SECRET_NAME


def main():
    existing = {secret.name for secret in modal.Secret.objects.list()}
    if SECRET_NAME in existing:
        print(f"Secret {SECRET_NAME} already exists; left unchanged.")
        return
    directory = Path(tempfile.mkdtemp(prefix="stormscore-modal-credential-"))
    os.chmod(directory, 0o700)
    path = directory / "MODAL_API_KEY.txt"
    key = secrets.token_urlsafe(48)
    # Exclusive create plus restrictive permissions before the first byte.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(key + "\n")
    try:
        modal.Secret.objects.create(SECRET_NAME, {"MODAL_API_KEY": key})
    except Exception:
        path.unlink()
        directory.rmdir()
        raise RuntimeError("Modal Secret creation failed; local handoff removed") from None
    print(f"Created Modal Secret {SECRET_NAME}.")
    print(f"Private key handoff (paste locally; do not share): {path}")


if __name__ == "__main__":
    main()
