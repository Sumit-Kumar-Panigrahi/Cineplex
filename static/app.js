// ==============================================================================
// CINEPLEX - Complete Movie Ticket Booking & DBMS Engine
// Tagline: Your Movies. Your Moments.
// Flow: Movies → ShowtimePicker → SeatMap → Reserve → Checkout → M-Ticket Pass
//       My Bookings → View Ticket | Cancel → Refund Receipt
//       Admin Dashboard → Real-Time Analytics | DBMS Live SQL Console
// ==============================================================================

// ── Global State ──────────────────────────────────────────────────────────────
const STATE = {
  city:     'Bhubaneswar',
  tab:      'now_showing',
  lang:     'All',
  genre:    'All',
  search:   '',
  date:     todayStr(),

  movie:    null,   // current movie object from /api/movies/:id
  show:     null,   // current show object from /api/shows/:id/seats → data.show

  seats:    [],     // array of seat_label strings currently selected
  token:    null,   // reservation_token returned by /reserve
  timer:    null,   // setInterval handle for 5-min hold
  timerSec: 300,    // remaining seconds

  snacks:   {},     // { snack_id: quantity }
  snackDefs:[],     // full list from /api/snacks

  cancelRef: null,  // booking_ref currently being reviewed for cancel
  payMethod: 'UPI',

  currentTicket: null // cached booking object for printing/downloading
};

const AUTH_KEY = 'cineplex_users_v2';
const SESSION_KEY = 'cineplex_session_v2';
const BOOKINGS_KEY = 'cineplex_user_bookings_v2';

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', boot);

function boot() {
  // Init auth (restore session)
  authInit();

  // City selector
  const cityEl = document.getElementById('citySelector');
  if (cityEl) {
    cityEl.value = STATE.city;
    cityEl.addEventListener('change', e => {
      STATE.city = e.target.value;
      const h = document.getElementById('headingCityName');
      if (h) h.textContent = STATE.city;
      fetchMovies();
      if (STATE.movie) loadShows(STATE.movie.id, STATE.date);
    });
  }

  // Enhanced Live Search with Instant Autocomplete Dropdown & Views Auto-switching
  initLiveSearch();

  // Tab buttons (data-status)
  document.querySelectorAll('.bms-tab-btn[data-status]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.bms-tab-btn[data-status]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      STATE.tab = btn.dataset.status;
      fetchMovies();
    });
  });

  // Language chips
  document.querySelectorAll('#langChips .bms-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#langChips .bms-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      STATE.lang = chip.dataset.lang;
      fetchMovies();
    });
  });

  // Genre chips
  document.querySelectorAll('#genreChips .bms-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#genreChips .bms-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      STATE.genre = chip.dataset.genre;
      fetchMovies();
    });
  });

  loadSnackDefs();
  fetchMovies();
  refreshBookingBadge();
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
}
function pad(n) { return String(n).padStart(2, '0'); }
function rs(n)  { return '₹' + Number(n).toFixed(2); }

function openModal(id)  { const m = document.getElementById(id); if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; } }
function closeModal(id) { const m = document.getElementById(id); if (m) { m.classList.remove('open'); document.body.style.overflow = ''; } }

function toast(msg, type = 'info') {
  let box = document.querySelector('.toast-container');
  if (!box) { box = document.createElement('div'); box.className = 'toast-container'; document.body.appendChild(box); }
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── View Switcher ─────────────────────────────────────────────────────────────
function switchView(v) {
  // Auth guard: "My Bookings" is only accessible when logged in
  if (v === 'bookings' && !currentUser()) {
    toast('Please sign in to view your bookings.', 'error');
    v = 'auth';
  }

  const mv = document.getElementById('moviesView');
  const bv = document.getElementById('bookingsView');
  const av = document.getElementById('authView');
  const admv = document.getElementById('adminView');

  if (mv) mv.style.display = v === 'movies'   ? '' : 'none';
  if (bv) bv.style.display = v === 'bookings' ? 'block' : 'none';
  if (av) av.style.display = v === 'auth'     ? 'block' : 'none';
  if (admv) admv.style.display = v === 'admin' ? 'block' : 'none';

  // update subnav active state
  const mLink = document.getElementById('subnavMoviesLink');
  const bLink = document.getElementById('subnavBookingsLink');
  const aLink = document.getElementById('subnavAccountLink');
  const admLink = document.getElementById('subnavAdminLink');
  if (mLink) mLink.classList.toggle('active', v === 'movies');
  if (bLink) bLink.classList.toggle('active', v === 'bookings');
  if (aLink) aLink.classList.toggle('active', v === 'auth');
  if (admLink) admLink.classList.toggle('active', v === 'admin');

  if (v === 'bookings') loadMyBookings();
  if (v === 'auth')     renderAuthPageView();
  if (v === 'admin')    initAdminView();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Enhanced Live Search & Dropdown Autocomplete ──────────────────────────────
function initLiveSearch() {
  const searchInput = document.getElementById('searchInput');
  const searchWrap  = document.getElementById('bmsSearchWrap');
  const clearBtn    = document.getElementById('searchClearBtn');
  const dropdown    = document.getElementById('searchDropdown');
  if (!searchInput) return;

  let debounceTimer = null;

  const performSearch = (q) => {
    STATE.search = q;
    fetchMovies();
  };

  const fetchDropdownResults = async (q) => {
    if (!dropdown) return;
    if (!q || q.length < 2) {
      dropdown.style.display = 'none';
      dropdown.innerHTML = '';
      return;
    }

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      renderSearchDropdown(data, q);
    } catch (err) {
      console.warn('Search autocomplete fetch failed:', err);
    }
  };

  searchInput.addEventListener('input', e => {
    const val = e.target.value.trim();
    if (clearBtn) clearBtn.style.display = val ? 'flex' : 'none';

    // Auto-switch to movies view if user searches from another tab
    const mv = document.getElementById('moviesView');
    if (mv && mv.style.display === 'none' && val.length > 0) {
      switchView('movies');
    }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      performSearch(val);
      fetchDropdownResults(val);
    }, 220);
  });

  searchInput.addEventListener('focus', () => {
    const val = searchInput.value.trim();
    if (val.length >= 2) {
      fetchDropdownResults(val);
    }
  });

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = searchInput.value.trim();
      if (dropdown) dropdown.style.display = 'none';
      switchView('movies');
      performSearch(val);
      const grid = document.getElementById('movieGrid');
      if (grid) grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (e.key === 'Escape') {
      if (dropdown) dropdown.style.display = 'none';
    }
  });

  document.addEventListener('click', e => {
    if (searchWrap && !searchWrap.contains(e.target)) {
      if (dropdown) dropdown.style.display = 'none';
    }
  });
}

function clearSearchInput() {
  const s = document.getElementById('searchInput');
  const clearBtn = document.getElementById('searchClearBtn');
  const dropdown = document.getElementById('searchDropdown');
  if (s) {
    s.value = '';
    s.focus();
  }
  if (clearBtn) clearBtn.style.display = 'none';
  if (dropdown) {
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
  }
  STATE.search = '';
  fetchMovies();
}
window.clearSearchInput = clearSearchInput;

function renderSearchDropdown(data, query) {
  const dropdown = document.getElementById('searchDropdown');
  if (!dropdown) return;

  const movies = data.movies || [];
  const theatres = data.theatres || [];

  if (movies.length === 0 && theatres.length === 0) {
    dropdown.innerHTML = `
      <div style="padding:1.25rem 1rem; text-align:center; color:#64748b; font-size:0.85rem;">
        No movies or theatres matching "<strong>${escapeHtml(query)}</strong>"
      </div>
    `;
    dropdown.style.display = 'block';
    return;
  }

  let html = '';

  if (movies.length > 0) {
    html += `<div class="cpx-search-section-title">Movies (${movies.length})</div>`;
    movies.slice(0, 5).forEach(m => {
      const poster = m.poster_url || '/static/posters/ramayan.svg';
      const statusBadge = m.is_now_showing ?
        '<span style="font-size:0.68rem; color:#059669; font-weight:800; background:#ecfdf5; padding:0.15rem 0.4rem; border-radius:3px;">Now Showing</span>' :
        '<span style="font-size:0.68rem; color:#d97706; font-weight:800; background:#fef3c7; padding:0.15rem 0.4rem; border-radius:3px;">Upcoming</span>';
      html += `
        <div class="cpx-search-item" onclick="selectMovieFromSearch(${m.id})">
          <img src="${poster}" alt="${escapeHtml(m.title)}" class="cpx-search-thumb" onerror="this.src='/static/posters/ramayan.svg'">
          <div style="flex:1; min-width:0;">
            <div style="font-size:0.88rem; font-weight:800; color:var(--text-dark); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(m.title)}</div>
            <div style="font-size:0.75rem; color:#64748b; display:flex; align-items:center; gap:0.4rem; margin-top:0.2rem;">
              <span style="display:inline-flex; align-items:center; gap:2px;"><svg class="cpx-icon cpx-icon-xs star-gold"><use href="#icon-star"></use></svg> <strong>${m.vote_average || '8.5'}</strong></span>
              <span>•</span>
              <span>${escapeHtml(m.language || 'Hindi')}</span>
              <span>•</span>
              ${statusBadge}
            </div>
          </div>
          <button type="button" class="cpx-search-action-btn" onclick="event.stopPropagation(); selectMovieFromSearch(${m.id})">
            ${m.is_now_showing ? 'Book' : 'Explore'}
          </button>
        </div>
      `;
    });
  }

  if (theatres.length > 0) {
    html += `<div class="cpx-search-section-title">Theatres (${theatres.length})</div>`;
    theatres.slice(0, 3).forEach(t => {
      html += `
        <div class="cpx-search-item" onclick="selectTheatreFromSearch('${escapeHtml(t.name)}', '${escapeHtml(t.city)}')">
          <div style="width:36px; height:48px; border-radius:4px; background:#f1f5f9; display:flex; align-items:center; justify-content:center; color:var(--cpx-red); flex-shrink:0;">
            <svg class="cpx-icon cpx-icon-sm"><use href="#icon-theater"></use></svg>
          </div>
          <div style="flex:1; min-width:0;">
            <div style="font-size:0.85rem; font-weight:800; color:var(--text-dark);">${escapeHtml(t.name)}</div>
            <div style="font-size:0.75rem; color:#64748b;">${escapeHtml(t.city)} • ${escapeHtml(t.address)}</div>
          </div>
        </div>
      `;
    });
  }

  html += `
    <div class="cpx-search-footer" onclick="viewAllSearchResults('${escapeHtml(query)}')">
      View all results for "${escapeHtml(query)}" &rarr;
    </div>
  `;

  dropdown.innerHTML = html;
  dropdown.style.display = 'block';
}

function selectMovieFromSearch(movieId) {
  const dropdown = document.getElementById('searchDropdown');
  if (dropdown) dropdown.style.display = 'none';
  switchView('movies');
  openMovieDetail(movieId);
}
window.selectMovieFromSearch = selectMovieFromSearch;

function selectTheatreFromSearch(theatreName, city) {
  const dropdown = document.getElementById('searchDropdown');
  if (dropdown) dropdown.style.display = 'none';
  if (city) {
    const citySel = document.getElementById('citySelector');
    if (citySel) {
      citySel.value = city;
      STATE.city = city;
      const h = document.getElementById('headingCityName');
      if (h) h.textContent = city;
    }
  }
  switchView('movies');
  toast(`Selected ${theatreName} (${city})`, 'info');
}
window.selectTheatreFromSearch = selectTheatreFromSearch;

