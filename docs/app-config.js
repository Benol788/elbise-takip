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

  const originalFetch = window.fetch.bind(window);

  function currentOwner() {
    const saved = localStorage.getItem("activeOwner");
    return OWNERS.includes(saved) ? saved : DEFAULT_OWNER;
  }

  function otherOwner() {
    return currentOwner() === "Kerim" ? "Selin" : "Kerim";
  }

  function setCurrentOwner(owner) {
    const next = OWNERS.includes(owner) ? owner : DEFAULT_OWNER;
    window.__ACTIVE_OWNER = next;
    localStorage.setItem("activeOwner", next);

    document.querySelectorAll("[data-owner-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.ownerTab === next);
    });

    const ownerSelect = document.querySelector("#owner");
    if (ownerSelect) ownerSelect.value = next;

    injectMoveButtons();
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
      await fetch(`https://ntfy.sh/${encodeURIComponent(topic)}/publish?${params.toString()}`, {
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

  window.__ACTIVE_OWNER = currentOwner();

  window.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = String(init?.method || input?.method || "GET").toUpperCase();
    const isProductsApi = url.includes(".supabase.co") && url.includes("/products");

    if (isProductsApi && method === "GET" && url.includes("select=")) {
      const response = await originalFetch(input, init);
      if (!response.ok) return response;

      const rows = await response.clone().json();
      const owner = currentOwner();
      const filtered = Array.isArray(rows)
        ? rows.filter((row) => (row.owner || DEFAULT_OWNER) === owner)
        : rows;

      setTimeout(injectMoveButtons, 50);

      return new Response(JSON.stringify(filtered), {
        status: response.status,
        statusText: response.statusText,
        headers: { "Content-Type": "application/json" }
      });
    }

    if (isProductsApi && (method === "POST" || method === "PATCH") && init?.body) {
      try {
        const payload = JSON.parse(init.body);
        payload.owner = document.querySelector("#owner")?.value || currentOwner();
        init = { ...init, body: JSON.stringify(payload) };
      } catch {}
    }

    return originalFetch(input, init);
  };

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

    button.textContent = "Taşındı";
    document.querySelector("#refresh")?.click();
  }

  function injectOwnerUi() {
    const form = document.querySelector("#add-form");
    const alertLabel = document.querySelector("#alert-mode")?.closest("label");

    if (form && alertLabel && !document.querySelector("#owner")) {
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

    const listSection = document.querySelector("#products")?.closest("section");
    const listTitle = listSection?.querySelector("h2");

    if (listSection && listTitle && !document.querySelector(".owner-tabs")) {
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
        document.querySelector("#refresh")?.click();
      });
    }

    injectNotificationTestUi();
    setCurrentOwner(currentOwner());
  }

  function injectNotificationTestUi() {
    const listSection = document.querySelector("#products")?.closest("section");
    const tabs = document.querySelector(".owner-tabs");

    if (!listSection || !tabs || document.querySelector(".notification-tests")) return;

    const box = document.createElement("div");
    box.className = "notification-tests";
    box.innerHTML = `
      <button class="notify-test kerim" data-test-owner="Kerim" type="button">Kerim test bildirimi</button>
      <button class="notify-test selin" data-test-owner="Selin" type="button">Selin test bildirimi</button>
    `;

    tabs.insertAdjacentElement("afterend", box);
  }

  function injectMoveButtons() {
    const targetOwner = otherOwner();

    document.querySelectorAll("#products .product").forEach((card) => {
      if (card.querySelector("[data-move-owner-id]")) return;

      const id =
        card.querySelector("button[data-id]")?.dataset.id ||
        card.querySelector("button[data-edit-id]")?.dataset.editId ||
        card.querySelector("button[data-favorite-id]")?.dataset.favoriteId;

      const actions =
        card.querySelector(".product-actions") ||
        card.querySelector("button[data-id]")?.parentElement;

      if (!id || !actions) return;

      const button = document.createElement("button");
      button.className = "secondary move-owner";
      button.type = "button";
      button.dataset.moveOwnerId = id;
      button.dataset.targetOwner = targetOwner;
      button.textContent = `${targetOwner}'e taşı`;

      const editButton = actions.querySelector("button[data-edit-id]");
      if (editButton) {
        actions.insertBefore(button, editButton);
      } else {
        actions.prepend(button);
      }
    });
  }

  function injectOwnerStyles() {
    if (document.querySelector("#owner-tab-styles")) return;

    const style = document.createElement("style");
    style.id = "owner-tab-styles";
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

      .notify-test:disabled {
        opacity: 0.72;
        cursor: wait;
      }

      .move-owner {
        background: linear-gradient(135deg, #6d7cff, #9b7cff) !important;
        color: white !important;
      }

      #owner {
        font-weight: 700;
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
    injectOwnerStyles();
    injectOwnerUi();

    const list = document.querySelector("#products");
    if (list) {
      new MutationObserver(() => injectMoveButtons()).observe(list, {
        childList: true,
        subtree: true
      });
    }

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
        if (!moveButton) return;

        event.preventDefault();
        event.stopPropagation();

        moveProduct(moveButton.dataset.moveOwnerId, moveButton.dataset.targetOwner, moveButton).catch((error) => {
          console.error(error);
          alert(error.message);
        });
      },
      true
    );

    injectMoveButtons();
  });
})();
