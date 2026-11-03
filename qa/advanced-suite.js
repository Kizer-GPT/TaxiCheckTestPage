/* TaxiCheck public synthetic mockup ONLY: isolated mobile QA stages 2 + 3.
   The fixture is a second same-origin iframe; writes affect ONLY that iframe's
   in-memory fake records. Never operate on an Apps Script page, real accounts,
   or any form in the tester's primary page. This script does nothing unless
   ?qa=run and the public synthetic-data warning is present. */
(function () {
  'use strict';
  if (new URLSearchParams(location.search).get('qa') !== 'run') return;
  const marker = document.querySelector('.demo-notice');
  if (!marker || !/вымышлен|демонстрац/i.test(marker.textContent)) return;

  function assert(condition, code) {
    if (!condition) throw new Error(code);
  }
  function amount(raw) {
    const compact = String(raw).replace(/[\u00a0\u202f\s₽]/g, '').replace(',', '.');
    const match = compact.match(/-?\d+(?:\.\d{1,2})?/);
    const s = match ? match[0] : '';
    const number = Number(s);
    assert(s && Number.isFinite(number), 'NOT_NUMERIC: '+String(raw).slice(0,24));
    return Math.round(number * 100);
  }
  function near(actual, expected, code) {
    assert(Math.abs(actual - expected) <= 1, code + ': ' + actual + ' != ' + expected);
  }
  function tempFrame() {
    return new Promise((resolve, reject) => {
      const iframe = document.createElement('iframe');
      iframe.setAttribute('aria-hidden', 'true');
      iframe.setAttribute('tabindex', '-1');
      iframe.setAttribute('title', 'Временный макет для автоматической проверки');
      iframe.style.cssText = 'position:fixed;left:-10000px;top:0;width:390px;height:820px;border:0;visibility:hidden;pointer-events:none';
      let settled = false;
      const timeout = setTimeout(() => { if (!settled) { settled = true; iframe.remove(); reject(new Error('QA_FIXTURE_TIMEOUT')); } }, 12000);
      iframe.addEventListener('load', () => {
        if (settled) return;
        settled = true; clearTimeout(timeout);
        try {
          assert(iframe.contentDocument && iframe.contentDocument.querySelector('#homeCashValue'), 'QA_FIXTURE_NOT_READY');
          assert(iframe.contentDocument.querySelector('.demo-notice'), 'NOT_PUBLIC_DEMO');
          resolve(iframe);
        } catch (err) { iframe.remove(); reject(err); }
      }, {once: true});
      iframe.addEventListener('error', () => {
        if (!settled) { settled = true; clearTimeout(timeout); iframe.remove(); reject(new Error('QA_FIXTURE_LOAD_ERROR')); }
      }, {once: true});
      // Explicitly do not inherit ?qa=run: prevent recursive tests and duplicate panels.
      const url = new URL(location.href);
      url.search = '?qa_fixture=1';
      url.hash = '';
      iframe.src = url.href;
      document.body.appendChild(iframe);
    });
  }
  function fixture(f) {
    const doc = f.contentDocument;
    const win = f.contentWindow;
    const el = selector => {
      const item = doc.querySelector(selector);
      assert(item, 'MISSING: ' + selector);
      return item;
    };
    const click = selector => el(selector).click();
    const input = (selector,value) => {
      const item=el(selector); item.value=String(value);
      item.dispatchEvent(new win.Event('input',{bubbles:true}));
      item.dispatchEvent(new win.Event('change',{bubbles:true}));
    };
    const nav = screen => {
      click('[data-nav="'+screen+'"]');
      assert(!el(screen==='settings'?'#detail':'#'+screen).hidden,'NO_SCREEN: '+screen);
    };
    const detail = screen => {
      nav('report');
      click('#tileGrid [data-screen="'+screen+'"]');
      assert(!el('#detail').hidden, 'DETAIL_NOT_SHOWN: '+screen);
    };
    const rub = selector => amount(el(selector).textContent);
    const record = tag => {
      const list=Array.from(doc.querySelectorAll('#detailContent .record'));
      const item=list.find(x=>x.textContent.includes(tag));
      assert(item,'TEST_RECORD_NOT_FOUND: '+tag);
      return item;
    };
    const expandedRecord = tag => {
      let item=record(tag);
      item.querySelector('[data-expand]').click();
      item=record(tag);
      assert(item.querySelector('[data-edit]') && item.querySelector('[data-delete]'), 'RECORD_ACTIONS_MISSING');
      return item;
    };
    const saveRecord = (type,tag,number,more) => {
      detail(type);
      click('#detailContent [data-add="'+type+'"]');
      input('#amountInput',number);
      input('#commentInput',tag);
      if(more && more.litres){input('#litresInput',more.litres);input('#priceInput',more.price);}
      click('#saveEntry');
      record(tag);
    };
    const editRecord = (type,tag,number) => {
      detail(type);
      const item=expandedRecord(tag);
      item.querySelector('[data-edit]').click();
      assert(!!doc.querySelector('#entryForm'), 'EDIT_FORM_MISSING');
      input('#amountInput',number);
      click('#saveEntry');
      record(tag);
    };
    const deleteRecord = (type,tag) => {
      detail(type);
      const item=expandedRecord(tag);
      const originalConfirm=win.confirm;
      try {
        win.confirm=()=>true;
        item.querySelector('[data-delete]').click();
      } finally {win.confirm=originalConfirm;}
      assert(!Array.from(doc.querySelectorAll('#detailContent .record')).some(x=>x.textContent.includes(tag)),
        'DELETED_RECORD_STILL_VISIBLE');
    };
    return {doc,win,el,click,input,nav,detail,rub,record,expandedRecord,saveRecord,editRecord,deleteRecord};
  }

  async function run(report) {
    let frame=null;
    try {
      frame = await tempFrame();
    } catch(err) {
      report('Этапы 2–3: создание независимого макета','fail',err.message||String(err));
      return;
    }
    const f=fixture(frame), doc=f.doc, win=f.win;
    let jsErrors=0,baseline,baselineFuel,baselineOther;
    win.addEventListener('error',()=>jsErrors++);
    win.addEventListener('unhandledrejection',()=>jsErrors++);
    async function check(name,fn) {
      try {await fn();report(name,'pass');}
      catch(err) {report(name,'fail',String(err&&err.message||err).slice(0,130));}
    }
    try {
      await check('Изоляция: отдельная копия макета',() => {
        assert(frame.contentWindow!==window,'NOT_ISOLATED');
        assert(frame.contentDocument!==document,'NOT_ISOLATED_DOM');
        assert(!frame.contentDocument.querySelector('#tcAutoQa'),'NESTED_TEST');
        assert(/вымышлен|демонстрац/i.test(f.el('.demo-notice').textContent),'NOT_SYNTHETIC');
      });
      await check('Этап 2: мобильная навигация и фиксированная панель',()=>{
        const nav=f.el('#bottomNav'),css=win.getComputedStyle(nav);
        assert(css.position==='fixed','NAV_NOT_FIXED');
        const buttons=nav.querySelectorAll('[data-nav]');
        assert(buttons.length===4,'NOT_FOUR_NAV_TABS');
        for(const b of buttons){assert(b.getBoundingClientRect().height>=44,'SMALL_NAV_TOUCH_TARGET');}
      });
      await check('Этап 2: кнопки смен и режимов удобного размера',()=>{
        for(const selector of ['#modeShifts','#modeCustom','#shiftEditToggle','.shift-chip']){
          const b=f.el(selector);
          assert(b.getBoundingClientRect().height>=44,'SMALL_TOUCH_TARGET: '+selector);
        }
      });
      await check('Этап 2: корректные типы полей даты, времени, суммы',()=>{
        assert(f.el('#from').type==='date'&&f.el('#to').type==='date','DATE_INPUT_TYPE');
        assert(f.el('#timeFrom').type==='time'&&f.el('#timeTo').type==='time','TIME_INPUT_TYPE');
        f.nav('home');f.click('[data-quick="cash"]');
        assert(f.el('#quickAmount').type==='number','MONEY_INPUT_TYPE');
        assert(f.el('#quickComment').maxLength===180,'COMMENT_LIMIT');
        assert(win.getComputedStyle(f.el('#quickAmount')).fontSize, 'INPUT_STYLE_MISSING');
        f.click('#quickEntryClose');
      });
      await check('Этап 2: нет боковой прокрутки на главной',()=>{
        f.nav('home');
        assert(doc.documentElement.scrollWidth<=win.innerWidth+3,'HOME_HORIZONTAL_OVERFLOW');
      });
      await check('Этап 2: нет боковой прокрутки в отчёте',()=>{
        f.nav('report');
        assert(doc.documentElement.scrollWidth<=win.innerWidth+3,'REPORT_HORIZONTAL_OVERFLOW');
      });
      await check('Этап 2: нет боковой прокрутки в детализации',()=>{
        for(const name of ['cash','fuel','other','commissions']){
          f.detail(name);
          assert(doc.documentElement.scrollWidth<=win.innerWidth+3,'DETAIL_OVERFLOW: '+name);
        }
      });
      await check('Этап 2: неверные даты не меняют период',()=>{
        f.nav('home');f.click('#modeCustom');
        const from=f.el('#from').value,to=f.el('#to').value;
        f.input('#from','2026-10-26');f.input('#to','2026-10-21');
        f.click('#periodShow');
        assert(/Проверь даты/i.test(f.el('#toast').textContent),'INVALID_DATE_NOT_REJECTED');
        f.input('#from',from);f.input('#to',to);
        f.click('#modeShifts');
        assert(!f.el('#shiftModePanel').hidden,'MODE_RESTORE_FAILED');
      });
      await check('Этап 2: поля демонстрационного логина заблокированы',()=>{
        f.nav('settings');f.click('#openConnections');
        f.click('[data-preview-login="apark"]');
        assert(f.el('#mockLogin').disabled&&f.el('#mockPassword').disabled,'LOGIN_FIELDS_ENABLED');
        assert(f.el('.login-mockup-submit').disabled,'LOGIN_SUBMIT_ENABLED');
      });
      await check('Этап 2: пробный неверный ввод не сохраняется',()=>{
        f.nav('home');
        baseline=f.rub('#homeNetValue');
        f.click('[data-quick="cash"]');
        f.input('#quickAmount',0);
        f.el('#quickEntryForm').dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));
        near(f.rub('#homeNetValue'),baseline,'INVALID_QUICK_CHANGED_NET');
        assert(!f.el('#quickEntryForm').hidden,'INVALID_QUICK_CLOSED_FORM');
        f.click('#quickEntryClose');
      });
      await check('Этап 2: ночная смена сохраняет границу после полуночи',()=>{
        f.nav('home');
        const current=f.el('#shiftRibbon [data-shift-id="s22"]');
        assert(current.textContent.includes('→'),'NIGHT_END_MISSING');
        assert(f.el('#periodLine').textContent.includes('23.10'),'CROSS_MIDNIGHT_DATE_MISSING');
      });
      await check('Этап 3: арифметика кассы, комиссии и аренды',()=>{
        f.nav('report');
        near(f.rub('#tileGross')-f.rub('#tileCommissions'),f.rub('#tileCash'),'GROSS_MINUS_FEES');
        near(f.rub('#tileRentBonus')+f.rub('#tileRentMain'),f.rub('#tileRent'),'RENT_BONUS_RECONCILIATION');
      });
      await check('Этап 3: чистыми = касса − комиссия − аренда деньгами − расходы',()=>{
        f.nav('report');
        const expected=f.rub('#tileGross')-f.rub('#tileCommissions')-f.rub('#tileRentMain')-
          f.rub('#tileFuel')-f.rub('#tileOther');
        near(f.rub('#homeNetValue'),expected,'NET_INVARIANT');
      });
      await check('Этап 3: наличный заказ увеличивает кассу и чистыми',()=>{
        f.nav('home');baseline={cash:f.rub('#homeCashValue'),net:f.rub('#homeNetValue')};
        f.click('[data-quick="cash"]');f.input('#quickAmount',125.25);
        f.input('#quickComment','QA CASH 7431');
        f.el('#quickEntryForm').dispatchEvent(new win.Event('submit',{bubbles:true,cancelable:true}));
        near(f.rub('#homeCashValue'),baseline.cash+12525,'CASH_AFTER_CREATE');
        near(f.rub('#homeNetValue'),baseline.net+12525,'NET_AFTER_CASH');
        f.detail('cash');f.record('QA CASH 7431');
      });
      await check('Этап 3: изменение наличных пересчитывает результат',()=>{
        f.editRecord('cash','QA CASH 7431',225.25);
        near(f.rub('#homeCashValue'),baseline.cash+22525,'CASH_AFTER_EDIT');
        near(f.rub('#homeNetValue'),baseline.net+22525,'NET_AFTER_CASH_EDIT');
      });
      await check('Этап 3: удаление наличных восстанавливает кассу',()=>{
        f.deleteRecord('cash','QA CASH 7431');
        near(f.rub('#homeCashValue'),baseline.cash,'CASH_AFTER_DELETE');
        near(f.rub('#homeNetValue'),baseline.net,'NET_AFTER_CASH_DELETE');
      });
      await check('Этап 3: заправка уменьшает чистыми',()=>{
        f.nav('report');baselineFuel={fuel:f.rub('#tileFuel'),net:f.rub('#homeNetValue')};
        f.saveRecord('fuel','QA FUEL 7431',200.50,{litres:3.00,price:66.83});
        near(f.rub('#tileFuel'),baselineFuel.fuel+20050,'FUEL_AFTER_CREATE');
        near(f.rub('#homeNetValue'),baselineFuel.net-20050,'NET_AFTER_FUEL_CREATE');
      });
      await check('Этап 3: изменение заправки пересчитывает расход',()=>{
        f.editRecord('fuel','QA FUEL 7431',300.50);
        near(f.rub('#tileFuel'),baselineFuel.fuel+30050,'FUEL_AFTER_EDIT');
        near(f.rub('#homeNetValue'),baselineFuel.net-30050,'NET_AFTER_FUEL_EDIT');
      });
      await check('Этап 3: удаление заправки восстанавливает итог',()=>{
        f.deleteRecord('fuel','QA FUEL 7431');
        near(f.rub('#tileFuel'),baselineFuel.fuel,'FUEL_AFTER_DELETE');
        near(f.rub('#homeNetValue'),baselineFuel.net,'NET_AFTER_FUEL_DELETE');
      });
      await check('Этап 3: прочий расход уменьшает чистыми',()=>{
        f.nav('report');baselineOther={other:f.rub('#tileOther'),net:f.rub('#homeNetValue')};
        f.saveRecord('other','QA OTHER 7431',80.25);
        near(f.rub('#tileOther'),baselineOther.other+8025,'OTHER_AFTER_CREATE');
        near(f.rub('#homeNetValue'),baselineOther.net-8025,'NET_AFTER_OTHER_CREATE');
      });
      await check('Этап 3: изменение прочего расхода пересчитывает итог',()=>{
        f.editRecord('other','QA OTHER 7431',90.25);
        near(f.rub('#tileOther'),baselineOther.other+9025,'OTHER_AFTER_EDIT');
        near(f.rub('#homeNetValue'),baselineOther.net-9025,'NET_AFTER_OTHER_EDIT');
      });
      await check('Этап 3: удаление прочего расхода восстанавливает итог',()=>{
        f.deleteRecord('other','QA OTHER 7431');
        near(f.rub('#tileOther'),baselineOther.other,'OTHER_AFTER_DELETE');
        near(f.rub('#homeNetValue'),baselineOther.net,'NET_AFTER_OTHER_DELETE');
      });
      await check('Этап 3: бонусы не прибавляются повторно к прибыли',()=>{
        f.nav('report');
        const expected=f.rub('#tileCash')-f.rub('#tileRentMain')-f.rub('#tileFuel')-f.rub('#tileOther');
        near(f.rub('#homeNetValue'),expected,'BONUS_DOUBLE_COUNT');
      });
      await check('Этап 3: отмена редактирования не меняет суммы',()=>{
        f.detail('cash');
        const old=f.rub('#homeNetValue');
        f.click('#detailContent [data-add="cash"]');
        f.input('#amountInput',9999);
        f.click('#cancelEntry');
        near(f.rub('#homeNetValue'),old,'CANCEL_MUTATED_NET');
        assert(!doc.querySelector('#entryForm'),'CANCEL_DID_NOT_CLOSE');
      });

      await check('Презентация: одно нажатие имитирует заказ, но не обращается к API',async()=>{
        f.nav('report');
        const base={gross:f.rub('#tileGross'),fees:f.rub('#tileCommissions'),cash:f.rub('#tileCash'),net:f.rub('#homeNetValue')};
        const originalFetch=win.fetch;
        const originalXHR=win.XMLHttpRequest;
        let network=0;
        try{
          win.fetch=function(){network++;throw new Error('DEMO_NETWORK_FORBIDDEN')};
          win.XMLHttpRequest=function(){network++;throw new Error('DEMO_XHR_FORBIDDEN')};
          f.click('#refreshBtn');
          assert(f.el('#refreshBtn').disabled,'DEMO_REFRESH_NOT_LOADING');
          assert(f.el('[data-demo-source="main"]').dataset.status==='running','DEMO_LAMP_NOT_YELLOW');
          await new Promise(resolve=>setTimeout(resolve,1350));
        }finally{win.fetch=originalFetch;win.XMLHttpRequest=originalXHR}
        assert(network===0,'DEMO_NETWORK_USED');
        assert(!f.el('#refreshBtn').disabled,'DEMO_REFRESH_STUCK');
        assert(f.el('[data-demo-source="main"]').dataset.status==='success','DEMO_LAMP_NOT_GREEN');
        near(f.rub('#tileGross'),base.gross+138000,'DEMO_GROSS_NOT_UPDATED');
        near(f.rub('#tileCommissions'),base.fees+35880,'DEMO_FEES_NOT_UPDATED');
        near(f.rub('#tileCash'),base.cash+102120,'DEMO_AFTER_FEES_NOT_UPDATED');
        near(f.rub('#homeNetValue'),base.net+102120,'DEMO_NET_NOT_UPDATED');
        assert(/вымышлен|демо/i.test(f.el('#demoSyncNote').textContent),'DEMO_WARNING_MISSING');
        f.detail('cash');f.record('TC-DEMO-101');
        f.detail('commissions');f.record('TC-DEMO-101');
        f.nav('settings');f.click('#resetDemo');
        near(f.rub('#tileGross'),base.gross,'DEMO_RESET_GROSS');
        near(f.rub('#homeNetValue'),base.net,'DEMO_RESET_NET');
      });

      await check('Этап 3: JS-ошибок в пробных сценариях нет',()=>{
        assert(jsErrors===0,'QA_FIXTURE_JAVASCRIPT_ERROR');
      });
    } finally {
      frame.remove(); // drops all synthetic CRUD changes and temporary focus/state
    }
  }
  window.TaxiCheckAdvancedQa = Object.freeze({run});
})();