function viewAllSearchResults(query) {
  const dropdown = document.getElementById('searchDropdown');
  if (dropdown) dropdown.style.display = 'none';
  switchView('movies');
  STATE.search = query;
  fetchMovies();
  const grid = document.getElementById('movieGrid');
  if (grid) grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
window.viewAllSearchResults = viewAllSearchResults;

function clearFilters() {
  STATE.lang = 'All'; STATE.genre = 'All'; STATE.search = '';
  const s = document.getElementById('searchInput'); if (s) s.value = '';
  const clearBtn = document.getElementById('searchClearBtn'); if (clearBtn) clearBtn.style.display = 'none';
  const dropdown = document.getElementById('searchDropdown'); if (dropdown) { dropdown.style.display = 'none'; dropdown.innerHTML = ''; }
  document.querySelectorAll('#langChips .bms-chip').forEach((c,i) => c.classList.toggle('active', i===0));
  document.querySelectorAll('#genreChips .bms-chip').forEach((c,i) => c.classList.toggle('active', i===0));
  fetchMovies();
  toast('Filters reset to default view.', 'info');
}

// ==============================================================================
// SECTION 1 – MOVIES CATALOGUE & DISCOVERY
// ==============================================================================
async function fetchMovies() {
  try {
    const params = new URLSearchParams();
    if (STATE.tab)   params.set('status', STATE.tab);
    if (STATE.lang && STATE.lang !== 'All')   params.set('language', STATE.lang);
    if (STATE.genre && STATE.genre !== 'All') params.set('genre', STATE.genre);
    if (STATE.search) params.set('search', STATE.search);

    const res = await fetch(`/api/movies?${params.toString()}`);
    const data = await res.json();
    if (data.success) {
      renderHero(data.movies);
      renderGrid(data.movies);
    }
  } catch (err) {
    console.error("fetchMovies error:", err);
  }
}

// ── Movie Artwork Fallback Helpers ──────────────────────────────────────────
function getMovieSlug(title) {
  if (!title) return 'ramayan';
  const clean = title.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (clean.includes('ramayan')) return 'ramayan';
  if (clean.includes('pushpa')) return 'pushpa2';
  if (clean.includes('kalki')) return 'kalki2898ad';
  if (clean.includes('stree')) return 'stree2';
  if (clean.includes('chhaava')) return 'chhaava';
  if (clean.includes('jailer')) return 'jailer2';
  if (clean.includes('scene')) return 'scene';
  if (clean.includes('udta')) return 'udta_teer';
  if (clean.includes('jadi')) return 'jadi';
  if (clean.includes('conclusion')) return 'drishyam_conclusion';
  if (clean.includes('drishyam')) return 'drishyam';
  if (clean.includes('jawan')) return 'jawan';
  if (clean.includes('dhurandhar')) return 'dhurandhar';
  if (clean.includes('mookuthi')) return 'mookuthi_amman2';
  if (clean.includes('bouma')) return 'bouma';
  if (clean.includes('dnk')) return 'dnk';
  if (clean.includes('arjuna')) return 'itllu_arjuna';
  if (clean.includes('interstellar')) return 'interstellar';
  if (clean.includes('inception')) return 'inception';
  if (clean.includes('avengers') || clean.includes('endgame')) return 'avengers_endgame';
  if (clean.includes('titanic')) return 'titanic';
  if (clean.includes('catinthehat') || clean.includes('cat')) return 'cat_in_the_hat';
  if (clean.includes('clayface')) return 'clayface';
  if (clean.includes('tummereho')) return 'tum_mere_ho';
  return clean || 'ramayan';
}

function getMovieFallbackPoster(m) {
  if (m && m.offline_poster_path) return m.offline_poster_path;
  const slug = getMovieSlug(m ? m.title : '');
  return `/static/posters/${slug}.svg`;
}

function getMovieFallbackBackdrop(m) {
  if (m && m.offline_poster_path && m.offline_poster_path.endsWith('.svg')) {
    return m.offline_poster_path.replace('.svg', '_backdrop.svg');
  }
  const slug = getMovieSlug(m ? m.title : '');
  return `/static/posters/${slug}_backdrop.svg`;
}

let heroTimer = null;
function renderHero(movies) {
  if (!movies || !movies.length) return;
  const b = document.getElementById('heroBanner');
  if (!b) return;

  // Filter top movies for featured carousel (e.g. Interstellar, Ramayan, Pushpa 2, Kalki, Stree 2, Inception)
  STATE.heroMovies = movies.filter(m => m.featured || m.rating >= 8.5);
  if (!STATE.heroMovies.length) STATE.heroMovies = movies.slice(0, 6);
  STATE.heroIndex = 0;

  renderHeroDots();
  showHeroMovie(0);

  // Auto-rotate hero every 7 seconds
  if (heroTimer) clearInterval(heroTimer);
  heroTimer = setInterval(() => {
    nextHeroMovie();
  }, 7000);
}

function renderHeroDots() {
  const dotsBox = document.getElementById('heroDots');
  if (!dotsBox) return;
  dotsBox.innerHTML = '';
  (STATE.heroMovies || []).forEach((m, idx) => {
    const dot = document.createElement('span');
    dot.className = `hero-dot ${idx === (STATE.heroIndex || 0) ? 'active' : ''}`;
    dot.title = m.title;
    dot.onclick = () => showHeroMovie(idx);
    dotsBox.appendChild(dot);
  });
}

function showHeroMovie(idx) {
  const list = STATE.heroMovies;
  if (!list || !list.length) return;
  if (idx < 0) idx = list.length - 1;
  if (idx >= list.length) idx = 0;
  STATE.heroIndex = idx;

  const f = list[idx];
  const b = document.getElementById('heroBanner');
  if (!b) return;

  const fallbackBackdrop = getMovieFallbackBackdrop(f);
  const fallbackPoster   = getMovieFallbackPoster(f);

  // 1. Immediately apply bespoke local SVG backdrop (Guaranteed to NEVER be a grey box!)
  b.style.backgroundImage = `url('${fallbackBackdrop}')`;

  // 2. If valid remote TMDB backdrop exists, preload and upgrade smoothly
  if (f.backdrop_path && !f.backdrop_path.includes('null') && !f.backdrop_path.includes('placeholder')) {
    const preloader = new Image();
    preloader.onload = () => {
      if (STATE.heroIndex === idx) {
        b.style.backgroundImage = `url('${f.backdrop_path}')`;
      }
    };
    preloader.src = f.backdrop_path;
  }

  // 3. Update Poster Thumbnail
  const thumb = document.getElementById('heroPosterThumb');
  if (thumb) {
    thumb.src = f.poster_path || fallbackPoster;
    thumb.onerror = () => { thumb.onerror = null; thumb.src = fallbackPoster; };
  }

  // 4. Update Meta & Text
  document.getElementById('heroTitle').textContent    = f.title;
  document.getElementById('heroRating').innerHTML     = `<svg class="cpx-icon cpx-icon-xs star-gold" style="vertical-align:middle; margin-right:3px;"><use href="#icon-star"></use></svg> <strong>${f.rating}/10</strong> (${f.votes_count ? (f.votes_count/1000).toFixed(1)+'K' : '20K'} Votes)`;
  document.getElementById('heroCert').textContent     = f.certification || 'UA 16+';
  document.getElementById('heroLang').textContent     = f.language;
  document.getElementById('heroRuntime').textContent  = `${f.runtime} mins`;
  const genresEl = document.getElementById('heroGenres');
  if (genresEl) genresEl.textContent = (f.genres_list || []).join(', ') || 'Action, Drama';
  document.getElementById('heroOverview').textContent = f.overview;

  document.getElementById('heroBtnBook').onclick    = () => bookMovieNow(f.id);
  document.getElementById('heroBtnTrailer').onclick = () => watchTrailer(f.trailer_url, f.title);

  // 5. Update dots active class
  document.querySelectorAll('#heroDots .hero-dot').forEach((dot, dIdx) => {
    dot.classList.toggle('active', dIdx === idx);
  });
}

function prevHeroMovie() {
  showHeroMovie((STATE.heroIndex || 0) - 1);
}
window.prevHeroMovie = prevHeroMovie;

function nextHeroMovie() {
  showHeroMovie((STATE.heroIndex || 0) + 1);
}
window.nextHeroMovie = nextHeroMovie;

function renderGrid(movies) {
  const grid = document.getElementById('movieGrid');
  if (!grid) return;
  grid.innerHTML = '';
  if (!movies.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:3.5rem;background:#fff;border-radius:10px;border:1px solid #e2e8f0;">
      <p style="font-weight:800;color:var(--text-dark);font-size:1.15rem;margin-bottom:0.4rem;">No matching movies found</p>
      <p style="font-size:0.85rem;color:#64748b;margin-bottom:1rem;">Try relaxing your language or genre filter criteria.</p>
      <button class="btn-bms-red" onclick="clearFilters()">Reset Filters</button></div>`;
    return;
  }
  movies.forEach(m => {
    const card = document.createElement('div');
    card.className = 'bms-movie-card';
    const genres = (m.genres_list || []).slice(0, 2).join(', ');
    const fb = getMovieFallbackPoster(m);
    card.innerHTML = `
      <div class="bms-poster-box" onclick="openMovieDetail(${m.id})">
        <img class="bms-poster" src="${m.poster_path || fb}" alt="${m.title}" loading="lazy"
             onerror="this.onerror=null;this.src='${fb}'">
        <div class="bms-rating-strip">
          <div style="display:flex; align-items:center; gap:3px;"><svg class="cpx-icon cpx-icon-xs star-gold"><use href="#icon-star"></use></svg> <span>${m.rating}/10</span></div>
          <div class="votes">${m.votes_count ? (m.votes_count/1000).toFixed(1)+'K' : '20K'} votes</div>
        </div>
      </div>
      <div class="bms-card-info">
        <h3 class="bms-card-title" onclick="openMovieDetail(${m.id})" title="${m.title}">${m.title}</h3>
        <div class="bms-card-cert">${m.certification || 'UA'} • ${m.language}</div>
        <div class="bms-card-genres">${genres}</div>
        <button class="bms-card-btn" onclick="bookMovieNow(${m.id})">${m.is_now_showing ? 'Book Tickets' : 'Explore'}</button>
      </div>`;
    grid.appendChild(card);
  });
}

// ==============================================================================
// SECTION 2 – MOVIE DETAIL + SHOWTIMES
// ==============================================================================
async function bookMovieNow(movieId) {
  await openMovieDetail(movieId);
  setTimeout(() => {
    const tc = document.getElementById('theatersContainer');
    if (tc) tc.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    if (tc) {
      tc.style.transition = 'box-shadow 0.3s';
      tc.style.boxShadow  = '0 0 0 3px var(--cpx-red)';
      setTimeout(() => { tc.style.boxShadow = 'none'; }, 1200);
    }
  }, 450);
}

async function openMovieDetail(movieId) {
  try {
    const res = await fetch(`/api/movies/${movieId}`);
    const data = await res.json();
    if (!data.success) return;
    const m = data.movie;
    STATE.movie = m;

    document.getElementById('modalMovieTitle').textContent = m.title;
    document.getElementById('detailTitle').textContent      = m.title;
    document.getElementById('detailRating').innerHTML       = `<svg class="cpx-icon cpx-icon-sm star-gold" style="vertical-align:middle; margin-right:3px;"><use href="#icon-star"></use></svg>${m.rating}/10`;
    document.getElementById('detailCert').textContent       = m.certification || 'UA 16+';
    document.getElementById('detailRuntime').textContent    = `${m.runtime} mins`;
    document.getElementById('detailLang').textContent       = m.language;
    document.getElementById('detailGenres').textContent     = (m.genres_list || []).join(' • ');
    document.getElementById('detailOverview').textContent   = m.overview;

    const poster = document.getElementById('detailPoster');
    poster.src = m.poster_path;
    poster.onerror = () => { poster.onerror = null; poster.src = getMovieFallbackPoster(m); };

    document.getElementById('detailBtnTrailer').onclick = () => watchTrailer(m.trailer_url, m.title);

    buildDateScroller();
    loadShows(m.id, STATE.date);
    openModal('movieDetailModal');
  } catch (err) {
    console.error("openMovieDetail error:", err);
  }
}

function buildDateScroller() {
  const scroller = document.getElementById('dateScroller');
  if (!scroller) return;
  scroller.innerHTML = '';
  const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const today = new Date();

  for (let i = 0; i < 5; i++) {
    const d = new Date();
    d.setDate(today.getDate() + i);
    const dateStr = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;

    const btn = document.createElement('button');
    btn.className = `date-btn ${i === 0 ? 'active' : ''}`;
    btn.innerHTML = `<div class="date-day">${i === 0 ? 'TODAY' : days[d.getDay()]}</div>
                     <div class="date-num">${d.getDate()} ${months[d.getMonth()]}</div>`;
    btn.onclick = () => {
      document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      STATE.date = dateStr;
      if (STATE.movie) loadShows(STATE.movie.id, dateStr);
    };
    scroller.appendChild(btn);
  }
}

async function loadShows(movieId, date) {
  const container = document.getElementById('theatersContainer');
  if (!container) return;
  container.innerHTML = '<div style="text-align:center;padding:2rem;color:#64748b;">Loading cinema auditoriums...</div>';

  try {
    const res = await fetch(`/api/movies/${movieId}/shows?date=${date}&city=${encodeURIComponent(STATE.city)}`);
    const data = await res.json();
    container.innerHTML = '';

    if (!data.success || !data.theaters || !data.theaters.length) {
      container.innerHTML = `<div style="text-align:center;padding:2.5rem;background:#f8fafc;border-radius:8px;border:1px dashed #cbd5e1;">
        <p style="font-weight:700;color:var(--text-dark);margin-bottom:0.25rem;">No showtimes scheduled for this date</p>
        <p style="font-size:0.8rem;color:#64748b;">Try selecting another date or switching city.</p>
      </div>`;
      return;
    }

    data.theaters.forEach(t => {
      const card = document.createElement('div');
      card.className = 'theater-card';
      let showsHtml = '';
      t.shows.forEach(s => {
        showsHtml += `
          <button class="showtime-pill" onclick="openSeatMap(${s.show_id})" title="${s.screen_name} (${s.screen_type})">
            <div>${s.show_time}</div>
            <div style="font-size:0.65rem;opacity:0.85;">${s.screen_type || 'Dolby Atmos'}</div>
          </button>`;
      });

      card.innerHTML = `
        <div class="theater-name">${t.theater_name}</div>
        <div class="theater-address">${t.address}</div>
        <div class="shows-row">${showsHtml}</div>`;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<div style="color:#ef4444;text-align:center;padding:1.5rem;">Could not load showtimes.</div>';
  }
}

// ==============================================================================
// SECTION 3 – SEAT SELECTION & HOLD TIMER
// ==============================================================================
async function openSeatMap(showId) {
  if (!currentUser()) {
    toast('Please sign in to select seats and reserve tickets.', 'error');
    closeModal('movieDetailModal');
    switchView('auth');
    return;
  }

  STATE.seats = [];
  STATE.token = null;
  clearInterval(STATE.timer);
  updateSeatBar();

  try {
    const res = await fetch(`/api/shows/${showId}/seats`);
    const data = await res.json();
    if (!data.success) return;
    STATE.show = data.data.show;

    document.getElementById('seatmapMovieTitle').textContent = STATE.show.movie_title;
    document.getElementById('seatmapMeta').textContent =
      `${STATE.show.theater_name} • ${STATE.show.screen_name} • ${STATE.show.show_date} at ${STATE.show.show_time}`;

    renderSeatMap(data.data.seats);
    closeModal('movieDetailModal');
    openModal('seatmapModal');
  } catch (err) {
    toast('Could not load auditorium seat map.', 'error');
  }
}

function renderSeatMap(seatList) {
  const container = document.getElementById('seatRowsContainer');
  if (!container) return;
  container.innerHTML = '';

  const tiers = [
    { key: 'RECLINER', name: 'Recliner (Luxe Comfort)', price: STATE.show.price_vip, rows: ['A', 'B'], cols: 10 },
    { key: 'PRIME',    name: 'Prime (Optimal View)',    price: STATE.show.price_premium, rows: ['C', 'D', 'E'], cols: 12 },
    { key: 'CLASSIC',  name: 'Classic (Standard)',      price: STATE.show.price_executive, rows: ['F', 'G', 'H'], cols: 12 }
  ];

  const seatMap = {};
  seatList.forEach(s => { seatMap[s.seat_label] = s; });

  tiers.forEach(t => {
    const title = document.createElement('div');
    title.className = 'bms-tier-title';
    title.innerHTML = `<span>${t.name}</span><strong>${rs(t.price)}</strong>`;
    container.appendChild(title);

    t.rows.forEach(r => {
      const rowDiv = document.createElement('div');
      rowDiv.className = 'seat-row';
      rowDiv.innerHTML = `<div class="seat-row-label">${r}</div>`;

      for (let c = 1; c <= t.cols; c++) {
        if (t.cols === 12 && c === 7) {
          const aisle = document.createElement('div');
          aisle.className = 'seat-aisle-gap';
          rowDiv.appendChild(aisle);
        }

        const label = `${r}${c}`;
        const s = seatMap[label] || { status: 'AVAILABLE' };
        const btn = document.createElement('button');
        btn.className = `seat-btn ${s.status.toLowerCase()}`;
        btn.textContent = c;
        btn.dataset.seat = label;
        btn.dataset.tier = t.key;
        btn.disabled = s.status !== 'AVAILABLE';

        if (s.status === 'AVAILABLE') {
          btn.onclick = handleSeatClick;
        }
        rowDiv.appendChild(btn);
      }
      container.appendChild(rowDiv);
    });
  });
}

function handleSeatClick(e) {
  const btn = e.currentTarget;
  const seat = btn.dataset.seat;
  const idx = STATE.seats.indexOf(seat);

  if (idx > -1) {
    STATE.seats.splice(idx, 1);
    btn.classList.remove('selected');
  } else {
    if (STATE.seats.length >= 10) {
      toast('Maximum 10 tickets can be reserved at once.', 'error');
      return;
    }
    STATE.seats.push(seat);
    btn.classList.add('selected');
  }
  updateSeatBar();
}

function ticketSubtotal() {
  if (!STATE.show) return 0;
  return STATE.seats.reduce((sum, s) => {
    const row = s[0].toUpperCase();
    if (['A', 'B'].includes(row)) return sum + STATE.show.price_vip;
    if (['C', 'D', 'E'].includes(row)) return sum + STATE.show.price_premium;
    return sum + STATE.show.price_executive;
  }, 0);
}

function updateSeatBar() {
  const pills = document.getElementById('selectedSeatsPills');
  const priceEl = document.getElementById('selectedSeatsPrice');
  const btn = document.getElementById('btnProceedCheckout');
  if (!pills || !priceEl || !btn) return;

  if (!STATE.seats.length) {
    pills.innerHTML = '<span style="color:#94a3b8;font-size:0.8rem;">Tap a seat to select</span>';
    priceEl.textContent = '₹0';
    btn.disabled = true;
    btn.style.opacity = '0.45';
    btn.textContent = 'Select Seats';
  } else {
    pills.innerHTML = STATE.seats.map(s => `<span class="seat-pill-tag">${s}</span>`).join('');
    priceEl.textContent = rs(ticketSubtotal());
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.textContent = `Pay ${rs(ticketSubtotal())} & Checkout`;
  }
}

// ==============================================================================
// SECTION 4 – CHECKOUT & RESERVATION HOLD
// ==============================================================================
async function proceedToCheckout() {
  if (!STATE.seats.length || !STATE.show) return;

  try {
    const res = await fetch(`/api/shows/${STATE.show.id}/reserve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat_labels: STATE.seats, reservation_token: STATE.token })
    });
    const data = await res.json();
    if (!data.success) {
      toast(data.error || 'Seat hold conflict. Please choose another seat.', 'error');
      openSeatMap(STATE.show.id);
      return;
    }

    STATE.token = data.reservation_token;
    startHoldTimer(data.expires_in || 300);
    closeModal('seatmapModal');
    openCheckoutModal();
  } catch (err) {
    toast('Reservation request failed.', 'error');
  }
}

