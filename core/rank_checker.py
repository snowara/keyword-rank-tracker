"""네이버 쇼핑 API 순위 체크 엔진"""
import re
import time
import logging
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass

from config import (
    NAVER_SHOP_API_URL, NAVER_API_HEADERS,
    MAX_PAGES, ITEMS_PER_PAGE, RATE_LIMIT_DELAY,
    REQUEST_TIMEOUT, MAX_RETRIES, EARLY_STOP_PAGES,
)

logger = logging.getLogger(__name__)


@dataclass
class RankResult:
    rank: Optional[int] = None  # None이면 순위권 밖
    title: str = ""
    mall_name: str = ""
    price: int = 0
    link: str = ""
    product_id: str = ""
    total_searched: int = 0  # 탐색한 총 상품 수


def _clean_html(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", text) if text else ""


def _fetch_page(query: str, start: int, sort: str = "sim") -> Optional[Dict]:
    """네이버 쇼핑 API 1페이지 호출 (재시도 포함)"""
    params = {
        "query": query,
        "display": ITEMS_PER_PAGE,
        "start": start,
        "sort": sort,
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                NAVER_SHOP_API_URL,
                headers=NAVER_API_HEADERS,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning(f"Rate limit (429), 2초 대기 후 재시도 ({attempt+1}/{MAX_RETRIES})")
                time.sleep(2)
            else:
                logger.error(f"API 에러 {resp.status_code}: {resp.text[:200]}")
                time.sleep(1)
        except requests.RequestException as e:
            logger.error(f"네트워크 오류: {e}")
            time.sleep(1)
    return None


def _match_item(item: dict, target_type: str, target_value: str) -> bool:
    """상품이 타겟과 매칭되는지 확인"""
    value_lower = target_value.lower()
    if target_type == "mall":
        mall = (item.get("mallName") or "").lower()
        return value_lower in mall
    elif target_type == "title":
        title = _clean_html(item.get("title") or "").lower()
        return value_lower in title
    elif target_type == "both":
        mall = (item.get("mallName") or "").lower()
        title = _clean_html(item.get("title") or "").lower()
        return value_lower in mall or value_lower in title
    return False


def check_rank(keyword: str, target_type: str, target_value: str,
               sort: str = "sim", max_pages: int = None) -> RankResult:
    """
    키워드 검색 결과에서 타겟의 순위를 찾는다.

    Args:
        keyword: 검색 키워드
        target_type: 매칭 유형 ('mall', 'title', 'both')
        target_value: 매칭 값 (스토어명 또는 상품명 키워드)
        sort: 정렬 기준 (sim, date, asc, dsc)
        max_pages: 최대 탐색 페이지 (기본: config 설정)

    Returns:
        RankResult 객체
    """
    if max_pages is None:
        max_pages = MAX_PAGES

    found = False
    pages_since_found = 0
    total_searched = 0
    result = RankResult(rank=None)

    for page in range(max_pages):
        start = page * ITEMS_PER_PAGE + 1
        data = _fetch_page(keyword, start, sort)

        if not data or "items" not in data:
            logger.warning(f"페이지 {page+1} 데이터 없음, 종료")
            break

        items = data["items"]
        if not items:
            break

        for idx, item in enumerate(items):
            rank = start + idx
            total_searched = rank

            if _match_item(item, target_type, target_value):
                if not found:
                    # 첫 번째 매칭만 기록
                    found = True
                    result = RankResult(
                        rank=rank,
                        title=_clean_html(item.get("title", "")),
                        mall_name=item.get("mallName", ""),
                        price=int(item.get("lprice", 0)),
                        link=item.get("link", ""),
                        product_id=item.get("productId", ""),
                    )

        if found:
            pages_since_found += 1
            if pages_since_found >= EARLY_STOP_PAGES:
                break

        # 마지막 페이지가 아니면 rate limit 대기
        if page < max_pages - 1:
            time.sleep(RATE_LIMIT_DELAY)

    result.total_searched = total_searched
    return result


def check_all_keywords(keywords: List[Dict], progress_callback=None) -> List[Dict]:
    """
    전체 키워드 순위 체크.

    Args:
        keywords: DB에서 가져온 키워드 목록
        progress_callback: (current, total, keyword) 콜백

    Returns:
        [{keyword_id, keyword, result: RankResult}, ...]
    """
    results = []
    total = len(keywords)

    for i, kw in enumerate(keywords):
        if progress_callback:
            progress_callback(i, total, kw["keyword"])

        result = check_rank(
            keyword=kw["keyword"],
            target_type=kw["target_type"],
            target_value=kw["target_value"],
            sort=kw.get("sort_type", "sim"),
        )
        results.append({
            "keyword_id": kw["id"],
            "keyword": kw["keyword"],
            "result": result,
        })

        # 키워드 간 추가 대기
        if i < total - 1:
            time.sleep(0.3)

    if progress_callback:
        progress_callback(total, total, "완료")

    return results
