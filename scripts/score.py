#!/usr/bin/env python3
"""打分：在隔离容器里运行 main 上该题的验证器，核对 claimed_score，判定是否为有效突破，写结果文件。

题目由门禁从 PR 路径确定（work/gate.json 的 shot.problem），这里再核对一次它是 main 上合规的题目目录，
然后用 main 上的 problems/<题目>/verify/Dockerfile 构建验证器镜像（构建上下文是题目目录）。

判定顺序：
  1. 暂停开关打开 → paused
  2. 门禁未通过 → not_shot / rejected / error
  3. SHOT.md 不合规 → rejected；验证器判无效 → invalid
  4. 对 main 上这道题的每个 shot 重跑验证器：复算无效或与 claimed_score 不一致的不计入纪录（写进 chain_warnings）
  5. claimed_score 与验证结果不完全相等 → claim_mismatch
  6. 证书与 main 上某个 shot 的 canonical_hash 相同 → duplicate
  7. 当前纪录 = 预设基线与 main 上复算通过的 shots（按合并顺序）中的最好成绩：
     未达基线 → below_baseline；达到基线但不优于纪录 → not_record；
     优于纪录但改进不足 ε → below_epsilon；否则 → breakthrough
结果里记下打分时 main 的提交（base_sha），回帖 job 据此判断结果是否过期。

用法（线上）：python3 -I scripts/score.py --work work --image fewshots-verifier:main --out out/result.json
用法（本地无 Docker）：加 --runner local
"""

from __future__ import annotations

import argparse
import re
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fslib as F  # noqa: E402

CONTAINER_START_MARGIN = 30  # 容器启动的额外时间（秒）
BUILD_TIMEOUT = 900          # 构建验证器镜像的超时（秒）
_SAFE_PATH_RE = re.compile(r"/[A-Za-z0-9/._-]+")
_SAFE_IMAGE_RE = re.compile(r"[a-z0-9][a-z0-9._/-]*(?::[A-Za-z0-9._-]+)?(?:@sha256:[0-9a-f]{64})?")


def docker_command(image: str, shot_dir: Path, name: str) -> list:
    """验证器容器：无网络、只读根文件系统、nobody 用户、内存与进程数受限、shot 目录只读挂载。"""
    src = str(Path(shot_dir).absolute())
    if not _SAFE_PATH_RE.fullmatch(src) or not _SAFE_IMAGE_RE.fullmatch(image):
        raise F.VerifierError("非法的镜像名或挂载路径")
    return [
        "docker", "run", "--rm", "--name", name,
        "--network=none",
        "--read-only",
        "--user", "65534:65534",
        "--memory=4g", "--memory-swap=4g",
        "--pids-limit=256",
        "--cpus=2",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--mount", f"type=bind,source={src},target=/shot,readonly",
        image, "/shot",
    ]


def build_command(image: str, problem_dir: Path) -> list:
    """用 main 上题目目录里的 verify/Dockerfile 构建验证器镜像，构建上下文是题目目录。"""
    ctx = str(Path(problem_dir).absolute())
    if not _SAFE_PATH_RE.fullmatch(ctx) or not _SAFE_IMAGE_RE.fullmatch(image):
        raise F.VerifierError("非法的镜像名或构建路径")
    return ["docker", "build", "--pull", "-t", image, "-f", f"{ctx}/verify/Dockerfile", ctx]


def build_image(image: str, problem_dir: Path) -> None:
    try:
        proc = subprocess.run(build_command(image, problem_dir), capture_output=True, timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise F.VerifierError("构建验证器镜像超时") from None
    except OSError:
        raise F.VerifierError("无法启动 docker") from None
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", "replace")[-2000:], file=sys.stderr)
        raise F.VerifierError("构建验证器镜像失败")


def run_verifier_docker(image: str, shot_dir: Path, timeout: int) -> dict:
    name = "fewshots-verify-" + secrets.token_hex(6)
    cmd = docker_command(image, shot_dir, name)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout + CONTAINER_START_MARGIN)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, timeout=30)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
        raise F.VerifierRejected(f"验证超时（{timeout} 秒）") from None
    except OSError:
        raise F.VerifierError("无法启动 docker") from None
    if proc.returncode == 137:
        raise F.VerifierRejected("验证器被强制终止（可能超出内存或进程数限制）")
    if proc.returncode != 0:
        print(proc.stderr.decode("utf-8", "replace")[-2000:], file=sys.stderr)
        raise F.VerifierError(f"容器退出码 {proc.returncode}")
    return F.parse_verifier_output(proc.stdout)