function startHoldTimer(seconds) {
  clearInterval(STATE.timer);
  STATE.timerSec = seconds;
  tickTimer();
  STATE.timer = setInterval(() => {
    STATE.timerSec--;
    if (STATE.timerSec <= 0) {
      clearInterval(STATE.timer);
      toast('Seat hold expired. Seats have been liberated.', 'error');
      releaseHeldSeats();
      closeModal('checkoutModal');
      if (STATE.show) openSeatMap(STATE.show.id);
    } else {
      tickTimer();
    }
  }, 1000);
}

function tickTimer() {
  const m = Math.floor(STATE.timerSec / 60);
  const s = STATE.timerSec % 60;
  const str = `${m}:${pad(s)}`;
  document.querySelectorAll('.reservation-timer-display').forEach(el => el.textContent = str);
}

function releaseHeldSeats() {
  if (STATE.show && STATE.token && STATE.seats.length) {
    fetch(`/api/shows/${STATE.show.id}/release`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seat_labels: STATE.seats, reservation_token: STATE.token })
    }).catch(() => {});
  }
}

async function loadSnackDefs() {
  try {
    const res = await fetch('/api/snacks');
    const data = await res.json();
    if (data.success) STATE.snackDefs = data.snacks || [];
  } catch {}
}

function openCheckoutModal() {
  const user = currentUser();
  if (user) prefillCheckoutForm(user);

  document.getElementById('checkoutMovieTitle').textContent = STATE.show.movie_title;
  document.getElementById('checkoutMeta').textContent =
    `${STATE.show.theater_name} • ${STATE.show.show_date} at ${STATE.show.show_time}`;
  document.getElementById('checkoutSeatsBadge').textContent =
    `${STATE.seats.length} Seat(s): ${STATE.seats.join(', ')}`;

  renderSnacks();
  recalcBill();
  openModal('checkoutModal');
}

function renderSnacks() {
  const container = document.getElementById('checkoutSnacksContainer');
  if (!container) return;
  container.innerHTML = '';
  STATE.snackDefs.forEach(s => {
    const qty = STATE.snacks[s.id] || 0;
    const card = document.createElement('div');
    card.className = 'bms-snack-card';
    card.innerHTML = `
      <img class="snack-img" src="${s.image_url}" alt="${s.name}" onerror="this.onerror=null;this.src='/static/posters/snack_fallback.svg'">
      <div style="flex-grow:1;">
        <div class="snack-title">${s.name}</div>
        <div style="font-size:0.75rem; color:#64748b;">${s.description || ''}</div>
        <div class="snack-price">${rs(s.price)}</div>
      </div>
      <div style="display:flex; align-items:center; gap:0.4rem;">
        <button type="button" class="btn-bms-red" style="padding:0.2rem 0.55rem; background:#e2e8f0; color:#334155;" onclick="changeSnack(${s.id}, -1)">-</button>
        <span style="font-weight:800; min-width:18px; text-align:center;">${qty}</span>
        <button type="button" class="btn-bms-red" style="padding:0.2rem 0.55rem;" onclick="changeSnack(${s.id}, 1)">+</button>
      </div>`;
    container.appendChild(card);
  });
}

