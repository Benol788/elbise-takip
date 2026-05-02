from __future__ import annotations

import argparse
import json
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


def product_exists(products: list[Any], product_id: str) -> bool:
    for product in products:
        if isinstance(product, str) and product == product_id:
            return True
        if isinstance(product, dict) and str(product.get("product_id")) == product_id:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="config.json içine Trendyol ürün kodu ekler")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--product-id", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    products = config.setdefault("products", [])
    if not isinstance(products, list):
        raise ValueError("config.json içindeki products alanı liste olmalı.")

    product_id = normalize_product_id(args.product_id)
    if product_exists(products, product_id):
        print(f"{product_id} zaten takip listesinde.")
        return

    products.append(product_id)
    save_config(config_path, config)
    print(f"{product_id} takip listesine eklendi.")


if __name__ == "__main__":
    main()
