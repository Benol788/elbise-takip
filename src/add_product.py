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


def normalize_product_id(product_id: str) -> str:
    digits = "".join(ch for ch in product_id.strip() if ch.isdigit())
    if not digits:
        raise ValueError("Ürün kodu rakam içermiyor.")
    return digits


def product_id_from_link_or_code(value: str) -> str:
    text = value.strip()
    match = re.search(r"-p-(\d+)", text)
    if match:
        return match.group(1)
    return normalize_product_id(text)


def optional_price(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(float(value.replace(",", ".")))


def product_exists(products: list[Any], product_id: str) -> bool:
    for product in products:
        if isinstance(product, str) and product == product_id:
            return True
        if isinstance(product, dict) and str(product.get("product_id")) == product_id:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="config.json içine Trendyol ürünü ekler")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--product", required=True, help="Trendyol ürün linki veya ürün kodu")
    parser.add_argument("--min-price")
    parser.add_argument("--max-price")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    products = config.setdefault("products", [])
    if not isinstance(products, list):
        raise ValueError("config.json içindeki products alanı liste olmalı.")

    product_id = product_id_from_link_or_code(args.product)
    if product_exists(products, product_id):
        print(f"{product_id} zaten takip listesinde.")
        return

    min_price = optional_price(args.min_price)
    max_price = optional_price(args.max_price)
    if min_price is not None and max_price is not None:
        product: Any = {
            "product_url": args.product.strip() if args.product.strip().startswith("http") else "",
            "product_id": product_id,
            "target_price_min": min_price,
            "target_price_max": max_price,
        }
    else:
        product = product_id

    products.append(product)
    save_config(config_path, config)
    print(f"{product_id} takip listesine eklendi.")


if __name__ == "__main__":
    main()