function changeSnack(id, delta) {
  const cur = STATE.snacks[id] || 0;
  const nxt = Math.max(0, cur + delta);
  if (nxt === 0) delete STATE.snacks[id];
  else STATE.snacks[id] = nxt;
  renderSnacks();
  recalcBill();
}

function recalcBill() {
  const tSub = ticketSubtotal();
  let sTotal = 0;
  STATE.snackDefs.forEach(s => {
    const q = STATE.snacks[s.id] || 0;
    sTotal += q * s.price;
  });

  const convFee = Math.round((tSub + sTotal) * 0.05 * 100) / 100;
  const gst = Math.round(convFee * 0.18 * 100) / 100;
  const grand = Math.round((tSub + sTotal + convFee + gst) * 100) / 100;

  document.getElementById('billTicketSubtotal').textContent = rs(tSub);
  document.getElementById('billSnacksTotal').textContent    = rs(sTotal);
  document.getElementById('billConvenienceFee').textContent = rs(convFee);
  document.getElementById('billTaxes').textContent          = rs(gst);
  document.getElementById('billGrandTotal').textContent     = rs(grand);
  document.getElementById('payBtnAmount').textContent       = rs(grand);
}

function selectPaymentMethod(method, btn) {
  STATE.payMethod = method;
  document.querySelectorAll('.payment-tab-btn').forEach(b => b.style.background = '#64748b');
  btn.style.background = '#059669';
  document.getElementById('payFieldsUpi').style.display  = method === 'UPI' ? 'block' : 'none';
  document.getElementById('payFieldsCard').style.display = method === 'Card' ? 'block' : 'none';
}

// ==============================================================================
// SECTION 5 – PAYMENT PROCESSING & DIGITAL PASS GENERATION
// ==============================================================================
async function processPayment() {
  const name  = document.getElementById('custName')?.value.trim();
  const email = document.getElementById('custEmail')?.value.trim().toLowerCase();
  const phone = document.getElementById('custPhone')?.value.trim();

  if (!name || !email || !phone) {
    toast('Please fill all customer contact fields.', 'error');
    return;
  }

  const snacksArr = [];
  STATE.snackDefs.forEach(s => {
    const q = STATE.snacks[s.id];
    if (q > 0) snacksArr.push({ id: s.id, name: s.name, quantity: q, price: s.price });
  });

  const submitBtn = document.getElementById('btnSubmitPayment');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Processing Transaction...'; }

  try {
    const res = await fetch(`/api/shows/${STATE.show.id}/book`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seat_labels: STATE.seats,
        customer_name: name,
        customer_email: email,
        customer_phone: phone,
        payment_method: STATE.payMethod,
        reservation_token: STATE.token,
        snacks: snacksArr
      })
    });
    const data = await res.json();
    if (!data.success) {
      toast(data.error || 'Payment execution failed.', 'error');
      if (submitBtn) { submitBtn.disabled = false; recalcBill(); }
      return;
    }

    clearInterval(STATE.timer);
    linkBookingToUser(data.booking_ref);
    closeModal('checkoutModal');
    toast(`Booking Confirmed! Reference: ${data.booking_ref}`, 'success');
    refreshBookingBadge();
    showMTicket(data.booking_ref);
  } catch (err) {
    toast('Payment connection error.', 'error');
  } finally {
    if (submitBtn) { submitBtn.disabled = false; recalcBill(); }
  }
}

// ==============================================================================
// SECTION 6 – DIGITAL M-TICKET PASS & PRINT/DOWNLOAD
// ==============================================================================
async function showMTicket(ref) {
  try {
    const data = await fetch(`/api/bookings/${ref}`).then(r => r.json());
    if (!data.success) return;
    const t = data.booking;
    STATE.currentTicket = t;

    const poster = document.getElementById('ticketPoster');
    poster.src = t.poster_path;
    poster.onerror = () => { poster.onerror = null; poster.src = t.offline_poster_path || getMovieFallbackPoster({ title: t.movie_title }); };

    document.getElementById('ticketTitle').textContent   = t.movie_title;
    document.getElementById('ticketLang').textContent    = `${t.certification || 'UA 16+'} • ${t.language}`;
    document.getElementById('ticketRef').textContent     = t.booking_ref;
    document.getElementById('ticketDate').textContent    = `${t.show_date}  •  ${t.show_time}`;
    document.getElementById('ticketCinema').textContent  = `${t.theater_name} (${t.city || 'Bhubaneswar'})`;
    document.getElementById('ticketScreen').textContent  = t.screen_name;
    document.getElementById('ticketSeats').textContent   = t.seat_numbers;
    document.getElementById('ticketAmount').textContent  = rs(t.total_amount);
    document.getElementById('ticketHolder').textContent  = t.customer_name;
    document.getElementById('ticketQrContainer').innerHTML = buildQR(t.qr_data || t.booking_ref);

    document.getElementById('ticketBtnCancel').onclick = () => {
      closeModal('ticketModal');
      openCancelModal(t.booking_ref);
    };

    openModal('ticketModal');
  } catch (err) {
    console.error("showMTicket error:", err);
  }
}

