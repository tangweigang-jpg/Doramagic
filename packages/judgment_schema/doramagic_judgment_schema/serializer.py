"""JSONL 格式的判断持久化和索引维护。"""

from __future__ import annotations

import fcntl
import logging
import os
from pathlib import Path

from .types import Judgment, Relation

logger = logging.getLogger(__name__)


class JudgmentStore:
    """文件系统上的判断库。JSONL 存储 + 内存索引。"""

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)
        self.domains_dir = self.base_path / "domains"
        self.domains_dir.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._judgments: dict[str, Judgment] = {}  # id -> Judgment
        self._domain_index: dict[str, list[str]] = {}  # domain -> [ids]
        self._relation_graph: dict[str, list[Relation]] = {}  # id -> [relations]

        # 初始化：加载已有数据
        self._load_all()

    def _load_all(self) -> None:
        """从 JSONL 文件加载所有判断到内存。"""
        for jsonl_file in self.domains_dir.glob("*.jsonl"):
            self._load_file(jsonl_file)

        # 加载 universal
        universal_path = self.base_path / "universal.jsonl"
        if universal_path.exists():
            self._load_file(universal_path)

    def _load_file(self, path: Path) -> None:
        """加载单个 JSONL 文件，跳过损坏行。"""
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                judgment = Judgment.model_validate_json(line)
                self._index(judgment)
            except Exception:
                logger.warning("跳过损坏的 JSONL 行: %s:%d", path, i)

    def _index(self, judgment: Judgment) -> None:
        """将判断加入内存索引。防止重复 ID 污染 domain_index。"""
        is_update = judgment.id in self._judgments
        if is_update:
            # 清理旧的 domain_index 条目
            old = self._judgments[judgment.id]
            for domain in old.scope.domains:
                id_list = self._domain_index.get(domain, [])
                if judgment.id in id_list:
                    id_list.remove(judgment.id)

        self._judgments[judgment.id] = judgment
        for domain in judgment.scope.domains:
            self._domain_index.setdefault(domain, []).append(judgment.id)
        self._relation_graph[judgment.id] = list(judgment.relations)

    def get(self, judgment_id: str) -> Judgment | None:
        """按 ID 获取判断。"""
        return self._judgments.get(judgment_id)

    def list_by_domain(self, domain: str) -> list[Judgment]:
        """列出指定领域的所有判断。"""
        ids = self._domain_index.get(domain, [])
        return [self._judgments[id_] for id_ in ids if id_ in self._judgments]

    def list_all(self) -> list[Judgment]:
        """列出所有判断。"""
        return list(self._judgments.values())

    def get_relations(self, judgment_id: str, max_hops: int = 2) -> list[Judgment]:
        """BFS 图谱扩展，返回 max_hops 跳内的所有相关判断。"""
        visited: set[str] = {judgment_id}
        frontier: set[str] = {judgment_id}
        result: list[Judgment] = []

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for current_id in frontier:
                for rel in self._relation_graph.get(current_id, []):
                    if rel.target_id not in visited:
                        visited.add(rel.target_id)
                        next_frontier.add(rel.target_id)
                        j = self._judgments.get(rel.target_id)
                        if j:
                            result.append(j)
            frontier = next_frontier
            if not frontier:
                break

        return result

    def store(self, judgment: Judgment) -> None:
        """写入一颗判断。原子追加到 JSONL 文件 + 更新内存索引。"""
        # 幂等：content_hash 查重
        for existing in self._judgments.values():
            if existing.hash == judgment.hash and existing.id != judgment.id:
                return  # 已存在相同内容的判断，跳过

        # 确定文件路径
        primary_domain = judgment.scope.domains[0]
        if judgment.scope.level == "universal":
            file_path = self.base_path / "universal.jsonl"
        else:
            file_path = self.domains_dir / f"{primary_domain}.jsonl"

        # 原子追加写入：file locking + fsync
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = judgment.model_dump_json(exclude_none=True) + "\n"
        with open(file_path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # 更新内存索引
        self._index(judgment)

    def count(self) -> int:
        """返回判断总数。"""
        return len(self._judgments)

    def count_by_domain(self) -> dict[str, int]:
        """按领域统计判断数。"""
        return {domain: len(ids) for domain, ids in self._domain_index.items()}

    def count_by_layer(self) -> dict[str, int]:
        """按层统计判断数。"""
        result: dict[str, int] = {}
        for j in self._judgments.values():
            layer_val = j.layer if isinstance(j.layer, str) else j.layer.value
            result[layer_val] = result.get(layer_val, 0) + 1
        return result
