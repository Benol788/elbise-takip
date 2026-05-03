from __future__ import annotations

import argparse
import json
import html as html_lib
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


PROXY_BASE_URL = "https://urun-okuyucu.darendelikerim.workers.dev"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.kitapyurdu.com/",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass(frozen=True)
class ProductSnapshot:
    title: str
    price: float | None
    currency: str
    matching_sizes: list[str]
    stock_known: bool
    overall_stock: bool | None
    source: str


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def request_text(url: str, timeout: int = 25) -> tuple[str, str]:
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return body, response.geturl()


def request_json(url: str, headers: dict[str, str], timeout: int = 25) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def supabase_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def supabase_update_product(config: dict[str, Any], payload: dict[str, Any]) -> None:
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    row_id = str(config.get("_supabase_id", "")).strip()
    if not supabase_url or not supabase_key or not row_id:
        return

    query = urlencode({"id": f"eq.{row_id}"})
    request = Request(
        f"{supabase_url}/rest/v1/products?{query}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=supabase_headers({"Prefer": "return=minimal"}),
        method="PATCH",
    )
    with urlopen(request, timeout=25) as response:
        response.read()
        
def supabase_products() -> list[dict[str, Any]]:
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_key:
        return []

    query = urlencode({"select": "*", "order": "created_at.asc"})
    rows = request_json(
        f"{supabase_url}/rest/v1/products?{query}",
        supabase_headers(),
   )

    products = []
    for row in rows:
        product: dict[str, Any] = {
            "_supabase_id": row.get("id") or "",
            "name": row.get("name") or f"Ürün {row.get('product_id') or row.get('id')}",
            "product_url": row.get("product_url") or "",
            "product_id": row.get("product_id") or "",
            "target_price_min": float(row.get("target_price_min") or 0),
            "target_price_max": float(row.get("target_price_max") or 1_000_000),
            "target_sizes": row.get("target_sizes") or [],
            "color_keywords": row.get("color_keywords") or [],
            "is_paused": bool(row.get("is_paused")),
            "alert_mode": row.get("alert_mode") or "price_stock",
        }
        products.append(product)
    return products


def proxied_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "kitapyurdu.com" in host:
        return f"{PROXY_BASE_URL}/?url={quote(url, safe='')}"
    return url

def candidate_urls(config: dict[str, Any]) -> list[str]:
    product_id = str(config.get("product_id", "")).strip()
    urls = []
    if product_id:
        urls.extend(
            [
                (
                    "https://public.trendyol.com/discovery-web-productgw-service/"
                    f"api/productDetail/{quote(product_id)}?storefrontId=1&culture=tr-TR"
                    "&linearVariants=true&isLegalRequirementConfirmed=false"
                ),
                (
                    "https://apigw.trendyol.com/discovery-web-productgw-service/"
                    f"api/productDetail/{quote(product_id)}?storefrontId=1&culture=tr-TR"
                    "&linearVariants=true&isLegalRequirementConfirmed=false"
                ),
            ]
        )
    product_url = str(config.get("product_url", "")).strip()
    if product_url:
        urls.append(product_url)
    return urls


def product_configs(config: dict[str, Any]) -> list[dict[str, Any]]:
    remote_products = supabase_products()
    products = remote_products or config.get("products")
    if not isinstance(products, list):
        return [config]

    shared_keys = {
        "target_price_min",
        "target_price_max",
        "target_sizes",
        "color_keywords",
        "is_paused",
        "alert_mode",
        "ntfy_topic",
        "state_file",
    }
    shared = {key: config[key] for key in shared_keys if key in config}
    merged = []
    for index, product in enumerate(products, start=1):
        if isinstance(product, (str, int)):
            item = {**shared, "product_id": str(product)}
        elif isinstance(product, dict):
            item = {**shared, **product}
        else:
            continue
        item.setdefault("name", f"Ürün {item.get('product_id', index)}")
        item.setdefault("target_price_min", 0)
        item.setdefault("target_price_max", 1_000_000)
        item.setdefault("target_sizes", [])
        item.setdefault("color_keywords", [])
        item.setdefault("is_paused", False)
        item.setdefault("alert_mode", "price_stock")
        merged.append(item)
    return merged


