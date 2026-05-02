from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_config(path: Path, config: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        file.write("\n")


def extract_product_id(value: str) -> str:
    text = value.strip()
    match = re.search(r"-p-(\d+)", text)
    if match:
        return match.group(1)
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits


def matches(product: Any, query: str, query_id: str) -> bool:
    if isinstance(product, str):
        return product == query_id or product == query
    if not isinstance(product, dict):
        return False

    product_id = str(product.get("product_id") or "")
    product_url = str(product.get("product_url") or "")
    if query_id and product_id == query_id:
        return True
    if query and product_url == query:
        return True
    if query and query in product_url:
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="config.json içinden ürün siler")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--product", required=True, help="Silinecek ürün linki veya ürün kodu")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    products = config.get("products", [])
    if not isinstance(products, list):
        raise ValueError("config.json içindeki products alanı liste olmalı.")

    query = args.product.strip()
    query_id = extract_product_id(query)
    kept = [product for product in products if not matches(product, query, query_id)]
    removed_count = len(products) - len(kept)

    if removed_count == 0:
        print(f"Eşleşen ürün bulunamadı: {query}")
        return

    config["products"] = kept
    save_config(config_path, config)
    print(f"{removed_count} ürün listeden silindi.")


if __name__ == "__main__":
    main()
