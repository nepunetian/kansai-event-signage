let events = [];
let currentFilter = 'all';
let heroIndex = 0;
let pageIndex = 0;
const CARDS_PER_PAGE = 6;
const FALLBACK_IMAGE = 'placeholder.svg';

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function fmtDate(iso){
  const d = new Date(iso + 'T00:00:00');
  return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short'}).format(d);
}

function dateRangeText(e){
  const start = fmtDate(e.start_date);
  const endDate = e.end_date && e.end_date !== e.start_date ? '〜' + fmtDate(e.end_date) : '';
  return `${start}${endDate}`;
}

function safeImage(url){
  return url && String(url).trim() ? url : FALLBACK_IMAGE;
}

function eventStart(e){
  return new Date((e.start_date || e.end_date) + 'T00:00:00');
}

function eventEnd(e){
  return new Date((e.end_date || e.start_date) + 'T23:59:59');
}

function isTodayEvent(e){
  const todayStart = new Date();
  todayStart.setHours(0,0,0,0);
  const todayEnd = new Date(todayStart);
  todayEnd.setHours(23,59,59,999);

  return eventStart(e) <= todayEnd && eventEnd(e) >= todayStart;
}

function isThisWeekendEvent(e){
  const now = new Date();
  now.setHours(0,0,0,0);

  // 「今週末」= 次に来る土日。
  // 土曜なら今日+明日、日曜なら今日だけを含む。
  const day = now.getDay();
  let sat;
  if(day === 6){
    sat = new Date(now);
  }else if(day === 0){
    sat = new Date(now);
    sat.setDate(now.getDate()-1);
  }else{
    const diffToSat = 6 - day;
    sat = new Date(now);
    sat.setDate(now.getDate()+diffToSat);
  }
  sat.setHours(0,0,0,0);

  const sun = new Date(sat);
  sun.setDate(sat.getDate()+1);
  sun.setHours(23,59,59,999);

  // 開始日ではなく「開催期間が土日に重なるか」で判定
  return eventStart(e) <= sun && eventEnd(e) >= sat;
}

function matches(e){
  if(currentFilter==='all') return true;
  if(currentFilter==='today') return isTodayEvent(e);
  if(currentFilter==='weekend') return isThisWeekendEvent(e);
  if(currentFilter==='tech') return e.category === 'tech';
  if(currentFilter==='rail') return e.category === 'rail';
  if(currentFilter==='anime') return e.category === 'anime';
  if(currentFilter==='food') return e.category === 'food';
  if(currentFilter==='car') return e.category === 'car';
  if(currentFilter==='tourism') return ['tourism','exhibition'].includes(e.category);
  if(Array.isArray(e.categories) && e.categories.length){
    return e.categories.includes(currentFilter);
  }
  return e.category===currentFilter;
}

function tagHtml(tags=[]){
  return tags.map(t=>`<span class="tag">${t}</span>`).join('');
}

function getFilteredEvents(){
  const today = new Date();
  today.setHours(0,0,0,0);
  return events
    .filter(e => {
      const end = new Date((e.end_date || e.start_date) + 'T23:59:59');
      return end >= today;
    })
    .filter(matches)
    .sort((a,b)=>b.score-a.score);
}

