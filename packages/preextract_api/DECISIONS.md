# DECISIONS: api.read (S3-Gemini)

## 1. 架构选择

- **FastAPI**: 满足只读、轻量、高性能的要求，自带 OpenAPI 文档。
- **数据加载策略**: 启动时扫描 `data_dir` 并将 `snapshot_manifest.json` 加载到内存。Bricks 和 Truth 内容也是预加载，以保证查询性能。
- **CORS**: 默认开启 `CORSMiddleware`，允许所有 origin，方便终端和开发调试工具调用。

## 2. 知识原子 (Atoms) 处理

- 由于当前的 fixture 中 `atoms_parquet_path` 为 null，且没有 Parquet 文件，我实现了一个兼容 `atoms.json` 的备选方案。
- 在 `GET /domains/{id}/atoms` 中，支持内存中的过滤和分页。

## 3. 体检 (Health Check) 逻辑

- 目前 fixture 尚未包含 `health_report.json`。
- 在 `GET /domains/{id}/health/{project}` 中，实现了一个简单的启发式逻辑：如果 project 在任何 brick 的 `source_project_ids` 中，则返回 `healthy`，否则返回 `unknown`。

## 4. 扩展性考虑

- 预留了 `POST /admin/reload` 接口，用于在不重启服务的情况下刷新快照数据（例如新的 snapshot 被构建出来后）。
- 支持通过环境变量 `DORAMAGIC_API_DATA_DIR` 灵活配置快照存储位置。

## 5. 候选扩展 (Candidate Extensions)

- **建议字段**: `DomainListItem` 增加 `stats` 字典，直接返回完整的 `SnapshotStats`。
- **搜索优化**: `/atoms` 端点建议增加语义搜索 (Vector Search) 支持，而不仅仅是关键字过滤。
