const _fetch = window.fetch;
window.fetch = async (...args) => {
  const res = await _fetch(...args);
  if (res.status === 401) location.href = "login.html";
  return res;
};

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  location.href = "login.html";
});

const API_BASE = "/api/properties";

const form = document.getElementById("property-form");
const idField = document.getElementById("property-id");
const formTitle = document.getElementById("form-title");
const submitBtn = document.getElementById("submit-btn");
const cancelBtn = document.getElementById("cancel-edit");
const tableBody = document.getElementById("properties-body");

const fields = ["title", "address", "property_type", "price", "bedrooms", "bathrooms", "status", "description"];

function getFormData() {
  const data = {};
  for (const field of fields) {
    const el = document.getElementById(field);
    data[field] = el.value;
  }
  data.price = parseFloat(data.price) || 0;
  data.bedrooms = parseInt(data.bedrooms, 10) || 0;
  data.bathrooms = parseInt(data.bathrooms, 10) || 0;
  return data;
}

function fillForm(property) {
  idField.value = property.id;
  for (const field of fields) {
    document.getElementById(field).value = property[field];
  }
  formTitle.textContent = `Edit: ${property.title}`;
  submitBtn.textContent = "Save changes";
  cancelBtn.hidden = false;
}

function resetForm() {
  form.reset();
  idField.value = "";
  formTitle.textContent = "Add a property";
  submitBtn.textContent = "Add property";
  cancelBtn.hidden = true;
}

async function loadProperties() {
  tableBody.innerHTML = `<tr><td colspan="8">Loading...</td></tr>`;
  const res = await fetch(API_BASE);
  const properties = await res.json();

  if (properties.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="8">No properties yet. Add one above.</td></tr>`;
    return;
  }

  tableBody.innerHTML = "";
  for (const property of properties) {
    const row = document.createElement("tr");
    const statusClass = `status-${property.status}`;
    row.innerHTML = `
      <td>${escapeHtml(property.title)}</td>
      <td>${escapeHtml(property.address)}</td>
      <td>${escapeHtml(property.property_type)}</td>
      <td>AED ${Number(property.price).toLocaleString()}</td>
      <td>${property.bedrooms}</td>
      <td>${property.bathrooms}</td>
      <td><span class="status-badge ${statusClass}">${escapeHtml(property.status)}</span></td>
      <td class="actions-cell">
        <button class="small-btn edit-btn" data-id="${property.id}">Edit</button>
        <button class="small-btn delete-btn" data-id="${property.id}">Delete</button>
      </td>
    `;
    tableBody.appendChild(row);
  }

  tableBody.querySelectorAll(".edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => editProperty(btn.dataset.id));
  });
  tableBody.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteProperty(btn.dataset.id));
  });
}

async function editProperty(id) {
  const res = await fetch(`${API_BASE}/${id}`);
  if (!res.ok) return;
  const property = await res.json();
  fillForm(property);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function deleteProperty(id) {
  if (!confirm("Delete this property? This cannot be undone.")) return;
  await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
  loadProperties();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = getFormData();
  const id = idField.value;

  const res = await fetch(id ? `${API_BASE}/${id}` : API_BASE, {
    method: id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(`Something went wrong: ${err.detail || res.statusText}`);
    return;
  }

  resetForm();
  loadProperties();
});

cancelBtn.addEventListener("click", resetForm);

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

loadProperties();

const bookingsBody = document.getElementById("bookings-body");

async function loadBookings() {
  const res = await fetch("/api/bookings");
  const bookings = await res.json();
  if (bookings.length === 0) {
    bookingsBody.innerHTML = `<tr><td colspan="7">No bookings yet.</td></tr>`;
    return;
  }
  bookingsBody.innerHTML = "";
  for (const b of bookings) {
    const row = document.createElement("tr");
    const cancelled = b.status === "cancelled";
    row.innerHTML = `
      <td>${escapeHtml(b.viewing_time)}</td>
      <td>${escapeHtml(b.property_title)}</td>
      <td>${escapeHtml(b.customer_name)}</td>
      <td>${escapeHtml(b.customer_phone)}</td>
      <td>${escapeHtml(b.customer_email)}</td>
      <td><span class="status-badge ${cancelled ? "status-off-market" : "status-available"}">${escapeHtml(b.status)}</span></td>
      <td>${cancelled ? "" : `<button class="small-btn delete-btn" data-id="${b.id}">Cancel</button>`}</td>
    `;
    bookingsBody.appendChild(row);
  }
  bookingsBody.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Cancel this viewing?")) return;
      await fetch(`/api/bookings/${btn.dataset.id}/cancel`, { method: "POST" });
      loadBookings();
    });
  });
}

loadBookings();
