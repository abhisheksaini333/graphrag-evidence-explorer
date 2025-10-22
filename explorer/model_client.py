"""Bounded local model HTTP contract; no automatic generation retries."""
import json
import math
from urllib.parse import urlsplit
import urllib.error
import urllib.request
from .domain import Invalid


class ModelUnavailable(Invalid):
    pass


class ModelClient:
    def __init__(self, url="http://127.0.0.1:8090", timeout=65):
        try:
            if not isinstance(url, str) or any(char.isspace() or ord(char) < 32 for char in url):
                raise ValueError("invalid URL")
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment or parsed.path not in ("", "/")
                    or "\\" in url or (parsed.port is not None and parsed.port < 1)):
                raise ValueError("invalid URL")
        except ValueError as exc:
            raise Invalid("Model URL must be an HTTP origin without credentials") from exc
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise Invalid("Model timeout must be finite and at most 300 seconds")
        self.url, self.timeout = url.rstrip("/"), timeout

    def post(self, path, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        request = urllib.request.Request(
            self.url + path, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ModelUnavailable(
                        "Model response exceeds the bounded contract"
                    )
                return json.loads(raw)
        except (OSError, ValueError) as exc:
            raise ModelUnavailable(
                "Local model request failed; inspect model readiness and request limits"
            ) from exc

    def health(self):
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=5) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ModelUnavailable("Model health exceeds the bounded contract")
                return json.loads(raw)
        except (OSError, ValueError) as exc:
            raise ModelUnavailable("Local model is not ready") from exc

    def generate(self, prompt, max_new_tokens=192):
        return self.post(
            "/generate", {"prompt": prompt, "max_new_tokens": max_new_tokens}
        )

    def embed(self, texts):
        return self.post("/embed", {"texts": texts})
