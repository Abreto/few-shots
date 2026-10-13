# p000 · Golomb 尺（沙盒）

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p000` |
| metric | 长度 / length |
| direction | `min`（越小越好） |
| baseline | `2047` |
| epsilon | `1`（`absolute`） |
| verifier | `python3 problems/p000-sandbox/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

p000 是沙盒题，用来走通提交流程：成绩不进记分牌，不发奖励。

## 问题

一把 Golomb 尺是一组互不相同的整数刻度，其中任意两个刻度之差都互不相同。尺子的长度是最大刻度减最小刻度。

给定刻度个数 n = 12（`problem.toml` 的 `[params] n`），找一把尽量短的 Golomb 尺。

## 为什么重要

Golomb 尺用于射电望远镜阵列的天线布置和纠错码的设计。n = 12 时的最短长度 85 已经被证明是最优的，所以这道题的答案可以核对，适合用来练习提交。

## 证书

- 文件名 `certificate.json`，内容形如 `{"marks": [0, 1, 3, …]}`；可以带 `"n": 12`，不允许其他键。
- `marks` 恰好有 12 个刻度。每个刻度都是 JSON 整数（不能是小数、字符串或布尔值），绝对值不超过 10^15，互不相同，顺序不限。
- 任意两个刻度之差互不相同。
- 文件为 UTF-8 编码的 JSON，不超过 64 KiB，嵌套不超过 8 层，不允许重复的键。
- 成绩是长度，总是整数，例如 `"85"`。
- 规范化：刻度平移到从 0 开始，取自身与镜像中字典序较小的一个；`canonical_hash` 是规范化 JSON 的 sha256。同一把尺子平移或镜像后得到同一个哈希。

## 预设基线

刻度取 2^k − 1（k = 0, 1, …, 11）：0, 1, 3, 7, 15, …, 2047。任意两个刻度之差都形如 2^j − 2^i，二进制表示互不相同，所以这是一把合法的 Golomb 尺，长度 2047。

证书在 `baseline/certificate.json`，复现：

```bash
python3 problems/p000-sandbox/verify/verify.py problems/p000-sandbox/baseline
```
