"""积木 v2 存储层 — SQLite + FTS5 全文搜索。

支持 10000+ 积木的高效检索与分页，并提供将积木约束注入 LLM prompt 的能力。

架构说明：
- 主表 bricks：结构化列 + raw_json 存完整 BrickV2
- 虚拟表 bricks_fts：FTS5 索引，加速关键词检索
- 所有写操作保持主表与 FTS 索引的一致性（使用 content table 模式）
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import yaml
from doramagic_contracts.brick_v2 import BrickV2
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# 默认数据库路径
_DEFAULT_DB_PATH = Path.home() / ".doramagic" / "bricks.db"

# FTS5 内容表触发器（保持 content table 与 FTS 同步）
_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS bricks_ai AFTER INSERT ON bricks BEGIN
    INSERT INTO bricks_fts(rowid, id, name, category, tags, core_capability, constraints)
    VALUES (
        new.rowid,
        new.id,
        new.name,
        new.category,
        new.tags,
        new.core_capability,
        new.constraints
    );
END;

CREATE TRIGGER IF NOT EXISTS bricks_ad AFTER DELETE ON bricks BEGIN
    INSERT INTO bricks_fts(bricks_fts, rowid, id, name, category, tags, core_capability, constraints)
    VALUES (
        'delete',
        old.rowid,
        old.id,
        old.name,
        old.category,
        old.tags,
        old.core_capability,
        old.constraints
    );
END;

CREATE TRIGGER IF NOT EXISTS bricks_au AFTER UPDATE ON bricks BEGIN
    INSERT INTO bricks_fts(bricks_fts, rowid, id, name, category, tags, core_capability, constraints)
    VALUES (
        'delete',
        old.rowid,
        old.id,
        old.name,
        old.category,
        old.tags,
        old.core_capability,
        old.constraints
    );
    INSERT INTO bricks_fts(rowid, id, name, category, tags, core_capability, constraints)
    VALUES (
        new.rowid,
        new.id,
        new.name,
        new.category,
        new.tags,
        new.core_capability,
        new.constraints
    );
END;
"""


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(tz=UTC).isoformat()


def _brick_to_row(brick: BrickV2) -> dict:
    """将 BrickV2 转换为数据库行字典。"""
    return {
        "id": brick.id,
        "name": brick.name,
        "version": brick.version,
        "category": json.dumps(brick.category, ensure_ascii=False),
        "tags": json.dumps(brick.tags, ensure_ascii=False),
        "capability_type": brick.capability_type,
        "data_source": brick.data_source,
        "inputs": json.dumps(
            {k: v.model_dump() for k, v in brick.inputs.items()},
            ensure_ascii=False,
        ),
        "outputs": json.dumps(
            {k: v.model_dump() for k, v in brick.outputs.items()},
            ensure_ascii=False,
        ),
        "requires": json.dumps(brick.requires, ensure_ascii=False),
        "conflicts_with": json.dumps(brick.conflicts_with, ensure_ascii=False),
        "compatible_with": json.dumps(brick.compatible_with, ensure_ascii=False),
        "core_capability": brick.core_capability,
        # constraints 展开为纯文本，便于 FTS5 检索
        "constraints": " ".join(brick.constraints),
        "common_failures": json.dumps(
            [fp.model_dump() for fp in brick.common_failures],
            ensure_ascii=False,
        ),
        "source": brick.source,
        "freshness_date": brick.freshness_date,
        "quality_score": brick.quality_score,
        "usage_count": brick.usage_count,
        "evidence_refs": json.dumps(brick.evidence_refs, ensure_ascii=False),
        "raw_json": brick.model_dump_json(),
    }


def _row_to_brick(row: sqlite3.Row) -> BrickV2:
    """从数据库行还原 BrickV2，优先使用 raw_json。"""
    return BrickV2.model_validate_json(row["raw_json"])


