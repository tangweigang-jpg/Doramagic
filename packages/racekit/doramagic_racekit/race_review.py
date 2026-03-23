"""Review template and score helpers for Doramagic race rounds."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

from .race_config import canonical_module_name, module_branch_slug
from .race_workspace import _resolve_output_root, _resolve_repo_root

REVIEW_DIMENSIONS = {
    "Contract 正确性": 25.0,
    "可验证性": 20.0,
    "集成适配度": 20.0,
    "代码清晰度": 15.0,
    "性能成本": 10.0,
    "运维稳定性": 10.0,
}

SCORE_LINE_PATTERN = re.compile(
    r"^- (?P<dimension>.+?) \| weight=(?P<weight>\d+(?:\.\d+)?) \| score=(?P<score>\d+(?:\.\d+)?)\s*$"
)


def generate_review_template(round_num: int, module_name: str) -> Path:
    """Generate a markdown review template for one race module."""

    canonical_module = canonical_module_name(module_name)
    repo_root = _resolve_repo_root()
    output_root = _resolve_output_root(repo_root)
    output_path = output_root / "r{0:02d}".format(round_num) / module_branch_slug(canonical_module) / "REVIEW.md"
    score_lines = "\n".join(
        "- {0} | weight={1:g} | score=".format(name, weight)
        for name, weight in REVIEW_DIMENSIONS.items()
    )

    content = """# Doramagic Race Review

- Round: {round_num}
- Module: `{module_name}`
- Review Result: TBD

## Submission Checklist

- [ ] 模块代码
- [ ] 单元测试
- [ ] 至少 1 条基于 Sim2 或等价 fixture 的集成测试
- [ ] `README.md`
- [ ] `DECISIONS.md`

## Review Checks

- [ ] schema 是否完全一致
- [ ] error path 是否按定义返回
- [ ] 性能是否在预算内
- [ ] 有没有偷改上游 / 下游 contract
- [ ] fixture 是否能复现

## Weighted Scores

说明：`score` 使用 0-10 分，最终总分按权重折算成 100 分。

{score_lines}

## Notes

### Candidate A

- Strengths:
- Risks:

### Candidate B

- Strengths:
- Risks:
""".format(
        round_num=round_num,
        module_name=canonical_module,
        score_lines=score_lines,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def score_submission(review_path: str) -> float:
    """Calculate the weighted total score from a completed review report."""

    review_file = Path(review_path).expanduser().resolve()
    scores: Dict[str, float] = {}

    for line in review_file.read_text(encoding="utf-8").splitlines():
        match = SCORE_LINE_PATTERN.match(line.strip())
        if not match:
            continue

        dimension = match.group("dimension")
        weight = float(match.group("weight"))
        score = float(match.group("score"))

        expected_weight = REVIEW_DIMENSIONS.get(dimension)
        if expected_weight is None:
            raise ValueError("Unexpected review dimension: {0}".format(dimension))
        if abs(expected_weight - weight) > 1e-6:
            raise ValueError("Weight mismatch for {0}: {1}".format(dimension, weight))
        if score < 0 or score > 10:
            raise ValueError("Score must be between 0 and 10: {0}={1}".format(dimension, score))

        scores[dimension] = score

    missing = [name for name in REVIEW_DIMENSIONS if name not in scores]
    if missing:
        raise ValueError("Missing scores for review dimensions: {0}".format(", ".join(missing)))

    total = 0.0
    for name, weight in REVIEW_DIMENSIONS.items():
        total += (scores[name] / 10.0) * weight
    return round(total, 2)
