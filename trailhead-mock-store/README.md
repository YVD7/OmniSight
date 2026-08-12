# Trailhead — Mock E-commerce App (OmniSight test fixture)

A small static storefront (product list → cart → checkout) built as the
Week 0 test fixture from the OmniSight execution plan. Pure HTML/CSS/JS,
no build step, no backend — cart state lives in `localStorage`.

## Files
- `index.html` — product listing (6 items)
- `cart.html` — cart with quantity controls and order summary
- `checkout.html` — shipping form + **planted visual bug**
- `styles.css` — shared styles
- `app.js` — cart logic (add/remove/qty, totals, toast)

## The planted bug
`styles.css` has a clearly-marked block around `.order-action-panel`
(the wrapper around the "Place order" button on the checkout page):

```css
.order-action-panel {
  overflow: hidden;
  max-height: 64px;
}
```

At desktop widths the button and "Save details" checkbox fit on one row,
so nothing looks wrong. Under 480px the row wraps onto two lines, but the
`max-height: 64px` + `overflow: hidden` clips the second line — so the
"Place order" button is partially or fully cut off on mobile, even though
it's still present in the DOM (a Selenium/Cypress `find_element` assertion
would still pass). This is exactly the class of bug OmniSight is meant to
catch visually and patch (e.g. by changing to `overflow: visible` and
removing the fixed `max-height`, or switching the row to `flex-wrap: wrap`
with `height: auto`).

To see it: open `checkout.html`, open dev tools, switch to a mobile
viewport (e.g. iPhone SE / 375px), and look at the bottom of the form.

## Running locally
No build tools needed:

```bash
cd mock-app
python3 -m http.server 8080
# visit http://localhost:8080
```

## Deployment (free options)
See the accompanying deployment guide for step-by-step instructions for
Netlify, Vercel, and GitHub Pages.
