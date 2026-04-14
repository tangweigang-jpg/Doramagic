"""蓝图提取管线——主编排。

流程（SOP v3.2）：
  step0: 指纹探针
  step1: Clone
  step2a: 架构提取
  step2b_2d: 声明验证（与用例扫描并行）
  step2c: 业务决策标注（依赖 2a+2b）
  step3: 自动验证
  step4: 组装蓝图（requires_human=True）
  step5: 一致性检查
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from doramagic_shared_utils.llm_adapter import LLMAdapter

from .extract.extractor import BlueprintExtractor
from .repo_manager import clone_repo, get_commit_hash
from .state import PipelineState

logger = logging.getLogger(__name__)

# 步骤 0 指纹探针的关键词表
SUBDOMAIN_KEYWORDS: dict[str, list[str]] = {
    "TRD": ["backtest", "strategy", "order", "signal", "position", "broker", "exchange", "trader"],
    "A_STOCK": ["a.stock", "a.share", "cn_a", "涨跌停", "t\\+1", "印花税", "turnover_rate", "zvt", "tushare", "akshare", "baostock"],
    "PRC": ["pricing", "option", "derivative", "yield", "volatility", "greeks", "black.scholes"],
    "RSK": ["portfolio", "optimization", "risk", "var", "cvar", "allocation", "factor", "attribution"],
    "CRD": ["credit", "scoring", "pd", "lgd", "loan", "npl", "basel", "default"],
    "CMP": ["tax", "compliance", "esg", "emission", "regulatory", "disclosure"],
    "DAT": ["data", "time.series", "feature", "database", "provider", "api", "recorder"],
    "AIL": ["reinforcement", "fine.tune", "llm", "agent", "forecast", "neural", "rl"],
    "INS":     ["actuarial", "reserving", "mortality", "solvency", "claim", "premium", "cat_risk", "annuity"],
    "LND":     ["loan", "origination", "underwriting", "collection", "payment", "ledger", "bnpl", "amortization"],
    "TRS":     ["treasury", "alm", "liquidity", "irrbb", "cash_pool", "funding", "lcr", "nsfr"],
    "AML":     [r"\baml\b", "kyc", "sanction", "transaction_monitoring", "suspicious", r"\bpep\b(?![\d])", "money.laundering", "anti.money", "typolog"],
}

# 指纹探针最小关键词命中数
_FINGERPRINT_MIN_HITS = 2


@dataclass
class BlueprintPipelineResult:
    blueprint_id: str
    subdomain_labels: list[str] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_human: bool = False
    human_step: str = ""


def fingerprint_repo(repo_path: Path) -> list[str]:
    """步骤 0：快速判断项目子领域。

    搜索 README + Python 文件名 + 目录名，对每个子领域统计关键词命中数，
    命中数 >= _FINGERPRINT_MIN_HITS 则标记该子领域。
    若无匹配则默认返回 ["TRD"]。
    """
    text_sources: list[str] = []

    # v6.4 fix: include repo root directory name itself — project names
    # like "AMLSim" contain domain keywords that should count as a hit
    text_sources.append(repo_path.name.lower())

    readme = repo_path / "README.md"
    if readme.exists():
        text_sources.append(readme.read_text(errors="ignore").lower())

    # 搜索 Python 文件名 + module docstring (v6.4 fix)
    # README + filenames alone miss domain keywords in Java/multi-lang
    # projects (e.g., AMLSim has "aml"/"suspicious" only in .py content).
    # Read the first 5 lines of each .py (module docstring/comments) —
    # high signal, low false-positive risk vs reading 30+ lines.
    for py_file in repo_path.rglob("*.py"):
        rel = str(py_file.relative_to(repo_path))
        if "__pycache__" in rel or ".venv" in rel or "node_modules" in rel:
            continue
        text_sources.append(py_file.name.lower())
        try:
            head = py_file.read_text(errors="ignore").split("\n")[:5]
            text_sources.append(" ".join(head).lower())
        except OSError:
            pass

    # Project metadata files (setup.py, pyproject.toml have descriptions)
    for meta_file in ["setup.py", "pyproject.toml", "setup.cfg"]:
        p = repo_path / meta_file
        if p.exists():
            try:
                text_sources.append(p.read_text(errors="ignore").lower())
            except OSError:
                pass

    # 目录名
    for item in repo_path.rglob("*"):
        if item.is_dir() and "__pycache__" not in str(item) and ".venv" not in str(item):
            text_sources.append(item.name.lower())

    combined = " ".join(text_sources)
    labels: list[str] = []
    for label, keywords in SUBDOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if re.search(kw, combined))
        if hits >= _FINGERPRINT_MIN_HITS:
            labels.append(label)

    return labels if labels else ["TRD"]


def _extract_claims(round1_content: str) -> list[str]:
    """从步骤 2a 的架构提取报告中提取事实性声明。

    优先抓带标记符的行，其次带编号的行，最后退化为章节标题。
    最多返回 15 条。
    """
    claims: list[str] = []
    for line in round1_content.split("\n"):
        line = line.strip()
        if any(marker in line for marker in ["✅", "❌", "⚠️", "声明:", "claim:"]):
            claims.append(line)
        elif re.match(r"^\d+\.", line) and len(line) > 20:
            claims.append(line)

    # 退化：取章节标题作为声明
    if not claims:
        for line in round1_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("###") or stripped.startswith("##"):
                claims.append(stripped.lstrip("#").strip())

    return claims[:15]


async def run_blueprint_pipeline(
    repo_url: str | None,
    repo_path: Path | None,
    domain: str,
    blueprint_id: str,
    output_dir: Path,
    adapter: LLMAdapter,
    *,
    resume: bool = False,
    single_step: str | None = None,
) -> BlueprintPipelineResult:
    """执行完整蓝图提取管线。

    Args:
        repo_url: 远程仓库 URL（repo_url 与 repo_path 二选一）
        repo_path: 本地仓库路径（已 clone）
        domain: 领域名，如 "finance"
        blueprint_id: 蓝图 ID，如 "finance-bp-060"
        output_dir: 管线输出根目录
        adapter: LLM 适配器
        resume: 是否从上次断点续跑
        single_step: 若指定，只执行该步骤

    Returns:
        BlueprintPipelineResult 运行结果
    """
    result = BlueprintPipelineResult(blueprint_id=blueprint_id)

    # 初始化状态
    state_path = output_dir / blueprint_id / "_state.json"
    state: PipelineState
    if resume:
        loaded = PipelineState.load(state_path)
        state = loaded if loaded is not None else PipelineState(pipeline="blueprint", blueprint_id=blueprint_id)
    else:
        state = PipelineState(pipeline="blueprint", blueprint_id=blueprint_id)

    extractor = BlueprintExtractor(adapter)
    run_dir = output_dir / blueprint_id
    run_dir.mkdir(parents=True, exist_ok=True)

    steps = ["step0", "step1", "step2a", "step2b_2d", "step2c", "step3", "step4", "step5"]

    for step in steps:
        if single_step and step != single_step:
            continue
        if state.should_skip(step):
            logger.info("Skipping completed step: %s", step)
            continue

        state.start_step(step)
        state.save(state_path)
        logger.info("Starting step: %s", step)

        try:
            if step == "step0":
                # 指纹探针
                rp = repo_path or Path(f"repos/{blueprint_id.split('-')[-1]}")
                labels = fingerprint_repo(rp)
                result.subdomain_labels = labels
                state.mark_complete(step, {"subdomain_labels": labels})
                logger.info("Subdomain labels: %s", labels)

            elif step == "step1":
                # Clone
                if repo_url and not repo_path:
                    rp = clone_repo(repo_url, Path("repos"))
                else:
                    rp = repo_path or Path(f"repos/{blueprint_id.split('-')[-1]}")
                commit = get_commit_hash(rp)
                state.mark_complete(step, {"repo_path": str(rp), "commit_hash": commit})
                logger.info("Repo ready: %s @ %s", rp, commit)

            elif step == "step2a":
                # 架构提取
                rp = Path(state.step_outputs.get("step1", {}).get("repo_path", ""))
                content = await extractor.extract_architecture(rp)
                output_file = run_dir / "step2a_round1.md"
                output_file.write_text(content)
                state.mark_complete(step, {"report_path": str(output_file)})
                logger.info("Architecture report written: %s", output_file)

            elif step == "step2b_2d":
                # 声明验证 + 用例扫描（并行）
                rp = Path(state.step_outputs["step1"]["repo_path"])
                round1_path = Path(state.step_outputs["step2a"]["report_path"])
                round1_content = round1_path.read_text()
                claims = _extract_claims(round1_content)
                logger.info("Extracted %d claims for verification", len(claims))

                round2_task = extractor.verify_claims(rp, claims)
                usecase_task = extractor.scan_use_cases(rp)
                round2_content, usecase_content = await asyncio.gather(round2_task, usecase_task)

                round2_file = run_dir / "step2b_round2.md"
                round2_file.write_text(round2_content)
                usecase_file = run_dir / "step2d_usecases.md"
                usecase_file.write_text(usecase_content)
                state.mark_complete(step, {
                    "round2_path": str(round2_file),
                    "usecase_path": str(usecase_file),
                })
                logger.info("Claim verification + use case scan complete")

            elif step == "step2c":
                # 业务决策标注
                rp = Path(state.step_outputs["step1"]["repo_path"])
                round1 = Path(state.step_outputs["step2a"]["report_path"]).read_text()
                round2 = Path(state.step_outputs["step2b_2d"]["round2_path"]).read_text()
                labels = state.step_outputs.get("step0", {}).get("subdomain_labels", ["TRD"])
                content = await extractor.annotate_business_decisions(rp, round1, round2, labels)
                bd_file = run_dir / "step2c_business.md"
                bd_file.write_text(content)
                state.mark_complete(step, {"business_path": str(bd_file)})
                logger.info("Business decision annotation written: %s", bd_file)

            elif step == "step3":
                # 自动验证：检查 LLM 报告中引用的源码路径是否存在
                rp = Path(state.step_outputs["step1"]["repo_path"])
                reports = []
                for key in ("step2a", "step2b_2d", "step2c"):
                    for path_key in ("report_path", "round2_path", "business_path"):
                        p = state.step_outputs.get(key, {}).get(path_key)
                        if p and Path(p).exists():
                            reports.append(Path(p).read_text())
                combined = "\n".join(reports)
                # 提取 file:line 引用并验证文件存在性
                file_refs = re.findall(r'(\S+\.py)(?::(\d+))?', combined)
                missing_files: list[str] = []
                checked = set()
                for fpath, _ in file_refs:
                    if fpath in checked:
                        continue
                    checked.add(fpath)
                    candidate = rp / fpath
                    if not candidate.exists():
                        # 尝试去掉前缀匹配
                        found = list(rp.rglob(Path(fpath).name))
                        if not found:
                            missing_files.append(fpath)
                verified = len(missing_files) == 0
                if missing_files:
                    logger.warning(
                        "Step 3: %d/%d file references not found: %s",
                        len(missing_files), len(checked), missing_files[:10],
                    )
                else:
                    logger.info("Step 3: All %d file references verified", len(checked))
                state.mark_complete(step, {
                    "verified": verified,
                    "checked_count": len(checked),
                    "missing_files": missing_files[:20],
                })

            elif step == "step4":
                # 组装蓝图（需要人工参与）
                result.requires_human = True
                result.human_step = "step4"
                logger.info("Step 4: Assembly requires human review. Pipeline paused.")
                logger.info("Intermediate outputs in: %s", run_dir)
                state.mark_complete(step, {"requires_human": True})
                break  # 暂停管线

            elif step == "step5":
                # 一致性检查：BD 分类合法性 + UC 必要字段 + 跨报告阶段一致性
                issues: list[str] = []
                bd_path = state.step_outputs.get("step2c", {}).get("business_path")
                uc_path = state.step_outputs.get("step2b_2d", {}).get("usecase_path")
                valid_types = {"T", "B", "BA", "DK", "RC", "M", "B/BA", "M/B", "M/BA"}
                if bd_path and Path(bd_path).exists():
                    bd_text = Path(bd_path).read_text()
                    # 检查 BD 分类是否在合法集合内
                    bd_types = re.findall(r'\|\s*\d+\s*\|[^|]+\|\s*([A-Z/]+)\s*\|', bd_text)
                    for t in bd_types:
                        if t.strip() not in valid_types:
                            issues.append(f"Invalid BD type: '{t.strip()}'")
                    if len(bd_types) < 5:
                        issues.append(f"BD count {len(bd_types)} < minimum 5")
                if uc_path and Path(uc_path).exists():
                    uc_text = Path(uc_path).read_text()
                    # 检查 UC 必要字段
                    for field in ("negative_keywords", "disambiguation", "data_domain"):
                        if field not in uc_text:
                            issues.append(f"UC missing required field: {field}")
                consistent = len(issues) == 0
                if issues:
                    logger.warning("Step 5: %d consistency issues: %s", len(issues), issues)
                else:
                    logger.info("Step 5: All consistency checks passed")
                state.mark_complete(step, {"consistent": consistent, "issues": issues})

        except Exception as e:
            error_msg = f"Step {step} failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            state.errors.append(error_msg)
            state.save(state_path)
            break

        state.save(state_path)
        result.steps_completed.append(step)

    logger.info(
        "=== 管线结束: %s — 完成步骤 %s，错误 %d ===",
        blueprint_id, result.steps_completed, len(result.errors),
    )
    return result
