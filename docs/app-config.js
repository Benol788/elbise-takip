window.APP_CONFIG = {
  supabaseUrl: "https://jbwsmwzegsvqnmimslkp.supabase.co",
  supabaseAnonKey: "sb_publishable_OShnnNwc2O16QggB2nVLaA_D3juCxrb"
};

(() => {
  const OWNERS = ["Kerim", "Selin"];
  const DEFAULT_OWNER = "Kerim";

  const NTFY_TOPICS = {
    Kerim: "abdul-elbise-660272836-20260502",
    Selin: "selin-elbise-20260503-9c7f2a"
  };

  const CATEGORIES = {
    "Diğer": "other",
    "Elbise": "dress",
    "Kitap": "book",
    "Elektronik": "tech",
    "Kozmetik": "beauty"
  };

  const originalFetch = window.fetch.bind(window);
  let allRows = [];
  let applyTimer = null;

  function currentOwner() {
    const saved = localStorage.getItem("activeOwner");
    return OWNERS.includes(saved) ? saved : DEFAULT_OWNER;
  }

  function otherOwner() {
    return currentOwner() === "Kerim" ? "Selin" : "Kerim";
  }

  function rowOwner(row) {
    return OWNERS.includes(row?.owner) ? row.owner : DEFAULT_OWNER;
  }

  function productsEndpoint(query = "") {
    const raw = window.APP_CONFIG.supabaseUrl.replace(/\/$/, "");
    const base = raw.includes("/rest/v1") ? raw : `${raw}/rest/v1`;
    return `${base}/products${query}`;
  }

  function supabaseHeaders(extra = {}) {
    const key = window.APP_CONFIG.supabaseAnonKey;
    return {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      ...extra
    };
  }

  function isProductsApi(url) {
    const text = String(url || "");
    return text.includes(".supabase.co") && text.includes("/products");
  }

  function fieldValue(selector, fallback = "") {
    return document.querySelector(selector)?.value?.trim() || fallback;
  }

  function isProductSavePayload(payload) {
    return (
      Object.prototype.hasOwnProperty.call(payload, "product_id") ||
      Object.prototype.hasOwnProperty.call(payload, "product_url") ||
      Object.prototype.hasOwnProperty.call(payload, "target_price_min") ||
      Object.prototype.hasOwnProperty.call(payload, "target_price_max")
    );
  }

  function rowId(card) {
    return (
      card.querySelector("button[data-id]")?.dataset.id ||
      card.querySelector("button[data-edit-id]")?.dataset.editId ||
      card.querySelector("button[data-favorite-id]")?.dataset.favoriteId ||
      card.querySelector("button[data-pause-id]")?.dataset.pauseId
    );
  }

  function findRow(id) {
    return allRows.find((row) => row.id === id);
  }

  function visibleRows() {
    const owner = currentOwner();
    return allRows.filter((row) => rowOwner(row) === owner);
  }

  function scheduleApply(delay = 80) {
    clearTimeout(applyTimer);
    applyTimer = setTimeout(applyProductsView, delay);
  }

  window.__ACTIVE_OWNER = currentOwner();

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init?.method || input?.method || "GET").toUpperCase();
    let nextInit = init;

    if (isProductsApi(url) && (method === "POST" || method === "PATCH") && init?.body) {
      try {
        const payload = JSON.parse(init.body);

        if (isProductSavePayload(payload)) {
          payload.owner = fieldValue("#owner", currentOwner());
          payload.note = fieldValue("#note");
          payload.category = fieldValue("#category", "Diğer");
          nextInit = { ...init, body: JSON.stringify(payload) };
        }
      } catch {}
    }

    const response = await originalFetch(input, nextInit);

    if (isProductsApi(url) && method === "GET" && url.includes("select=") && response.ok) {
     try {
       const rows = await response.clone().json();
       allRows = Array.isArray(rows) ? rows : [];

       const owner = currentOwner();
       const filteredRows = allRows.filter((row) => rowOwner(row) === owner);

       setTimeout(() => {
         scheduleApply(80);
       }, 80);

       return new Response(JSON.stringify(filteredRows), {
         status: response.status,
         statusText: response.statusText,
         headers: { "Content-Type": "application/json" }
       });
     } catch {}
  }

    return response;
  };

  function setCurrentOwner(owner) {
    const next = OWNERS.includes(owner) ? owner : DEFAULT_OWNER;
    window.__ACTIVE_OWNER = next;
    localStorage.setItem("activeOwner", next);

    document.querySelectorAll("[data-owner-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.ownerTab === next);
    });

    const ownerSelect = document.querySelector("#owner");
    if (ownerSelect) ownerSelect.value = next;

    document.querySelector("#refresh")?.click();
    scheduleApply(80);
  }

  async function sendTestNotification(owner, button) {
    const topic = NTFY_TOPICS[owner];
    if (!topic) {
      alert("Bildirim kanalı bulunamadı.");
      return;
    }

    const oldText = button.textContent;
    button.disabled = true;
    button.textContent = "Gönderiliyor";

    const params = new URLSearchParams({
      title: `${owner} test bildirimi`,
      message: `${owner} için test bildirimi gönderildi.\nPanel bildirimi çalışıyor.`,
      tags: "bell,shopping"
    });

    try {
      await originalFetch(`https://ntfy.sh/${encodeURIComponent(topic)}/publish?${params.toString()}`, {
        mode: "no-cors",
        cache: "no-store"
      });

      button.textContent = "Gönderildi";
      setTimeout(() => {
        button.disabled = false;
        button.textContent = oldText;
      }, 1600);
    } catch {
      button.disabled = false;
      button.textContent = oldText;
      alert("Test bildirimi gönderilemedi.");
    }
  }

  async function moveProduct(id, targetOwner, button) {
    button.disabled = true;
    button.textContent = "Taşınıyor";

    const response = await originalFetch(productsEndpoint(`?id=eq.${encodeURIComponent(id)}`), {
      method: "PATCH",
      headers: supabaseHeaders({ Prefer: "return=minimal" }),
      body: JSON.stringify({ owner: targetOwner })
    });

    if (!response.ok) {
      button.disabled = false;
      button.textContent = `${targetOwner}'e taşı`;
      throw new Error("Ürün taşınamadı.");
    }

    const row = findRow(id);
    if (row) row.owner = targetOwner;

    button.textContent = "Taşındı";
    document.querySelector("#refresh")?.click();
    scheduleApply(200);
  }

  function injectFormExtras() {
    const form = document.querySelector("#add-form");
    if (!form) return;

    const alertLabel = document.querySelector("#alert-mode")?.closest("label");
    const actions = form.querySelector(".actions");

    if (alertLabel && !document.querySelector("#owner")) {
      const label = document.createElement("label");
      label.innerHTML = `
        Kişi
        <select id="owner">
          <option value="Kerim">Kerim</option>
          <option value="Selin">Selin</option>
        </select>
      `;
      form.insertBefore(label, alertLabel);
    }

    const ownerLabel = document.querySelector("#owner")?.closest("label");

    if (ownerLabel && !document.querySelector("#category")) {
      const label = document.createElement("label");
      label.innerHTML = `
        Kategori
        <select id="category">
          <option value="Diğer">Diğer</option>
          <option value="Elbise">Elbise</option>
          <option value="Kitap">Kitap</option>
          <option value="Elektronik">Elektronik</option>
          <option value="Kozmetik">Kozmetik</option>
        </select>
      `;
      form.insertBefore(label, ownerLabel);
    }

    if (actions && !document.querySelector("#note")) {
      const label = document.createElement("label");
      label.className = "note-field";
      label.innerHTML = `
        Ürün notu
        <textarea id="note" rows="2" placeholder="Örn: Selin için, hediye olabilir, indirim bekleniyor"></textarea>
      `;
      form.insertBefore(label, actions);
    }

    const ownerSelect = document.querySelector("#owner");
    if (ownerSelect) ownerSelect.value = currentOwner();
  }

  function injectOwnerTabs() {
    const listSection = document.querySelector("#products")?.closest("section");
    const listTitle = listSection?.querySelector("h2");

    if (!listSection || !listTitle) return;

    if (!document.querySelector(".owner-tabs")) {
      const tabs = document.createElement("div");
      tabs.className = "owner-tabs";
      tabs.innerHTML = OWNERS.map((owner) => `
        <button class="owner-tab" data-owner-tab="${owner}" type="button">${owner}</button>
      `).join("");

      listTitle.insertAdjacentElement("afterend", tabs);

      tabs.addEventListener("click", (event) => {
        const button = event.target.closest("[data-owner-tab]");
        if (!button) return;

        setCurrentOwner(button.dataset.ownerTab);
      });
    }

    document.querySelectorAll("[data-owner-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.ownerTab === currentOwner());
    });
  }

  function injectNotificationTests() {
    const tabs = document.querySelector(".owner-tabs");
    if (!tabs || document.querySelector(".notification-tests")) return;

    const box = document.createElement("div");
    box.className = "notification-tests";
    box.innerHTML = `
      <button class="notify-test kerim" data-test-owner="Kerim" type="button">Kerim test bildirimi</button>
      <button class="notify-test selin" data-test-owner="Selin" type="button">Selin test bildirimi</button>
    `;

    tabs.insertAdjacentElement("afterend", box);
  }

  function injectMoveButton(card, row) {
    const id = row?.id || rowId(card);
    const actions =
      card.querySelector(".product-actions") ||
      card.querySelector("button[data-id]")?.parentElement;

    if (!id || !actions) return;

    const targetOwner = otherOwner();
    const nextText = `${targetOwner}'e taşı`;
    const existing = card.querySelector("[data-move-owner-id]");

    if (existing) {
      existing.dataset.targetOwner = targetOwner;
      if (existing.textContent !== nextText) existing.textContent = nextText;
      return;
    }

    const button = document.createElement("button");
    button.className = "secondary move-owner";
    button.type = "button";
    button.dataset.moveOwnerId = id;
    button.dataset.targetOwner = targetOwner;
    button.textContent = nextText;

    const editButton = actions.querySelector("button[data-edit-id]");
    if (editButton) {
      actions.insertBefore(button, editButton);
    } else {
      actions.prepend(button);
    }
  }

  function decorateCard(card, row) {
    if (!row) return;

    const signature = `${row.category || "Diğer"}|${row.note || ""}`;
    if (card.dataset.extraSignature === signature) return;
    card.dataset.extraSignature = signature;

    card.querySelector(".category-badge")?.remove();
    card.querySelector(".product-note")?.remove();

    const title = card.querySelector(".title");
    if (!title) return;

    const category = row.category || "Diğer";
    const badge = document.createElement("span");
    badge.className = `category-badge category-${CATEGORIES[category] || "other"}`;
    badge.textContent = category;
    title.appendChild(badge);

    if (row.note) {
      const note = document.createElement("div");
      note.className = "product-note";
      note.textContent = `Not: ${row.note}`;
      title.insertAdjacentElement("afterend", note);
    }
  }

  function applyProductsView() {
    injectStyles();
    injectFormExtras();
    injectOwnerTabs();
    injectNotificationTests();

    const list = document.querySelector("#products");
    const status = document.querySelector("#status");
    if (!list) return;

    const owner = currentOwner();
    const cards = Array.from(list.querySelectorAll(".product"));

    list.querySelectorAll(".owner-empty").forEach((item) => item.remove());

    if (!cards.length) {
      if (status && allRows.length) status.textContent = `${visibleRows().length} ürün`;
      return;
    }

    cards.forEach((card) => {
      const id = rowId(card);
      const row = findRow(id);

      if (allRows.length && (!row || rowOwner(row) !== owner)) {
        card.hidden = true;
        return;
      }

      card.hidden = false;
      injectMoveButton(card, row);
      decorateCard(card, row);
    });

    const visibleCount = visibleRows().length;
    if (status) status.textContent = `${visibleCount} ürün`;

    const visibleCards = cards.filter((card) => !card.hidden);
    if (!visibleCards.length && allRows.length) {
      const empty = document.createElement("div");
      empty.className = "empty owner-empty";
      empty.textContent = "Bu listede ürün yok.";
      list.appendChild(empty);
    }
  }

  function fillExtraFields(id) {
    const row = findRow(id);
    if (!row) return;

    const owner = document.querySelector("#owner");
    const category = document.querySelector("#category");
    const note = document.querySelector("#note");

    if (owner) owner.value = rowOwner(row);
    if (category) category.value = row.category || "Diğer";
    if (note) note.value = row.note || "";
  }

  function injectStyles() {
    if (document.querySelector("#app-config-extension-styles")) return;

    const style = document.createElement("style");
    style.id = "app-config-extension-styles";
    style.textContent = `
      .owner-tabs {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin: 0 0 10px;
        padding: 6px;
        border: 1px solid rgba(123, 140, 180, 0.2);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.75);
      }

      .owner-tab {
        min-height: 40px;
        border: 0;
        border-radius: 12px;
        background: #2f3b4f;
        color: white;
        font-weight: 800;
        cursor: pointer;
      }

      .owner-tab.active {
        background: linear-gradient(135deg, #ff7ab6, #527cff);
        box-shadow: 0 10px 22px rgba(82, 124, 255, 0.22);
      }

      .notification-tests {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin: 0 0 14px;
      }

      .notify-test {
        min-height: 38px;
        border: 0;
        border-radius: 12px;
        color: white;
        font-weight: 800;
        cursor: pointer;
      }

      .notify-test.kerim {
        background: linear-gradient(135deg, #1f8ef1, #527cff);
      }

      .notify-test.selin {
        background: linear-gradient(135deg, #ff6da8, #9b7cff);
      }

      .move-owner {
        background: linear-gradient(135deg, #6d7cff, #9b7cff) !important;
        color: white !important;
      }

      #owner,
      #category {
        font-weight: 700;
      }

      .note-field {
        grid-column: span 2;
      }

      #note {
        width: 100%;
        resize: vertical;
        min-height: 48px;
        border: 1px solid #d6e0f2;
        border-radius: 14px;
        padding: 11px 12px;
        color: #172554;
        background: rgba(255, 255, 255, 0.92);
        font: inherit;
        font-weight: 600;
        outline: none;
      }

      #note:focus {
        border-color: #7c9cff;
        box-shadow: 0 0 0 4px rgba(124, 156, 255, 0.18);
      }

      .product-note {
        width: fit-content;
        max-width: 100%;
        margin: 7px 0 8px;
        padding: 7px 10px;
        border-radius: 12px;
        background: rgba(255, 122, 182, 0.14);
        color: #8a2459;
        font-size: 14px;
        font-weight: 800;
        overflow-wrap: anywhere;
      }

      .category-badge {
        display: inline-flex;
        align-items: center;
        margin-left: 8px;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 900;
      }

      .category-other { background: #eef2ff; color: #334155; }
      .category-dress { background: #ffe4f1; color: #a21caf; }
      .category-book { background: #dcfce7; color: #15803d; }
      .category-tech { background: #dbeafe; color: #1d4ed8; }
      .category-beauty { background: #ffedd5; color: #c2410c; }

      @media (max-width: 760px) {
        .note-field {
          grid-column: 1 / -1;
        }
      }

      @media (max-width: 520px) {
        .owner-tabs,
        .notification-tests {
          grid-template-columns: 1fr;
        }
      }
    `;

    document.head.appendChild(style);
  }

  document.addEventListener("DOMContentLoaded", () => {
    injectStyles();
    injectFormExtras();
    injectOwnerTabs();
    injectNotificationTests();

    document.addEventListener(
      "click",
      (event) => {
        const testButton = event.target.closest("[data-test-owner]");
        if (testButton) {
          event.preventDefault();
          event.stopPropagation();
          sendTestNotification(testButton.dataset.testOwner, testButton);
          return;
        }

        const moveButton = event.target.closest("[data-move-owner-id]");
        if (moveButton) {
          event.preventDefault();
          event.stopPropagation();

          moveProduct(moveButton.dataset.moveOwnerId, moveButton.dataset.targetOwner, moveButton).catch((error) => {
            console.error(error);
            alert(error.message);
          });
          return;
        }

        const editButton = event.target.closest("button[data-edit-id]");
        if (editButton) {
          setTimeout(() => fillExtraFields(editButton.dataset.editId), 0);
        }
      },
      true
    );

    let ticks = 0;
    const boot = setInterval(() => {
      applyProductsView();
      ticks += 1;
      if (ticks > 12) clearInterval(boot);
    }, 400);

    scheduleApply(250);
  });
})();
