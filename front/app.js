const API_BASE = "http://localhost:8000";

async function fetchOffers() {
  const res = await fetch(`${API_BASE}/offers?page=1&page_size=50&department=93`);
  return await res.json();
}

async function fetchOffer(id) {
  const res = await fetch(`${API_BASE}/offers/${id}`);
  return await res.json();
}

function renderList(offers) {
  const listEl = document.getElementById("job-list");
  listEl.innerHTML = "";
  offers.forEach(offer => {
    const item = document.createElement("div");
    item.className = "job-item";
    item.innerHTML = `
      <div class="job-title">${offer.title}</div>
      <div class="job-meta">
        ${offer.company_name || "Entreprise inconnue"} – 
        ${offer.postal_code || ""} ${offer.city_label || ""}
      </div>
    `;
    item.addEventListener("click", () => showDetail(offer.job_id));
    listEl.appendChild(item);
  });
}

async function showDetail(id) {
  const detailEl = document.getElementById("job-detail");
  detailEl.innerHTML = "<p>Chargement...</p>";
  const offer = await fetchOffer(id);
  detailEl.innerHTML = `
    <h2>${offer.title}</h2>
    <p><strong>${offer.company_name || "Entreprise inconnue"}</strong></p>
    <p>${offer.postal_code || ""} ${offer.city_label || ""}</p>
    <p><strong>Contrat :</strong> ${offer.contract_type || "N/A"}</p>
    <p><strong>Salaire :</strong> ${offer.salary_text || "Non communiqué"}</p>
    <hr/>
    <pre style="white-space: pre-wrap;">${offer.description || ""}</pre>
  `;
}

(async function main() {
  const offers = await fetchOffers();
  renderList(offers);
})();

async function showDetail(id) {
  const detailEl = document.getElementById("job-detail");
  detailEl.innerHTML = "<p>Chargement...</p>";
  const offer = await fetchOffer(id);

  const location = [offer.postal_code, offer.city_label]
    .filter(Boolean)
    .join(" ");

  const salary =
    offer.salary_text ||
    (offer.salary_min && offer.salary_max
      ? `${offer.salary_min} - ${offer.salary_max} ${offer.salary_currency || ""}`
      : "Non communiqué");

  detailEl.innerHTML = `
    <h2 style="margin-top: 0;">${offer.title}</h2>

    <p style="margin: 4px 0;">
      <strong>${offer.company_name || "Entreprise inconnue"}</strong>
      ${location ? " – " + location : ""}
    </p>

    <p style="margin: 4px 0; font-size: 0.9rem; color: #555;">
      <strong>Contrat :</strong> ${offer.contract_type || "N/A"}
      ${offer.contract_nature ? ` (${offer.contract_nature})` : ""}
      ${
        offer.remote_type
          ? `<br/><strong>Remote :</strong> ${offer.remote_type}`
          : ""
      }
    </p>

    <p style="margin: 4px 0; font-size: 0.9rem; color: #555;">
      <strong>Salaire :</strong> ${salary}
    </p>

    ${
      offer.experience_required
        ? `<p style="margin: 4px 0; font-size: 0.9rem; color: #555;">
             <strong>Expérience :</strong> ${offer.experience_required}
           </p>`
        : ""
    }

    ${
      offer.sector
        ? `<p style="margin: 4px 0; font-size: 0.9rem; color: #555;">
             <strong>Secteur :</strong> ${offer.sector}
           </p>`
        : ""
    }

    <hr style="margin: 16px 0;"/>

    <h3 style="margin-top: 0;">Description</h3>
    <div style="white-space: pre-wrap; line-height: 1.4; font-size: 0.9rem;">
      ${offer.description || "Pas de description disponible."}
    </div>
  `;
}