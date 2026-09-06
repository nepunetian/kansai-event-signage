let events = [];
let currentFilter = 'all';
let heroIndex = 0;

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function fmtDate(iso){
  const d = new Date(iso + 'T00:00:00');
  return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short'}).format(d);
}

function isToday(iso){
  const now = new Date();
  const d = new Date(iso+'T00:00:00');
  return now.toDateString() === d.toDateString();
}

function isThisWeekend(iso){
  const now = new Date();
  const day = now.getDay();
  const diffToSat = (6 - day + 7) % 7;
  const sat = new Date(now); sat.setHours(0,0,0,0); sat.setDate(now.getDate()+diffToSat);
  const sun = new Date(sat); sun.setDate(sat.getDate()+1);
  const d = new Date(iso+'T00:00:00');
  return d >= sat && d <= sun;
}

function matches(e){
  if(currentFilter==='all') return true;
  if(currentFilter==='today') return isToday(e.start_date);
  if(currentFilter==='weekend') return isThisWeekend(e.start_date);
  if(currentFilter==='tech') return e.category === 'tech';
  if(currentFilter==='rail') return e.category === 'rail';
  if(currentFilter==='tourism') return ['tourism','exhibition'].includes(e.category);
  return e.category === currentFilter;
}

function tagHtml(tags=[]){
  return tags.map(t=>`<span class="tag">${t}</span>`).join('');
}

function render(){
  const today = new Date(); today.setHours(0,0,0,0);
  const list = events.filter(e => {
    const end = new Date((e.end_date || e.start_date) + 'T23:59:59');
    return end >= today;
  }).filter(matches).sort((a,b)=>b.score-a.score);
  $('#count').textContent = `${list.length}件`;
  $('#grid').innerHTML = list.length ? list.map((e,i)=>`
    <article class="card ${i===0?'featured':''}">
      <div>
        <div class="card-top">
          <div class="card-date">${fmtDate(e.start_date)}${e.end_date && e.end_date!==e.start_date ? '〜'+fmtDate(e.end_date):''}</div>
          <div class="card-score">${e.score}</div>
        </div>
        <h4>${e.title}</h4>
        <div class="place">${e.area} ｜ ${e.venue}</div>
        <div class="desc">${e.description}</div>
      </div>
      <div>
        <div class="tags">${tagHtml(e.tags)}</div>
        <div class="source">${e.source ? '情報元: ' + e.source : ''}</div>
      </div>
    </article>
  `).join('') : `<div class="empty">該当するイベントはありません</div>`;

  if(list.length){
    heroIndex %= list.length;
    setHero(list[heroIndex]);
  }
}

function setHero(e){
  $('#heroMeta').textContent = `${fmtDate(e.start_date)} ｜ ${e.area} ｜ ${e.venue}`;
  $('#heroTitle').textContent = e.title;
  $('#heroDesc').textContent = e.description;
  $('#heroTags').innerHTML = tagHtml(e.tags);
  $('#heroScore').textContent = e.score;
}

function updateClock(){
  const now = new Date();
  $('#clock').textContent = new Intl.DateTimeFormat('ja-JP',{hour:'2-digit',minute:'2-digit',hour12:false}).format(now);
  $('#date').textContent = new Intl.DateTimeFormat('ja-JP',{year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(now);
}

async function loadEvents(){
  try{
    const res = await fetch(`events.json?ts=${Date.now()}`,{cache:'no-store'});
    events = await res.json();
    $('#updated').textContent = `最終更新: ${new Date().toLocaleString('ja-JP')}`;
    render();
  }catch(err){
    console.error(err);
    $('#grid').innerHTML = `<div class="empty">イベントデータを読み込めませんでした</div>`;
  }
}

$$('.filter').forEach(btn=>{
  btn.addEventListener('click',()=>{
    $$('.filter').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    heroIndex = 0;
    render();
  });
});

setInterval(()=>{
  const list = events.filter(matches).sort((a,b)=>b.score-a.score);
  if(list.length){
    heroIndex = (heroIndex + 1) % list.length;
    setHero(list[heroIndex]);
  }
},12000);

setInterval(loadEvents, 15*60*1000);
setInterval(updateClock,1000);
updateClock();
loadEvents();
