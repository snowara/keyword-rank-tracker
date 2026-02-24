"""APScheduler 기반 자동 순위 체크 스케줄러"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.db_manager import (
    get_keywords, add_rank_record, get_latest_ranks,
    get_setting, set_setting,
)
from core.rank_checker import check_all_keywords
from core.alert_sender import check_and_send_alerts

logger = logging.getLogger(__name__)

_scheduler = None  # type: BackgroundScheduler
JOB_ID = "daily_rank_check"


def _run_scheduled_check():
    """스케줄러에서 호출하는 전체 키워드 체크"""
    logger.info("스케줄 순위 체크 시작")

    # 이전 순위 수집
    latest = get_latest_ranks()
    prev_ranks = {}
    for r in latest:
        prev_ranks[r["keyword_id"]] = r["rank"]

    # 활성 키워드 체크
    keywords = get_keywords(active_only=True)
    if not keywords:
        logger.info("활성 키워드 없음 — 스킵")
        return

    results = check_all_keywords(keywords)

    # DB 저장
    for cr in results:
        result = cr["result"]
        add_rank_record(
            keyword_id=cr["keyword_id"],
            rank=result.rank,
            title=result.title,
            mall_name=result.mall_name,
            price=result.price,
            link=result.link,
            product_id=result.product_id,
        )

    # 알림 체크 + 발송
    check_and_send_alerts(results, prev_ranks)

    set_setting("last_check_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(f"스케줄 순위 체크 완료: {len(results)}건")


def get_scheduler():
    return _scheduler


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def start_scheduler(hour: int = 9, minute: int = 0):
    """스케줄러 시작"""
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _scheduler.add_job(
        _run_scheduled_check,
        CronTrigger(hour=hour, minute=minute),
        id=JOB_ID,
        replace_existing=True,
        name="매일 순위 체크",
    )
    _scheduler.start()
    set_setting("scheduler_enabled", "1")
    set_setting("scheduler_hour", str(hour))
    set_setting("scheduler_minute", str(minute))
    logger.info(f"스케줄러 시작: 매일 {hour:02d}:{minute:02d}")


def stop_scheduler():
    """스케줄러 중지"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    set_setting("scheduler_enabled", "0")
    logger.info("스케줄러 중지")


def init_scheduler_from_settings():
    """설정값에서 스케줄러 복원"""
    if get_setting("scheduler_enabled", "0") == "1":
        hour = int(get_setting("scheduler_hour", "9"))
        minute = int(get_setting("scheduler_minute", "0"))
        start_scheduler(hour, minute)