function printMTicket() {
  const ticketEl = document.getElementById('printableTicket');
  if (!ticketEl) {
    window.print();
    return;
  }

  // Remove any previous print frame
  const oldFrame = document.getElementById('cpxPrintFrame');
  if (oldFrame) oldFrame.remove();

  // Create isolated single-page print iframe
  const frame = document.createElement('iframe');
  frame.id = 'cpxPrintFrame';
  frame.style.position = 'fixed';
  frame.style.right = '0';
  frame.style.bottom = '0';
  frame.style.width = '0';
  frame.style.height = '0';
  frame.style.border = 'none';
  frame.style.zIndex = '-9999';
  document.body.appendChild(frame);

  const doc = frame.contentWindow.document;
  doc.open();
  doc.write(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Cineplex Ticket - ${STATE.currentTicket ? STATE.currentTicket.booking_ref : 'Print'}</title>
      <style>
        @page {
          size: A4 portrait;
          margin: 1.2cm;
        }
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          -webkit-print-color-adjust: exact !important;
          print-color-adjust: exact !important;
        }
        html, body {
          background: #ffffff !important;
          color: #0f172a !important;
          width: 100%;
          height: auto;
          display: flex;
          justify-content: center;
          padding-top: 10px;
        }
        .bms-ticket-card {
          width: 440px;
          background: #ffffff;
          border: 2px solid #0f172a;
          border-radius: 12px;
          overflow: hidden;
          page-break-inside: avoid !important;
          page-break-after: avoid !important;
          page-break-before: avoid !important;
          break-inside: avoid !important;
        }
        .bms-ticket-top {
          background: #0f172a !important;
          color: #ffffff !important;
          padding: 1.15rem 1.25rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 3px solid #e11d48;
        }
        .bms-status-badge.confirmed {
          background: #ecfdf5 !important;
          color: #047857 !important;
          border: 1px solid #a7f3d0;
          padding: 0.2rem 0.6rem;
          border-radius: 99px;
          font-size: 0.72rem;
          font-weight: 800;
          text-transform: uppercase;
        }
        .bms-ticket-body {
          padding: 1.25rem;
        }
        .ticket-tear {
          position: relative;
          height: 1px;
          border-top: 2px dashed #cbd5e1;
          margin: 0.9rem 0;
        }
        .ticket-tear::before, .ticket-tear::after {
          content: "";
          position: absolute;
          top: -11px;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: #ffffff;
          border: 1px solid #0f172a;
        }
        .ticket-tear::before { left: -24px; }
        .ticket-tear::after  { right: -24px; }
      </style>
    </head>
    <body>
      ${ticketEl.outerHTML}
    </body>
    </html>
  `);
  doc.close();

  setTimeout(() => {
    frame.contentWindow.focus();
    frame.contentWindow.print();
    setTimeout(() => {
      if (frame.parentNode) frame.parentNode.removeChild(frame);
    }, 2000);
  }, 350);
}
window.printMTicket = printMTicket;

function downloadTicketPDF() {
  const t = STATE.currentTicket;
  if (!t || !t.booking_ref) {
    toast('No active ticket found to download.', 'error');
    return;
  }
  toast(`Generating official PDF for ${t.booking_ref}...`, 'info');
  const a = document.createElement('a');
  a.href = `/api/bookings/${t.booking_ref}/pdf`;
  a.download = `CINEPLEX_TICKET_${t.booking_ref}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
window.downloadTicketPDF = downloadTicketPDF;

function downloadTicketPass() {
  const t = STATE.currentTicket;
  if (!t) return;
  const content = `
================================================================================
CINEPLEX DIGITAL M-TICKET PASS
Your Movies. Your Moments.
================================================================================
Booking Reference: ${t.booking_ref}
Payment Reference: ${t.payment_ref || 'CONFIRMED'}
Status:            ${t.status}
--------------------------------------------------------------------------------
Movie:             ${t.movie_title} (${t.language})
Cinema / Theatre:  ${t.theater_name} (${t.city || 'Bhubaneswar'})
Auditorium:        ${t.screen_name}
Date & Showtime:   ${t.show_date} at ${t.show_time}
Reserved Seats:    ${t.seat_numbers}
--------------------------------------------------------------------------------
Customer Name:     ${t.customer_name}
Mobile / Email:    ${t.customer_phone} | ${t.customer_email}
Amount Paid:       ${rs(t.total_amount)} (${t.payment_method || 'UPI'})
Verification Code: ${t.qr_data || t.booking_ref}
================================================================================
* Present this digital receipt at turnstile gates for entry.
* Powered by SQLite Relational Architecture (3NF).
================================================================================
  `.trim();

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `CINEPLEX_PASS_${t.booking_ref}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  toast(`Pass downloaded for ${t.booking_ref}`, 'success');
}

// Procedural SVG QR Code Generator (Offline, no CDN dependencies)
function buildQR(text) {
  const SIZE = 128, MODS = 23, CELL = SIZE / MODS;
  let seed = 0;
  for (let i = 0; i < text.length; i++) seed = (seed * 31 + text.charCodeAt(i)) & 0x7fffffff;
  let rects = '';
  const isEye = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= MODS-7) || (r >= MODS-7 && c < 7);
  const eye = (ox, oy) => {
    for (let r = 0; r < 7; r++) for (let c = 0; c < 7; c++)
      if (r===0||r===6||c===0||c===6||(r>=2&&r<=4&&c>=2&&c<=4))
        rects += `<rect x="${(ox+c)*CELL}" y="${(oy+r)*CELL}" width="${CELL+.1}" height="${CELL+.1}" fill="#0f172a"/>`;
  };
  eye(0,0); eye(MODS-7,0); eye(0,MODS-7);
  let s = seed;
  for (let r = 0; r < MODS; r++) for (let c = 0; c < MODS; c++) {
    if (!isEye(r,c)) {
      s = (s * 1664525 + 1013904223) & 0x7fffffff;
      if (s % 3 === 0 || (r+c) % 4 === 0)
        rects += `<rect x="${c*CELL}" y="${r*CELL}" width="${CELL+.1}" height="${CELL+.1}" fill="#0f172a"/>`;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${SIZE} ${SIZE}" width="${SIZE}" height="${SIZE}">${rects}</svg>`;
}

// ==============================================================================
// SECTION 7 – CANCELLATION & SEAT RELEASE
// ==============================================================================
async function openCancelModal(ref) {
  STATE.cancelRef = ref;
  try {
    const data = await fetch(`/api/bookings/${ref}`).then(r => r.json());
    if (!data.success) return;
    const b = data.booking;

    if (b.status === 'CANCELLED') {
      showRefundReceipt(b);
      return;
    }

    document.getElementById('cancelMovieTitle').textContent   = b.movie_title;
    document.getElementById('cancelShowDetails').textContent  = `${b.theater_name} • ${b.show_date} at ${b.show_time}`;
    document.getElementById('cancelSeats').textContent        = b.seat_numbers;
    document.getElementById('cancelOriginalAmount').textContent = rs(b.total_amount);

    const fee = b.seats_count * 30.0;
    const refAmt = Math.max(0, b.total_amount - fee);
    document.getElementById('cancelFee').textContent          = `- ${rs(fee)}`;
    document.getElementById('cancelRefundAmount').textContent = rs(refAmt);

    openModal('cancelModal');
  } catch {}
}

async function confirmCancellation() {
  if (!STATE.cancelRef) return;
  const reason = document.getElementById('cancelReason')?.value || 'Change of plans';
  try {
    const res = await fetch(`/api/bookings/${STATE.cancelRef}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    const data = await res.json();
    if (!data.success) {
      toast(data.error || 'Cancellation request failed.', 'error');
      return;
    }

    closeModal('cancelModal');
    toast(`Ticket cancelled. Seats ${data.released_seats} released back to cinema.`, 'success');

    // Fetch refreshed booking record for summary modal
    const bData = await fetch(`/api/bookings/${STATE.cancelRef}`).then(r => r.json());
    if (bData.success) {
      showRefundReceipt(bData.booking);
    }
    loadMyBookings();
    refreshBookingBadge();
  } catch {
    toast('Cancellation communication error.', 'error');
  }
}

function showRefundReceipt(b) {
  document.getElementById('afterCancelRef').textContent        = b.cancellation_ref || 'CAN-CONFIRMED';
  document.getElementById('afterCancelBookingRef').textContent = b.booking_ref;
  document.getElementById('afterCancelMovie').textContent      = b.movie_title;
  document.getElementById('afterCancelShow').textContent       = `${b.theater_name} (${b.show_date} at ${b.show_time})`;
  document.getElementById('afterCancelRefund').textContent     = rs(b.refund_amount || b.total_amount);
  document.getElementById('afterCancelSeats').textContent      = b.seat_numbers;
  document.getElementById('afterCancelDate').textContent       = b.cancelled_at || 'Just now';
  openModal('afterCancellationModal');
}

// ==============================================================================
// SECTION 8 – USER BOOKINGS VIEW
// ==============================================================================
async function loadMyBookings() {
  const container = document.getElementById('bookingsList');
  if (!container) return;
  container.innerHTML = '<div style="text-align:center;padding:2rem;color:#64748b;">Loading your reservations...</div>';

  try {
    const res = await fetch('/api/bookings');
    const data = await res.json();
    const all = data.bookings || [];
    const user = currentUser();
    const userRefs = getUserBookingRefs();

    // Match tickets by email, phone, or linked reference
    const myBookings = all.filter(b => {
      if (!user) return false;
      const emailMatch = b.customer_email && b.customer_email.toLowerCase() === user.email.toLowerCase();
      const phoneMatch = b.customer_phone && b.customer_phone === user.phone;
      const refMatch   = userRefs.includes(b.booking_ref);
      return emailMatch || phoneMatch || refMatch;
    });

    if (!myBookings.length) {
      container.innerHTML = `
        <div style="text-align:center; padding:3.5rem 1.5rem; background:#fff; border-radius:12px; border:1px dashed #cbd5e1;">
          <div style="margin-bottom:0.75rem;"><svg class="cpx-icon cpx-icon-xl" style="color:#94a3b8; width:48px; height:48px;"><use href="#icon-ticket"></use></svg></div>
          <p style="font-weight:900; color:var(--text-dark); font-size:1.15rem; margin:0 0 0.3rem 0;">No Movie Tickets Yet</p>
          <p style="font-size:0.85rem; color:#64748b; margin:0 0 1.25rem 0;">Explore blockbusters in Bhubaneswar and book with instant digital M-Tickets.</p>
          <button class="btn-bms-red" onclick="switchView('movies')">Browse Now Showing</button>
        </div>`;
      return;
    }

    container.innerHTML = '';
    myBookings.forEach(b => {
      const cancelled = b.status === 'CANCELLED';
      const fb = b.offline_poster_path || getMovieFallbackPoster({ title: b.movie_title });
      const item = document.createElement('div');
      item.className = 'bms-booking-item';
      item.dataset.status = b.status;
      item.style.cssText = 'display:flex; gap:1.25rem; align-items:center; padding:1.2rem; background:#fff; border:1px solid #e2e8f0; border-radius:12px; box-shadow:var(--shadow-sm); flex-wrap:wrap;';
      item.innerHTML = `
        <img src="${b.poster_path}" alt="${b.movie_title}"
             style="width:68px; height:98px; border-radius:6px; object-fit:cover; flex-shrink:0;"
             onerror="this.onerror=null;this.src='${fb}'">
        <div style="flex-grow:1; min-width:240px;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.35rem;">
            <span class="bms-status-badge ${cancelled ? 'cancelled' : 'confirmed'}">
              ${cancelled ? 'Cancelled' : 'Confirmed'}
            </span>
            <span style="font-size:0.75rem; color:#64748b;">Ref: <strong style="color:var(--text-dark);">${b.booking_ref}</strong></span>
          </div>
          <h3 style="font-size:1.05rem; font-weight:900; color:var(--text-dark); margin:0 0 0.25rem 0;">${b.movie_title}</h3>
          <div style="font-size:0.8rem; color:#475569; margin-bottom:0.25rem;">
            ${b.theater_name} • <strong>${b.show_date} at ${b.show_time}</strong> (${b.screen_name})
          </div>
          <div style="font-size:0.82rem;">
            Seats: <strong style="color:var(--cpx-red);">${b.seat_numbers}</strong> • Total Paid: <strong>${rs(b.total_amount)}</strong> (${b.payment_method || 'UPI'})
          </div>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.4rem; min-width:130px;">
          ${cancelled
            ? `<button class="btn-bms-red" style="background:#f1f5f9; color:#334155; font-size:0.75rem;" onclick="openCancelModal('${b.booking_ref}')">Refund Receipt</button>`
            : `<button class="btn-bms-red" style="font-size:0.75rem;" onclick="showMTicket('${b.booking_ref}')">View M-Ticket</button>
               <button class="btn-bms-red" style="background:#fff; border:1px solid #ef4444; color:#ef4444; font-size:0.75rem;" onclick="openCancelModal('${b.booking_ref}')">Cancel</button>`
          }
        </div>`;
      container.appendChild(item);
    });
  } catch {
    container.innerHTML = '<div style="color:#ef4444;text-align:center;padding:1.5rem;">Could not load bookings.</div>';
  }
}

function filterBookings(status, btn) {
  document.querySelectorAll('.my-bookings-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.bms-booking-item').forEach(el => {
    if (status === 'ALL') el.style.display = 'flex';
    else el.style.display = el.dataset.status === status ? 'flex' : 'none';
  });
}

async function refreshBookingBadge() {
  const badge = document.getElementById('navBookingsCount');
  if (!badge) return;
  const user = currentUser();
  if (!user) { badge.style.display = 'none'; return; }
  try {
    const res = await fetch('/api/bookings');
    const data = await res.json();
    const count = (data.bookings || []).filter(b => b.customer_email && b.customer_email.toLowerCase() === user.email.toLowerCase() && b.status === 'CONFIRMED').length;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'inline-block' : 'none';
  } catch {}
}

function formatTrailerEmbedUrl(rawUrl) {
  if (!rawUrl) return '';
  if (rawUrl.includes('/embed/')) return rawUrl;
  const ytMatch = rawUrl.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([\w-]{11})/);
  if (ytMatch && ytMatch[1]) {
    return `https://www.youtube.com/embed/${ytMatch[1]}?autoplay=1&rel=0`;
  }
  return rawUrl;
}

function watchTrailer(url, title) {
  const modal = document.getElementById('trailerModal');
  const frame = document.getElementById('trailerFrame');
  const titleEl = document.getElementById('trailerModalTitle');
  if (titleEl) titleEl.textContent = `${title || 'Movie'} - Official Trailer & Teaser`;

  const embedUrl = formatTrailerEmbedUrl(url);

  if (embedUrl) {
    if (frame) {
      frame.style.display = 'block';
      frame.src = embedUrl;
    }
    const fbBox = document.getElementById('trailerFallbackBox');
    if (fbBox) fbBox.style.display = 'none';
    openModal('trailerModal');
  } else {
    const slug = getMovieSlug(title);
    const backdrop = `/static/posters/${slug}_backdrop.svg`;
    if (frame) frame.style.display = 'none';
    let fbBox = document.getElementById('trailerFallbackBox');
    if (!fbBox) {
      fbBox = document.createElement('div');
      fbBox.id = 'trailerFallbackBox';
      const container = frame ? frame.parentElement : modal;
      if (container) container.appendChild(fbBox);
    }
    fbBox.style.cssText = `display:flex; flex-direction:column; align-items:center; justify-content:center; position:absolute; inset:0; background:linear-gradient(rgba(15,23,42,0.85), rgba(15,23,42,0.95)), url('${backdrop}') center/cover; color:#fff; padding:2rem; text-align:center;`;
    fbBox.innerHTML = `
      <div style="margin-bottom:0.75rem;"><svg class="cpx-icon" style="color:var(--cpx-red); width:52px; height:52px;"><use href="#icon-film"></use></svg></div>
      <h3 style="font-size:1.4rem; font-weight:900; margin-bottom:0.5rem;">${title || 'Movie'} Official Preview</h3>
      <p style="font-size:0.9rem; color:#cbd5e1; max-width:480px; margin-bottom:1.25rem;">
        Official cinema preview reel &amp; verified showcase active in Bhubaneswar theatres.
      </p>
      <button class="btn-bms-red" onclick="closeTrailer(); if(STATE.movie) bookMovieNow(STATE.movie.id);" style="padding:0.6rem 1.4rem; display:inline-flex; align-items:center; gap:0.4rem;">
        <svg class="cpx-icon cpx-icon-sm"><use href="#icon-ticket"></use></svg> Book Tickets Now
      </button>
    `;
    openModal('trailerModal');
  }
}

function closeTrailer() {
  const frame = document.getElementById('trailerFrame');
  if (frame) frame.src = '';
  const fbBox = document.getElementById('trailerFallbackBox');
  if (fbBox) fbBox.style.display = 'none';
  closeModal('trailerModal');
}

async function triggerTMDBSync() {
  toast('Initiating live TMDB movie poster sync...', 'info');
  try {
    const res = await fetch('/api/tmdb/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    if (data.success) {
      toast(data.message, 'success');
      fetchMovies();
      closeModal('tmdbConfigModal');
    }
  } catch {
    toast('TMDB API request failed. Local fallback retained.', 'error');
  }
}

function validateNameInput(el) {
  el.value = el.value.replace(/^[^a-zA-Z]+/, '');
}
function validatePhoneInput(el) {
  let v = el.value.replace(/\D/g, '');
  if (v.startsWith('91') && v.length === 12) v = v.slice(2);
  el.value = v.slice(0, 10);
}

// ==============================================================================
// SECTION 9 – USER AUTHENTICATION & REST PROFILE SYNC
// ==============================================================================
function authGetUsers() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) {
      const defaultUsers = [
        {
          name: 'Sumit Kumar Panigrahi',
          email: 'sumit@example.com',
          phone: '8984378785',
          passwordHash: btoa('password123'),
          isAdmin: false,
          createdAt: new Date().toISOString()
        },
        {
          name: 'Cineplex Admin',
          email: 'admin@cineplex.com',
          phone: '9999999999',
          passwordHash: btoa('admin123'),
          isAdmin: true,
          createdAt: new Date().toISOString()
        }
      ];
      localStorage.setItem(AUTH_KEY, JSON.stringify(defaultUsers));
      return defaultUsers;
    }
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function authSaveUsers(users) {
  try { localStorage.setItem(AUTH_KEY, JSON.stringify(users)); } catch {}
}

function authGetSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
}

