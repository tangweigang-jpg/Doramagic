# Compare Decisions

## 1. Pairwise mock matching instead of embeddings

Round 2 赛马版不接外部向量服务。`compare.py` 采用 deterministic pairwise matching：

- lexical：关键词 canonicalization + overlap
- semantic：归一化 token Jaccard
- structured：subject / predicate / object / type / scope slot matching

## 2. Graph clustering

所有跨项目 atom 先做 pairwise 打分，再按 `PARTIAL >= 0.62` 连边，最后用连通分量形成 cluster。这样能把“同义措辞变化”稳定聚合，避免误标 `ORIGINAL`。

## 3. ORIGINAL 必须二次检索

support=1 的 cluster 不会直接判 `ORIGINAL`。必须再扫一遍所有跨项目 pairwise 候选，确认没有任何替代匹配达到 `partial_threshold`，然后才输出 `ORIGINAL`，并把二次检索结果写入 `notes`。

## 4. Community signals 不忽略

`community_signals` 不参与主匹配语义，但参与 `support_independence` 计算，避免实现上完全丢弃这部分 contract 输入。

## 5. comparison_result.json 固定输出

函数返回 `CompareOutput` 的同时，会额外写出固定文件名 `comparison_result.json`。默认写到系统临时目录下的 `doramagic_compare/<domain_id>/`，测试可通过 `DORAMAGIC_COMPARE_OUTPUT_DIR` 覆盖。
