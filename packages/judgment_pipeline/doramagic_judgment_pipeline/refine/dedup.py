"""去重流水线。规范化 + 分桶 + 强重复匹配。"""

from __future__ import annotations

from dataclasses import dataclass

from doramagic_judgment_schema.normalizer import CanonicalSignature, compute_signature
from doramagic_judgment_schema.types import Judgment


@dataclass
class DedupResult:
    unique: list[Judgment]  # 去重后的判断
    duplicates: list[tuple[str, str, str]]  # (保留id, 重复id, 原因)


def dedup_judgments(judgments: list[Judgment]) -> DedupResult:
    """
    对判断列表执行去重。
    Step 1: 计算 canonical signature
    Step 2: 按 scope_sig 分桶
    Step 3: 桶内强重复匹配
    """
    # Step 1: 计算签名
    sigs: dict[str, CanonicalSignature] = {}
    for j in judgments:
        sigs[j.id] = compute_signature(j)

    # Step 2: 分桶
    buckets: dict[str, list[Judgment]] = {}
    for j in judgments:
        bucket_key = sigs[j.id].scope_sig
        buckets.setdefault(bucket_key, []).append(j)

    # Step 3: 桶内强重复匹配
    unique: list[Judgment] = []
    duplicates: list[tuple[str, str, str]] = []
    seen_rule_sigs: dict[str, str] = {}  # bucket+rule_sig -> first judgment id

    for bucket_key, bucket_judgments in buckets.items():
        for j in bucket_judgments:
            sig = sigs[j.id]
            composite_key = f"{bucket_key}||{sig.rule_sig}"

            if composite_key in seen_rule_sigs:
                duplicates.append(
                    (
                        seen_rule_sigs[composite_key],
                        j.id,
                        f"强重复：rule_sig 一致（桶 {bucket_key}）",
                    )
                )
            else:
                cause_key = f"{bucket_key}||{sig.cause_sig}"
                if cause_key in seen_rule_sigs:
                    duplicates.append(
                        (
                            seen_rule_sigs[cause_key],
                            j.id,
                            f"根因重复：cause_sig 一致（桶 {bucket_key}）",
                        )
                    )
                else:
                    seen_rule_sigs[composite_key] = j.id
                    seen_rule_sigs[f"{bucket_key}||{sig.cause_sig}"] = j.id
                    unique.append(j)

    return DedupResult(unique=unique, duplicates=duplicates)