function authSaveSession(user) {
  try {
    if (user) localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    else       localStorage.removeItem(SESSION_KEY);
  } catch {}
}

function currentUser() {
  return authGetSession();
}

async function authInit() {
  authGetUsers();
  const user = currentUser();
  if (user) {
    renderNavLoggedIn(user);
  } else {
    renderNavLoggedOut();
  }

  // Zero-credential sync between browser and backend database
  try {
    const localUsers = authGetUsers();
    const res = await fetch('/api/auth/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ users: localUsers })
    });
    const data = await res.json();
    if (data.users && data.users.length) {
      authSaveUsers(data.users);
    }
  } catch {}
}

function renderNavLoggedIn(user) {
  const loginBtn  = document.getElementById('navLoginBtn');
  const userChip  = document.getElementById('navUserChip');
  const avatarEl  = document.getElementById('navUserAvatar');
  const nameEl    = document.getElementById('navUserName');
  const dropName  = document.getElementById('dropUserName');
  const dropEmail = document.getElementById('dropUserEmail');
  const accLink   = document.getElementById('subnavAccountLink');

  if (loginBtn)  loginBtn.style.display  = 'none';
  if (userChip)  userChip.style.display = 'flex';
  if (avatarEl)  avatarEl.textContent = (user.name || 'S')[0].toUpperCase();
  if (nameEl)    nameEl.textContent   = (user.name || '').split(' ')[0] || 'User';
  if (dropName)  dropName.textContent  = user.name;
  if (dropEmail) dropEmail.textContent = user.email;
  if (accLink)   accLink.textContent   = `Hi, ${(user.name || '').split(' ')[0]}`;
}

function renderNavLoggedOut() {
  const loginBtn = document.getElementById('navLoginBtn');
  const userChip = document.getElementById('navUserChip');
  const dropdown = document.getElementById('userDropdown');
  const accLink  = document.getElementById('subnavAccountLink');

  if (loginBtn) loginBtn.style.display = '';
  if (userChip) userChip.style.display = 'none';
  if (dropdown) dropdown.style.display = 'none';
  if (accLink)  accLink.textContent   = 'Account & Profile';
}

function toggleUserMenu() {
  const dd = document.getElementById('userDropdown');
  if (dd) dd.style.display = dd.style.display === 'block' ? 'none' : 'block';
}

function closeUserMenu() {
  const dd = document.getElementById('userDropdown');
  if (dd) dd.style.display = 'none';
}

document.addEventListener('click', e => {
  const chip = document.getElementById('navUserChip');
  const dd   = document.getElementById('userDropdown');
  if (dd && chip && !chip.contains(e.target) && !dd.contains(e.target)) {
    dd.style.display = 'none';
  }
});

function fillDemoLogin(type) {
  const emailInp = document.getElementById('pageLoginEmail') || document.getElementById('loginEmail');
  const pwdInp   = document.getElementById('pageLoginPassword') || document.getElementById('loginPassword');
  if (type === 'admin') {
    if (emailInp) emailInp.value = 'admin@cineplex.com';
    if (pwdInp)   pwdInp.value   = 'admin123';
    toast('Admin credentials loaded (Cineplex Admin).', 'info');
  } else {
    if (emailInp) emailInp.value = 'sumit@example.com';
    if (pwdInp)   pwdInp.value   = 'password123';
    toast('Demo credentials loaded (Sumit Kumar Panigrahi).', 'info');
  }
}

function togglePwd(inputId, iconEl) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    if (iconEl) iconEl.innerHTML = '<svg class="cpx-icon cpx-icon-sm" style="color:#64748b;"><use href="#icon-eye-off"></use></svg>';
  } else {
    inp.type = 'password';
    if (iconEl) iconEl.innerHTML = '<svg class="cpx-icon cpx-icon-sm" style="color:#64748b;"><use href="#icon-eye"></use></svg>';
  }
}

function switchAuthTab(tab) {
  const loginForm    = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const tabLogin     = document.getElementById('tabLogin');
  const tabRegister  = document.getElementById('tabRegister');
  const title        = document.getElementById('authModalTitle');

  const activeStyle   = { color: 'var(--cpx-red)', borderBottom: '2px solid var(--cpx-red)' };
  const inactiveStyle = { color: '#64748b',        borderBottom: '2px solid transparent' };

  if (tab === 'login') {
    if (loginForm)    loginForm.style.display    = '';
    if (registerForm) registerForm.style.display = 'none';
    if (tabLogin)     Object.assign(tabLogin.style,    activeStyle);
    if (tabRegister)  Object.assign(tabRegister.style, inactiveStyle);
    if (title)        title.textContent = 'Sign In';
  } else {
    if (loginForm)    loginForm.style.display    = 'none';
    if (registerForm) registerForm.style.display = '';
    if (tabLogin)     Object.assign(tabLogin.style,    inactiveStyle);
    if (tabRegister)  Object.assign(tabRegister.style, activeStyle);
    if (title)        title.textContent = 'Create Account';
  }
}

function switchAuthPageTab(tab) {
  const loginForm    = document.getElementById('authPageLoginForm');
  const registerForm = document.getElementById('authPageRegisterForm');
  const tabLogin     = document.getElementById('authPageTabLogin');
  const tabRegister  = document.getElementById('authPageTabRegister');

  if (tab === 'login') {
    if (loginForm)    loginForm.style.display    = 'block';
    if (registerForm) registerForm.style.display = 'none';
    if (tabLogin)     { tabLogin.style.color = 'var(--cpx-red)'; tabLogin.style.borderBottom = '3px solid var(--cpx-red)'; }
    if (tabRegister)  { tabRegister.style.color = '#64748b'; tabRegister.style.borderBottom = '3px solid transparent'; }
  } else {
    if (loginForm)    loginForm.style.display    = 'none';
    if (registerForm) registerForm.style.display = 'block';
    if (tabLogin)     { tabLogin.style.color = '#64748b'; tabLogin.style.borderBottom = '3px solid transparent'; }
    if (tabRegister)  { tabRegister.style.color = 'var(--cpx-red)'; tabRegister.style.borderBottom = '3px solid var(--cpx-red)'; }
  }
}

function handleRegistration(name, email, phone, password, confirm, isModal = false) {
  name  = (name || '').trim();
  email = (email || '').trim().toLowerCase();
  phone = (phone || '').trim();

  if (!name || !/^[A-Za-z]/.test(name)) {
    toast('Name must start with a letter.', 'error');
    return false;
  }
  if (!email || !email.includes('@') || !email.includes('.')) {
    toast('Please enter a valid email address.', 'error');
    return false;
  }
  const digits = phone.replace(/\D/g, '').slice(-10);
  if (digits.length !== 10) {
    toast('Phone number must be strictly 10 digits.', 'error');
    return false;
  }
  if (!password || password.length < 6) {
    toast('Password must be at least 6 characters long.', 'error');
    return false;
  }
  if (password !== confirm) {
    toast('Passwords do not match.', 'error');
    return false;
  }

  const users = authGetUsers();
  if (users.find(u => u.email === email)) {
    toast('An account with this email already exists. Please sign in.', 'error');
    return false;
  }

  const newUser = {
    name,
    email,
    phone: digits,
    passwordHash: btoa(password),
    isAdmin: email.includes('admin'),
    createdAt: new Date().toISOString()
  };
  users.push(newUser);
  authSaveUsers(users);

  fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, phone: digits, password_hash: btoa(password) })
  }).catch(() => {});

  const sessionUser = { name, email, phone: digits, isAdmin: newUser.isAdmin };
  authSaveSession(sessionUser);
  renderNavLoggedIn(sessionUser);

  if (isModal) closeModal('authModal');
  toast(`Welcome, ${name.split(' ')[0]}! Account created & synchronized.`, 'success');
  prefillCheckoutForm(sessionUser);
  refreshBookingBadge();
  if (document.getElementById('authView') && document.getElementById('authView').style.display !== 'none') {
    renderAuthPageView();
  }
  return true;
}

async function handleLogin(email, password, isModal = false) {
  email = (email || '').trim().toLowerCase();
  password = password || '';

  if (!email || !password) {
    toast('Please enter your email and password.', 'error');
    return false;
  }

  const users = authGetUsers();
  const user  = users.find(u => u.email === email);

  if (!user) {
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password_hash: btoa(password) })
      });
      const data = await res.json();
      if (data.success && data.user) {
        const syncedUser = {
          name: data.user.name,
          email: data.user.email,
          phone: data.user.phone,
          isAdmin: data.user.is_admin,
          passwordHash: btoa(password),
          createdAt: new Date().toISOString()
        };
        users.push(syncedUser);
        authSaveUsers(users);
        const sessionUser = { name: syncedUser.name, email: syncedUser.email, phone: syncedUser.phone, isAdmin: syncedUser.isAdmin };
        authSaveSession(sessionUser);
        renderNavLoggedIn(sessionUser);
        if (isModal) closeModal('authModal');
        toast(`Welcome back, ${syncedUser.name.split(' ')[0]}!`, 'success');
        prefillCheckoutForm(sessionUser);
        refreshBookingBadge();
        if (document.getElementById('authView') && document.getElementById('authView').style.display !== 'none') {
          renderAuthPageView();
        }
        return true;
      }
    } catch {}
    toast('No account found with this email. Please register.', 'error');
    return false;
  }

  if (user.passwordHash !== btoa(password)) {
    toast('Incorrect password. Please try again.', 'error');
    return false;
  }

  const sessionUser = { name: user.name, email: user.email, phone: user.phone, isAdmin: !!user.isAdmin };
  authSaveSession(sessionUser);
  renderNavLoggedIn(sessionUser);

  if (isModal) closeModal('authModal');
  toast(`Welcome back, ${user.name.split(' ')[0]}!`, 'success');

  prefillCheckoutForm(sessionUser);
  refreshBookingBadge();
  if (document.getElementById('authView') && document.getElementById('authView').style.display !== 'none') {
    renderAuthPageView();
  }
  return true;
}

