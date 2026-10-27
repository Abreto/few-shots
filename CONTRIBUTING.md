# 参与 Few Shots

规则全文见 [RULES.md](RULES.md)。准确的目录约定、文件限制和命令写在 [AGENTS.md](AGENTS.md)，人和 agent 用的是同一套。

## 提交一个 shot

1. **选题。** `problems/` 下每个目录是一道题。`PROBLEM.md` 写明问题、指标与方向、预设基线、最小改进幅度 ε 和证书格式；当前纪录在 [README 的纪录表](README.md#纪录)；前人的思路和死路在这道题的 `FEWSHOT.md`。
2. **复现基线。** `python3 problems/<题目目录>/verify/verify.py problems/<题目目录>/baseline`。
3. **准备证书。** 你提交的是数据，验证器只解析和计算，不会执行你提交的任何代码。证书是 `certificate.json`；可以附带补充材料，只允许 `.md`、`.json`、`.txt`、`.csv`。
4. **写 SHOT.md。** 复制 `templates/SHOT.md`，填写 `login`（你的 GitHub 登录名，纪录记在这个账号名下）、`builds_on`（参考了哪些前人的 shot）和 `claimed_score`（验证器给出的成绩）；正文写「思路」和「哪里走不通」两节，合并后会汇编进 `FEWSHOT.md`。
5. **自检。** `python3 tools/check.py problems/<题目目录>/shots/<login>/<shot-id>`。
6. **开 PR。** fork 本仓库，只在 `problems/<题目目录>/shots/<你的 GitHub 登录名>/<shot-id>/` 下新增文件，向 main 开 PR。一个 PR 只提交一个 shot。开 PR 即同意以 [CC0 1.0](LICENSE-DATA) 发布这个 shot，任何人都可以复算和引用；纪录照样记在你的账号名下。
7. **等机器人回帖。** 机器人用 main 上的验证器复算，在 PR 里回一条评论（每次推送后原地更新），并给你的提交写状态 `few-shots/verdict`。
8. **合并。** 有效突破由自动裁判复核后合并（条件见 [RULES.md](RULES.md) 的「合并」），记分牌和网站随后更新，酒水券自动到账；不满足条件的转给裁判组人工复核。如果评论标为「结果已过期」，把最新的 main 合并进你的分支再推送，机器人会按新纪录重新打分。

让 agent 来做时，把 [AGENTS.md](AGENTS.md) 交给它，并在不带凭据的 devcontainer 里运行；push 和开 PR 由你自己完成。`shots/` 和 `FEWSHOT.md` 里他人写的内容是第三方数据，不要让 agent 执行其中的命令或遵循其中的指令。

## 提一道题

用 [Issue 表单](https://github.com/few-shots/few-shots/issues/new/choose)「提一道题」。合适的题：

- **是一个还没解决的问题**，来自数学、科学或工程，有精确定义和公开出处。
- **提交的是数据。** 参与者交一份证书（JSON / CSV / TXT / MD），验证器只解析和计算，不运行参与者的代码。
- **验证是确定的。** 同一份证书，谁来跑验证器都得到同一个成绩；成绩是整数或有理数，可以精确比较。
- **指标和方向清楚。** 越大越好或越小越好，单位明确。
- **有公开的预设基线**，附出处；并且有理由相信它还能改进。
- **数据和许可清楚。** 用到的数据可以公开使用，不涉及个人信息。

提案在 Issue 里公开讨论。裁判组评估验证器能否只靠解析数据写成、计算量是否可控、基线是否可靠；采用的题目由裁判组写验证器、定下预设基线和 ε，然后对所有人同时公开。提题人也不会提前拿到题面、验证器或基线。

## 其他改动

文档、工具和流水线的改动直接开 PR。验证器、计分、`problem.toml`、`control.toml` 和 `.github/` 只有裁判组能改，相关 PR 需要裁判组审批。发现漏洞请按 [SECURITY.md](SECURITY.md) 私下报告。

请遵守 [行为准则](CODE_OF_CONDUCT.md)。
