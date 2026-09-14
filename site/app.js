const catalogData = [
  {
    category: 'Console',
    name: 'Emulatori per console',
    description: 'Nintendo, Sony, Sega, Microsoft e piattaforme vintage presenti in emulators/'
  },
  {
    category: 'TV',
    name: 'Launcher TV live',
    description: 'Streaming IPTV e monitoraggio canali tramite launch_tv_live_internazionale.py'
  },
  {
    category: 'Media',
    name: 'Player multimediale',
    description: 'Riproduzione video e gestione contenuti con mediaplayer.py'
  },
  {
    category: 'Web',
    name: 'Browser integrato',
    description: 'Accesso web con browser.py'
  },
  {
    category: 'Utility',
    name: 'Downloader',
    description: 'Gestione download multipla e avanzata con downloader.py'
  },
  {
    category: 'Tool',
    name: 'Utility aggiuntive',
    description: 'Strumenti per gestione file, installazione e conversione'
  }
];

const catalogNode = document.getElementById('catalogCards');
const galleryNode = document.getElementById('galleryCategories');
const signupForm = document.getElementById('signupForm');
const loginForm = document.getElementById('loginForm');
const registrationMessage = document.getElementById('registrationMessage');
const downloadSection = document.getElementById('download');

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Richiesta fallita');
  }
  return data;
}

function renderCatalog() {
  catalogNode.innerHTML = catalogData
    .map(
      (item) => `
        <article class="card">
          <span class="tag">${item.category}</span>
          <h4>${item.name}</h4>
          <p>${item.description}</p>
        </article>
      `
    )
    .join('');

  document.getElementById('platformCount').textContent = '15+';
  document.getElementById('appCount').textContent = '6';
  document.getElementById('toolCount').textContent = '4';
}

const galleryData = [];

function renderGallery(groups = galleryData) {
  if (!galleryNode) return;

  const safeGroups = groups.filter((group) => Array.isArray(group.items) && group.items.length > 0);

  if (!safeGroups.length) {
    galleryNode.innerHTML = '<p class="empty-state">Nessuno screenshot disponibile al momento.</p>';
    return;
  }

  galleryNode.innerHTML = safeGroups
    .map(
      (group) => `
        <div class="gallery-group">
          <h4>${group.category}</h4>
          <div class="gallery-grid">
            ${group.items
              .map(
                (item) => {
                  const src = encodeURI(item.image);
                  return `
                    <a class="gallery-item" href="${src}" target="_blank" rel="noreferrer">
                      <img src="${src}" alt="${item.name}" loading="lazy" />
                      <span>${item.name}</span>
                    </a>
                  `;
                }
              )
              .join('')}
          </div>
        </div>
      `
    )
    .join('');
}

async function loadGallery() {
  try {
    const response = await fetch('/api/gallery');
    if (!response.ok) {
      throw new Error('Gallery non disponibile');
    }
    const payload = await response.json();
    const categories = Array.isArray(payload.categories) ? payload.categories.filter((group) => group.category !== 'Emulatori') : [];
    renderGallery(categories);
  } catch (error) {
    renderGallery(galleryData);
  }
}

signupForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const fullName = document.getElementById('fullName').value.trim();
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value.trim();
  const country = document.getElementById('country').value.trim();
  const accountType = document.getElementById('accountType').value;

  try {
    await apiRequest('/api/register', {
      method: 'POST',
      body: JSON.stringify({ full_name: fullName, email, password, country, account_type: accountType })
    });

    showMessage(`Registrazione completata per ${fullName}. Accesso abilitato.`, 'success');
    signupForm.reset();
    downloadSection.classList.remove('hidden');
    window.location.hash = '#download';
  } catch (error) {
    showMessage(error.message, 'error');
  }
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value.trim();

  try {
    await apiRequest('/api/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    showMessage('Login effettuato con successo.', 'success');
    loginForm.reset();
    downloadSection.classList.remove('hidden');
    window.location.hash = '#download';
  } catch (error) {
    showMessage(error.message, 'error');
  }
});

function showMessage(message, type) {
  registrationMessage.textContent = message;
  registrationMessage.className = `message ${type}`;
  registrationMessage.classList.remove('hidden');
}

renderCatalog();
loadGallery();
