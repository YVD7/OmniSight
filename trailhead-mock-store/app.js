// ---- Trailhead mock-store cart logic (localStorage-backed) ----

const PRODUCTS = [
  { id: "p1", name: "Ridgeline 40L Pack", tag: "Backpacks", price: 189, icon: "🎒", color: "#e7ded0" },
  { id: "p2", name: "Alpine 2P Tent", tag: "Shelter", price: 249, icon: "⛺", color: "#dde7de" },
  { id: "p3", name: "Ember Down Sleeping Bag", tag: "Sleep", price: 159, icon: "🛏️", color: "#efe0d6" },
  { id: "p4", name: "Basecamp Stove Kit", tag: "Cooking", price: 79, icon: "🔥", color: "#f1e3cf" },
  { id: "p5", name: "Clearflow Water Filter", tag: "Hydration", price: 45, icon: "💧", color: "#dbe8ec" },
  { id: "p6", name: "Summit Trail Boots", tag: "Footwear", price: 139, icon: "🥾", color: "#e6ded2" },
];

function getCart() {
  try { return JSON.parse(localStorage.getItem("trailhead_cart")) || {}; }
  catch (e) { return {}; }
}

function saveCart(cart) {
  localStorage.setItem("trailhead_cart", JSON.stringify(cart));
  updateCartCount();
}

function addToCart(id) {
  const cart = getCart();
  cart[id] = (cart[id] || 0) + 1;
  saveCart(cart);
  showToast("Added to cart");
}

function setQty(id, qty) {
  const cart = getCart();
  if (qty <= 0) { delete cart[id]; }
  else { cart[id] = qty; }
  saveCart(cart);
  if (typeof renderCart === "function") renderCart();
}

function removeFromCart(id) {
  setQty(id, 0);
}

function cartCount() {
  const cart = getCart();
  return Object.values(cart).reduce((a, b) => a + b, 0);
}

function cartTotal() {
  const cart = getCart();
  let total = 0;
  Object.entries(cart).forEach(([id, qty]) => {
    const p = PRODUCTS.find(p => p.id === id);
    if (p) total += p.price * qty;
  });
  return total;
}

function updateCartCount() {
  const el = document.getElementById("cart-count");
  if (el) el.textContent = cartCount();
}

function showToast(msg) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
}

document.addEventListener("DOMContentLoaded", updateCartCount);
