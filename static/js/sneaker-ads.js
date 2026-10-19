/*
 * Sneaker Wall adverts for the call-centre screens.
 *
 * Every AD_EVERY_MS a full-screen advert pops up, stays for AD_SHOW_MS (1 minute) with a
 * live countdown, then disappears. Each advert showcases a different sneaker type;
 * they rotate in order. Preview instantly by opening the dashboard with  ?ad=now
 *
 * Images live in static/images/ads/NN.jpeg. To change what is shown, edit ADS below.
 */
(function () {
  'use strict';

  var AD_SHOW_MS = 60 * 1000;            // how long an advert stays up: 1 minute
  var AD_EVERY_MS = 10 * 60 * 1000;      // how often a new advert pops up
  var FIRST_AD_MS = 60 * 1000;           // first advert, this long after the page loads
  var RETRY_MS = 30 * 1000;              // re-check if something else (breakdown pop-up) is showing

  var script = document.currentScript;
  var BASE = (script && script.dataset.base) || '/static/images/ads/';

  // One advert per sneaker type. "photos" are file numbers in static/images/ads/.
  var ADS = [
    { type: 'Adidas Samba', line: 'The terrace classic. Black, white, tan and metallic silver.',
      photos: [['05', 'Samba OG White/Black'], ['06', 'Samba Metallic Silver'], ['16', 'Samba OG Brown'], ['35', 'Samba White/Tan']] },
    { type: 'Nike Air Force 1', line: 'Clean, bold and always in style.',
      photos: [['01', 'Air Force 1 x The North Face'], ['07', 'Air Force 1 Brown Swoosh'], ['45', 'Air Force 1 x The North Face Brown'], ['46', 'Air Force 1 Black Suede']] },
    { type: 'New Balance', line: 'Comfort-first classics: the 530 and the 9060.',
      photos: [['02', 'New Balance 530'], ['08', 'New Balance 9060 Black/Grey'], ['09', 'New Balance 9060 Cream'], ['28', 'New Balance 9060 Brown']] },
    { type: 'Nike Air Max', line: 'Visible Air. Unmistakable look.',
      photos: [['10', 'Air Max 95'], ['12', 'Air Max Dn'], ['17', 'Air Max 97 Silver Gradient'], ['19', 'Air Max 97 Black/Red']] },
    { type: 'Converse', line: 'Chuck Taylor and Chuck 70. Timeless canvas.',
      photos: [['20', 'Chuck 70 Low Black'], ['26', 'Chuck 70 Low White'], ['34', 'Chuck Taylor All Star Hi White'], ['38', 'Chuck 70 Low Cream']] },
    { type: 'Running', line: 'Built for speed from Adidas, Nike and On.',
      photos: [['13', 'Nike Zoom Fly'], ['21', 'Adidas Adizero Black'], ['39', 'On Cloudsurfer'], ['47', 'Adidas Adizero Adios Pro Blue']] },
    { type: 'Court Classics', line: 'Reebok and Puma, the everyday court look.',
      photos: [['57', 'Reebok Club C 85 Black'], ['58', 'Reebok Club C 85 Navy'], ['49', 'Puma Suede Cream/Black'], ['50', 'Puma Suede Black/Cream']] }
  ];

  // A different motivational quote on each advert; they rotate in order.
  var QUOTES = [
    ['Success is the sum of small efforts, repeated day in and day out.', 'Robert Collier'],
    ['Don’t watch the clock; do what it does. Keep going.', 'Sam Levenson'],
    ['The harder you work for something, the greater you’ll feel when you achieve it.', ''],
    ['It always seems impossible until it’s done.', 'Nelson Mandela'],
    ['Every call is a new chance to make someone’s day, and yours.', ''],
    ['Winners are not people who never fail, but people who never quit.', ''],
    ['Believe you can and you’re halfway there.', 'Theodore Roosevelt'],
    ['Your target is not a wall, it’s a doorway. Walk through it.', ''],
    ['Champions keep playing until they get it right.', 'Billie Jean King'],
    ['A smile in your voice can change the whole call.', ''],
    ['Discipline is choosing between what you want now and what you want most.', ''],
    ['Teamwork makes the dream work.', '']
  ];

  var KEY_NEXT = 'sneakerAds.nextAt';
  var KEY_IDX = 'sneakerAds.index';
  var KEY_QUOTE = 'sneakerAds.quote';
  function store(k, v) { try { localStorage.setItem(k, String(v)); } catch (e) {} }
  function load(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  // ---- markup + styles (injected so the dashboard template stays untouched) ----
  var css = '\
  .sad{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;position:fixed;inset:0;z-index:9998;display:none;align-items:center;justify-content:center;padding:2.5vh 3vw;\
       background:rgba(17,24,39,.78);opacity:0;transition:opacity .6s ease}\
  .sad.open{display:flex}.sad.show{opacity:1}\
  .sad-card{background:#fff;border-radius:1.5rem;box-shadow:0 25px 70px rgba(0,0,0,.5);width:100%;max-width:1500px;max-height:95vh;\
       overflow:hidden;display:flex;flex-direction:column;transform:translateY(40px) scale(.97);transition:transform .7s cubic-bezier(.2,.8,.2,1)}\
  .sad.show .sad-card{transform:none}\
  .sad-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);flex:1;min-height:0}\
  .sad-text{padding:3.5vh 3vw;display:flex;flex-direction:column;justify-content:center;gap:1.6vh;background:linear-gradient(160deg,#f5f8fc,#fff)}\
  .sad-eyebrow{font-weight:700;letter-spacing:.18em;text-transform:uppercase;font-size:clamp(.8rem,1.2vw,1.2rem);color:#4D96FF}\
  .sad-type{font-weight:900;line-height:1.02;font-size:clamp(2.4rem,5.2vw,5.4rem);color:#1F2937}\
  .sad-type span{color:#4D96FF}\
  .sad-line{font-size:clamp(1rem,1.7vw,1.7rem);color:#4b5563}\
  .sad-quote{margin-top:1.2vh;padding-left:1rem;border-left:4px solid #4D96FF;font-size:clamp(1rem,1.6vw,1.6rem);font-style:italic;color:#1f2937}\n  .sad-quote small{display:block;margin-top:.3rem;font-style:normal;font-size:.7em;color:#6b7280}\n  .sad-rewards{display:flex;gap:1rem;flex-wrap:wrap;margin-top:1vh}\
  .sad-pill{padding:.7rem 1.2rem;border-radius:999px;font-weight:800;font-size:clamp(.9rem,1.4vw,1.4rem);color:#fff;background:#4D96FF}\
  .sad-pill.two{background:#9C78E4}\
  .sad-photos{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:.6rem;padding:.6rem;background:#fff;min-height:0}\
  .sad-photo{position:relative;border-radius:1rem;overflow:hidden;background:#f3f4f6;min-height:0}\
  .sad-photo img{width:100%;height:100%;object-fit:cover;display:block}\
  .sad-photo span{position:absolute;left:0;right:0;bottom:0;padding:.5rem .8rem;color:#fff;font-weight:700;font-size:clamp(.8rem,1.2vw,1.2rem);\
       background:linear-gradient(transparent,rgba(17,24,39,.8))}\
  .sad-foot{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1.2vh 3vw;background:#fff;border-top:1px solid #E5E7EB;\
       font-weight:700;color:#1F2937;font-size:clamp(.9rem,1.4vw,1.4rem)}\
  .sad-timer{background:linear-gradient(135deg,#4D96FF,#9C78E4);color:#fff;padding:.5rem 1.1rem;border-radius:2rem;white-space:nowrap}\
  .sad-bar{height:.55rem;background:#E5E7EB}.sad-bar i{display:block;height:100%;width:100%;background:linear-gradient(90deg,#4D96FF,#9C78E4);transform-origin:left}\
  @media(max-width:800px){.sad-body{grid-template-columns:1fr}}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var root = document.createElement('div');
  root.className = 'sad';
  root.setAttribute('aria-hidden', 'true');
  root.innerHTML =
    '<div class="sad-card">' +
      '<div class="sad-body">' +
        '<div class="sad-text">' +
          '<div class="sad-eyebrow">Altitude BPO Sneaker Wall</div>' +
          '<div class="sad-type" id="sad-type"></div>' +
          '<div class="sad-line" id="sad-line"></div>' +
          '<div class="sad-quote" id="sad-quote"></div>' +
          '<div class="sad-rewards"><span class="sad-pill">On target: free pair</span><span class="sad-pill two">2nd place: about 30% off</span></div>' +
        '</div>' +
        '<div class="sad-photos" id="sad-photos"></div>' +
      '</div>' +
      '<div class="sad-bar"><i id="sad-bar"></i></div>' +
      '<div class="sad-foot"><span>Hit your target and pick any pair from the wall.</span>' +
        '<span class="sad-timer">Closing in <span id="sad-clock">01:00</span></span></div>' +
    '</div>';
  document.body.appendChild(root);

  var el = {
    type: root.querySelector('#sad-type'), line: root.querySelector('#sad-line'),
    quote: root.querySelector('#sad-quote'), photos: root.querySelector('#sad-photos'), clock: root.querySelector('#sad-clock'),
    bar: root.querySelector('#sad-bar')
  };
  var tick = null, hideTimer = null, startTimer = null;

  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function isBusy() {
    var m = document.getElementById('breakdown-modal');
    return !!(m && m.classList.contains('open'));
  }

  function hide() {
    clearInterval(tick); clearTimeout(hideTimer);
    root.classList.remove('show');
    setTimeout(function () { root.classList.remove('open'); root.setAttribute('aria-hidden', 'true'); }, 650);
  }

  function show() {
    var idx = parseInt(load(KEY_IDX), 10);
    if (isNaN(idx) || idx < 0) idx = 0;
    var ad = ADS[idx % ADS.length];
    store(KEY_IDX, (idx + 1) % ADS.length);

    var words = ad.type.split(' ');
    var last = words.pop();
    el.type.innerHTML = (words.length ? esc(words.join(' ')) + ' ' : '') + '<span>' + esc(last) + '</span>';
    el.line.textContent = ad.line;

    var qi = parseInt(load(KEY_QUOTE), 10);
    if (isNaN(qi) || qi < 0) qi = 0;
    var q = QUOTES[qi % QUOTES.length];
    store(KEY_QUOTE, (qi + 1) % QUOTES.length);
    el.quote.innerHTML = '“' + esc(q[0]) + '”' + (q[1] ? '<small>— ' + esc(q[1]) + '</small>' : '');
    el.photos.innerHTML = ad.photos.map(function (p) {
      return '<div class="sad-photo"><img src="' + BASE + p[0] + '.jpeg" alt="' + esc(p[1]) + '"><span>' + esc(p[1]) + '</span></div>';
    }).join('');

    root.classList.add('open');
    root.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.add('show'); }); });

    var endAt = Date.now() + AD_SHOW_MS;
    function paint() {
      var left = Math.max(0, endAt - Date.now());
      var s = Math.ceil(left / 1000);
      el.clock.textContent = pad(Math.floor(s / 60)) + ':' + pad(s % 60);
      el.bar.style.transform = 'scaleX(' + (left / AD_SHOW_MS) + ')';
    }
    paint();
    clearInterval(tick);
    tick = setInterval(paint, 250);
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, AD_SHOW_MS);
  }

  function schedule(delay) {
    clearTimeout(startTimer);
    store(KEY_NEXT, Date.now() + delay);
    startTimer = setTimeout(attempt, delay);
  }

  function attempt() {
    if (isBusy()) { schedule(RETRY_MS); return; }   // don't sit on top of the sales breakdown
    show();
    schedule(AD_SHOW_MS + AD_EVERY_MS);              // next advert: after this one ends + the gap
  }

  // Dashboard pages reload on new data, so remember when the next advert is due.
  if (/[?&]ad=now\b/.test(location.search)) {
    startTimer = setTimeout(attempt, 500);
  } else {
    var due = parseInt(load(KEY_NEXT), 10);
    var wait = isNaN(due) ? FIRST_AD_MS : Math.max(due - Date.now(), 2000);
    startTimer = setTimeout(attempt, Math.min(wait, AD_SHOW_MS + AD_EVERY_MS));
    store(KEY_NEXT, Date.now() + wait);
  }

  // Clicking the backdrop dismisses it, so a screen is never stuck.
  root.addEventListener('click', function (e) { if (e.target === root) hide(); });
})();
