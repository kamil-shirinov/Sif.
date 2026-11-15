"""Fetch and hash-check public tokenizer files during the CPU image build."""
import hashlib
from pathlib import Path
import urllib.request

FILES = {
    "o200k_base.tiktoken": "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d",
    "cl100k_base.tiktoken": "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
}


def main():
    directory = Path("/opt/tiktoken-cache")
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        url = "https://openaipublic.blob.core.windows.net/encodings/" + name
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("Public tokenizer checksum mismatch")
        (directory / name).write_bytes(data)
        (directory / hashlib.sha1(url.encode()).hexdigest()).write_bytes(data)
    print("Public tokenizer files cached and verified")


if __name__ == "__main__":
    main()
