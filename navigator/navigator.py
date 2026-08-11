
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def run_navigator(base_url: str, out_dir: str = "output"):
    """Everything lives here: viewport loop, checkout flow, screenshots,
    bounding boxes, and manifest writing — no helper functions."""

    # Viewport definitions
    viewports = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 390, "height": 844},
    }


    tracked_selectors = {
        "product_card": "[data-testid='product-card']",
        "product_link": "[data-testid='product-card'] a",
        "add_to_cart_btn": "[data-testid='add-to-cart-btn']",
        "cart_icon": "[data-testid='cart-icon']",
        "checkout_btn": "[data-testid='checkout-btn']",
        "place_order_btn": "[data-testid='place-order-btn']",
    }

    output_dir = Path(out_dir)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = []

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for viewport_name, size in viewports.items():
            print(f"Running flow at viewport: {viewport_name} ({size['width']}x{size['height']})")
            context = browser.new_context(viewport=size)
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.accept())

            try:
               
                steps = [
                    ("01_home", lambda: (
                        page.goto(base_url, wait_until="networkidle"),
                        page.wait_for_selector(tracked_selectors["product_link"], state="visible"),
                    )),
                    ("02_product", lambda: (
                        page.click(tracked_selectors["product_link"]),
                        page.wait_for_load_state("networkidle"),
                        page.wait_for_selector(tracked_selectors["add_to_cart_btn"], state="visible"),
                    )),
                    ("03_cart", lambda: (
                        page.locator(tracked_selectors["add_to_cart_btn"]).scroll_into_view_if_needed(),
                        page.locator(tracked_selectors["add_to_cart_btn"]).click(force=True),
                        page.wait_for_selector(tracked_selectors["cart_icon"], state="visible"),
                        page.click(tracked_selectors["cart_icon"], force=True),
                        page.wait_for_load_state("networkidle"),
                    )),
                    ("04_checkout", lambda: (
                        page.wait_for_selector(tracked_selectors["checkout_btn"], state="visible"),
                        page.locator(tracked_selectors["checkout_btn"]).click(force=True),
                        page.wait_for_load_state("networkidle"),
                    )),
                ]

                for step_name, action in steps:
                    # Perform the step's action
                    action()

                    # Screenshot
                    shot_path = run_dir / f"{viewport_name}_{step_name}.png"
                    page.screenshot(path=str(shot_path), full_page=True)

                    # Bounding boxes for every tracked selector, inline
                    boxes = {}
                    for name, selector in tracked_selectors.items():
                        el = page.query_selector(selector)
                        boxes[name] = el.bounding_box() if el is not None else None

                    # Record into manifest
                    manifest.append(
                        {
                            "viewport": viewport_name,
                            "step": step_name,
                            "url": page.url,
                            "screenshot": str(shot_path.relative_to(output_dir)),
                            "bounding_boxes": boxes,
                            "timestamp": time.time(),
                        }
                    )
                    print(f"  [{viewport_name}] captured '{step_name}' -> {shot_path.name}")

            except Exception as e:
                print(f"  ERROR at viewport {viewport_name}: {e}")
                manifest.append({"viewport": viewport_name, "error": str(e)})
            finally:
                context.close()

        browser.close()

    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. Manifest written to {manifest_path}")
    return manifest_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run checkout flow navigator across viewports")
    parser.add_argument("--base-url", required=True, help="Base URL of the deployed mock app")
    parser.add_argument("--out", default="output", help="Output directory")
    args = parser.parse_args()

    run_navigator(args.base_url, args.out)
