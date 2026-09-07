let events = [];
let currentFilter = 'all';
let heroIndex = 0;
let pageIndex = 0;
const CARDS_PER_PAGE = 6;
const FALLBACK_IMAGE = 'placeholder.svg';

const PREFS_KEY = 'kansaiEventSignagePrefs';
const PREFS_BACKUP_KEY = 'kansaiEventSignagePrefsBackup';
const LEGACY_PREF_KEYS = [
  'kansaiEventSignagePrefsV1',
  'kansaiEventSignagePrefsV2'
];

function safeParsePrefs(raw){
  try{
    const parsed = JSON.parse(raw || '{}');
    if(parsed && typeof parsed === 'object'){
      return {
        votes: parsed.votes && typeof parsed.votes === 'object' ? parsed.votes : {},
        updatedAt: Number(parsed.updatedAt || 0)
      };
    }
  }catch(_){}
  return {votes:{}, updatedAt:0};
}

function mergePrefs(a, b){
  const result = {votes:{}, updatedAt:Math.max(a.updatedAt||0, b.updatedAt||0)};
  const allKeys = new Set([
    ...Object.keys(a.votes || {}),
    ...Object.keys(b.votes || {})
  ]);

  allKeys.forEach(key=>{
    const va = a.votes?.[key];
    const vb = b.votes?.[key];
    if(!va) result.votes[key] = vb;
    else if(!vb) result.votes[key] = va;
    else{
      // より新しく投票された方を採用
      result.votes[key] = Number(va.votedAt||0) >= Number(vb.votedAt||0) ? va : vb;
    }
  });
  return result;
}

function loadPrefs(){
  // 通常データ + バックアップを統合
  let prefs = mergePrefs(
    safeParsePrefs(localStorage.getItem(PREFS_KEY)),
    safeParsePrefs(localStorage.getItem(PREFS_BACKUP_KEY))
  );

  // 旧バージョンの学習データも自動移行
  LEGACY_PREF_KEYS.forEach(key=>{
    prefs = mergePrefs(prefs, safeParsePrefs(localStorage.getItem(key)));
  });

  return prefs;
}

let userPrefs = loadPrefs();
let lastVoteAction = null;

function savePrefs(){
  userPrefs.updatedAt = Date.now();
  const payload = JSON.stringify(userPrefs);

  try{
    // 同一オリジン内に2重保存。
    // GitHub Pagesのファイル更新・events.json更新では消えない。
    localStorage.setItem(PREFS_KEY, payload);
    localStorage.setItem(PREFS_BACKUP_KEY, payload);

    // 旧キーが存在する場合も同期して、v10〜v13からの往復でも保持
    LEGACY_PREF_KEYS.forEach(key=>{
      if(localStorage.getItem(key) !== null){
        localStorage.setItem(key, payload);
      }
    });
  }catch(err){
    console.warn('学習データを保存できませんでした', err);
  }
}

