import argparse
import json
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def run_navigator(base_url: str, out_dir: str = "output"):
    """Everything lives here: viewport loop, checkout flow, screenshots,
    bounding boxes, and manifest writing — no helper functions.

    Selectors and flow are tuned for the Trailhead mock store:
      index.html (product cards + inline add-to-cart)
        -> cart.html (via nav "Cart" link)
        -> checkout.html (via "Proceed to checkout")
        -> place order (planted visual bug lives on .order-action-panel,
           clips "Place order" under 480px — make sure the mobile
           viewport actually reaches and screenshots this step).
    """

    # Viewport definitions
    viewports = {
        "desktop": {"width": 1440, "height": 900},
        "tablet": {"width": 768, "height": 1024},
        "mobile": {"width": 390, "height": 844},
    }

    # Trailhead has no data-testid attributes; these map to its real
    # classes / structure instead.
    tracked_selectors = {
        "product_card": ".card",
        "add_to_cart_btn": ".card .btn-primary",          # first product's button
        "cart_icon": "a.cart-link",                        # header nav, always present
        "checkout_btn": ".summary-card a.btn-primary",     # "Proceed to checkout" on cart.html
        "place_order_btn": "#checkout-form button[type='submit']",
    }

    output_dir = Path(out_dir)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = []

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for viewport_name, size in viewports.items():
            logger.info(f"Running flow at viewport: {viewport_name} ({size['width']}x{size['height']})")
            context = browser.new_context(viewport=size)
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.accept())

            try:
                steps = [
                    ("01_home", lambda: (
                        page.goto(base_url, wait_until="networkidle"),
                        page.evaluate("localStorage.clear()"),  # deterministic cart state per run
                        page.reload(wait_until="networkidle"),
                        page.wait_for_selector(tracked_selectors["product_card"], state="visible"),
                    )),
                    ("02_add_to_cart", lambda: (
                        page.locator(tracked_selectors["add_to_cart_btn"]).first.scroll_into_view_if_needed(),
                        page.locator(tracked_selectors["add_to_cart_btn"]).first.click(force=True),
                        page.wait_for_timeout(500),  # let the toast/cart-count update settle
                    )),
                    ("03_cart", lambda: (
                        page.click(tracked_selectors["cart_icon"], force=True),
                        page.wait_for_load_state("networkidle"),
                        page.wait_for_selector(tracked_selectors["checkout_btn"], state="visible"),
                    )),
                    ("04_checkout", lambda: (
                        page.locator(tracked_selectors["checkout_btn"]).click(force=True),
                        page.wait_for_load_state("networkidle"),
                        page.wait_for_selector(tracked_selectors["place_order_btn"], state="visible"),
                    )),
                    ("05_place_order", lambda: (
                        page.locator(tracked_selectors["place_order_btn"]).scroll_into_view_if_needed(),
                        # deliberately no click here yet — this step exists to
                        # capture the checkout screen (incl. the planted
                        # .order-action-panel clipping bug) BEFORE submitting,
                        # since placeOrder() clears the cart and redirects.
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
                    logger.info(f"  [{viewport_name}] captured '{step_name}' -> {shot_path.name}")

            except Exception as e:
                logger.error(f"  ERROR at viewport {viewport_name}: {e}")
                manifest.append({"viewport": viewport_name, "error": str(e)})
            finally:
                context.close()

        browser.close()

    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Done. Manifest written to {manifest_path}")
    return manifest_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Run checkout flow navigator across viewports")
    parser.add_argument("--base-url", required=True, help="Base URL of the deployed mock app")
    parser.add_argument("--out", default="output", help="Output directory")
    args = parser.parse_args()

    run_navigator(args.base_url, args.out)