function escapeAttr(str){
  return String(str ?? '').replace(/"/g, '&quot;');
}

function render(){
  const list = getFilteredEvents();
  $('#count').textContent = `${list.length}件`;

  if(!list.length){
    $('#panelTitle').textContent = 'イベント一覧';
    $('#pageInfo').textContent = '0 / 0';
    $('#grid').innerHTML = `<div class="empty">該当するイベントはありません</div>`;
    $('#heroImage').src = FALLBACK_IMAGE;
    $('#heroMeta').textContent = '---';
    $('#heroTitle').textContent = 'イベントがありません';
    $('#heroDesc').textContent = '';
    $('#heroTags').innerHTML = '';
    $('#heroScore').textContent = '--';
    $('#heroSource').textContent = '情報元: --';
    return;
  }

  heroIndex = heroIndex % list.length;
  const hero = list[heroIndex];
  setHero(hero);

  const others = list.filter((_, idx) => idx !== heroIndex);
  const totalPages = Math.max(1, Math.ceil(others.length / CARDS_PER_PAGE));
  pageIndex = pageIndex % totalPages;
  const start = pageIndex * CARDS_PER_PAGE;
  const pageItems = others.slice(start, start + CARDS_PER_PAGE);

  $('#panelTitle').textContent = currentFilter === 'all' ? 'おすすめイベント' : '絞り込みイベント';
  $('#pageInfo').textContent = `${pageIndex + 1} / ${totalPages}`;

  $('#grid').innerHTML = pageItems.length ? pageItems.map((e,i)=>`
    <article class="card ${i===0 ? 'featured' : ''}">
      <div class="thumb-wrap">
        <img class="thumb" src="${escapeAttr(safeImage(e.image_url))}" alt="${escapeAttr(e.title)}" loading="lazy"
             onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}'">
      </div>
      <div class="card-body">
        <div>
          <div class="card-head">
            <div class="card-date">${dateRangeText(e)}</div>
            <div class="card-score">${e.score}</div>
          </div>
          <h4>${e.title}</h4>
          <div class="place">${e.area} ｜ ${e.venue}</div>
          <div class="desc">${e.description || ''}</div>
        </div>
        <div>
          <div class="tags">${tagHtml(e.tags)}</div>
          <div class="source">${e.source ? '情報元: ' + e.source : ''}${e.source_url ? ' ｜ <a href="' + e.source_url + '" target="_blank" rel="noopener">詳細</a>' : ''}</div>
        </div>
      </div>
    </article>
  `).join('') : `<div class="empty">表示できるイベントがありません</div>`;
}

function setHero(e){
  const heroImg = $('#heroImage');
  heroImg.src = safeImage(e.image_url);
  heroImg.onerror = function(){ this.onerror = null; this.src = FALLBACK_IMAGE; };
  heroImg.alt = e.title || '注目イベント画像';
  $('#heroMeta').textContent = `${dateRangeText(e)} ｜ ${e.area} ｜ ${e.venue}`;
  $('#heroTitle').textContent = e.title;
  $('#heroDesc').textContent = e.description || '';
  $('#heroTags').innerHTML = tagHtml(e.tags);
  $('#heroScore').textContent = e.score;
  $('#heroSource').innerHTML = `${e.source ? '情報元: ' + e.source : '情報元: --'}${e.source_url ? ' ｜ <a href="' + e.source_url + '" target="_blank" rel="noopener">詳細</a>' : ''}`;
}

function updateClock(){
  const now = new Date();
  $('#clock').textContent = new Intl.DateTimeFormat('ja-JP',{hour:'2-digit',minute:'2-digit',hour12:false}).format(now);
  $('#date').textContent = new Intl.DateTimeFormat('ja-JP',{year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(now);
}

async function loadEvents(){
  // まず events-data.js の同梱データを即時表示
  if(Array.isArray(window.EVENT_DATA) && window.EVENT_DATA.length){
    events = window.EVENT_DATA;
    $('#updated').textContent = `最終更新: ${new Date().toLocaleString('ja-JP')}（同梱データ）`;
    heroIndex = 0;
    pageIndex = 0;
    render();
  }

  // GitHub Pages上では events.json も取り直して最新化
  try{
    const res = await fetch(`./events.json?ts=${Date.now()}`, {cache:'no-store'});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const latest = await res.json();
    if(Array.isArray(latest) && latest.length){
      events = latest;
      window.EVENT_DATA = latest;
      $('#updated').textContent = `最終更新: ${new Date().toLocaleString('ja-JP')}`;
      heroIndex = 0;
      pageIndex = 0;
      render();
    }
  }catch(err){
    console.warn('events.jsonの再取得に失敗。events-data.jsを使用します。', err);
    if(!events.length){
      $('#grid').innerHTML = `<div class="empty">イベントデータを読み込めませんでした</div>`;
    }
  }
}

$$('.filter').forEach(btn=>{
  btn.addEventListener('click',()=>{
    $$('.filter').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    heroIndex = 0;
    pageIndex = 0;
    render();
  });
});

// 注目イベント切替
setInterval(()=>{
  const list = getFilteredEvents();
  if(list.length){
    heroIndex = (heroIndex + 1) % list.length;
    render();
  }
}, 12000);

// 一覧ページ切替
setInterval(()=>{
  const list = getFilteredEvents();
  const others = list.filter((_, idx) => idx !== heroIndex);
  const totalPages = Math.max(1, Math.ceil(others.length / CARDS_PER_PAGE));
  if(totalPages > 1){
    pageIndex = (pageIndex + 1) % totalPages;
    render();
  }
}, 16000);

setInterval(loadEvents, 15 * 60 * 1000);
setInterval(updateClock, 1000);
updateClock();
loadEvents();
