"""文档提取器单元测试 — 使用 mock LLM。"""

import asyncio
import json

from doramagic_judgment_pipeline.extract.doc_extractor import (
    SOURCE_TYPE_TO_LAYER,
    SOURCE_TYPE_TO_SECTION,
    extract_doc_judgments,
)
from doramagic_judgment_pipeline.source_adapters.base import RawExperienceRecord


class MockLLMResponse:
    def __init__(self, text: str):
        self.content = text


class MockLLMAdapter:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def chat(self, **kwargs):
        return MockLLMResponse(self._response_text)


def _make_doc_record() -> RawExperienceRecord:
    return RawExperienceRecord(
        source_type="github_readme",
        source_id="readme:limitations",
        source_url="https://github.com/freqtrade/freqtrade#readme",
        source_platform="github",
        project_or_community="freqtrade/freqtrade",
        title="Known Limitations",
        body="yfinance has rate limits. You must cache data locally to avoid disruption.",
        signals={"source_type": "github_readme"},
    )


class TestDocExtractor:
    def test_extract_valid_judgment(self):
        llm_output = json.dumps(
            [
                {
                    "when": "使用 yfinance 拉取历史数据进行回测时",
                    "modality": "must",
                    "action": "在本地建立数据缓存，每次运行先检查缓存是否存在",
                    "consequence_kind": "service_disruption",
                    "consequence_description": "高频请求触发 yfinance 限流，回测流水线中断",
                    "layer": "resource",
                    "severity": "medium",
                    "confidence_score": 0.8,
                    "crystal_section": "hard_constraints",
                    "evidence_summary": "README Limitations: rate limits may apply",
                }
            ]
        )

        adapter = MockLLMAdapter(llm_output)
        record = _make_doc_record()

        judgments = asyncio.run(
            extract_doc_judgments(
                record=record,
                adapter=adapter,
                domain="finance",
                id_counter=1,
            )
        )

        assert len(judgments) == 1
        j = judgments[0]
        assert j.layer == "resource"
        assert j.compilation.crystal_section == "hard_constraints"
        assert j.confidence.source == "S1_single_project"
        assert j.confidence.evidence_refs[0].type == "doc"

    def test_experience_layer_rejected(self):
        """文档提取器不应产出 experience 层判断。"""
        llm_output = json.dumps(
            [
                {
                    "when": "对外部 API 进行集成测试时",
                    "modality": "must",
                    "action": "使用 mock 服务替代真实 API 调用避免外部依赖",
                    "consequence_kind": "bug",
                    "consequence_description": "测试因外部服务不可用而失败",
                    "layer": "experience",
                    "severity": "low",
                    "confidence_score": 0.6,
                    "crystal_section": "hard_constraints",
                    "evidence_summary": "文档中的测试建议",
                }
            ]
        )

        adapter = MockLLMAdapter(llm_output)
        record = _make_doc_record()

        judgments = asyncio.run(
            extract_doc_judgments(
                record=record,
                adapter=adapter,
                domain="finance",
                id_counter=1,
            )
        )

        if judgments:
            assert judgments[0].layer != "experience"

    def test_empty_extraction(self):
        adapter = MockLLMAdapter("[]")
        record = _make_doc_record()
        judgments = asyncio.run(
            extract_doc_judgments(record=record, adapter=adapter, domain="finance")
        )
        assert judgments == []

    def test_invalid_json(self):
        adapter = MockLLMAdapter("This is not JSON at all")
        record = _make_doc_record()
        judgments = asyncio.run(
            extract_doc_judgments(record=record, adapter=adapter, domain="finance")
        )
        assert judgments == []

    def test_source_type_mappings(self):
        assert SOURCE_TYPE_TO_LAYER["github_readme"].value == "knowledge"
        assert SOURCE_TYPE_TO_LAYER["github_changelog"].value == "resource"
        assert SOURCE_TYPE_TO_SECTION["github_readme"].value == "code_skeleton"
        assert SOURCE_TYPE_TO_SECTION["github_deps"].value == "hard_constraints"
