"""蓝图 YAML 解析器。

将 YAML 文件解析为结构化的 ParsedBlueprint，供约束采集管线使用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ParsedStage:
    """蓝图中的一个阶段。"""

    id: str
    name: str
    order: int
    responsibility: str
    interface: dict = field(default_factory=dict)
    replaceable_points: list[dict] = field(default_factory=list)
    pseudocode_example: str = ""
    design_decisions: list[str] = field(default_factory=list)
    acceptance_hints: list[str] = field(default_factory=list)
    # v1.1: non-code blueprint resource references (stage-level hint only)
    resource_refs: list[str] = field(default_factory=list)  # resource IDs used in this stage


@dataclass
class ParsedEdge:
    """蓝图中的一条数据流边。"""

    id: str
    from_stage: str
    to_stage: str
    data: str
    edge_type: str = "data_flow"
    required: bool = True
    condition: str | None = None


@dataclass
class GlobalContract:
    """蓝图中的一条全局契约。"""

    contract: str
    evidence: str = ""
    note: str = ""


@dataclass
class ParsedResource:
    """蓝图关联资源（v1.1）。"""

    id: str
    type: str
    name: str
    path: str | None = None
    description: str = ""
    used_in_stages: list[str] = field(default_factory=list)


@dataclass
class ParsedRelation:
    """蓝图间关系（v1.1 扩展）。"""

    type: str  # alternative_to/specializes/generalizes/depends_on/complementary/contains
    target: str
    description: str = ""
    evidence: str = ""


@dataclass
class ParsedBlueprint:
    """解析后的蓝图结构。"""

    id: str
    name: str
    domain: str
    version: str
    stages: list[ParsedStage]
    edges: list[ParsedEdge]
    global_contracts: list[GlobalContract]
    evidence: dict[str, str]  # key -> "filepath:line-range" or "file:§section"
    applicability: dict
    source: dict
    not_suitable_for: list[str]
    raw: dict  # 完整 YAML dict
    # v1.1: non-code blueprint support
    resources: list[ParsedResource] = field(default_factory=list)
    relations: list[ParsedRelation] = field(default_factory=list)
    activation: dict = field(default_factory=dict)  # applicability.activation

    @property
    def stage_ids(self) -> list[str]:
        return [s.id for s in self.stages]

    @property
    def edge_ids(self) -> list[str]:
        return [e.id for e in self.edges]

    def get_stage(self, stage_id: str) -> ParsedStage | None:
        for s in self.stages:
            if s.id == stage_id:
                return s
        return None

    def get_edge(self, edge_id: str) -> ParsedEdge | None:
        for e in self.edges:
            if e.id == edge_id:
                return e
        return None

    def get_edges_for_stage(self, stage_id: str) -> list[ParsedEdge]:
        """获取与某个 stage 相关的所有 edge（作为 from 或 to）。"""
        return [e for e in self.edges if e.from_stage == stage_id or e.to_stage == stage_id]


def load_blueprint(yaml_path: Path) -> ParsedBlueprint:
    """加载并解析一份蓝图 YAML 文件。

    Args:
        yaml_path: 蓝图 YAML 文件路径

    Returns:
        ParsedBlueprint 结构化对象

    Raises:
        FileNotFoundError: YAML 文件不存在
        ValueError: YAML 结构不符合蓝图格式
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"蓝图文件不存在: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"蓝图 YAML 格式无效: {yaml_path}")

    bp_id = raw.get("id", "")
    if not bp_id:
        raise ValueError(f"蓝图缺少 id 字段: {yaml_path}")

    # 解析 stages（P2-7: 将 KeyError 转为 ValueError）
    stages = []
    for i, s in enumerate(raw.get("stages", [])):
        if not isinstance(s, dict):
            raise ValueError(f"stages[{i}] 不是 dict: {type(s).__name__}")
        if "id" not in s:
            raise ValueError(f"stages[{i}] 缺少 id 字段")
        stages.append(
            ParsedStage(
                id=s["id"],
                name=s.get("name", ""),
                order=s.get("order", 0),
                responsibility=s.get("responsibility", ""),
                interface=s.get("interface", {}),
                replaceable_points=s.get("replaceable_points", []),
                pseudocode_example=s.get("pseudocode_example", ""),
                design_decisions=s.get("design_decisions", []),
                acceptance_hints=s.get("acceptance_hints", []),
            )
        )

    # 解析 data_flow edges（P2-7: 健壮性校验）
    edges = []
    for i, e in enumerate(raw.get("data_flow", [])):
        if not isinstance(e, dict) or "id" not in e:
            raise ValueError(f"data_flow[{i}] 格式无效或缺少 id")
        edges.append(
            ParsedEdge(
                id=e["id"],
                from_stage=e.get("from_stage", ""),
                to_stage=e.get("to_stage", ""),
                data=e.get("data", ""),
                edge_type=e.get("edge_type", "data_flow"),
                required=e.get("required", True),
                condition=e.get("condition"),
            )
        )

    # 解析 global_contracts
    global_contracts = []
    for gc in raw.get("global_contracts", []):
        if isinstance(gc, dict):
            global_contracts.append(
                GlobalContract(
                    contract=gc.get("contract", ""),
                    evidence=gc.get("evidence", ""),
                    note=gc.get("note", ""),
                )
            )
        elif isinstance(gc, str):
            global_contracts.append(GlobalContract(contract=gc))

    # 解析 applicability
    applicability = raw.get("applicability", {})
    not_suitable_for = applicability.get("not_suitable_for", [])

    # 解析 evidence
    evidence = raw.get("source", {}).get("evidence", {})

    # v1.1: 解析 resources
    resources = []
    for r in raw.get("resources", []):
        if isinstance(r, dict) and "id" in r:
            resources.append(
                ParsedResource(
                    id=r["id"],
                    type=r.get("type", ""),
                    name=r.get("name", ""),
                    path=r.get("path"),
                    description=r.get("description", ""),
                    used_in_stages=r.get("used_in_stages", []),
                )
            )

    # v1.1: 解析 relations
    relations = []
    for rel in raw.get("relations", []):
        if isinstance(rel, dict) and "type" in rel:
            relations.append(
                ParsedRelation(
                    type=rel["type"],
                    target=rel.get("target", ""),
                    description=rel.get("description", ""),
                    evidence=rel.get("evidence", ""),
                )
            )

    # v1.1: 解析 activation（applicability 子字段）
    activation = applicability.get("activation", {})

    logger.info(
        "蓝图加载完成: %s — %d stages, %d edges, %d global_contracts, %d resources, %d relations",
        bp_id,
        len(stages),
        len(edges),
        len(global_contracts),
        len(resources),
        len(relations),
    )

    return ParsedBlueprint(
        id=bp_id,
        name=raw.get("name", ""),
        domain=applicability.get("domain", ""),
        version=raw.get("version", ""),
        stages=stages,
        edges=edges,
        global_contracts=global_contracts,
        evidence=evidence,
        applicability=applicability,
        source=raw.get("source", {}),
        not_suitable_for=not_suitable_for,
        raw=raw,
        resources=resources,
        relations=relations,
        activation=activation,
    )
