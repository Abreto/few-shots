# 安全与漏洞报告 · Security

[English below](#english)

本仓库启用了 GitHub 的私密漏洞报告（private vulnerability reporting）。

## 怎么报告

1. 打开本仓库的 **Security** 标签页，点 **Report a vulnerability**（[直接打开](https://github.com/few-shots/few-shots/security/advisories/new)）。
2. 写清楚：影响哪道题或哪个工作流、复现步骤、你认为的影响。
3. 报告只有你和裁判组看得到。不要开公开的 Issue、PR 或讨论，也不要在别处公开。

## 什么算漏洞

- 不合格的证书能通过验证器，或者成绩被算错；
- 打分工作流可以被注入命令、拿到不该有的权限，或者被 PR 改变自己的打分方式；
- 记分牌或大屏数据可以被参与者操纵；
- 任何令牌、密钥的泄露。

## 之后会发生什么

1. 裁判组 24 小时内确认收到，并判断是否成立。
2. 成立的，裁判组把本仓库 `control.toml` 的 `paused` 设为 `true`。开关合并后，新启动的打分运行和每次回帖前都会读到它：机器人回帖说明已暂停，所有 PR 的 `few-shots/verdict` 为 pending，无法合并；记分牌停止更新。
3. 修复后，用修好的验证器把受影响题目的纪录链逐条复算，修正记分牌，再恢复开关。
4. 公开致谢报告人（报告人不愿具名的除外）。

修复之前利用漏洞、且没有报告的纪录作废，相应奖励收回。

## 善意研究

只在自己的 fork 或本地环境里验证问题；不要攻击他人的 PR、账号或任何基础设施，不要用漏洞去拿纪录。

---

## English

This repository has GitHub private vulnerability reporting enabled.

### How to report

1. Open the **Security** tab of this repository and click **Report a vulnerability** ([direct link](https://github.com/few-shots/few-shots/security/advisories/new)).
2. Say which problem or workflow is affected, how to reproduce it, and what you think the impact is.
3. Only you and the referees can see the report. Do not open a public issue, PR or discussion, and do not disclose it elsewhere.

### What counts

- an invalid certificate passes a verifier, or a score is computed wrongly;
- the scoring workflow can be injected with commands, gains permissions it should not have, or can be changed by a PR to alter its own scoring;
- participants can manipulate the board or the big-screen data;
- any token or key leaks.

### What happens next

1. The referees acknowledge within 24 hours and assess the report.
2. If it holds, they set `paused = true` in `control.toml`. Once merged, new scoring runs and every bot reply read it: the bot says scoring is paused, every PR's `few-shots/verdict` stays pending so nothing can be merged, and the board stops updating.
3. After the fix, the affected problems' record chains are recomputed one by one with the fixed verifier, the board is corrected, and the switch is turned back.
4. The reporter is credited publicly, unless they prefer not to be named.

Records that exploit an unreported vulnerability before it is fixed are void, and their rewards are withdrawn.

### Good-faith research

Verify problems only in your own fork or local environment. Do not attack other people's PRs, accounts or any infrastructure, and do not use a vulnerability to set records.