function eventKey(e){
  const raw = e.source_url || `${e.title || ''}|${e.start_date || ''}|${e.venue || ''}`;
  // data属性でも安全に扱える単純キーへ
  let h = 2166136261;
  for(let i=0;i<raw.length;i++){
    h ^= raw.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return 'e' + (h >>> 0).toString(36);
}

function featureSnapshot(e){
  return {
    categories: Array.isArray(e.categories) && e.categories.length ? [...e.categories] : [e.category].filter(Boolean),
    tags: Array.isArray(e.tags) ? [...e.tags] : [],
    source: e.source || '',
    area: e.area || '',
    venue: e.venue || ''
  };
}

function setVote(e, value){
  const key = eventKey(e);
  const old = userPrefs.votes[key] ? {...userPrefs.votes[key]} : null;

  lastVoteAction = {
    key,
    previous: old,
    nextValue: value,
    title: e.title || ''
  };

  // 同じ評価をもう一度押すと解除。
  // 反対側を押すと 👍 ↔ 👎 を変更。
  if(old && old.value === value){
    delete userPrefs.votes[key];
  }else{
    userPrefs.votes[key] = {
      value,
      ...featureSnapshot(e),
      title: e.title || '',
      votedAt: Date.now()
    };
  }

  savePrefs();
  updateUndoVoteButton();
  heroIndex = 0;
  pageIndex = 0;
  render();
}

function updateUndoVoteButton(){
  const btn = $('#undoVote');
  if(!btn) return;
  btn.disabled = !lastVoteAction;
  if(lastVoteAction){
    btn.textContent = '↶ 直前の評価を戻す';
    btn.title = lastVoteAction.title
      ? `「${lastVoteAction.title}」の直前の評価を元に戻す`
      : '直前の評価を元に戻す';
  }else{
    btn.textContent = '↶ 直前の評価を戻す';
    btn.title = '';
  }
}

function undoLastVote(){
  if(!lastVoteAction) return;

  const {key, previous} = lastVoteAction;
  if(previous){
    userPrefs.votes[key] = previous;
  }else{
    delete userPrefs.votes[key];
  }

  lastVoteAction = null;
  savePrefs();
  updateUndoVoteButton();
  heroIndex = 0;
  pageIndex = 0;
  render();
}

function getVote(e){
  return userPrefs.votes[eventKey(e)]?.value || 0;
}

function overlapCount(a=[], b=[]){
  const bs = new Set(b);
  return a.reduce((n,x)=>n + (bs.has(x) ? 1 : 0), 0);
}

function preferenceBonus(e){
  const direct = getVote(e);
  let bonus = direct === 1 ? 38 : direct === -1 ? -90 : 0;
  const f = featureSnapshot(e);

  Object.values(userPrefs.votes).forEach(v=>{
    if(!v || !v.value) return;
    // そのイベント自身への効果は direct で処理済み
    if(v.title && v.title === e.title && v.venue === e.venue) return;

    const sign = v.value > 0 ? 1 : -1;
    const catOverlap = overlapCount(f.categories, v.categories || []);
    const tagOverlap = overlapCount(f.tags, v.tags || []);

    bonus += sign * Math.min(12, catOverlap * 7);
    bonus += sign * Math.min(9, tagOverlap * 3);

    if(f.source && v.source && f.source === v.source) bonus += sign * 4;
    if(f.area && v.area && f.area === v.area) bonus += sign * 1;
    if(f.venue && v.venue && f.venue === v.venue) bonus += sign * 3;
  });

  // 類似嗜好による補正は過学習を避けるため制限
  if(direct === 0) bonus = Math.max(-35, Math.min(35, bonus));
  return bonus;
}

function personalizedRawScore(e){
  // 並び替え用。上限を設けず、元スコアと学習補正の差を保持する。
  return Number(e.score || 0) + preferenceBonus(e);
}

function displayRecommendationScore(raw){
  /*
    表示用スコアは高得点帯を圧縮する。
    以前は 99 で単純カットしていたため、上位イベントが大量に99になっていた。

    目安:
      raw 50  -> 50
      raw 70  -> 70
      raw 85  -> 81
      raw 99  -> 91
      raw 115 -> 95
      raw 135 -> 98

    99は極端に強い好みが積み重なった場合だけ。
  */
  const x = Number(raw || 0);

  if(x <= 70) return Math.max(0, Math.round(x));
  if(x <= 100){
    return Math.round(70 + (x - 70) * (22 / 30)); // 70→92
  }
  if(x <= 120){
    return Math.round(92 + (x - 100) * (4 / 20)); // 100→96
  }
  if(x <= 145){
    return Math.round(96 + (x - 120) * (2 / 25)); // 120→98
  }
  return 99;
}

function personalizedScore(e){
  return displayRecommendationScore(personalizedRawScore(e));
}

function learningCount(){
  return Object.keys(userPrefs.votes).length;
}

function updateLearningStatus(){
  const el = $('#learningStatus');
  if(!el) return;
  const votes = Object.values(userPrefs.votes);
  const likes = votes.filter(v=>v.value===1).length;
  const dislikes = votes.filter(v=>v.value===-1).length;
  el.textContent = `学習 👍${likes} / 👎${dislikes}`;
}


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
  const cats = Array.isArray(e.categories) && e.categories.length ? e.categories : [e.category];
  if(currentFilter==='tourism') return cats.includes('tourism') || cats.includes('exhibition');
  return cats.includes(currentFilter);
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
    .sort((a,b)=>personalizedRawScore(b)-personalizedRawScore(a) || String(a.start_date).localeCompare(String(b.start_date)));
}

