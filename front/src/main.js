// front/src/main.js

const form = document.getElementById("search-form");
const queryInput = document.getElementById("query-input");
const cityInput = document.getElementById("city-input");
const statusDiv = document.getElementById("status");
const resultsDiv = document.getElementById("results");
const detailDiv = document.getElementById("detail");

let selectedCard = null;
let lastQuery = null;
let lastCity = null;

function setSelectedCard(card) {
  if (selectedCard) {
    selectedCard.classList.remove("selected");
  }
  selectedCard = card;
  selectedCard.classList.add("selected");
}

async function fetchOfferDetail(jobId) {
  detailDiv.innerHTML = "<p>Chargement du détail...</p>";

  try {
    const response = await fetch(`http://localhost:8000/offers/${jobId}`);
    if (!response.ok) {
      throw new Error(`Erreur serveur: ${response.status}`);
    }

    const data = await response.json();

    const container = document.createElement("div");
    const title = document.createElement("h2");
    title.textContent = data.title;

    const desc = document.createElement("p");
    desc.textContent = data.description || "(Pas de description disponible)";

    container.appendChild(title);
    container.appendChild(desc);

    detailDiv.innerHTML = "";
    detailDiv.appendChild(container);
  } catch (err) {
    console.error(err);
    detailDiv.innerHTML =
      "<p style='color:red;'>Impossible de charger le détail de l'offre.</p>";
  }
}

async function trackClick(jobId) {
  console.log(
    "trackClick appelé avec jobId =",
    jobId,
    "lastQuery =",
    lastQuery,
    "lastCity =",
    lastCity
  );

  if (!lastQuery) {
    return;
  }

  try {
    await fetch("http://localhost:8000/track-click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: lastQuery,
        city: lastCity,
        job_id: jobId,
      }),
    });
  } catch (err) {
    console.error("Erreur lors du tracking du clic", err);
  }
}

async function searchOffers(query, city) {
  lastQuery = query;
  lastCity = city;

  statusDiv.textContent = "Recherche en cours...";
  statusDiv.className = "";
  resultsDiv.innerHTML = "";
  detailDiv.innerHTML = "";
  selectedCard = null;

  try {
    const response = await fetch("http://localhost:8000/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: query,
        city: city,
        period: null,
        limit: 10,
      }),
    });

    if (!response.ok) {
      throw new Error(`Erreur serveur: ${response.status}`);
    }

    const data = await response.json();

    if (data.total === 0) {
      statusDiv.textContent = `Aucune offre trouvée pour "${query}".`;
      return;
    }

    statusDiv.textContent = `${data.total} offre(s) trouvée(s) pour "${query}".`;

    data.results.forEach((offer) => {
      const card = document.createElement("div");
      card.className = "offer-card";

      const title = document.createElement("h2");
      title.className = "offer-title";
      title.textContent = offer.title;

      const score = document.createElement("div");
      score.className = "offer-score";
      score.textContent = `Score de pertinence : ${offer.score.toFixed(3)}`;

      card.appendChild(title);
      card.appendChild(score);

      card.addEventListener("click", () => {
        setSelectedCard(card);
        trackClick(offer.job_id);
        fetchOfferDetail(offer.job_id);
      });

      resultsDiv.appendChild(card);
    });
  } catch (err) {
    console.error(err);
    statusDiv.textContent = "Une erreur est survenue lors de la recherche.";
    statusDiv.className = "error";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  const city = cityInput.value.trim() || null;
  if (!query) return;
  searchOffers(query, city);
});