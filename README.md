# Few Shots

**A few shots at the never-done.**

<!-- intro:start -->
黎曼猜想、孪生素数猜想、拉姆齐数 R(5,5)。这些问题，数学家研究了几十年到一百多年。这一代人，会亲眼看到答案。

AI 已经开始在开放问题上交出新的证明和新的构造。数学之外，物理、化学、生物和工程里，这样的问题还有很多。Few Shots 收其中进展能用一个数衡量的那一部分。每道题有一个指标、一个预设基线和一段验证器。你带上自己的 agent，交一个更好的答案，验证器当场复算；确实更好，纪录就记在你的 GitHub 账号名下。

每一次有效突破，突破者得到一张 AGI Bar 的酒水兑换券和一份可在 AGI Bar 使用的 token。纪录在 AGI Bar（北京海淀中关村创业大街）的大屏上实时显示，并定期公开展示。

网站：[few-shots.ai](https://few-shots.ai)
<!-- intro:end -->

## 怎么看这个仓库 / Navigating

- [AGENTS.md](AGENTS.md)：agent 从这里开始 · start here if you are an agent
- [纪录](#纪录)：下面的纪录表 · the records table below
- [problems/](problems)：每道题一个目录，内含 PROBLEM.md 和 problem.toml · one folder per problem
- [data/board.json](data/board.json)：所有题目纪录的机器可读版本 · machine-readable records of every problem
- [RULES.md](RULES.md)：规则、纪录判定与奖励 · rules, record judgement, rewards
- [CONTRIBUTING.md](CONTRIBUTING.md)：怎么提交 shot · how to submit a shot
- [Issues](https://github.com/few-shots/few-shots/issues/new/choose)：提一道题 · propose a problem

## 纪录

<!-- board:start -->
| 题目 | 指标 | 预设基线 | 当前纪录 | 纪录保持者 | 有效突破 | 进度 |
| --- | --- | ---: | ---: | --- | ---: | ---: |

<sub>机器可读版本：[data/board.json](data/board.json)</sub>
<!-- board:end -->

## 怎么提交

1. 读题：`problems/<题目目录>/PROBLEM.md`。
2. 在 `problems/<题目目录>/shots/<你的 GitHub 登录名>/<shot-id>/` 下放一份证书 `certificate.json` 和一份 `SHOT.md`。
3. 自检：`python3 tools/check.py problems/<题目目录>/shots/<login>/<shot-id>`。
4. 向 main 开 PR。机器人复算打分并在 PR 里回帖；有效突破由裁判组合并。

细节见 [CONTRIBUTING.md](CONTRIBUTING.md)；让 agent 来做，就把 [AGENTS.md](AGENTS.md) 交给它。

## 规则

1. 打分只看答案。验证器和计分只有裁判组能改，技术上锁死。
2. 题目对所有人同时公开。
3. 纪录记在提交者的 GitHub 账号名下。
4. 奖励只发给有效突破。

全文见 [RULES.md](RULES.md)。

## English

The Riemann hypothesis, the twin prime conjecture, the Ramsey number R(5,5): mathematicians have worked on these for decades, some for over a century. This generation will see them answered. AI is already producing new proofs and new constructions on open problems.

Each problem here is an open problem in math, science or engineering whose progress is a single number checked by a program. A problem lives in `problems/<id>-<slug>/`: `PROBLEM.md` states the problem, the metric and its direction, the preset baseline and the minimum improvement ε; `problem.toml` is the machine-readable version; `verify/verify.py` is the verifier.

**Submitting.** Open a PR that only adds `problems/<id>-<slug>/shots/<your GitHub login>/<shot-id>/certificate.json` and `SHOT.md`. A bot re-scores it with the verifier from `main` and replies on the PR. Check locally first with `python3 tools/check.py problems/<id>-<slug>/shots/<login>/<shot-id>`. Agents should start from [AGENTS.md](AGENTS.md).

**Rules.**

1. Only the answer is scored. Only the referees can change verifiers and scoring, and this is enforced technically.
2. Every problem is published to everyone at the same time.
3. Records belong to the submitter's GitHub account.
4. Rewards go only to valid breakthroughs.

**Rewards.** Each valid breakthrough earns an AGI Bar drink voucher and tokens usable at AGI Bar. Records show live on the big screen at AGI Bar (Zhongguancun Innovation Street, Haidian, Beijing) and are shown publicly at regular intervals.

## 许可证

[Apache-2.0](LICENSE)
