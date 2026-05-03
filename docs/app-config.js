window.APP_CONFIG = {
  supabaseUrl: "https://jbwsmwzegsvqnmimslkp.supabase.co",
  supabaseAnonKey: "sb_publishable_OShnnNwc2O16QggB2nVLaA_D3juCxrb"
};

(() => {
  const OWNERS = ["Kerim", "Selin"];
  const DEFAULT_OWNER = "Kerim";
  const originalFetch = window.fetch.bind(window);

  function currentOwner() {
    const saved = localStorage.getItem("activeOwner");
    return OWNERS.includes(saved) ? saved : DEFAULT_OWNER;
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

    setCurrentOwner(currentOwner());
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
        margin: 0 0 14px;
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

      #owner {
        font-weight: 700;
      }

      @media (max-width: 520px) {
        .owner-tabs {
          grid-template-columns: 1fr;
        }
      }
    `;
    document.head.appendChild(style);
  }

  document.addEventListener("DOMContentLoaded", () => {
    injectOwnerStyles();
    injectOwnerUi();
  });
})();
