#!/usr/bin/env bash
set -e

# 1. 检查 Python 版本 (>= 3.9)
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "错误: 未找到 $PYTHON_CMD 命令。请安装 Python 3.9 或以上版本。"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if $(awk "BEGIN {exit !($PY_VERSION < 3.9)}") ; then
    echo "错误: 需要 Python >= 3.9，当前版本是 $PY_VERSION"
    exit 1
fi
echo "✅ Python 版本检查通过: $PY_VERSION"

# 2. 安装依赖
echo "📦 安装开发依赖..."
pip3 install --user pydantic eval_type_backport pytest ruff mypy hatchling

# 3. 验证 contracts 可导入
echo "🔍 验证 contracts 模块导入..."
export PYTHONPATH="$(pwd)/packages/contracts:$PYTHONPATH"
if $PYTHON_CMD -c "import doramagic_contracts; print('✅ doramagic_contracts 导入成功')" &> /dev/null; then
    echo "✅ doramagic_contracts 导入成功"
else
    echo "❌ 错误: doramagic_contracts 导入失败"
    exit 1
fi

# 4. 运行全量检查
echo "🚀 运行 make check..."
make check

echo "🎉 开发环境配置完成！"
