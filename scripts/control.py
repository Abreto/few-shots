#!/usr/bin/env python3
"""读取暂停开关：本仓库 main 分支上的 control.toml。

control.toml 示例：
    paused = false
    reason = ""          # 暂停时展示给参与者的说明，可以留空

总是用 GitHub API 的 contents 接口按 ref=main 读取（不读工作区里的文件，也不经 raw 地址约 5 分钟的 CDN 缓存），
所以 PR 分支和 checkout 的版本都影响不了它。
读不到、解析失败或格式不对时按"已暂停"处理（宁可不打分，也不在失控时打分）。

用法：python3 -I scripts/control.py --out work/control.json
输出：work/control.json；向 $GITHUB_OUTPUT 写 paused=true|false。
打分的回帖 job（scripts/report.py）发帖前会再调用一次 fetch_control；记分牌工作流的两个 job 各读一次。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fslib as F  # noqa: E402

CONTROL_URL = f"https://github.com/{F.REPO}/blob/main/control.toml"
CONTROL_API_PATH = f"/repos/{F.REPO}/contents/control.toml"
CONTROL_REF = "main"
MAX_BYTES = 16 * 1024


def _paused(reason: str) -> dict:
    return {"paused": True, "reason": reason}


def parse_control(data: bytes) -> dict:
    """解析 control.toml；任何异常都按暂停处理。"""
    try:
        d = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, RecursionError, MemoryError):
        return _paused("暂停开关文件无法解析，按暂停处理")
    paused = d.get("paused")
    if type(paused) is not bool:
        return _paused("暂停开关缺少布尔值 paused，按暂停处理")
    reason = d.get("reason", "")
    reason = F.sanitize_inline(reason, 200) if isinstance(reason, str) else ""
    return {"paused": paused, "reason": reason}


def _read_only_api(token: str | None) -> F.GitHubAPI:
    return F.GitHubAPI(token, allow_write=False, timeout=15, max_bytes=4 * MAX_BYTES)


def fetch_control(api: F.GitHubAPI | None = None) -> dict:
    """通过 GitHub API（不经 raw 的 CDN 缓存）读取开关；任何失败都按暂停处理。

    本仓库是公开仓库：带令牌的请求被拒（401/403/404）时，再不带令牌读一次。
    """
    if api is None:
        api = _read_only_api(os.environ.get("GITHUB_TOKEN") or None)
    try:
        try:
            obj = api.get(CONTROL_API_PATH, {"ref": CONTROL_REF})
        except F.GitHubAPIError as e:
            if not getattr(api, "token", None) or e.status not in (401, 403, 404):
                raise
            obj = _read_only_api(None).get(CONTROL_API_PATH, {"ref": CONTROL_REF})
    except Exception:
        return _paused("无法读取暂停开关，按暂停处理")
    if not isinstance(obj, dict) or obj.get("type") != "file" or obj.get("encoding") != "base64" \
            or not isinstance(obj.get("content"), str):
        return _paused("暂停开关的读取结果格式异常，按暂停处理")
    try:
        data = base64.b64decode(obj["content"].encode("ascii"), validate=False)
    except (ValueError, binascii.Error, UnicodeEncodeError):
        return _paused("暂停开关的读取结果格式异常，按暂停处理")
    if len(data) > MAX_BYTES:
        return _paused("暂停开关文件过大，按暂停处理")
    return parse_control(data)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="读取暂停开关")
    ap.add_argument("--out", default="work/control.json")
    args = ap.parse_args(argv)
    control = fetch_control()
    F.write_json_file(args.out, control)
    F.set_output("paused", "true" if control["paused"] else "false")
    print(f"paused: {control['paused']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