def parse_payload(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)

    json_markers = [
        r"<script[^>]+id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>",
        r"window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});",
        r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
    ]
    for pattern in json_markers:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(1))

    datalayer_match = re.search(
        r"PuzzleJs\.emit\([^;]*?__PRODUCT_DETAIL__DATALAYER[^,]*,\s*({.*?})\);",
        text,
        flags=re.DOTALL,
    )
    if datalayer_match:
        return json.loads(datalayer_match.group(1))

    return {"html": text}


def walk(value: Any) -> list[Any]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(walk(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(walk(child))
    return items


def normalize_text(value: Any) -> str:
    return str(value or "").casefold().strip()


def find_title(payload: Any) -> str:
    title_keys = {"name", "title", "productname", "producttitle", "productpname"}
    for item in walk(payload):
        if isinstance(item, dict):
            for key, value in item.items():
                if normalize_text(key).replace("_", "") in title_keys and isinstance(value, str):
                    clean = value.strip()
                    if len(clean) > 5:
                        return clean
    return "Takip edilen elbise"


def find_currency(payload: Any) -> str:
    for item in walk(payload):
        if isinstance(item, dict):
            for key, value in item.items():
                if "currency" in normalize_text(key) and isinstance(value, str):
                    return value
    return "TL"


def find_overall_stock(payload: Any) -> bool | None:
    quantity_seen: bool | None = None
    for item in walk(payload):
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            key_text = normalize_text(key).replace("_", "")
            value_text = normalize_text(value).replace(" ", "")
            if key_text.endswith("status") or key_text in {"availability"}:
                if value_text in {"stockout", "soldout", "outofstock", "tükendi", "stoktayok"}:
                    return False
                if value_text in {"instock", "onsale", "available", "stoktavar"}:
                    return True
            if key_text in {"productquantity", "quantity", "stockquantity"}:
                try:
                    quantity_seen = float(value) > 0
                except (TypeError, ValueError):
                    continue
    return quantity_seen


def find_price(payload: Any) -> float | None:
    price_values: list[float] = []
    price_key_hints = ("price", "amount", "selling", "discounted")

    for item in walk(payload):
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            key_text = normalize_text(key)
            if not any(hint in key_text for hint in price_key_hints):
                continue
            if isinstance(value, (int, float)) and 10 <= float(value) <= 1_000_000:
                price_values.append(float(value))
            elif isinstance(value, str):
                numeric = parse_price_string(value)
                if numeric is not None:
                    price_values.append(numeric)
            elif isinstance(value, dict):
                for nested_key in ("value", "amount", "text"):
                    numeric = value.get(nested_key)
                    if isinstance(numeric, (int, float)) and 10 <= float(numeric) <= 1_000_000:
                        price_values.append(float(numeric))
                    elif isinstance(numeric, str):
                        parsed = parse_price_string(numeric)
                        if parsed is not None:
                            price_values.append(parsed)

    if not price_values:
        return None
    return min(price_values)


def parse_price_string(value: str) -> float | None:
    match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)", value)
    if not match:
        return None
    number = match.group(1).replace(".", "").replace(",", ".")
    try:
        parsed = float(number)
    except ValueError:
        return None
    if 10 <= parsed <= 1_000_000:
        return parsed
    return None


def stock_flag(item: dict[str, Any]) -> bool | None:
    false_words = {"false", "0", "outofstock", "soldout", "tükendi", "stokta yok"}
    true_words = {"true", "1", "instock", "available", "sellable", "stokta var"}
    stock_keys = (
        "stock",
        "available",
        "availability",
        "sellable",
        "quantity",
        "inventory",
        "isbuyable",
        "issellable",
    )

    for key, value in item.items():
        key_text = normalize_text(key).replace("_", "")
        if not any(hint in key_text for hint in stock_keys):
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            value_text = normalize_text(value).replace(" ", "")
            if value_text in true_words:
                return True
            if value_text in false_words:
                return False
    return None


def find_matching_sizes(payload: Any, target_sizes: list[str]) -> tuple[list[str], bool]:
    wanted = {normalize_text(size): size for size in target_sizes}
    in_stock: set[str] = set()
    seen_without_stock: set[str] = set()

    for item in walk(payload):
        if not isinstance(item, dict):
            continue
        blob = normalize_text(json.dumps(item, ensure_ascii=False))
        for wanted_key, original_size in wanted.items():
            if not re.search(rf"(^|[^a-z0-9]){re.escape(wanted_key)}([^a-z0-9]|$)", blob):
                continue
            flag = stock_flag(item)
            if flag is True:
                in_stock.add(original_size)
            elif flag is None:
                seen_without_stock.add(original_size)

    if in_stock:
        return sorted(in_stock), True
    if seen_without_stock:
        return sorted(seen_without_stock), False
    return [], False


def color_matches(payload: Any, color_keywords: list[str]) -> bool:
    if not color_keywords:
        return True
    text = normalize_text(json.dumps(payload, ensure_ascii=False))
    return any(normalize_text(keyword) in text for keyword in color_keywords)


def plain_html_text(html: str) -> str:  
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#8378;", "TL")
    text = text.replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


def meta_content(html: str, name: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(name)}["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def kitapyurdu_snapshot(html: str, final_url: str) -> ProductSnapshot:
    text = plain_html_text(html)
    print(f"Kitapyurdu metin örneği: {text[:500]}")
    print(f"Kitapyurdu fiyat adayları: {re.findall(r'[0-9]{1,3}(?:\\.[0-9]{3})*,[0-9]{2}', text)[:20]}")
    title = meta_content(html, "og:title") or "Kitapyurdu ürünü"

    price = None
    price_patterns = [
        r"Kitapyurdu\s*Fiyat.{0,160}?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
        r"Kitapyurdu.{0,220}?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
        r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*TL",
    ]

    for pattern in price_patterns:
        price_match = re.search(pattern, text, flags=re.IGNORECASE)
        if price_match:
            price = parse_price_string(price_match.group(1))
            if price is not None:
                break

    if price is None:
        all_prices = [
            parse_price_string(match)
            for match in re.findall(r"[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}", text)
        ]
        all_prices = [value for value in all_prices if value is not None]
        if all_prices:
            price = min(all_prices)

    normalized = normalize_text(text)
    false_words = ("stokta yok", "tükendi", "temin edilemiyor", "satışta değildir")
    true_words = ("sepete ekle", "kargoya verilir", "saatte kargoda", "stokta")

    if any(word in normalized for word in false_words):
        overall_stock = False
    elif any(word in normalized for word in true_words):
        overall_stock = True
    else:
        overall_stock = None

    return ProductSnapshot(
        title=title,
        price=price,
        currency="TL",
        matching_sizes=[],
        stock_known=True,
        overall_stock=overall_stock,
        source=final_url,
    )

def hepsiburada_snapshot(html: str, final_url: str) -> ProductSnapshot:
    text = plain_html_text(html)
    title = meta_content(html, "og:title") or "Hepsiburada ürünü"

    price = None
    price_patterns = [
        r'"price"\s*:\s*"?([0-9][0-9.,]*)"?',
        r'"finalPrice"\s*:\s*"?([0-9][0-9.,]*)"?',
        r'"discountedPrice"\s*:\s*"?([0-9][0-9.,]*)"?',
        r'"amount"\s*:\s*"?([0-9][0-9.,]*)"?',
        r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*TL",
    ]

    for pattern in price_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            price = parse_price_string(match.group(1))
            if price is not None:
                break

    normalized = normalize_text(text)
    false_words = ("stokta yok", "tükendi", "satışta değildir", "ürün geçici olarak temin edilememektedir")
    true_words = ("sepete ekle", "stok adedi", "500 adetten az", "kargoya verilir")

    if any(word in normalized for word in false_words):
        overall_stock = False
    elif any(word in normalized for word in true_words):
        overall_stock = True
    else:
        overall_stock = None

    return ProductSnapshot(
        title=title,
        price=price,
        currency="TL",
        matching_sizes=[],
        stock_known=True,
        overall_stock=overall_stock,
        source=final_url,
    )

def fetch_snapshot(config: dict[str, Any]) -> ProductSnapshot:
    last_error: Exception | None = None
    for url in candidate_urls(config):
        try:
            request_url = proxied_url(url)
            print(f"Okuma adresi: {request_url}")
            text, final_url = request_text(request_url)
            host = urlparse(url).netloc.lower()
            if "kitapyurdu.com" in host:
                return kitapyurdu_snapshot(text, url)
            if "hepsiburada.com" in host:
                return hepsiburada_snapshot(text, final_url)
            payload = parse_payload(text)
            if not color_matches(payload, list(config.get("color_keywords", []))):
                continue
            matching_sizes, stock_known = find_matching_sizes(payload, list(config.get("target_sizes", [])))
            return ProductSnapshot(
                title=find_title(payload),
                price=find_price(payload),
                currency=find_currency(payload),
                matching_sizes=matching_sizes,
                stock_known=stock_known,
                overall_stock=find_overall_stock(payload),
                source=final_url,
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
    raise RuntimeError(f"Ürün bilgisi alınamadı: {last_error}")


def should_alert(snapshot: ProductSnapshot, config: dict[str, Any]) -> tuple[bool, str]:
    alert_mode = str(config.get("alert_mode") or "price_stock")
    min_price = float(config["target_price_min"])
    max_price = float(config["target_price_max"])
    target_sizes = list(config.get("target_sizes", []))

    price_ok = snapshot.price is not None and min_price <= snapshot.price <= max_price

    def size_status() -> tuple[bool, str | None]:
        if not target_sizes:
            return True, None
        if not snapshot.matching_sizes:
            return False, f"{'/'.join(target_sizes)} beden bilgisi stokta görünmüyor."
        if not snapshot.stock_known:
            return True, "Hedef beden görüldü ama stok bayrağı net değil."
        return True, None

    if alert_mode == "price":
        if snapshot.price is None:
            return False, "Fiyat okunamadı."
        if not price_ok:
            return False, f"Fiyat aralık dışında: {snapshot.price:g} {snapshot.currency}."
        return True, "Fiyat hedef aralıkta görünüyor."

    if alert_mode == "stock":
        size_ok, size_reason = size_status()
        if not size_ok:
            return False, size_reason or "Hedef beden stokta görünmüyor."
        if target_sizes:
            if size_reason:
                return True, size_reason
            return True, "Hedef beden stokta görünüyor."
        if snapshot.overall_stock is True:
            return True, "Ürün stokta görünüyor."
        if snapshot.overall_stock is False:
            return False, "Ürün stokta değil."
        return False, "Stok durumu net okunamadı."

    if snapshot.price is None:
        return False, "Fiyat okunamadı."
    if snapshot.overall_stock is False:
        return False, "Fiyat uygun olabilir, ancak ürün genel durumu stokta değil."
    if not price_ok:
        return False, f"Fiyat aralık dışında: {snapshot.price:g} {snapshot.currency}."

    size_ok, size_reason = size_status()
    if not size_ok:
        return False, size_reason or "Hedef beden stokta görünmüyor."
    if size_reason:
        return True, f"Fiyat uygun; {size_reason}"
    if not target_sizes:
        return True, "Fiyat uygun ve ürün stokta görünüyor."
    return True, "Fiyat uygun ve hedef beden stokta görünüyor."

def send_ntfy(topic: str, title: str, message: str, click_url: str) -> None:
    url = f"https://ntfy.sh/{quote(topic)}"
    request = Request(
        url,
        data=message.encode("utf-8"),
        method="POST",
        headers={
            "Title": title,
            "Tags": "dress,shopping",
            "Click": click_url,
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    with urlopen(request, timeout=20) as response:
        response.read()


def signature(snapshot: ProductSnapshot) -> str:
    sizes = ",".join(snapshot.matching_sizes)
    price = "unknown" if snapshot.price is None else f"{snapshot.price:.2f}"
    return f"{price}|{sizes}|{snapshot.stock_known}|{snapshot.overall_stock}"


def product_key(config: dict[str, Any]) -> str:
    return str(config.get("product_id") or config.get("product_url") or config.get("name") or "default")


def product_link(config: dict[str, Any], snapshot: ProductSnapshot | None = None) -> str:
    product_url = str(config.get("product_url", "")).strip()
    if product_url:
        return product_url
    if snapshot and snapshot.source and "/api/" not in snapshot.source:
        return snapshot.source
    product_id = str(config.get("product_id", "")).strip()
    if product_id:
        return f"https://www.trendyol.com/sr?q={quote(product_id)}"
    return "https://www.trendyol.com"


def run_product_once(
    product_config: dict[str, Any],
    app_config: dict[str, Any],
    config_path: Path,
    state: dict[str, Any],
    force_notify: bool = False,
) -> ProductSnapshot:
    snapshot = fetch_snapshot(product_config)
    name = str(product_config.get("name") or snapshot.title)
    should_send, reason = should_alert(snapshot, product_config)

    current_signature = f"{signature(snapshot)}|{product_config.get('alert_mode', 'price_stock')}"
    key = product_key(product_config)
    product_state = state.setdefault("products", {}).setdefault(key, {})
    already_sent = product_state.get("last_alert_signature") == current_signature

    print(f"Ürün: {name}")
    print(f"Başlık: {snapshot.title}")
    print(f"Fiyat: {snapshot.price if snapshot.price is not None else 'okunamadı'} {snapshot.currency}")
    print(f"Eşleşen bedenler: {', '.join(snapshot.matching_sizes) or 'yok'}")
    print(f"Genel stok: {snapshot.overall_stock if snapshot.overall_stock is not None else 'bilinmiyor'}")
    print(f"Kaynak: {snapshot.source}")
    print(f"Durum: {reason}")
    supabase_update_product(
        product_config,
        {
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "last_price": snapshot.price,
            "last_currency": snapshot.currency,
            "last_stock_status": (
                "var"
                if snapshot.overall_stock is True
                else "yok"
                if snapshot.overall_stock is False
                else "bilinmiyor"
            ),
            "last_matching_sizes": snapshot.matching_sizes,
            "last_status": reason,
            "last_source": snapshot.source,
        },
    )

    if should_send and (force_notify or not already_sent):
        link = product_link(product_config, snapshot)
        size_text = ", ".join(snapshot.matching_sizes) or "beden filtresi yok"
        message = (
            f"{snapshot.title}\n"
            f"Fiyat: {snapshot.price:g} {snapshot.currency}\n"
            f"Beden: {size_text}\n"
            f"{reason}\n"
            f"{link}"
        )
        send_ntfy(str(product_config["ntfy_topic"]), "Elbise alarmi", message, link)
        product_state["last_alert_signature"] = current_signature
        product_state["last_alert_at"] = int(time.time())
        print("Bildirim gönderildi.")
    elif should_send:
        print("Koşullar uygun, ancak bu durum için bildirim zaten gönderilmiş.")

    return snapshot


def run_once(config: dict[str, Any], config_path: Path, force_notify: bool = False) -> list[ProductSnapshot]:
    state_path = (config_path.parent / config.get("state_file", "data/state.json")).resolve()
    state = load_json(state_path) if state_path.exists() else {}
    snapshots = []
    for index, product_config in enumerate(product_configs(config), start=1):
        if index > 1:
            print("")

        if product_config.get("is_paused"):
            name = product_config.get("name") or product_config.get("product_id") or product_config.get("product_url")
            print(f"Ürün duraklatıldı, kontrol atlandı: {name}")
            continue

        try:
            snapshots.append(run_product_once(product_config, config, config_path, state, force_notify))
            
        except Exception as exc:
            name = product_config.get("name") or product_config.get("product_id") or product_config.get("product_url")
            print(f"Ürün kontrol edilemedi: {name}")
            print(f"Hata: {exc}")
            supabase_update_product(
                product_config,
                {
                    "last_checked_at": datetime.now(timezone.utc).isoformat(),
                    "last_status": f"Hata: {exc}",
                    "last_stock_status": "bilinmiyor",
                },
            )

    save_json(state_path, state)
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Elbise fiyat/stok izleyici")
    parser.add_argument("--config", default="config.json", help="Config JSON dosyası")
    parser.add_argument("--once", action="store_true", help="Tek kontrol yap ve çık")
    parser.add_argument("--test-notify", action="store_true", help="Telefona test bildirimi gönder")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_json(config_path)
    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if ntfy_topic:
        config["ntfy_topic"] = ntfy_topic

    if args.test_notify:
        send_ntfy(
            str(config["ntfy_topic"]),
            "Elbise alarmi test",
            "Bildirim kurulumu çalışıyor.",
            str(config.get("product_url") or "https://www.trendyol.com"),
        )
        print("Test bildirimi gönderildi.")
        return

    while True:
        try:
            run_once(config, config_path)
        except Exception as exc:
            print(f"Hata: {exc}")
        if args.once:
            break
        time.sleep(int(config.get("check_interval_seconds", 600)))


if __name__ == "__main__":
    main()