class BrickStore:
    """积木 v2 数据库操作。

    线程安全策略：每次操作创建独立连接（check_same_thread=False + WAL 模式）。
    不在对象级别持久化连接，避免多线程共享连接的问题。
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        fallback_dir: str | Path | None = None,
    ) -> None:
        """初始化 BrickStore。

        Args:
            db_path: 数据库文件路径，None 则使用默认路径 ~/.doramagic/bricks.db。
            fallback_dir: YAML 文件目录，数据库不可用时从此目录加载。
                         None 则不启用离线回退。
        """
        if db_path is None:
            self.db_path = _DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)
        self.fallback_dir = Path(fallback_dir) if fallback_dir else None

    def _connect(self) -> sqlite3.Connection:
        """创建并返回 SQLite 连接，启用 WAL 模式与 Row factory。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL 模式：写操作不阻塞读操作
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_db(self) -> None:
        """创建主表、FTS5 索引和同步触发器。

        幂等操作，可重复调用。
        """
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bricks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT DEFAULT '1.0.0',
                    category TEXT,
                    tags TEXT,
                    capability_type TEXT,
                    data_source TEXT,
                    inputs TEXT,
                    outputs TEXT,
                    requires TEXT,
                    conflicts_with TEXT,
                    compatible_with TEXT,
                    core_capability TEXT,
                    constraints TEXT,
                    common_failures TEXT,
                    source TEXT DEFAULT 'manual',
                    freshness_date TEXT,
                    quality_score REAL DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0,
                    evidence_refs TEXT,
                    raw_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS bricks_fts USING fts5(
                    id,
                    name,
                    category,
                    tags,
                    core_capability,
                    constraints,
                    content='bricks',
                    content_rowid='rowid'
                );
            """)
            conn.executescript(_FTS_TRIGGERS)
            # 如果数据库为空且有 fallback_dir，自动导入
            count = conn.execute("SELECT COUNT(*) FROM bricks").fetchone()[0]
            if count == 0 and self.fallback_dir and self.fallback_dir.exists():
                logger.info("数据库为空，从 %s 自动导入积木", self.fallback_dir)
        if count == 0 and self.fallback_dir and self.fallback_dir.exists():
            imported = self.import_dir(self.fallback_dir)
            logger.info("自动导入 %d 个积木", imported)
        logger.debug("init_db 完成，路径：%s", self.db_path)

    def upsert(self, brick: BrickV2) -> None:
        """插入或更新积木。

        更新时自动维护 updated_at；首次插入设置 created_at。

        Args:
            brick: 要写入的 BrickV2 积木。
        """
        row = _brick_to_row(brick)
        now = _now_iso()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM bricks WHERE id = ?", (brick.id,)
            ).fetchone()

            if existing:
                row["updated_at"] = now
                row["created_at"] = existing["created_at"]
            else:
                row["created_at"] = now
                row["updated_at"] = now

            conn.execute(
                """
                INSERT INTO bricks (
                    id, name, version, category, tags, capability_type, data_source,
                    inputs, outputs, requires, conflicts_with, compatible_with,
                    core_capability, constraints, common_failures, source,
                    freshness_date, quality_score, usage_count, evidence_refs,
                    raw_json, created_at, updated_at
                ) VALUES (
                    :id, :name, :version, :category, :tags, :capability_type, :data_source,
                    :inputs, :outputs, :requires, :conflicts_with, :compatible_with,
                    :core_capability, :constraints, :common_failures, :source,
                    :freshness_date, :quality_score, :usage_count, :evidence_refs,
                    :raw_json, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    category = excluded.category,
                    tags = excluded.tags,
                    capability_type = excluded.capability_type,
                    data_source = excluded.data_source,
                    inputs = excluded.inputs,
                    outputs = excluded.outputs,
                    requires = excluded.requires,
                    conflicts_with = excluded.conflicts_with,
                    compatible_with = excluded.compatible_with,
                    core_capability = excluded.core_capability,
                    constraints = excluded.constraints,
                    common_failures = excluded.common_failures,
                    source = excluded.source,
                    freshness_date = excluded.freshness_date,
                    quality_score = excluded.quality_score,
                    usage_count = excluded.usage_count,
                    evidence_refs = excluded.evidence_refs,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                row,
            )
        logger.debug("upsert 积木：%s", brick.id)

    def get(self, brick_id: str) -> BrickV2 | None:
        """按 id 获取积木。

        Args:
            brick_id: 积木唯一标识。

        Returns:
            BrickV2 对象，不存在时返回 None。
        """
        with self._connect() as conn:
            row = conn.execute("SELECT raw_json FROM bricks WHERE id = ?", (brick_id,)).fetchone()
        if row is None:
            return None
        return _row_to_brick(row)

    def search(self, query: str, limit: int = 10) -> list[BrickV2]:
        """全文搜索积木。

        使用 FTS5 MATCH 语法，匹配 name / category / tags / core_capability / constraints 字段。
        数据库不可用时回退到 YAML 文件目录做简单文本匹配。

        Args:
            query: 搜索关键词，支持 FTS5 MATCH 语法（如 "股票 AND 价格"）。
            limit: 最多返回数量，默认 10。

        Returns:
            按相关性排序的 BrickV2 列表。
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT b.raw_json
                    FROM bricks_fts f
                    JOIN bricks b ON b.rowid = f.rowid
                    WHERE bricks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            return [_row_to_brick(r) for r in rows]
        except Exception:
            logger.warning("数据库搜索失败，回退到 YAML 文件目录")
            return self._fallback_search(query, limit)

    def _fallback_search(self, query: str, limit: int = 10) -> list[BrickV2]:
        """从 YAML 文件目录做简单文本匹配（离线回退）。"""
        if not self.fallback_dir or not self.fallback_dir.exists():
            return []
        query_lower = query.lower()
        results: list[BrickV2] = []
        for yaml_file in self.fallback_dir.rglob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                brick = BrickV2.model_validate(data)
                searchable = f"{brick.name} {' '.join(brick.tags)} {brick.core_capability}"
                if query_lower in searchable.lower():
                    results.append(brick)
                    if len(results) >= limit:
                        break
            except Exception:
                continue
        return results

    def search_by_capability(
        self,
        capability_type: str,
        data_source: str | None = None,
    ) -> list[BrickV2]:
        """按能力类型和数据源过滤积木。

        Args:
            capability_type: 能力类型，如 "poll" / "filter" / "notify" / "transform"。
            data_source: 数据来源过滤，None 表示不过滤。

        Returns:
            匹配的 BrickV2 列表，按 quality_score 降序排列。
        """
        with self._connect() as conn:
            if data_source is None:
                rows = conn.execute(
                    """
                    SELECT raw_json FROM bricks
                    WHERE capability_type = ?
                    ORDER BY quality_score DESC
                    """,
                    (capability_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT raw_json FROM bricks
                    WHERE capability_type = ? AND data_source = ?
                    ORDER BY quality_score DESC
                    """,
                    (capability_type, data_source),
                ).fetchall()
        return [_row_to_brick(r) for r in rows]

    def list_all(self, limit: int = 100, offset: int = 0) -> list[BrickV2]:
        """分页列出所有积木。

        Args:
            limit: 每页数量，默认 100。
            offset: 偏移量，默认 0。

        Returns:
            BrickV2 列表，按 usage_count 降序（常用积木优先）。
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT raw_json FROM bricks
                ORDER BY usage_count DESC, quality_score DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [_row_to_brick(r) for r in rows]

    def delete(self, brick_id: str) -> bool:
        """删除积木。

        Args:
            brick_id: 要删除的积木 id。

        Returns:
            True 表示成功删除，False 表示 id 不存在。
        """
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM bricks WHERE id = ?", (brick_id,))
        deleted = cur.rowcount > 0
        if deleted:
            logger.debug("已删除积木：%s", brick_id)
        return deleted

    def import_from_yaml(self, yaml_path: str | Path) -> BrickV2:
        """从 YAML 文件导入单个积木。

        YAML 文件结构与 BrickV2 字段一一对应。

        Args:
            yaml_path: YAML 文件路径。

        Returns:
            导入并写入的 BrickV2 对象。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: YAML 格式错误或字段校验失败。
        """
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"YAML 文件不存在：{path}")

        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"YAML 文件顶层必须为字典：{path}")

        try:
            brick = BrickV2.model_validate(raw)
        except ValidationError as e:
            raise ValueError(f"积木字段校验失败（{path}）：{e}") from e

        self.upsert(brick)
        logger.info("从 YAML 导入积木：%s (%s)", brick.id, path)
        return brick

    def import_dir(self, dir_path: str | Path) -> int:
        """批量导入目录下所有 YAML 积木（.yaml / .yml）。

        跳过校验失败的文件并记录警告，不中断整批导入。

        Args:
            dir_path: 包含 YAML 积木文件的目录。

        Returns:
            成功导入的积木数量。
        """
        base = Path(dir_path)
        if not base.is_dir():
            raise NotADirectoryError(f"目录不存在：{base}")

        yaml_files = sorted(base.glob("*.yaml")) + sorted(base.glob("*.yml"))
        success_count = 0

        for yaml_file in yaml_files:
            try:
                self.import_from_yaml(yaml_file)
                success_count += 1
            except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
                logger.warning("跳过文件 %s：%s", yaml_file.name, e)

        logger.info("批量导入完成：%d / %d 个文件成功", success_count, len(yaml_files))
        return success_count

    def stats(self) -> dict:
        """统计信息：总数、按分类统计、按能力类型统计。

        Returns:
            包含 total / by_category / by_capability_type / by_source 的字典。
        """
        with self._connect() as conn:
            total: int = conn.execute("SELECT COUNT(*) FROM bricks").fetchone()[0]

            capability_rows = conn.execute(
                """
                SELECT capability_type, COUNT(*) as cnt
                FROM bricks
                GROUP BY capability_type
                ORDER BY cnt DESC
                """
            ).fetchall()

            source_rows = conn.execute(
                """
                SELECT source, COUNT(*) as cnt
                FROM bricks
                GROUP BY source
                ORDER BY cnt DESC
                """
            ).fetchall()

            # category 是 JSON 数组，需逐行展开统计
            all_categories: list[str] = []
            for row in conn.execute("SELECT category FROM bricks").fetchall():
                try:
                    cats = json.loads(row["category"] or "[]")
                    all_categories.extend(cats)
                except (json.JSONDecodeError, TypeError):
                    pass

        by_category: dict[str, int] = {}
        for cat in all_categories:
            by_category[cat] = by_category.get(cat, 0) + 1
        by_category = dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True))

        return {
            "total": total,
            "by_capability_type": {r["capability_type"]: r["cnt"] for r in capability_rows},
            "by_category": by_category,
            "by_source": {r["source"]: r["cnt"] for r in source_rows},
        }

    def to_prompt_constraints(self, brick_ids: list[str]) -> str:
        """将选中的积木约束合并为 LLM system prompt 文本。

        这是积木的最终消费方式——把多个积木的约束拼成一段结构化文本注入 LLM。
        缺失的 brick_id 会被跳过并记录警告。

        Args:
            brick_ids: 要合并的积木 id 列表。

        Returns:
            格式化的约束文本，供直接注入 system prompt。空列表返回空字符串。

        示例输出::

            你正在生成工具代码。必须遵守以下约束：

            【股票价格提醒】
            核心能力：使用 akshare 获取 A 股实时行情
            - 使用 akshare 库，方法 ak.stock_zh_a_spot_em()
            - API 限流：最多 5 次/分钟，必须内置 sleep(12)

            【Telegram 消息通知】
            核心能力：通过 python-telegram-bot 发送 Telegram 消息
            - 使用 python-telegram-bot 库
            - 消息长度限制 4096 字符
        """
        if not brick_ids:
            return ""

        sections: list[str] = []
        for bid in brick_ids:
            brick = self.get(bid)
            if brick is None:
                logger.warning("to_prompt_constraints：积木 '%s' 不存在，跳过", bid)
                continue

            lines: list[str] = [f"【{brick.name}】"]
            lines.append(f"核心能力：{brick.core_capability}")
            for constraint in brick.constraints:
                lines.append(f"- {constraint}")

            if brick.common_failures:
                lines.append("已知失败模式：")
                for failure in brick.common_failures:
                    lines.append(f"  [{failure.severity}] {failure.pattern} → {failure.mitigation}")

            sections.append("\n".join(lines))

        if not sections:
            return ""

        header = "你正在生成工具代码。必须遵守以下约束：\n"
        return header + "\n\n".join(sections)
