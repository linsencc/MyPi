# -*- coding: utf-8 -*-
"""HTTPS 下载：磁盘缓存 + 重试 + 代理 + urllib / requests / curl 多路回退。"""
from __future__ import annotations

import hashlib
import os
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_DIR, ".image-cache")


def cache_path_for_url(url: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return os.path.join(_CACHE, h + ".dat")


def _atomic_write(path: str, data: bytes) -> None:
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix="dl.", suffix=".part", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    return ctx


def _urllib_fetch(url: str, timeout: int) -> bytes:
    ctx = _ssl_context()
    proxies = urllib.request.getproxies()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(proxies),
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPHandler(),
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DigitalFrame/1.2; +https://example.invalid)"
        },
    )
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def _requests_fetch(url: str, timeout: int) -> bytes:
    import requests

    proxies = requests.utils.get_environ_proxies(url)
    r = requests.get(
        url,
        timeout=(15, timeout),
        proxies=proxies,
        headers={"User-Agent": "DigitalFrame/1.2"},
    )
    r.raise_for_status()
    return r.content


def _curl_fetch(url: str, timeout: int) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".curl")
    os.close(fd)
    try:
        subprocess.run(
            [
                "curl",
                "-fsSL",
                "--globoff",
                "-L",
                "--connect-timeout",
                "20",
                "-m",
                str(timeout),
                "-A",
                "DigitalFrame/1.2",
                "-o",
                path,
                url,
            ],
            check=True,
            timeout=timeout + 20,
            env=os.environ.copy(),
        )
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def fetch_url_bytes(url: str, timeout: int = 120, use_cache: bool = True) -> bytes:
    """
    下载 URL 字节；成功则写入 .image-cache（按 URL 哈希命名）。
    顺序：缓存命中 → urllib×3 → requests×1 → curl×1。
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("fetch_url_bytes 需要 http(s) URL")

    cp = cache_path_for_url(url)
    if use_cache and os.path.isfile(cp) and os.path.getsize(cp) > 64:
        with open(cp, "rb") as f:
            return f.read()

    errors: list[str] = []

    for attempt in range(3):
        try:
            data = _urllib_fetch(url, timeout)
            if len(data) < 64:
                raise ValueError("响应过短，疑似错误页")
            if use_cache:
                _atomic_write(cp, data)
            return data
        except Exception as e:
            errors.append(f"urllib[{attempt + 1}]: {e!r}")
            time.sleep(0.6 * (attempt + 1))

    try:
        data = _requests_fetch(url, timeout)
        if len(data) < 64:
            raise ValueError("响应过短")
        if use_cache:
            _atomic_write(cp, data)
        return data
    except ImportError:
        errors.append("requests: 未安装")
    except Exception as e:
        errors.append(f"requests: {e!r}")

    try:
        data = _curl_fetch(url, timeout)
        if len(data) < 64:
            raise ValueError("响应过短")
        if use_cache:
            _atomic_write(cp, data)
        return data
    except FileNotFoundError:
        errors.append("curl: 未找到命令")
    except Exception as e:
        errors.append(f"curl: {e!r}")

    raise RuntimeError(
        "下载失败（已尝试 urllib 重试、requests、curl）。\n"
        + "\n".join(errors)
        + "\n提示：可设置 http_proxy/https_proxy；或先执行 show_poster.py --prefetch；"
        "或使用本地图 --image / -j 中 image_file。"
    ) from None