function escapeAttr(str){
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
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
    updateLearningStatus();
    return;
  }

  // メイン表示はおすすめ上位5件だけをローテーション
  const heroPool = list.slice(0, Math.min(5, list.length));
  heroIndex = heroIndex % heroPool.length;
  const hero = heroPool[heroIndex];
  setHero(hero);

  // サブ表示は6位以下だけ。メイン上位5件とは完全に分離する。
  const subList = list.slice(5);
  const totalPages = subList.length
    ? Math.ceil(subList.length / CARDS_PER_PAGE)
    : 0;

  if(totalPages > 0){
    pageIndex = pageIndex % totalPages;
  }else{
    pageIndex = 0;
  }

  const start = pageIndex * CARDS_PER_PAGE;
  const pageItems = subList.slice(start, start + CARDS_PER_PAGE);

  $('#panelTitle').textContent = currentFilter === 'all' ? 'おすすめイベント' : '絞り込みイベント';
  $('#pageInfo').textContent = totalPages > 0
    ? `${pageIndex + 1} / ${totalPages}`
    : `0 / 0`;

  $('#grid').innerHTML = pageItems.length ? pageItems.map((e,i)=>`
    <article class="card">
      <div class="thumb-wrap">
        <img class="thumb" src="${escapeAttr(safeImage(e.image_url))}" alt="${escapeAttr(e.title)}" loading="lazy"
             onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}'">
      </div>
      <div class="card-body">
        <div>
          <div class="card-head">
            <div class="card-date">${dateRangeText(e)}</div>
            <div class="card-score">${personalizedScore(e)}</div>
          </div>
          <h4>${e.title}</h4>
          <div class="place">${e.area} ｜ ${e.venue}</div>
          <div class="desc">${e.description || ''}</div>
        </div>
        <div>
          <div class="card-bottom">
            <div class="tags">${tagHtml(e.tags)}</div>
            <div class="card-feedback">
              <button class="feedback-btn mini ${getVote(e)===1 ? 'selected' : ''}" data-vote="1" data-event-key="${eventKey(e)}" type="button" title="いいね">👍</button>
              <button class="feedback-btn mini ${getVote(e)===-1 ? 'selected bad' : ''}" data-vote="-1" data-event-key="${eventKey(e)}" type="button" title="バッド">👎</button>
            </div>
          </div>
          <div class="source">${e.source ? '情報元: ' + e.source : ''}${e.source_url ? ' ｜ <a href="' + e.source_url + '" target="_blank" rel="noopener">詳細</a>' : ''}</div>
        </div>
      </div>
    </article>
  `).join('') : `<div class="empty">6位以下のイベントはありません</div>`;
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
  $('#heroScore').textContent = personalizedScore(e);
  $('#heroSource').innerHTML = `${e.source ? '情報元: ' + e.source : '情報元: --'}${e.source_url ? ' ｜ <a href="' + e.source_url + '" target="_blank" rel="noopener">詳細</a>' : ''}`;

  const like = $('#heroLike');
  const bad = $('#heroDislike');
  if(like && bad){
    like.dataset.eventKey = eventKey(e);
    bad.dataset.eventKey = eventKey(e);
    like.classList.toggle('selected', getVote(e) === 1);
    bad.classList.toggle('selected', getVote(e) === -1);
    bad.classList.toggle('bad', getVote(e) === -1);
  }
  updateLearningStatus();
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


function findEventByKey(key){
  return events.find(e => eventKey(e) === key);
}

document.addEventListener('click', (ev)=>{
  const btn = ev.target.closest('.feedback-btn');
  if(!btn) return;
  const key = btn.dataset.eventKey;
  const value = Number(btn.dataset.vote || (btn.id === 'heroLike' ? 1 : btn.id === 'heroDislike' ? -1 : 0));
  if(!key || !value) return;
  const event = findEventByKey(key);
  if(!event) return;
  ev.preventDefault();
  ev.stopPropagation();
  setVote(event, value);
});

const undoVote = $('#undoVote');
if(undoVote){
  undoVote.addEventListener('click', ()=>{
    undoLastVote();
  });
}
updateUndoVoteButton();

const resetLearning = $('#resetLearning');
if(resetLearning){
  resetLearning.addEventListener('click', ()=>{
    if(!learningCount()) return;
    if(confirm('いいね・バッドの学習内容をリセットしますか？')){
      userPrefs = {votes:{}, updatedAt:Date.now()};
      lastVoteAction = null;
      updateUndoVoteButton();
      try{
        localStorage.removeItem(PREFS_KEY);
        localStorage.removeItem(PREFS_BACKUP_KEY);
        LEGACY_PREF_KEYS.forEach(key=>localStorage.removeItem(key));
      }catch(_){}
      heroIndex = 0;
      pageIndex = 0;
      render();
    }
  });
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

// スライド制御
let heroTimer = null;
let pageTimer = null;

function advanceHero(){
  const list = getFilteredEvents();
  const heroCount = Math.min(5, list.length);
  if(heroCount > 0){
    heroIndex = (heroIndex + 1) % heroCount;
    render();
  }
}

function advanceSubPage(){
  const list = getFilteredEvents();
  const subList = list.slice(5);
  const totalPages = Math.ceil(subList.length / CARDS_PER_PAGE);
  if(totalPages > 1){
    pageIndex = (pageIndex + 1) % totalPages;
    render();
  }
}

function advanceWholeSlide(){
  const list = getFilteredEvents();
  if(!list.length) return;

  // 手動の「次へ」は画面全体を1段進める。
  // メイン: 上位5件の次候補
  // サブ: 6位以下の次ページ
  const heroCount = Math.min(5, list.length);
  if(heroCount > 0){
    heroIndex = (heroIndex + 1) % heroCount;
  }

  const subList = list.slice(5);
  const totalPages = Math.ceil(subList.length / CARDS_PER_PAGE);
  if(totalPages > 1){
    pageIndex = (pageIndex + 1) % totalPages;
  }else{
    pageIndex = 0;
  }

  render();
}

function restartSlideTimers(){
  if(heroTimer) clearInterval(heroTimer);
  if(pageTimer) clearInterval(pageTimer);

  heroTimer = setInterval(advanceHero, 12000);
  pageTimer = setInterval(advanceSubPage, 16000);
}

const nextSlide = $('#nextSlide');
if(nextSlide){
  nextSlide.addEventListener('click', ()=>{
    advanceWholeSlide();
    // 手動操作した瞬間を起点に自動切替時間を数え直す
    restartSlideTimers();
  });
}

restartSlideTimers();

setInterval(loadEvents, 15 * 60 * 1000);
setInterval(updateClock, 1000);
updateClock();
loadEvents();
