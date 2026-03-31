"""
比特币价格监控脚本

功能：
- 启动时记录比特币基准价格
- 每 5 分钟检查一次当前价格
- 当价格相比基准价格下跌 10% 时，通过 Telegram 发送提醒

依赖安装：
    pip install httpx python-telegram-bot>=20.0

环境变量（必须在运行前设置）：
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    export TELEGRAM_CHAT_ID="your_chat_id"

运行：
    python btc_monitor.py
"""

import asyncio
import logging
import os
from datetime import datetime

import httpx
from telegram import Bot
from telegram.error import Forbidden, RetryAfter, TelegramError

# ──────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 常量配置
# ──────────────────────────────────────────────

COINGECKO_API_URL: str = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
)
CHECK_INTERVAL_SECONDS: int = 5 * 60     # 检查间隔：5 分钟
DROP_THRESHOLD: float = 0.10             # 下跌阈值：10%
RETRY_BASE_SECONDS: float = 2.0          # 指数退避起始等待秒数
RETRY_MAX_SECONDS: float = 64.0          # 指数退避最大等待秒数
MAX_FETCH_RETRIES: int = 6               # 最大重试次数


# ──────────────────────────────────────────────
# 价格获取
# ──────────────────────────────────────────────

async def fetch_btc_price(client: httpx.AsyncClient) -> float:
    """从 CoinGecko 免费 API 获取比特币当前美元价格，含指数退避重试。

    Args:
        client: 复用的 httpx.AsyncClient 实例。

    Returns:
        比特币当前价格（USD）。

    Raises:
        RuntimeError: 超过最大重试次数后仍无法获取价格。
    """
    wait = RETRY_BASE_SECONDS
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = await client.get(COINGECKO_API_URL, timeout=15)
            if response.status_code == 429:
                logger.warning(
                    "CoinGecko 速率限制（429），第 %d/%d 次重试，等待 %.0fs …",
                    attempt,
                    MAX_FETCH_RETRIES,
                    wait,
                )
                await asyncio.sleep(wait)
                wait = min(wait * 2, RETRY_MAX_SECONDS)
                continue
            response.raise_for_status()
            data = response.json()
            price: float = float(data["bitcoin"]["usd"])
            return price
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP 错误（第 %d 次）：%s", attempt, exc)
            await asyncio.sleep(wait)
            wait = min(wait * 2, RETRY_MAX_SECONDS)
        except (httpx.RequestError, KeyError, ValueError) as exc:
            logger.error("请求或解析错误（第 %d 次）：%s", attempt, exc)
            await asyncio.sleep(wait)
            wait = min(wait * 2, RETRY_MAX_SECONDS)

    raise RuntimeError(
        f"超过最大重试次数 ({MAX_FETCH_RETRIES})，无法获取 BTC 价格"
    )


# ──────────────────────────────────────────────
# Telegram 通知
# ──────────────────────────────────────────────

