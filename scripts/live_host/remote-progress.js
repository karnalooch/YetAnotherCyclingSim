/* Read-only same-origin progress HUD. It never sends editor commands. */
(() => {
  'use strict';
  if (document.getElementById('yacs-progress-hud')) return;
  const host = document.createElement('aside');
  host.id = 'yacs-progress-hud';
  host.style.cssText = 'position:fixed;left:18px;top:64px;z-index:2147483000;pointer-events:none;width:min(330px,calc(100vw - 36px));';
  const root = host.attachShadow({mode: 'open'});
  root.innerHTML = `<style>
    :host {color:#edf4f1;font:13px/1.5 system-ui,sans-serif;}
    section {background:rgba(12,23,22,.91);border:1px solid #49605a;border-radius:12px;padding:14px 16px;box-shadow:0 8px 32px #0005;}
    header {display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
    strong {font-size:14px;} #state {font-size:11px;color:#8cdbc0;}
    #phase {font-size:14px;margin-bottom:8px;} progress {width:100%;height:7px;accent-color:#8cdbc0;}
    #detail {color:#c3d0ca;font-variant-numeric:tabular-nums;margin-top:6px;}
    #counts {border-top:1px solid #49605a;padding-top:8px;margin-top:10px;}
    #age {color:#a6b5ae;font-size:11px;margin-top:6px;}
    .stale #state {color:#ffce80;}
  </style><section><header><strong>Sadzenie kamieni</strong><span id="state">Łączenie…</span></header>
  <div id="phase">Oczekiwanie na odczyt</div><progress id="bar" max="100"></progress>
  <div id="detail"></div><div id="counts"></div><div id="age"></div></section>`;
  document.body.appendChild(host);
  const el = id => root.getElementById(id);
  const labels = {
    NO_CONTACT_JOB:'Oczekiwanie na zasiew', STARTED_PENDING_CURRENT_NATIVE_EXCLUSIONS:'Przygotowanie kontroli terenu',
    BIND_CURRENT_NATIVE_MESH_CHANGE_GUARDS:'Przygotowanie kontroli geometrii',
    READ_CURRENT_NATIVE_GEOMETRY:'1/3 · Skan drogi i otoczenia',
    MEASURE_LANDSCAPE_CONTACT:'2/3 · Pomiar kontaktu z podłożem',
    VERIFY_CURRENT_NATIVE_GEOMETRY:'3/3 · Końcowa kontrola geometrii',
    APPLY_VERIFIED_DIAGNOSTIC_LOCATIONS:'Ustawianie zaakceptowanych kamieni', COMPLETED:'Zakończono próbny zasiew'
  };
  const fmt = value => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString('pl-PL') : '—';
  let last = null;
  function render() {
    if (!last) return;
    const age = (Date.now() - Date.parse(last.observed_utc)) / 1000;
    const fresh = Number.isFinite(age) && age >= -5 && age <= 35 && last.observer_alive !== false;
    root.querySelector('section').classList.toggle('stale', !fresh);
    const failed = last.error === true || /FAILED|ROLLBACK_INCOMPLETE|CLEANUP_REQUIRED/.test(last.operation_status || '');
    const done = /COMPLETED/.test(last.operation_status || '');
    el('state').textContent = !fresh ? 'Brak świeżych danych' : failed ? 'Zatrzymano' : done ? 'Gotowe' : 'Na żywo';
    el('phase').textContent = failed ? 'Zasiew zatrzymany — sprawdź wynik w czacie' : labels[last.phase] || labels[last.operation_status] || 'Oczekiwanie na kolejny etap';
    let numerator = null, denominator = null, detail = '';
    if (last.phase === 'VERIFY_CURRENT_NATIVE_GEOMETRY' && Number.isSafeInteger(last.triangles_read) && Number.isSafeInteger(last.triangles_per_scan) && last.triangles_per_scan > 0) {
      numerator = last.triangles_read - last.triangles_per_scan; denominator = last.triangles_per_scan;
      detail = `${fmt(numerator)} / ${fmt(denominator)} trójkątów`;
    } else if (last.phase === 'MEASURE_LANDSCAPE_CONTACT') {
      numerator = last.sampled_positions; denominator = last.maximum_grid_positions;
      detail = `${fmt(numerator)} / maks. ${fmt(denominator)} pomiarów${last.active_site ? ' · '+last.active_site : ''}`;
    } else if (last.phase === 'READ_CURRENT_NATIVE_GEOMETRY') {
      detail = `${fmt(last.triangles_read)} sprawdzonych trójkątów`;
    } else if (done) {
      numerator = 1; denominator = 1; detail = 'Próba zakończona · podgląd do oceny';
    }
    const percent = Number.isFinite(numerator) && denominator > 0 ? Math.max(0, Math.min(100, 100*numerator/denominator)) : null;
    if (percent !== null && !failed) el('bar').value = percent; else el('bar').removeAttribute('value');
    el('bar').hidden = !fresh || failed;
    el('detail').textContent = detail;
    el('counts').textContent = `Posadzone: ${fmt(last.placed)} · Kontakt OK: ${fmt(last.accepted)} · Odrzucone: ${fmt(last.rejected)}`;
    el('age').textContent = Number.isFinite(age) ? `Odczyt ${Math.max(0,Math.floor(age))} s temu · odświeżanie co 10 s` : 'Czas odczytu niedostępny';
  }
  async function poll() {
    try {
      const response = await fetch('/yacs-progress.json', {cache:'no-store', signal:AbortSignal.timeout(4000)});
      if (!response.ok) throw new Error('Unavailable');
      const data = await response.json();
      if (data.schema_version !== 1 || typeof data.observed_utc !== 'string') throw new Error('Invalid progress');
      last = data; render();
    } catch (_) {
      if (last) render(); else el('state').textContent = 'Oczekiwanie na dane';
    } finally { setTimeout(poll, 2500); }
  }
  setInterval(render, 1000);
  poll();
})();
