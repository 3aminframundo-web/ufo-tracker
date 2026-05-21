// 🔑 Configuración
// ✅ CORRECCIÓN 1: La URL base termina en /api, no en /sightings
const API_BASE = "https://ufo-tracker-pjai.onrender.com/api";
const POLL_INTERVAL = 60000; // 60 segundos
let deferredPrompt = null;
let lastSightingDate = localStorage.getItem('lastSightingDate') || '';
let notifEnabled = localStorage.getItem('notifEnabled') === 'true';

// 🌍 Mapa
const map = L.map('map').setView([20, 0], 2);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '© CARTO | Datos: NUFORC',
  maxZoom: 19
}).addTo(map);

const ufoIcon = L.divIcon({ className: 'ufo-marker', html: '', iconSize: [30, 30], iconAnchor: [15, 15] });
let currentMarkers = [];

//  Funciones API
async function fetchSightings(shape = '', country = '', limit = 100) {
  const params = new URLSearchParams({ limit, shape, country });
  // ✅ CORRECCIÓN 2: Ahora la URL se forma correctamente: .../api/sightings
  const res = await fetch(`${API_BASE}/sightings?${params}`);
  if (!res.ok) throw new Error('Error API');
  return await res.json();
}

async function fetchStats() {
  // ✅ CORRECCIÓN 3: Ahora la URL se forma correctamente: .../api/stats
  const res = await fetch(`${API_BASE}/stats`);
  return await res.json();
}

// 📊 Renderizado
function renderSightings(data) {
  const container = document.getElementById('sightingsList');
  currentMarkers.forEach(m => map.removeLayer(m));
  currentMarkers = [];
  
  if (!data.data?.length) {
    container.innerHTML = '<p class="loading">No se encontraron avistamientos 🤷</p>';
    return;
  }
  
  // ✅ CORRECCIÓN 4: Sintaxis de flecha corregida (=>) y comillas limpias
  container.innerHTML = data.data.map(s => `
    <div class="sighting-card" data-id="${s.id}">
      <div class="date">📅 ${s.date_time}</div>
      <div class="location">📍 ${s.city}, ${s.state || ''} ${s.country.toUpperCase()}</div>
      <span class="shape">🔷 ${s.shape}</span>
      <p class="preview">${s.comments?.substring(0, 100)}${s.comments?.length > 100 ? '...' : ''}</p>
    </div>
  `).join('');

  data.data.forEach(s => {
    // ✅ CORRECCIÓN 5: Operador lógico corregido (&&)
    if (s.latitude && s.longitude) {
      const marker = L.marker([s.latitude, s.longitude], { icon: ufoIcon })
        .addTo(map)
        .bindPopup(`<b>${s.date_time}</b><br>${s.city}, ${s.country.toUpperCase()}<br><i>${s.shape}</i>`);
      currentMarkers.push(marker);
    }
  });
  
  const valid = data.data.find(s => s.latitude && s.longitude);
  if (valid) map.setView([valid.latitude, valid.longitude], 6);
}

function renderStats(stats) {
  const panel = document.getElementById('statsPanel');
  const topShapes = Object.entries(stats.top_shapes || {}).slice(0, 5);
  
  // ✅ CORRECCIÓN 6: Sintaxis de flecha corregida en renderStats
  panel.innerHTML = `
    <h4> Estadísticas</h4>
    <div class="stats-item"><span>Total:</span> <strong>${stats.total_records?.toLocaleString() || 0}</strong></div>
    ${topShapes.map(([shape, count]) => 
      `<div class="stats-item"><span>${shape}</span> <span>${count}</span></div>`
    ).join('')}
  `;
}

// 🔔 Notificaciones & Polling
function requestNotificationPermission() {
  if (!('Notification' in window)) return alert('Tu navegador no soporta notificaciones');
  Notification.requestPermission().then(perm => {
    if (perm === 'granted') {
      notifEnabled = true;
      localStorage.setItem('notifEnabled', 'true');
      document.getElementById('notifBtn').classList.add('active');
    }
  });
}

function sendNotification(title, body) {
  if (notifEnabled && Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/manifest.json', badge: '/manifest.json' });
  }
}

async function checkForNewSightings() {
  try {
    const res = await fetch(`${API_BASE}/sightings?limit=1`);
    const data = await res.json();
    if (data.data?.length > 0) {
      const latest = data.data[0];
      if (latest.date_time !== lastSightingDate) {
        sendNotification('🛸 ¡Nuevo Avistamiento!', `${latest.city}, ${latest.country}\nForma: ${latest.shape}`);
        lastSightingDate = latest.date_time;
        localStorage.setItem('lastSightingDate', latest.date_time);
        if (!document.hidden) fetchSightings().then(renderSightings);
      }
    }
  } catch (err) { console.error('Polling error:', err); }
}

// 📱 PWA Install
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('installBtn').classList.remove('hidden');
});

document.getElementById('installBtn').addEventListener('click', () => {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(res => {
      if (res.outcome === 'accepted') document.getElementById('installBanner').classList.remove('hidden');
      deferredPrompt = null;
    });
  }
});

document.getElementById('installConfirm').addEventListener('click', () => {
  document.getElementById('installBanner').classList.add('hidden');
});
document.getElementById('installDismiss').addEventListener('click', () => {
  document.getElementById('installBanner').classList.add('hidden');
});

document.getElementById('notifBtn').addEventListener('click', requestNotificationPermission);
if (notifEnabled) document.getElementById('notifBtn').classList.add('active');

// 🔄 Event Listeners UI
document.getElementById('searchBtn').addEventListener('click', async () => {
  const shape = document.getElementById('shapeFilter').value;
  const country = document.getElementById('countryFilter').value;
  document.getElementById('sightingsList').innerHTML = '<div class="loading">Buscando...</div>';
  try {
    renderSightings(await fetchSightings(shape, country));
  } catch (err) {
    document.getElementById('sightingsList').innerHTML = '<p class="loading">❌ Error al cargar</p>';
  }
});

document.getElementById('sightingsList').addEventListener('click', e => {
  const card = e.target.closest('.sighting-card');
  if (!card) return;
  document.getElementById('modalBody').innerHTML = card.innerHTML;
  document.getElementById('modal').classList.remove('hidden');
});
document.querySelector('.close').addEventListener('click', () => document.getElementById('modal').classList.add('hidden'));
document.getElementById('modal').addEventListener('click', e => { if (e.target.id === 'modal') document.getElementById('modal').classList.add('hidden'); });

// 🚀 Init
(async function init() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(console.error);
  }
  
  try {
    const [sightings, stats] = await Promise.all([fetchSightings(), fetchStats()]);
    renderSightings(sightings);
    renderStats(stats);
    if (!lastSightingDate && sightings.data?.[0]) {
      lastSightingDate = sightings.data[0].date_time;
      localStorage.setItem('lastSightingDate', lastSightingDate);
    }
    setInterval(checkForNewSightings, POLL_INTERVAL);
  } catch (err) {
    console.error('Init error:', err);
    document.getElementById('sightingsList').innerHTML = '<p class="loading">⚠️ Verifica la API en Render</p>';
  }
})();