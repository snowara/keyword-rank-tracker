"""Gmail SMTP 이메일 알림 발송"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from core.db_manager import get_setting, add_alert_log

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _load_template() -> str:
    """HTML 이메일 템플릿 로드"""
    path = TEMPLATE_DIR / "rank_alert.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "<html><body><h2>{title}</h2>{content}</body></html>"


def _build_alert_html(alerts: list) -> str:
    """알림 내용을 HTML로 변환"""
    template = _load_template()

    rows = ""
    for a in alerts:
        change = a.get("change", "")
        if isinstance(change, int):
            if change > 0:
                change_str = f'<span style="color:#e74c3c">▼ {abs(change)}단계 하락</span>'
            elif change < 0:
                change_str = f'<span style="color:#27ae60">▲ {abs(change)}단계 상승</span>'
            else:
                change_str = '<span style="color:#95a5a6">변동없음</span>'
        else:
            change_str = str(change)

        rank_display = a.get("rank", "-") or "순위권 밖"
        prev_display = a.get("prev_rank", "-") or "순위권 밖"

        rows += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #e0e0e0">{a.get('keyword','')}</td>
            <td style="padding:10px;border-bottom:1px solid #e0e0e0;text-align:center">{prev_display}</td>
            <td style="padding:10px;border-bottom:1px solid #e0e0e0;text-align:center;font-weight:bold">{rank_display}</td>
            <td style="padding:10px;border-bottom:1px solid #e0e0e0;text-align:center">{change_str}</td>
            <td style="padding:10px;border-bottom:1px solid #e0e0e0">{a.get('alert_type','')}</td>
        </tr>"""

    content = f"""
    <table style="width:100%;border-collapse:collapse;font-family:'Noto Sans KR',sans-serif">
        <thead>
            <tr style="background:#1B2A4A;color:#fff">
                <th style="padding:10px;text-align:left">키워드</th>
                <th style="padding:10px">이전 순위</th>
                <th style="padding:10px">현재 순위</th>
                <th style="padding:10px">변동</th>
                <th style="padding:10px;text-align:left">알림 유형</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""

    return template.replace("{title}", "네이버 쇼핑 순위 변동 알림").replace("{content}", content)


def _get_smtp_config() -> dict:
    """설정에서 SMTP 정보 조회"""
    return {
        "email": get_setting("gmail_address", ""),
        "password": get_setting("gmail_app_password", ""),
        "recipient": get_setting("alert_recipient", ""),
    }


def send_alert(alerts: list) -> bool:
    """
    순위 변동 알림 이메일 발송.

    Args:
        alerts: [{keyword, keyword_id, rank, prev_rank, change, alert_type}, ...]

    Returns:
        성공 여부
    """
    config = _get_smtp_config()
    if not all([config["email"], config["password"], config["recipient"]]):
        logger.warning("SMTP 설정 미완료 — 알림 미발송")
        return False

    if not alerts:
        return False

    html = _build_alert_html(alerts)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[순위 알림] {len(alerts)}건의 순위 변동 감지"
    msg["From"] = config["email"]
    msg["To"] = config["recipient"]
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(config["email"], config["password"])
            server.sendmail(config["email"], config["recipient"], msg.as_string())

        # 알림 로그 기록
        for a in alerts:
            add_alert_log(a["keyword_id"], a["alert_type"], f"{a['keyword']}: {a.get('change','')}")

        logger.info(f"알림 이메일 발송 완료: {len(alerts)}건")
        return True
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        return False


def check_and_send_alerts(check_results: list, prev_ranks: dict):
    """
    체크 결과와 이전 순위를 비교하여 알림 조건 판단 + 발송.

    Args:
        check_results: check_all_keywords 반환값
        prev_ranks: {keyword_id: prev_rank_int_or_None}
    """
    threshold = int(get_setting("alert_threshold", "5"))
    alert_top10 = get_setting("alert_top10", "1") == "1"
    alert_lost = get_setting("alert_lost", "1") == "1"
    alert_new = get_setting("alert_new", "1") == "1"
    alerts_enabled = get_setting("alerts_enabled", "0") == "1"

    if not alerts_enabled:
        return

    alerts = []

    for cr in check_results:
        kid = cr["keyword_id"]
        kw = cr["keyword"]
        result = cr["result"]
        curr = result.rank
        prev = prev_ranks.get(kid)

        if curr is None and prev is not None and alert_lost:
            alerts.append({
                "keyword": kw, "keyword_id": kid,
                "rank": None, "prev_rank": prev,
                "change": "순위 이탈",
                "alert_type": "순위 이탈",
            })
        elif curr is not None and prev is None and alert_new:
            alerts.append({
                "keyword": kw, "keyword_id": kid,
                "rank": curr, "prev_rank": None,
                "change": "신규 진입",
                "alert_type": "신규 진입",
            })
        elif curr is not None and prev is not None:
            change = curr - prev  # 양수=하락, 음수=상승
            # 순위 N단계 이상 변동
            if abs(change) >= threshold:
                alert_type = "순위 상승" if change < 0 else "순위 하락"
                alerts.append({
                    "keyword": kw, "keyword_id": kid,
                    "rank": curr, "prev_rank": prev,
                    "change": change,
                    "alert_type": alert_type,
                })
            # TOP10 진입/이탈
            if alert_top10:
                if prev > 10 and curr <= 10:
                    alerts.append({
                        "keyword": kw, "keyword_id": kid,
                        "rank": curr, "prev_rank": prev,
                        "change": change,
                        "alert_type": "TOP10 진입",
                    })
                elif prev <= 10 and curr > 10:
                    alerts.append({
                        "keyword": kw, "keyword_id": kid,
                        "rank": curr, "prev_rank": prev,
                        "change": change,
                        "alert_type": "TOP10 이탈",
                    })

    if alerts:
        send_alert(alerts)