def _escape_html(text: str) -> str:
    """对 Telegram HTML parse_mode 所需的三个特殊字符进行转义。

    Args:
        text: 待转义的字符串。

    Returns:
        转义后的字符串。
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_alert_message(
    baseline_price: float,
    current_price: float,
    drop_pct: float,
) -> str:
    """构建价格下跌告警的 HTML 消息文本。

    Args:
        baseline_price: 启动时记录的基准价格（USD）。
        current_price: 当前价格（USD）。
        drop_pct: 下跌幅度（0~1 之间的小数）。

    Returns:
        HTML 格式的 Telegram 消息字符串，长度不超过 4096 字符。
    """
    now = _escape_html(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    baseline_str = _escape_html(f"{baseline_price:,.2f}")
    current_str = _escape_html(f"{current_price:,.2f}")
    drop_str = _escape_html(f"{drop_pct * 100:.2f}")

    return (
        "<b>比特币价格跌幅告警</b>\n\n"
        f"时间：{now}\n"
        f"启动基准价格：<b>${baseline_str}</b>\n"
        f"当前价格：<b>${current_str}</b>\n"
        f"下跌幅度：<b>{drop_str}%</b>（阈值：{int(DROP_THRESHOLD * 100)}%）\n\n"
        "请注意风险，理性决策。"
    )


async def send_telegram_alert(
    bot: Bot,
    chat_id: str,
    baseline_price: float,
    current_price: float,
    drop_pct: float,
) -> None:
    """通过 Telegram 发送价格下跌告警，含限流重试和错误处理。

    Args:
        bot: 已初始化的 Telegram Bot 实例。
        chat_id: 目标 Chat ID。
        baseline_price: 启动时记录的基准价格（USD）。
        current_price: 当前价格（USD）。
        drop_pct: 下跌幅度（0~1 之间的小数）。
    """
    message = _build_alert_message(baseline_price, current_price, drop_pct)

    async def _send() -> None:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
        )

    try:
        await _send()
        logger.info("Telegram 告警已发送至 chat_id=%s", chat_id)
    except Forbidden:
        # Bot 被用户屏蔽，不可达，不重试
        logger.error(
            "Bot 被用户屏蔽（Forbidden 403），chat_id=%s 不可达，告警已跳过",
            chat_id,
        )
    except RetryAfter as exc:
        # Telegram 速率限制，等待后重试一次
        logger.warning(
            "Telegram 速率限制（RetryAfter），等待 %ds 后重试…",
            exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after)
        try:
            await _send()
            logger.info("Telegram 告警重试成功，chat_id=%s", chat_id)
        except TelegramError as retry_exc:
            logger.error("Telegram 告警重试失败：%s", retry_exc)
    except TelegramError as exc:
        logger.error("发送 Telegram 消息失败：%s", exc)


# ──────────────────────────────────────────────
# 主循环
# ──────────────────────────────────────────────

async def main() -> None:
    """主入口：读取环境变量、获取基准价格、进入定时监控循环。"""
    # 读取并校验环境变量
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        raise EnvironmentError(
            "缺少必要环境变量 TELEGRAM_BOT_TOKEN，请先执行：\n"
            "  export TELEGRAM_BOT_TOKEN='your_bot_token'"
        )
    if not chat_id:
        raise EnvironmentError(
            "缺少必要环境变量 TELEGRAM_CHAT_ID，请先执行：\n"
            "  export TELEGRAM_CHAT_ID='your_chat_id'"
        )

    bot = Bot(token=bot_token)

    async with httpx.AsyncClient() as client:
        # ── 获取启动基准价格（失败则持续重试直到成功）──
        logger.info("正在获取 BTC 启动基准价格…")
        baseline_price: float | None = None
        while baseline_price is None:
            try:
                baseline_price = await fetch_btc_price(client)
            except RuntimeError as exc:
                logger.error(
                    "获取基准价格失败：%s，60 秒后重试…", exc
                )
                await asyncio.sleep(60)

        logger.info(
            "BTC 基准价格已锁定：$%.2f | 阈值：%.0f%% | 检查间隔：%d 分钟",
            baseline_price,
            DROP_THRESHOLD * 100,
            CHECK_INTERVAL_SECONDS // 60,
        )

        alert_sent = False  # 同一跌幅周期内只发一次告警

        # ── 定时监控循环 ──
        while True:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

            try:
                current_price = await fetch_btc_price(client)
            except RuntimeError as exc:
                logger.error("获取价格失败，跳过本次检查：%s", exc)
                continue

            drop_pct = (baseline_price - current_price) / baseline_price
            change_sign = "-" if drop_pct > 0 else "+"
            logger.info(
                "BTC 当前价格：$%.2f | 基准：$%.2f | 变化：%s%.2f%%",
                current_price,
                baseline_price,
                change_sign,
                abs(drop_pct * 100),
            )

            if drop_pct >= DROP_THRESHOLD:
                # 价格下跌超过阈值
                if not alert_sent:
                    logger.warning(
                        "触发告警！价格下跌 %.2f%%，超过阈值 %.0f%%",
                        drop_pct * 100,
                        DROP_THRESHOLD * 100,
                    )
                    await send_telegram_alert(
                        bot=bot,
                        chat_id=chat_id,
                        baseline_price=baseline_price,
                        current_price=current_price,
                        drop_pct=drop_pct,
                    )
                    alert_sent = True
                else:
                    logger.info(
                        "价格仍处于告警区间（下跌 %.2f%%），告警已发送，不重复通知",
                        drop_pct * 100,
                    )
            else:
                # 价格恢复到阈值以上，重置告警标志
                if alert_sent:
                    logger.info(
                        "价格已从告警区间恢复（当前下跌 %.2f%%），重置告警状态",
                        drop_pct * 100,
                    )
                    alert_sent = False


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("监控已手动停止。")
    except EnvironmentError as env_err:
        logger.error("配置错误：%s", env_err)
