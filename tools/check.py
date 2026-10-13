#!/usr/bin/env python3
"""本地自检：提交 PR 前先跑一遍，规则与线上打分一致（线上在容器里跑验证器，这里直接用 python 跑）。

用法：python3 tools/check.py problems/<题目目录>/shots/<你的 GitHub 登录名>/<shot-id> [--json]

检查内容：
  1. 位置：shot 目录必须是本仓库的 problems/<题目目录>/shots/<login>/<shot-id>，题目目录要有 problem.toml
  2. 目录与文件白名单（文件类型、隐藏文件、符号链接、子目录、文件数与大小）
  3. SHOT.md（TOML front matter 与两节正文）
  4. 运行这道题的验证器，核对 claimed_score 是否与验证结果完全一致
  5. 复算本地仓库里这道题的其他 shot，按合并顺序取最好成绩为当前纪录（不含本 shot），
     再与预设基线、"当前纪录 + ε"比较；证书与已有 shot 本质相同时判为重复

退出码：0 有效突破；1 合规但不是有效突破；2 不合规或无效。
本地结论是估算：先 git pull 同步 main；最终以 PR 上机器人的评论为准。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fslib as F  # noqa: E402


def check(shot_dir: Path, root: Path = ROOT) -> tuple[dict, F.Problem | None]:
    res: dict = {"status": "error", "messages": [], "problem": None, "shot": None}
    try:
        pdir, _login, _sid = F.locate_shot_dir(shot_dir, root)
        problem = F.load_problem_dir(root, pdir)
    except F.ShotError as e:
        res.update(status="rejected", messages=e.messages)
        return res, None
    except (F.ConfigError, OSError, ValueError) as e:
        res.update(status="rejected", messages=[f"题目目录无法读取：{e}"])
        return res, None
    res["problem"] = pdir
    try:
        login, shot_id, _names = F.check_local_shot_dir(shot_dir, problem)
    except F.ShotError as e:
        res.update(status="rejected", messages=e.messages)
        return res, problem
    res["shot"] = f"{login}/{shot_id}"
    merged, source = F.list_merged_shots(root, pdir, exclude={res["shot"]})
    res["order_source"] = source
    verify_py = F.problem_path(root, pdir) / "verify" / "verify.py"

    def verifier(d: Path) -> dict:
        return F.run_verifier_local(d, problem.verifier_timeout_sec, verify_py)

    res.update(F.evaluate_shot(problem, Path(shot_dir), login, verifier, merged))
    res["baseline"] = F.fmt(problem.baseline)
    res["epsilon"] = f"{F.fmt(problem.epsilon)}（{problem.epsilon_mode}）"
    return res, problem


def print_human(res: dict, problem: F.Problem | None) -> None:
    title = {
        "rejected": "不合规", "error": "流程出错", "invalid": "验证器判定无效",
        "claim_mismatch": "claimed_score 与验证结果不一致",
        "duplicate": "证书与已有 shot 本质相同",
    }.get(res["status"]) or F.VERDICT_TEXT.get(res["status"], res["status"])
    if problem:
        print(f"题目：{problem.id} {problem.title_zh}（{problem.metric_zh}，{problem.direction}：{problem.direction_zh}）")
    if res.get("shot"):
        print(f"shot：{res['shot']}")
    for label, key in (("验证器得分", "score"), ("claimed_score", "claimed_score"),
                       ("预设基线", "baseline"), ("当前纪录", "record"),
                       ("有效突破需要", "required"), ("ε", "epsilon")):
        if res.get(key) is not None:
            extra = ""
            if key == "record":
                extra = f"（{res['record_ref']}）" if res.get("record_ref") else "（即预设基线）"
            if key == "required" and problem:
                extra = "（≥）" if problem.direction == "max" else "（≤）"
            print(f"{label}：{res[key]}{extra}")
    if res.get("order_source") == "filesystem":
        print("提示：不是 git 仓库或无法读取历史，按目录名顺序估算纪录。")
    print(f"结论：{title}")
    for m in res.get("messages", []):
        if m != title:
            print(f"  - {m}")
    for w in res.get("chain_warnings", []):
        print(f"  ! {w}")
    if res["status"] == "breakthrough":
        print("可以提交 PR 了。本地结论是估算，以 PR 上机器人的评论为准。")


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="提交前的本地自检")
    ap.add_argument("shot_dir", help="problems/<题目目录>/shots/<login>/<shot-id>")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    res, problem = check(Path(args.shot_dir))
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(res, problem)
    if res["status"] == "breakthrough":
        return 0
    if res["status"] in ("below_baseline", "not_record", "below_epsilon", "duplicate"):
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
