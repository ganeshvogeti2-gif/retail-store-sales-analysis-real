document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const menuButton = document.getElementById("menuButton");
  if (sidebar && menuButton) {
    menuButton.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (event) => {
      if (window.innerWidth <= 760 && sidebar.classList.contains("open") && !sidebar.contains(event.target) && event.target !== menuButton) {
        sidebar.classList.remove("open");
      }
    });
  }

  document.querySelectorAll(".dismiss").forEach((button) => {
    button.addEventListener("click", () => button.closest(".flash")?.remove());
  });

  document.querySelectorAll(".delete-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Delete this product? Products with sales history cannot be deleted.")) event.preventDefault();
    });
  });

  document.querySelectorAll(".toggle-password").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.parentElement.querySelector("input");
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      button.textContent = visible ? "Show" : "Hide";
    });
  });

  const productSelect = document.getElementById("productSelect");
  const quantityInput = document.getElementById("quantityInput");
  const totalOutput = document.getElementById("saleTotal");
  const stockHint = document.getElementById("stockHint");
  const updateSalePreview = () => {
    if (!productSelect || !quantityInput || !totalOutput) return;
    const option = productSelect.options[productSelect.selectedIndex];
    const price = Number(option?.dataset.price || 0);
    const stock = Number(option?.dataset.stock || 0);
    const quantity = Number(quantityInput.value || 0);
    totalOutput.textContent = `₹${(price * quantity).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (productSelect.value) {
      stockHint.textContent = `${stock} units available`;
      stockHint.style.color = quantity > stock ? "#bd5b65" : "";
    } else {
      stockHint.textContent = "Choose a product to see stock available.";
    }
    quantityInput.max = stock || "";
  };
  productSelect?.addEventListener("change", updateSalePreview);
  quantityInput?.addEventListener("input", updateSalePreview);
  updateSalePreview();
});