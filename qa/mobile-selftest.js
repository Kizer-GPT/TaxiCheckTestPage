/* TaxiCheck public mockup mobile self-test v2.
 * No real financial systems. Synthetic CRUD runs ONLY inside an expendable iframe.
 * Opt-in URL: ?qa=run. Public demo only; not an Apps Script test.
 */
(function () {
  'use strict';
  if (new URLSearchParams(window.location.search).get('qa') !== 'run') return;
  var $ = function (selector) { return document.querySelector(selector); };
  var checks = [], errors = [], busy = false;
  var titles = {cash:'Касса',commissions:'Комиссии',rent:'Аренда',fuel:'Заправки',
    other:'Прочие расходы',bonuses:'Бонусы',mileage:'Пробег',consumption:'Расход автомобиля'};
  var CSS = [
    '#tcAutoQa{position:fixed;z-index:2147483000;inset:auto 10px max(10px,env(safe-area-inset-bottom));',
    'width:calc(100% - 20px);max-width:530px;max-height:77dvh;overflow:auto;box-sizing:border-box;',
    'margin:0 auto;border:1px solid #5f7e9b;border-radius:19px;background:#111e2c;color:#eaf4ff;',
    'font:14px/1.45 -apple-system,BlinkMacSystemFont,Arial,sans-serif;',
    'box-shadow:0 10px 45px #000b;padding:14px;overscroll-behavior:contain}',
    '#tcAutoQa *{box-sizing:border-box}#tcAutoQa header{display:flex;align-items:center;justify-content:space-between;gap:10px}',
    '#tcAutoQa h2{font-size:19px;margin:0;font-weight:800}#tcAutoQa p{margin:8px 0;color:#b4c8da;font-size:12px}',
    '#tcAutoQa button{min-height:44px;border:1px solid #5c7ca0;border-radius:11px;padding:9px 12px;',
    'background:#243c59;color:#fff;font:inherit;font-weight:700}',
    '#tcAutoQa button:disabled{opacity:.55}#tcAutoQa .tcQaClose{min-width:44px}',
    '#tcAutoQa .tcQaActions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:12px}',
    '#tcAutoQa .tcQaActions button{font-size:12px;padding:8px 5px}',
    '#tcAutoQa ol{padding:0;list-style:none;margin:10px 0 0;display:grid;gap:6px}',
    '#tcAutoQa li{padding:8px 9px;border:1px solid #354d65;border-radius:9px;font-size:12px;overflow-wrap:anywhere}',
    '#tcAutoQa li[data-state=pass]{border-color:#3a785e}',
    '#tcAutoQa li[data-state=fail]{border-color:#bd6570}',
    '#tcAutoQa li[data-state=warn]{border-color:#9b814c}',
    '#tcAutoQa .tcQaTop{font-weight:800;font-variant-numeric:tabular-nums}',
    '@media(max-width:360px){#tcAutoQa{padding:10px}#tcAutoQa .tcQaActions button{font-size:11px}}'
  ].join('');
  var style = document.createElement('style'); style.id = 'tcAutoQaStyle'; style.textContent = CSS;
  document.head.appendChild(style);
  var panel = document.createElement('section');
  panel.id = 'tcAutoQa'; panel.setAttribute('role','region');
  panel.setAttribute('aria-label','TaxiCheck — самопроверка макета');
  panel.innerHTML = '<header><h2>TaxiCheck · автотест</h2><button class="tcQaClose" type="button" aria-label="Закрыть проверку">×</button></header>'+
    '<p>Проверяем интерфейс, ошибки ввода и пробные финансовые сценарии в отдельной временной копии макета. Настоящие деньги и твои записи не затрагиваются.</p>'+
    '<div class="tcQaTop" id="tcQaStatus" role="status" aria-live="polite">Подготовка…</div>'+
    '<ol id="tcQaResults"></ol><div class="tcQaActions">'+
    '<button type="button" id="tcQaAgain">Повторить</button>'+
    '<button type="button" id="tcQaCopy" disabled>Копировать</button>'+
    '<button type="button" id="tcQaShare" disabled>Поделиться</button></div>'+
    '<p>Все суммы вымышлены. Реальные касания, клавиатуру, удобство и внешний вид проверь вручную. Никаких аккаунтов и автоматической отправки.</p>';
  document.body.appendChild(panel);
  var status = $('#tcQaStatus'), output = $('#tcQaResults'), again = $('#tcQaAgain'),
    copy = $('#tcQaCopy'), share = $('#tcQaShare');
  function visible(el) { return !!el && !el.hidden && getComputedStyle(el).display !== 'none'; }
  function requireThat(ok, code) { if (!ok) throw new Error(code); }
  function element(selector) {
    var el = $(selector);
    requireThat(!!el, 'MISSING_ELEMENT: '+selector);
    return el;
  }
  function clickNav(screen) {
    var el = element('[data-nav="'+screen+'"]');
    el.click();
    requireThat(visible(element('#'+(screen==='settings'?'detail':screen))), 'NAVIGATION_FAILED: '+screen);
  }
  function result(label, state, detail) {
    checks.push({label:label,state:state,detail:detail||''});
    var li = document.createElement('li'); li.dataset.state = state;
    li.textContent = (state==='pass'?'✓ ':state==='warn'?'! ':'✕ ')+label+
      (detail?' · '+String(detail).slice(0,110):'');
    output.appendChild(li);
    status.textContent = 'Проверено: '+checks.length;
  }
  async function test(label, fn) {
    try { await fn(); result(label,'pass',''); }
    catch (err) { result(label,'fail',err && err.message || 'UNEXPECTED_FAILURE'); }
  }
  function timeStamp() {
    var d=new Date();
    return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')+
      ' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
  }
  function deviceName() {
    var ua=navigator.userAgent||'';
    return /iPhone|iPad|iPod/i.test(ua)?'iOS / Safari engine':
      /Android/i.test(ua)?'Android / mobile browser':'Desktop / browser';
  }
  function reportText() {
    var ok=checks.filter(x=>x.state==='pass').length;
    var fail=checks.filter(x=>x.state==='fail').length;
    return ['TaxiCheck · автотест публичного макета','Дата: '+timeStamp(),
      'Платформа: '+deviceName(),'Экран: '+window.innerWidth+' × '+window.innerHeight+' CSS px',
      'Итог: '+ok+' PASS, '+fail+' FAIL',
      'Проверены только синтетические операции в временном макете; нет проверки реальных денег, физических касаний или Apps Script.',
      ''].concat(checks.map(x=>(x.state==='pass'?'[PASS] ':x.state==='warn'?'[WARN] ':'[FAIL] ')+x.label+(x.detail?' — '+x.detail:''))).join('\n');
  }
  window.addEventListener('error',function(e){ errors.push('JS_ERROR'); });
  window.addEventListener('unhandledrejection',function(e){ errors.push('UNHANDLED_REJECTION'); });
  async function run() {
    if (busy) return; busy=true; again.disabled=true; copy.disabled=true; share.disabled=true;
    checks=[]; errors=[]; output.replaceChildren(); status.textContent='Запуск…';
    var startCash='',startNet='',initialNav='home',initialMode='shift';
    try {
      var active=$('[data-nav].active'); if(active && active.dataset.nav) initialNav=active.dataset.nav;
      initialMode=element('#modeCustom').classList.contains('active')?'custom':'shift';
      await test('Страница и скрипты загрузились',function(){
        requireThat(!!$('#home')&&!!$('#report')&&!!$('#detail'),'APP_NOT_READY');
        requireThat(!!$('#homeCashValue')&&!!$('#homeNetValue'),'KPI_NOT_FOUND');
      });
      await test('Данные явно помечены как демонстрационные',function(){
        requireThat(/демонстрац|вымышлен/i.test(element('#globalNotice').textContent),'DEMO_WARNING_MISSING');
      });
      await test('Главная и два основных показателя',function(){
        clickNav('home');
        startCash=element('#homeCashValue').textContent.trim();
        startNet=element('#homeNetValue').textContent.trim();
        requireThat(startCash!=='' && startCash!=='—' && startNet!=='' && startNet!=='—','HOME_KPI_EMPTY');
      });
      await test('Лента смен и переход через полночь',function(){
        var ribbon=element('#shiftRibbon');
        var chips=ribbon.querySelectorAll('[data-shift-id]');
        requireThat(chips.length>=3,'SHIFT_CHOICES_MISSING');
        requireThat(Array.from(chips).some(x=>x.textContent.includes('→')),'OVERNIGHT_SHIFT_MISSING');
      });
      await test('Переключение режимов периода',function(){
        element('#modeCustom').click();
        requireThat(visible(element('#customModePanel')),'CUSTOM_PERIOD_HIDDEN');
        requireThat(element('#from').type==='date' && element('#to').type==='date','NATIVE_DATES_MISSING');
        requireThat(element('#timeFrom').type==='time'&&element('#timeTo').type==='time','NATIVE_TIMES_MISSING');
        element('#modeShifts').click();
        requireThat(visible(element('#shiftModePanel')),'SHIFT_PERIOD_HIDDEN');
      });
      await test('Вкладка отчёта и восемь плиток',function(){
        clickNav('report');
        requireThat(element('#tileGrid').querySelectorAll('[data-screen]').length===8,'EIGHT_TILES_MISSING');
        requireThat(!!element('#tileGross').textContent.trim()&&!!element('#tileRent').textContent.trim(),'REPORT_TOTALS_MISSING');
      });
      for (var key of Object.keys(titles)) {
        await test('Раздел: '+titles[key],function(){
          clickNav('report');
          element('#tileGrid [data-screen="'+key+'"]').click();
          requireThat(visible(element('#detail')),'DETAIL_NOT_OPENED');
          requireThat(!!element('#detailHero').textContent.trim(),'DETAIL_EMPTY');
          requireThat(element('#detailTitle').textContent.trim().length>0,'DETAIL_TITLE_MISSING');
        });
      }
      await test('Экран чистого заработка',function(){
        clickNav('home');
        element('#home [data-screen="earnings"]').click();
        requireThat(visible(element('#detail')),'EARNINGS_NOT_OPENED');
      });
      await test('Аналитика доступна',function(){
        clickNav('analytics');
        requireThat(!!element('#analytics').textContent.trim(),'ANALYTICS_EMPTY');
      });
      await test('Настройки и ручной QA-чек-лист',function(){
        clickNav('settings');
        requireThat(!!element('#qaChecklistPanel'),'MANUAL_QA_MISSING');
        requireThat(!!element('#openConnections'),'CONNECTIONS_ENTRY_MISSING');
      });
      await test('Экран входа не авторизует пользователей',function(){
        clickNav('settings');
        element('#openConnections').click();
        requireThat(visible(element('#detail')),'CONNECTIONS_NOT_OPENED');
        requireThat(/демо|демонстрац/i.test(element('#detailContent').textContent),'CONNECTIONS_DEMO_NOTICE_MISSING');
      });
      await test('Основные показатели не изменились от навигации',function(){
        clickNav('home');
        requireThat(startCash===element('#homeCashValue').textContent.trim() &&
          startNet===element('#homeNetValue').textContent.trim(),'READ_ONLY_NAV_CHANGED_NUMBERS');
      });
      await test('Нет горизонтального выхода интерфейса',function(){
        requireThat(document.documentElement.scrollWidth <= window.innerWidth+3,'HORIZONTAL_OVERFLOW');
      });
      if(window.TaxiCheckAdvancedQa && typeof window.TaxiCheckAdvancedQa.run==='function'){
        try{await window.TaxiCheckAdvancedQa.run(result);}
        catch(e){result('Этапы 2–3: выполнение расширенных тестов','fail',String(e&&e.message||e));}
      }else{result('Этапы 2–3: набор проверок доступен','fail','ADVANCED_SUITE_MISSING');}
      await test('Нет обнаруженных ошибок JavaScript',function(){
        requireThat(!errors.length, errors[0]||'JS_RUNTIME_ERROR');
      });
    } finally {
      // Restore only navigation and filter view. Never invoke save, sync, reset or financial changes.
      try { if(initialMode==='custom')element('#modeCustom').click();else element('#modeShifts').click(); } catch (_) {}
      try { clickNav(['home','report','analytics','settings'].includes(initialNav)?initialNav:'home'); } catch (_) {}
      var fail=checks.filter(x=>x.state==='fail').length;
      status.textContent=fail?'✕ Ошибки: '+fail+' из '+checks.length:'✓ Успешно: '+checks.length+' из '+checks.length;
      copy.disabled=false; share.disabled=false; again.disabled=false; busy=false;
      window.TaxiCheckQaLastReport = {total:checks.length,failed:fail,complete:true};
    }
  }
  async function copyReport() {
    var t=reportText();
    try {
      if(navigator.clipboard && navigator.clipboard.writeText){await navigator.clipboard.writeText(t);}
      else {
        var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';
        document.body.appendChild(a);a.select();
        requireThat(document.execCommand('copy'),'COPY_NOT_ALLOWED');a.remove();
      }
      status.textContent='Отчёт скопирован';
    } catch (_) { status.textContent='Копирование недоступно. Используй «Поделиться».'; }
  }
  again.addEventListener('click',function(){ run(); });
  copy.addEventListener('click',function(){ copyReport(); });
  share.addEventListener('click',async function(){
    if(!navigator.share){await copyReport();return;}
    try {await navigator.share({title:'TaxiCheck · автотест',text:reportText()});}
    catch (err) {if(err && err.name!=='AbortError') status.textContent='Поделиться не удалось';}
  });
  $('.tcQaClose').addEventListener('click',function(){panel.hidden=true;});
  run();
})();
