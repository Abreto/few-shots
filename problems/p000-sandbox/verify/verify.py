#!/usr/bin/env python3
"""验证器（p000 沙盒：Golomb 尺）。

契约（所有题目通用）：
    python verify.py <shot_dir>
读取 <shot_dir>/certificate.json，向标准输出打印且只打印一行 JSON：
    {"valid": bool, "score": "精确有理数字符串" | null,
     "canonical_hash": "证书规范化后的 sha256（hex）" | null, "message": str}
退出码：0 表示已给出结论（无论 valid 真假）；非 0 表示用法或配置错误。

安全约束：只解析 JSON 与整数；不 eval、不 pickle、不 yaml.load、不做符号计算；
不访问网络；不回显输入中的字符串。只依赖 Python 3.12 标准库。

新题从这份文件出发：保留 load_config / read_certificate / strict_json / emit 等通用部分，
只改 check_certificate（题目规则、打分与规范化）。problem.toml 在本文件上一级目录（题目目录）里。
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

CERT_NAME = "certificate.json"
MAX_DEPTH = 8                 # JSON 最大嵌套深度
MAX_INT_DIGITS = 18           # 单个整数最多位数
MAX_ABS_MARK = 10**15         # 刻度绝对值上限
MAX_N = 2000                  # 刻度个数上限（差值检查是 O(n^2)）


class Invalid(Exception):
    """证书不合法；消息会原样出现在结果里，因此不得包含输入中的字符串。"""


# ---------- 配置 ----------

def find_problem_toml() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here / "problem.toml", here.parent / "problem.toml"):
        if cand.is_file():
            return cand
    raise FileNotFoundError("problem.toml not found")


def load_config(path: Path | None = None) -> dict:
    with open(path or find_problem_toml(), "rb") as f:
        data = tomllib.load(f)
    n = data["params"]["n"]
    limit = data["max_certificate_bytes"]
    if type(n) is not int or not 2 <= n <= MAX_N:
        raise ValueError("params.n out of range")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"n": n, "max_certificate_bytes": limit}


# ---------- 读取与解析（通用） ----------

def read_certificate(shot_dir: str | os.PathLike, limit: int) -> bytes:
    path = Path(shot_dir) / CERT_NAME
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise Invalid("缺少 certificate.json") from None
    except OSError:
        raise Invalid("无法读取 certificate.json（不允许符号链接）") from None
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise Invalid("certificate.json 不是普通文件")
        if st.st_size > limit:
            raise Invalid(f"certificate.json 超过大小上限 {limit} 字节")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise Invalid(f"certificate.json 超过大小上限 {limit} 字节")
    return data


def check_depth(text: str, limit: int = MAX_DEPTH) -> None:
    depth = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise Invalid(f"JSON 嵌套超过 {limit} 层")
        elif ch in "]}":
            depth -= 1


def _no_float(_s: str):
    raise Invalid("不允许小数或指数形式的数字")


def _no_constant(_s: str):
    raise Invalid("不允许 NaN 或 Infinity")


def _bounded_int(s: str) -> int:
    if len(s.lstrip("-")) > MAX_INT_DIGITS:
        raise Invalid(f"整数超过 {MAX_INT_DIGITS} 位")
    return int(s)


def _unique_keys(pairs: list) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise Invalid("JSON 对象中有重复的键")
        out[k] = v
    return out


def strict_json(data: bytes):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Invalid("certificate.json 必须是 UTF-8 文本") from None
    check_depth(text)
    try:
        return json.loads(
            text,
            parse_float=_no_float,
            parse_int=_bounded_int,
            parse_constant=_no_constant,
            object_pairs_hook=_unique_keys,
        )
    except RecursionError:
        raise Invalid("JSON 嵌套过深") from None
    except ValueError:
        raise Invalid("certificate.json 不是合法的 JSON") from None


def is_int(x) -> bool:
    return type(x) is int  # 排除 bool


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


# ---------- 题目规则（换题时只改这里） ----------

def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """返回 (score, 规范化对象)。Golomb 尺：n 个整数刻度，两两差互不相同；分数 = 长度。"""
    n = cfg["n"]
    if not isinstance(cert, dict):
        raise Invalid('证书必须是 JSON 对象，形如 {"marks": [...]}')
    extra = set(cert) - {"marks", "n"}
    if extra:
        raise Invalid("证书只允许 marks 与 n 两个键")
    if "n" in cert and (not is_int(cert["n"]) or cert["n"] != n):
        raise Invalid(f"n 必须等于 {n}")
    marks = cert.get("marks")
    if not isinstance(marks, list):
        raise Invalid("marks 必须是整数数组")
    if len(marks) != n:
        raise Invalid(f"marks 必须恰好有 {n} 个刻度，实际 {len(marks)} 个")
    for m in marks:
        if not is_int(m):
            raise Invalid("每个刻度都必须是整数")
        if abs(m) > MAX_ABS_MARK:
            raise Invalid("刻度绝对值超过上限 10^15")
    if len(set(marks)) != n:
        raise Invalid("刻度有重复")
    xs = sorted(marks)
    seen: set[int] = set()
    for i in range(n):
        for j in range(i + 1, n):
            d = xs[j] - xs[i]
            if d in seen:
                raise Invalid(f"差值 {d} 出现了不止一次，不是 Golomb 尺")
            seen.add(d)
    length = xs[-1] - xs[0]
    # 规范化：平移到 0 起点，取自身与镜像中字典序较小者
    a = [x - xs[0] for x in xs]
    b = sorted(length - x for x in a)
    canon = {"marks": min(a, b), "n": n}
    return Fraction(length), canon


# ---------- 入口 ----------

def verify_bytes(data: bytes, cfg: dict) -> dict:
    cert = strict_json(data)
    score, canon = check_certificate(cert, cfg)
    return {
        "valid": True,
        "score": str(score),
        "canonical_hash": canonical_hash(canon),
        "message": "ok",
    }


def verify_dir(shot_dir: str | os.PathLike, cfg: dict) -> dict:
    try:
        return verify_bytes(read_certificate(shot_dir, cfg["max_certificate_bytes"]), cfg)
    except Invalid as e:
        return invalid(str(e))
    except RecursionError:
        return invalid("JSON 嵌套过深")
    except MemoryError:
        return invalid("输入过大")
    except Exception:  # 不输出堆栈，避免泄露细节
        return invalid("验证器内部错误")


def invalid(message: str) -> dict:
    return {"valid": False, "score": None, "canonical_hash": None, "message": message}


def emit(result: dict) -> None:
    line = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(line.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        emit(invalid("用法：python verify.py <shot_dir>"))
        return 2
    try:
        cfg = load_config()
    except Exception:
        emit(invalid("验证器配置错误"))
        return 2
    emit(verify_dir(argv[1], cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