function authRegister() {
  const name     = document.getElementById('regName')?.value;
  const email    = document.getElementById('regEmail')?.value;
  const phone    = document.getElementById('regPhone')?.value;
  const password = document.getElementById('regPassword')?.value;
  const confirm  = document.getElementById('regConfirm')?.value;
  handleRegistration(name, email, phone, password, confirm, true);
}

function authLogin() {
  const email    = document.getElementById('loginEmail')?.value;
  const password = document.getElementById('loginPassword')?.value;
  handleLogin(email, password, true);
}

function pageAuthRegister() {
  const name     = document.getElementById('pageRegName')?.value;
  const email    = document.getElementById('pageRegEmail')?.value;
  const phone    = document.getElementById('pageRegPhone')?.value;
  const password = document.getElementById('pageRegPassword')?.value;
  const confirm  = document.getElementById('pageRegConfirm')?.value;
  handleRegistration(name, email, phone, password, confirm, false);
}

function pageAuthLogin() {
  const email    = document.getElementById('pageLoginEmail')?.value;
  const password = document.getElementById('pageLoginPassword')?.value;
  handleLogin(email, password, false);
}

function authLogout() {
  authSaveSession(null);
  renderNavLoggedOut();
  closeUserMenu();
  toast('Signed out successfully.', 'info');
  refreshBookingBadge();
  if (document.getElementById('authView') && document.getElementById('authView').style.display !== 'none') {
    renderAuthPageView();
  }
}

function toggleEditProfile() {
  const sec = document.getElementById('editProfileSection');
  if (!sec) return;
  const isHidden = sec.style.display === 'none';
  sec.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    const user = currentUser();
    if (user) {
      const n = document.getElementById('editNameInput');
      const p = document.getElementById('editPhoneInput');
      if (n) n.value = user.name;
      if (p) p.value = user.phone;
    }
  }
}

function saveProfileChanges() {
  const user = currentUser();
  if (!user) return;
  const newName  = document.getElementById('editNameInput')?.value.trim();
  const newPhone = document.getElementById('editPhoneInput')?.value.trim();

  if (!newName || !/^[A-Za-z]/.test(newName)) {
    toast('Name must start with a letter.', 'error');
    return;
  }
  const digits = (newPhone || '').replace(/\D/g, '').slice(-10);
  if (digits.length !== 10) {
    toast('Phone must be 10 digits.', 'error');
    return;
  }

  const users = authGetUsers();
  const idx = users.findIndex(u => u.email === user.email);
  if (idx !== -1) {
    users[idx].name  = newName;
    users[idx].phone = digits;
    authSaveUsers(users);
  }

  user.name  = newName;
  user.phone = digits;
  authSaveSession(user);
  renderNavLoggedIn(user);

  toggleEditProfile();
  renderAuthPageView();
  toast('Profile updated and saved in browser storage.', 'success');
}

function prefillCheckoutForm(user) {
  user = user || currentUser();
  if (!user) return;
  const nameEl  = document.getElementById('custName');
  const emailEl = document.getElementById('custEmail');
  const phoneEl = document.getElementById('custPhone');
  if (nameEl)  nameEl.value  = user.name;
  if (emailEl) emailEl.value = user.email;
  if (phoneEl) phoneEl.value = user.phone;
}

function linkBookingToUser(bookingRef) {
  const user = currentUser();
  if (!user) return;
  try {
    const map = JSON.parse(localStorage.getItem(BOOKINGS_KEY) || '{}');
    if (!map[user.email]) map[user.email] = [];
    if (!map[user.email].includes(bookingRef)) {
      map[user.email].push(bookingRef);
    }
    localStorage.setItem(BOOKINGS_KEY, JSON.stringify(map));
  } catch {}
}

function getUserBookingRefs() {
  const user = currentUser();
  if (!user) return [];
  try {
    const map = JSON.parse(localStorage.getItem(BOOKINGS_KEY) || '{}');
    return map[user.email] || [];
  } catch {
    return [];
  }
}

async function renderAuthPageView() {
  const loggedOutSec = document.getElementById('authPageLoggedOut');
  const loggedInSec  = document.getElementById('authPageLoggedIn');
  const user = currentUser();

  if (!user) {
    if (loggedOutSec) loggedOutSec.style.display = 'block';
    if (loggedInSec)  loggedInSec.style.display  = 'none';
    return;
  }

  if (loggedOutSec) loggedOutSec.style.display = 'none';
  if (loggedInSec)  loggedInSec.style.display  = 'block';

  const av = document.getElementById('accAvatar');
  const fn = document.getElementById('accFullName');
  const em = document.getElementById('accEmail');
  const ph = document.getElementById('accPhone');
  const ct = document.getElementById('accCity');
  const rb = document.getElementById('accRoleBadge');

  if (av) av.textContent = (user.name || 'S')[0].toUpperCase();
  if (fn) fn.textContent = user.name;
  if (em) em.textContent = user.email;
  if (ph) {
    if (user.phone && user.phone.length >= 10) {
      ph.textContent = `+91 ••••• ••${user.phone.slice(-3)}`;
    } else {
      ph.textContent = 'Verified Customer';
    }
  }
  if (ct) ct.textContent = STATE.city;
  if (rb) rb.innerHTML = user.isAdmin ?
    '<span style="display:inline-flex; align-items:center; gap:4px;"><svg class="cpx-icon cpx-icon-xs" style="color:var(--cpx-red);"><use href="#icon-shield"></use></svg> Cineplex Administrator</span>' :
    'Standard Customer';

  const listWrap = document.getElementById('accUserBookingsList');
  if (listWrap) listWrap.innerHTML = '<div style="text-align:center;padding:1.5rem;color:#64748b;">Synchronizing tickets from database…</div>';

  try {
    const res = await fetch('/api/bookings');
    const data = await res.json();
    const allBookings = data.bookings || [];
    const userRefs = getUserBookingRefs();

    const myBookings = allBookings.filter(b => {
      const emailMatch = b.customer_email && b.customer_email.toLowerCase() === user.email.toLowerCase();
      const phoneMatch = b.customer_phone && b.customer_phone === user.phone;
      const refMatch   = userRefs.includes(b.booking_ref);
      return emailMatch || phoneMatch || refMatch;
    });

    const totalCount  = myBookings.length;
    const activeCount = myBookings.filter(b => b.status === 'CONFIRMED').length;
    const totalSpent  = myBookings.reduce((sum, b) => b.status === 'CONFIRMED' ? sum + Number(b.total_amount || 0) : sum, 0);

    const stTotal  = document.getElementById('statTotalBookings');
    const stActive = document.getElementById('statActiveTickets');
    const stSpent  = document.getElementById('statTotalSpent');

    if (stTotal)  stTotal.textContent  = totalCount;
    if (stActive) stActive.textContent = activeCount;
    if (stSpent)  stSpent.textContent  = rs(totalSpent);

    if (!listWrap) return;

    if (!myBookings.length) {
      listWrap.innerHTML = `
        <div style="text-align:center; padding:2.5rem 1rem; background:#f8fafc; border-radius:8px; border:1px dashed #cbd5e1;">
          <div style="margin-bottom:0.5rem;"><svg class="cpx-icon cpx-icon-lg" style="color:#94a3b8; width:40px; height:40px;"><use href="#icon-ticket"></use></svg></div>
          <p style="font-weight:800; color:var(--text-dark); margin:0 0 0.3rem 0;">No tickets booked yet</p>
          <p style="font-size:0.8rem; color:#64748b; margin:0 0 1rem 0;">Browse our movie selection and reserve your seats with instant M-Tickets.</p>
          <button class="btn-bms-red" style="font-size:0.85rem;" onclick="switchView('movies')">Browse Now Showing</button>
        </div>`;
      return;
    }

    listWrap.innerHTML = '';
    myBookings.forEach(b => {
      const cancelled = b.status === 'CANCELLED';
      const fb = b.offline_poster_path || getMovieFallbackPoster({ title: b.movie_title });
      const item = document.createElement('div');
      item.style.cssText = 'display:flex; gap:1rem; align-items:center; padding:0.9rem; background:#fff; border:1px solid #e2e8f0; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05);';
      item.innerHTML = `
        <img src="${b.poster_path}" alt="${b.movie_title}"
             style="width:58px; height:82px; border-radius:4px; object-fit:cover; flex-shrink:0;"
             onerror="this.onerror=null;this.src='${fb}'">
        <div style="flex-grow:1;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
            <span class="bms-status-badge ${cancelled ? 'cancelled' : 'confirmed'}" style="font-size:0.65rem; padding:0.15rem 0.45rem;">
              ${cancelled ? 'Cancelled' : 'Confirmed'}
            </span>
            <span style="font-size:0.75rem; color:#64748b;">Ref: <strong style="color:var(--text-dark);">${b.booking_ref}</strong></span>
          </div>
          <h4 style="font-size:0.95rem; font-weight:800; color:var(--text-dark); margin:0 0 0.2rem 0;">${b.movie_title}</h4>
          <div style="font-size:0.75rem; color:#475569; margin-bottom:0.2rem;">
            ${b.theater_name} • <strong>${b.show_date} at ${b.show_time}</strong>
          </div>
          <div style="font-size:0.78rem;">
            Seats: <strong style="color:var(--cpx-red);">${b.seat_numbers}</strong> • Paid: <strong>${rs(b.total_amount)}</strong>
          </div>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.35rem; min-width:110px;">
          ${cancelled
            ? `<button class="btn-bms-red" style="background:#f1f5f9; color:#334155; font-size:0.72rem; padding:0.4rem 0.6rem;" onclick="openCancelModal('${b.booking_ref}')">Refund Receipt</button>`
            : `<button class="btn-bms-red" style="font-size:0.72rem; padding:0.4rem 0.6rem;" onclick="showMTicket('${b.booking_ref}')">View M-Ticket</button>
               <button class="btn-bms-red" style="background:#fff; border:1px solid #ef4444; color:#ef4444; font-size:0.72rem; padding:0.4rem 0.6rem;" onclick="openCancelModal('${b.booking_ref}')">Cancel</button>`
          }
        </div>`;
      listWrap.appendChild(item);
    });
  } catch {
    if (listWrap) listWrap.innerHTML = '<div style="color:#ef4444; text-align:center; padding:1.5rem;">Could not load synchronized tickets.</div>';
  }
}

// ==============================================================================
// SECTION 10 – ADMIN DASHBOARD & EVALUATOR DBMS VIVA CONSOLE
// ==============================================================================
function initAdminView() {
  refreshAdminData();
  loadDbmsPresets();
  loadAdminMovies();
  loadAdminTheaters();
  loadAdminShows();
  loadAdminBookings();
  loadAdminCancellations();
  loadAdminUsers();
}

async function refreshAdminData() {
  try {
    const res = await fetch('/api/admin/stats');
    const data = await res.json();
    if (data.success && data.metrics) {
      const m = data.metrics;
      document.getElementById('admStatRevenue').textContent = rs(m.net_revenue);
      document.getElementById('admStatTickets').textContent = m.total_tickets_sold;
      document.getElementById('admStatTheaters').textContent = m.total_theaters;
      document.getElementById('admStatMovies').textContent = `${m.total_movies} (${m.now_showing_movies} Showing)`;
      document.getElementById('admStatShows').textContent = m.total_shows.toLocaleString();
      document.getElementById('admStatCancellations').textContent = m.total_cancellations;
    }
  } catch (err) {
    console.error("refreshAdminData error:", err);
  }
}

