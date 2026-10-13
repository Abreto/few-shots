# 验证器镜像。构建上下文是题目目录（只放入 problem.toml 与 verify/verify.py，见题目目录里的 .dockerignore）：
#   docker build -t fewshots-verifier:main -f problems/<题目目录>/verify/Dockerfile problems/<题目目录>
# 打分流水线由 scripts/score.py 构建它。基础镜像固定到版本标签 + 摘要；升级时由裁判组审核新摘要。
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    LANG=C.UTF-8

WORKDIR /verifier
COPY problem.toml /verifier/problem.toml
COPY verify/verify.py /verifier/verify.py

# 运行时还会再加 --user 65534 --read-only --network=none 等限制（见 scripts/score.py）
USER 65534:65534
ENTRYPOINT ["python", "-I", "/verifier/verify.py"]
