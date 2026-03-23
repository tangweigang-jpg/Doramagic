"""Stage 0 提取模块测试。

用临时目录模拟不同类型的仓库，验证 extract_repo_facts 返回的 RepoFacts
通过 Pydantic schema 验证，且关键字段值符合预期。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 引用 contracts 包
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "contracts"))
# 引用 extraction 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from doramagic_contracts.extraction import RepoFacts  # noqa: E402
from doramagic_extraction.stage0 import extract_repo_facts  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: basic validation
# ---------------------------------------------------------------------------


class TestExtractRepoFactsBasic:
    def test_returns_repo_facts_instance(self, tmp_path: Path) -> None:
        """返回值是 RepoFacts 实例。"""
        result = extract_repo_facts(str(tmp_path))
        assert isinstance(result, RepoFacts)

    def test_schema_version(self, tmp_path: Path) -> None:
        """schema_version 必须符合合约。"""
        result = extract_repo_facts(str(tmp_path))
        assert result.schema_version == "dm.repo-facts.v1"

    def test_pydantic_validation_passes(self, tmp_path: Path) -> None:
        """RepoFacts 能通过 Pydantic model_validate 的完整验证。"""
        result = extract_repo_facts(str(tmp_path))
        # 通过 model_dump / model_validate 做一次往返，确保 schema 合规
        dumped = result.model_dump()
        validated = RepoFacts.model_validate(dumped)
        assert validated.schema_version == result.schema_version

    def test_json_roundtrip(self, tmp_path: Path) -> None:
        """RepoFacts 能序列化为 JSON 并反序列化。"""
        result = extract_repo_facts(str(tmp_path))
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        restored = RepoFacts.model_validate(parsed)
        assert restored.repo.repo_id == result.repo.repo_id

    def test_repo_ref_local_path(self, tmp_path: Path) -> None:
        """repo.local_path 指向传入的目录。"""
        result = extract_repo_facts(str(tmp_path))
        assert result.repo.local_path == str(tmp_path.resolve())

    def test_repo_ref_repo_id(self, tmp_path: Path) -> None:
        """repo.repo_id 为目录名。"""
        target = tmp_path / "my-project"
        target.mkdir()
        result = extract_repo_facts(str(target))
        assert result.repo.repo_id == "my-project"

    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        """不存在的路径应抛出 ValueError。"""
        with pytest.raises(ValueError, match="does not exist"):
            extract_repo_facts(str(tmp_path / "nonexistent"))

    def test_file_path_raises(self, tmp_path: Path) -> None:
        """传入文件路径（非目录）应抛出 ValueError。"""
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="not a directory"):
            extract_repo_facts(str(f))


# ---------------------------------------------------------------------------
# Tests: language detection
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    def test_detects_typescript(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "index.ts", "const x = 1;")
        _write(tmp_path / "src" / "app.tsx", "export default function App() {}")
        result = extract_repo_facts(str(tmp_path))
        assert "TypeScript" in result.languages

    def test_detects_python(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "print('hello')")
        _write(tmp_path / "utils.py", "def helper(): pass")
        result = extract_repo_facts(str(tmp_path))
        assert "Python" in result.languages

    def test_empty_repo_no_languages(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert result.languages == []

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        # node_modules 内的文件不应被计入
        _write(tmp_path / "node_modules" / "react" / "index.js", "module.exports = {};")
        _write(tmp_path / "src" / "app.ts", "const x = 1;")
        result = extract_repo_facts(str(tmp_path))
        # TypeScript 应出现，JavaScript (from node_modules) 不应覆盖它
        assert "TypeScript" in result.languages


# ---------------------------------------------------------------------------
# Tests: framework detection
# ---------------------------------------------------------------------------


class TestFrameworkDetection:
    def test_detects_nextjs(self, tmp_path: Path) -> None:
        _write(tmp_path / "next.config.js", "module.exports = {};")
        result = extract_repo_facts(str(tmp_path))
        assert "Next.js" in result.frameworks

    def test_detects_fastapi_via_pyproject(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "pyproject.toml",
            "[project]\ndependencies = ['fastapi>=0.100', 'uvicorn']\n",
        )
        result = extract_repo_facts(str(tmp_path))
        assert "FastAPI" in result.frameworks

    def test_detects_django_via_requirements(self, tmp_path: Path) -> None:
        _write(tmp_path / "requirements.txt", "django>=4.0\npsycopg2\n")
        result = extract_repo_facts(str(tmp_path))
        assert "Django" in result.frameworks

    def test_no_framework_on_empty_repo(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert result.frameworks == []


# ---------------------------------------------------------------------------
# Tests: entrypoint detection
# ---------------------------------------------------------------------------


class TestEntrypointDetection:
    def test_detects_main_py(self, tmp_path: Path) -> None:
        _write(tmp_path / "main.py", "if __name__ == '__main__': pass")
        result = extract_repo_facts(str(tmp_path))
        assert "main.py" in result.entrypoints

    def test_detects_nextjs_chat_route(self, tmp_path: Path) -> None:
        _write(tmp_path / "src" / "app" / "api" / "chat" / "route.ts", "export async function POST() {}")
        result = extract_repo_facts(str(tmp_path))
        assert "src/app/api/chat/route.ts" in result.entrypoints

    def test_no_entrypoints_on_empty_repo(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert result.entrypoints == []


# ---------------------------------------------------------------------------
# Tests: command detection
# ---------------------------------------------------------------------------


class TestCommandDetection:
    def test_detects_npm_scripts(self, tmp_path: Path) -> None:
        pkg = {"scripts": {"dev": "next dev", "build": "next build", "test": "jest"}}
        _write(tmp_path / "package.json", json.dumps(pkg))
        result = extract_repo_facts(str(tmp_path))
        assert "npm run dev" in result.commands
        assert "npm run build" in result.commands
        assert "npm run test" in result.commands

    def test_detects_pytest_from_pyproject(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "pyproject.toml",
            "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        )
        result = extract_repo_facts(str(tmp_path))
        assert "pytest" in result.commands

    def test_no_commands_on_empty_repo(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert result.commands == []


# ---------------------------------------------------------------------------
# Tests: dependency detection
# ---------------------------------------------------------------------------


class TestDependencyDetection:
    def test_detects_npm_dependencies(self, tmp_path: Path) -> None:
        pkg = {
            "dependencies": {"next": "^14.0", "react": "^18.0", "openai": "^4.0"},
            "devDependencies": {"typescript": "^5.0"},
        }
        _write(tmp_path / "package.json", json.dumps(pkg))
        result = extract_repo_facts(str(tmp_path))
        assert "next" in result.dependencies
        assert "react" in result.dependencies
        assert "openai" in result.dependencies
        assert "typescript" in result.dependencies

    def test_detects_python_requirements(self, tmp_path: Path) -> None:
        _write(tmp_path / "requirements.txt", "fastapi>=0.100\nuvicorn[standard]\npydantic==2.0\n")
        result = extract_repo_facts(str(tmp_path))
        assert "fastapi" in result.dependencies
        assert "uvicorn" in result.dependencies
        assert "pydantic" in result.dependencies

    def test_no_dependencies_on_empty_repo(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert result.dependencies == []


# ---------------------------------------------------------------------------
# Tests: repo_summary
# ---------------------------------------------------------------------------


class TestRepoSummary:
    def test_summary_contains_repo_name(self, tmp_path: Path) -> None:
        target = tmp_path / "calorie-tracker"
        target.mkdir()
        result = extract_repo_facts(str(target))
        assert "calorie-tracker" in result.repo_summary

    def test_summary_is_non_empty_string(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path))
        assert isinstance(result.repo_summary, str)
        assert len(result.repo_summary) > 0


# ---------------------------------------------------------------------------
# Tests: config passthrough (骨架阶段仅验证不报错)
# ---------------------------------------------------------------------------


class TestConfigPassthrough:
    def test_accepts_none_config(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path), config=None)
        assert isinstance(result, RepoFacts)

    def test_accepts_empty_config(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path), config={})
        assert isinstance(result, RepoFacts)

    def test_accepts_arbitrary_config(self, tmp_path: Path) -> None:
        result = extract_repo_facts(str(tmp_path), config={"exclude_dirs": ["vendor"]})
        assert isinstance(result, RepoFacts)
