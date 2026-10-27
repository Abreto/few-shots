# Verifier image. The build context is the problem directory (only problem.toml and verify/verify.py, see .dockerignore):
#   docker build -t fewshots-verifier:main -f problems/<problem dir>/verify/Dockerfile problems/<problem dir>
# scripts/score.py builds it for scoring. The base image is pinned to a tag and digest; the referees review digest upgrades.
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    LANG=C.UTF-8

WORKDIR /verifier
COPY problem.toml /verifier/problem.toml
COPY verify/verify.py /verifier/verify.py

# At run time scripts/score.py adds --user 65534 --read-only --network=none and resource limits
USER 65534:65534
ENTRYPOINT ["python", "-I", "/verifier/verify.py"]