def problem_info(problem: F.Problem) -> dict:
    return {
        "dir": problem.dir, "id": problem.id, "slug": problem.slug, "title_zh": problem.title_zh,
        "metric_zh": problem.metric_zh, "direction": problem.direction,
        "progress_unit": problem.progress_unit, "sandbox": problem.sandbox,
    }


def base_result(problem: F.Problem | None = None) -> dict:
    return {
        "schema": 2,
        "status": "error",
        "messages": [],
        "problem": problem_info(problem) if problem else None,
        "pr": None,
        "shot": None,
        "base_sha": None,
        "baseline": F.fmt(problem.baseline) if problem else None,
        "epsilon": F.fmt(problem.epsilon) if problem else None,
        "epsilon_mode": problem.epsilon_mode if problem else None,
        "score": None,
        "claimed_score": None,
        "record": None,
        "record_ref": None,
        "required": None,
        "progress": None,
        "canonical_hash": None,
        "verifier_message": None,
        "chain_warnings": [],
    }


def build_result(work: Path, root: Path, make_verifier) -> dict:
    """make_verifier(problem) 返回 verifier(shot_dir) -> dict；它可以在这里先构建镜像，失败时抛 VerifierError。"""
    res = base_result()
    res["base_sha"] = F.git_head(root)
    try:
        control = F.read_json_file(work / "control.json")
    except (OSError, ValueError):
        res["messages"] = ["未能读取暂停开关的结果，按出错处理"]
        return res
    if control.get("paused") is not False:
        res["status"] = "paused"
        reason = control.get("reason")
        res["messages"] = [reason] if isinstance(reason, str) and reason else []
        return res
    try:
        gate = F.read_json_file(work / "gate.json")
    except (OSError, ValueError):
        res["messages"] = ["门禁没有产出结果"]
        return res
    res["pr"] = gate.get("pr")
    if not gate.get("ok"):
        status = gate.get("status")
        res["status"] = status if status in ("not_shot", "rejected", "error") else "error"
        res["messages"] = [m for m in gate.get("messages", []) if isinstance(m, str)][:20]
        return res
    shot = gate.get("shot") or {}
    pdir, login, shot_id = shot.get("problem"), shot.get("login"), shot.get("shot_id")
    try:
        problem = F.load_problem_dir(root, pdir)
    except (F.ConfigError, OSError, ValueError):
        res["messages"] = ["门禁给出的题目目录在 main 上无法读取"]
        return res
    if not (isinstance(login, str) and F.LOGIN_RE.fullmatch(login)
            and isinstance(shot_id, str) and F.SHOT_ID_RE.fullmatch(shot_id)):
        res["messages"] = ["门禁结果格式异常"]
        return res
    res.update({k: v for k, v in base_result(problem).items() if k not in ("pr", "base_sha")})
    res["shot"] = {"problem": pdir, "login": login, "shot_id": shot_id}
    try:
        verifier = make_verifier(problem)
    except F.VerifierError as e:
        res["messages"] = [f"验证器准备失败：{e}"]
        return res
    merged, _source = F.list_merged_shots(root, pdir, exclude={f"{login}/{shot_id}"})
    res.update(F.evaluate_shot(problem, work / "shot", login, verifier, merged))
    return res


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="运行验证器并判定")
    ap.add_argument("--work", default="work")
    ap.add_argument("--out", default="out/result.json")
    ap.add_argument("--root", default=str(F.REPO_ROOT), help="main 的 checkout 目录")
    ap.add_argument("--runner", choices=("docker", "local"), default="docker")
    ap.add_argument("--image", default="fewshots-verifier:main")
    args = ap.parse_args(argv)
    root = Path(args.root)

    def make_verifier(problem: F.Problem):
        pdir = F.problem_path(root, problem.dir)
        timeout = problem.verifier_timeout_sec
        if args.runner == "docker":
            build_image(args.image, pdir)
            return lambda d: run_verifier_docker(args.image, d, timeout)
        return lambda d: F.run_verifier_local(d, timeout, pdir / "verify" / "verify.py")

    try:
        res = build_result(Path(args.work), root, make_verifier)
    except Exception as e:  # 结果文件必须产出，回帖 job 才能说明情况
        print(f"score internal error: {type(e).__name__}", file=sys.stderr)
        res = base_result()
        res["messages"] = ["打分脚本内部错误，请联系裁判组"]
    F.write_json_file(args.out, res)
    print(f"score: {res['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