function switchAdminTab(tab) {
  const sections = ['dbms', 'movies', 'theaters', 'shows', 'bookings', 'cancellations', 'users'];
  sections.forEach(s => {
    const btn = document.getElementById(`admTabBtn${s.charAt(0).toUpperCase() + s.slice(1)}`);
    const sec = document.getElementById(`admSection${s.charAt(0).toUpperCase() + s.slice(1)}`);
    if (btn) {
      btn.style.color = s === tab ? 'var(--cpx-red)' : '#64748b';
      btn.style.borderBottom = s === tab ? '3px solid var(--cpx-red)' : '3px solid transparent';
    }
    if (sec) sec.style.display = s === tab ? 'block' : 'none';
  });

  if (tab === 'movies') loadAdminMovies();
  if (tab === 'theaters') loadAdminTheaters();
  if (tab === 'shows') loadAdminShows();
  if (tab === 'bookings') loadAdminBookings();
  if (tab === 'cancellations') loadAdminCancellations();
  if (tab === 'users') loadAdminUsers();
}

// ── DBMS Live Viva Console ───────────────────────────────────────────────────
let DBMS_PRESETS = [];

async function loadDbmsPresets() {
  const container = document.getElementById('dbmsPresetButtons');
  if (!container) return;
  try {
    const res = await fetch('/api/dbms/demonstrations');
    const data = await res.json();
    if (data.success && data.demonstrations) {
      DBMS_PRESETS = data.demonstrations;
      container.innerHTML = '';
      data.demonstrations.forEach((d, idx) => {
        const btn = document.createElement('button');
        btn.className = `sql-demo-btn ${idx === 0 ? 'active' : ''}`;
        btn.innerHTML = `<div style="font-weight:800; font-size:0.82rem; margin-bottom:2px;">${d.title}</div>
                         <div style="font-size:0.72rem; color:#64748b; line-height:1.3;">${d.description}</div>`;
        btn.onclick = () => {
          document.querySelectorAll('.sql-demo-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          document.getElementById('sqlConsoleInput').value = d.sql.trim();
          executeAdminSqlQuery();
        };
        container.appendChild(btn);
      });

      // Populate first query by default
      if (data.demonstrations.length > 0) {
        document.getElementById('sqlConsoleInput').value = data.demonstrations[0].sql.trim();
        executeAdminSqlQuery();
      }
    }
  } catch (err) {
    console.error("loadDbmsPresets error:", err);
  }
}

async function executeAdminSqlQuery() {
  const query = document.getElementById('sqlConsoleInput')?.value.trim();
  const statusEl = document.getElementById('sqlExecutionStatus');
  const table = document.getElementById('sqlResultTable');
  if (!query || !table) return;

  if (statusEl) statusEl.textContent = 'Executing query...';

  try {
    const res = await fetch('/api/admin/sql-console', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await res.json();

    if (!data.success) {
      if (statusEl) statusEl.innerHTML = '<span style="color:#ef4444; font-weight:700;">Query Error</span>';
      table.innerHTML = `<thead><tr><th>Error Output</th></tr></thead><tbody><tr><td style="color:#ef4444; padding:1.25rem;">${data.error}</td></tr></tbody>`;
      return;
    }

    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#059669; font-weight:700;">Executed in ${data.execution_time_ms} ms (${data.count} rows returned)</span>`;
    }

    let thead = '<tr>';
    (data.columns || []).forEach(col => { thead += `<th>${col}</th>`; });
    thead += '</tr>';

    let tbody = '';
    if (!data.rows || !data.rows.length) {
      tbody = `<tr><td colspan="${data.columns.length || 1}" style="text-align:center; color:#64748b; padding:1.5rem;">Query executed successfully with 0 rows returned.</td></tr>`;
    } else {
      data.rows.forEach(r => {
        tbody += '<tr>';
        (data.columns || []).forEach(col => {
          const val = r[col];
          tbody += `<td>${val !== null && val !== undefined ? val : '<span style="color:#94a3b8;">NULL</span>'}</td>`;
        });
        tbody += '</tr>';
      });
    }

    table.innerHTML = `<thead>${thead}</thead><tbody>${tbody}</tbody>`;
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Network Error';
  }
}

function clearAdminSqlConsole() {
  const input = document.getElementById('sqlConsoleInput');
  if (input) input.value = '';
  const statusEl = document.getElementById('sqlExecutionStatus');
  if (statusEl) statusEl.textContent = '';
}

// ── Admin Movie Management ────────────────────────────────────────────────────
function toggleAddMovieForm() {
  const f = document.getElementById('admAddMovieForm');
  if (f) f.style.display = f.style.display === 'none' ? 'block' : 'none';
}

async function submitNewMovie() {
  const title = document.getElementById('admNewTitle')?.value.trim();
  const language = document.getElementById('admNewLanguage')?.value.trim() || 'Hindi';
  const certification = document.getElementById('admNewCert')?.value.trim() || 'UA 16+';
  const runtime = parseInt(document.getElementById('admNewRuntime')?.value || '150');
  const rating = parseFloat(document.getElementById('admNewRating')?.value || '8.8');
  const overview = document.getElementById('admNewOverview')?.value.trim() || 'Exciting new blockbuster release.';

  if (!title) { toast('Please enter a movie title.', 'error'); return; }

  try {
    const res = await fetch('/api/admin/movies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, language, certification, runtime, rating, overview, is_now_showing: 1 })
    });
    const data = await res.json();
    if (data.success) {
      toast(data.message, 'success');
      toggleAddMovieForm();
      loadAdminMovies();
      fetchMovies();
      refreshAdminData();
    }
  } catch {
    toast('Could not create movie.', 'error');
  }
}

async function loadAdminMovies() {
  const tbody = document.getElementById('admTableMoviesBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/admin/movies');
    const data = await res.json();
    if (data.success && data.movies) {
      tbody.innerHTML = '';
      data.movies.forEach(m => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${m.id}</td>
          <td><img src="${m.poster_path}" style="width:36px; height:50px; border-radius:3px; object-fit:cover;" onerror="this.onerror=null;this.src=getMovieFallbackPoster(m)"></td>
          <td><strong>${m.title}</strong></td>
          <td>${m.language}</td>
          <td><span style="display:inline-flex; align-items:center; gap:3px;"><svg class="cpx-icon cpx-icon-xs star-gold"><use href="#icon-star"></use></svg> ${m.rating}</span></td>
          <td><span class="bms-status-badge ${m.is_now_showing ? 'confirmed' : 'cancelled'}">${m.is_now_showing ? 'Now Showing' : 'Upcoming'}</span></td>
          <td>
            <button class="btn-bms-red" style="font-size:0.72rem; padding:0.25rem 0.55rem; background:#334155;" onclick="toggleMovieStatus(${m.id}, ${m.is_now_showing})">
              Toggle Status
            </button>
          </td>`;
        tbody.appendChild(tr);
      });
    }
  } catch {}
}

async function toggleMovieStatus(id, currentStatus) {
  try {
    const res = await fetch('/api/admin/movies', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, is_now_showing: currentStatus ? 0 : 1 })
    });
    const data = await res.json();
    if (data.success) {
      toast('Movie status updated.', 'success');
      loadAdminMovies();
      fetchMovies();
      refreshAdminData();
    }
  } catch {}
}

// ── Admin Theatres, Shows, Bookings, Cancellations, Users ────────────────────
async function loadAdminTheaters() {
  const tbody = document.getElementById('admTableTheatersBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/admin/theaters');
    const data = await res.json();
    if (data.success && data.theaters) {
      tbody.innerHTML = '';
      data.theaters.forEach(t => {
        tbody.innerHTML += `
          <tr>
            <td>${t.id}</td>
            <td><strong>${t.name}</strong></td>
            <td>${t.city}</td>
            <td>${t.address}</td>
            <td>${t.screens_count} Screens</td>
            <td><strong style="color:var(--cpx-red);">${t.active_shows_count}</strong> shows scheduled</td>
          </tr>`;
      });
    }
  } catch {}
}

async function loadAdminShows() {
  const tbody = document.getElementById('admTableShowsBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/admin/shows');
    const data = await res.json();
    if (data.success && data.shows) {
      tbody.innerHTML = '';
      data.shows.slice(0, 50).forEach(s => {
        tbody.innerHTML += `
          <tr>
            <td>#${s.id}</td>
            <td><strong>${s.movie_title}</strong></td>
            <td>${s.theater_name} (${s.city})</td>
            <td>${s.screen_name}</td>
            <td>${s.show_date}</td>
            <td><strong>${s.show_time}</strong></td>
            <td>VIP: ₹${s.price_vip} | Prime: ₹${s.price_premium} | Exec: ₹${s.price_executive}</td>
            <td>${s.booked_seats} / ${s.total_seats} booked</td>
          </tr>`;
      });
    }
  } catch {}
}

async function loadAdminBookings() {
  const tbody = document.getElementById('admTableBookingsBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/bookings');
    const data = await res.json();
    if (data.success && data.bookings) {
      tbody.innerHTML = '';
      data.bookings.forEach(b => {
        tbody.innerHTML += `
          <tr>
            <td><strong style="color:var(--cpx-red);">${b.booking_ref}</strong></td>
            <td>${b.customer_name}<br><span style="font-size:0.72rem;color:#64748b;">${b.customer_email}</span></td>
            <td>${b.movie_title}</td>
            <td>${b.theater_name}</td>
            <td>${b.show_date} at ${b.show_time}</td>
            <td>${b.seat_numbers}</td>
            <td><strong>${rs(b.total_amount)}</strong></td>
            <td>${b.payment_method || 'UPI'}</td>
            <td><span class="bms-status-badge ${b.status === 'CONFIRMED' ? 'confirmed' : 'cancelled'}">${b.status}</span></td>
          </tr>`;
      });
    }
  } catch {}
}

async function loadAdminCancellations() {
  const tbody = document.getElementById('admTableCancellationsBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/admin/cancellations');
    const data = await res.json();
    if (data.success && data.cancellations) {
      tbody.innerHTML = '';
      data.cancellations.forEach(c => {
        tbody.innerHTML += `
          <tr>
            <td><strong style="color:#be123c;">${c.cancellation_ref}</strong></td>
            <td>${c.booking_ref}</td>
            <td>${c.customer_name}<br><span style="font-size:0.72rem;color:#64748b;">${c.customer_email}</span></td>
            <td>${rs(c.original_amount)}</td>
            <td style="color:#be123c;">- ₹${c.cancellation_fee}</td>
            <td style="color:#059669;"><strong>${rs(c.refund_amount)}</strong></td>
            <td><span class="bms-status-badge confirmed">${c.refund_status}</span></td>
            <td>${c.cancelled_at}</td>
          </tr>`;
      });
    }
  } catch {}
}

async function loadAdminUsers() {
  const tbody = document.getElementById('admTableUsersBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    if (data.success && data.users) {
      tbody.innerHTML = '';
      data.users.forEach(u => {
        tbody.innerHTML += `
          <tr>
            <td>#${u.id}</td>
            <td><strong>${u.name}</strong></td>
            <td>${u.email}</td>
            <td>+91 ${u.phone}</td>
            <td><span class="bms-status-badge ${u.is_admin ? 'confirmed' : 'cancelled'}">${u.is_admin ? 'Admin' : 'Customer'}</span></td>
            <td>${u.total_bookings_count} bookings</td>
            <td><strong style="color:#059669;">${rs(u.total_spend)}</strong></td>
            <td>${(u.created_at || '').slice(0, 10)}</td>
          </tr>`;
      });
    }
  } catch {}
}
