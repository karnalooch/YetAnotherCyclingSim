// Exercise HUD behavior without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync(__dirname + '/remote-progress.js', 'utf8');
async function draw(data) {
  const elements = Object.fromEntries(['phase','bar','detail','counts','age','state'].map(id => [id, {textContent:'',removeAttribute(name){delete this[name];}}]));
  const section = {classList:{toggle(name,value){this[name]=value;}}};
  const root = {getElementById:id=>elements[id],querySelector:()=>section};
  const host = {style:{},attachShadow:()=>root};
  let fetches=0;
  const context = {
    document:{getElementById:()=>null,createElement:()=>host,body:{appendChild(){}}},
    fetch:async(url, options)=>{assert.equal(url,'/yacs-progress.data.js');assert.equal(options.cache,'no-store');fetches++;return {ok:true,json:async()=>data};},
    AbortSignal, Date, setTimeout(){},setInterval(){}
  };
  vm.runInNewContext(script,context);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(fetches,1);
  assert.match(host.style.cssText,/pointer-events:none/);
  return {elements,section};
}
(async()=>{
  const row={schema_version:1,observed_utc:new Date().toISOString(),operation_status:'CONTACT_JOB_RUNNING',phase:'VERIFY_CURRENT_NATIVE_GEOMETRY',triangles_read:350,triangles_per_scan:200,placed:0,accepted:1,rejected:4};
  let ui=await draw(row);
  assert.equal(ui.elements.bar.value,75,'second pass must subtract first pass');
  assert.match(ui.elements.counts.textContent,/Posadzone: 0/);
  ui=await draw({...row,phase:'READ_CURRENT_NATIVE_GEOMETRY',triangles_per_scan:null});
  assert.equal(ui.elements.bar.value,undefined,'unknown total must not show a percentage');
  ui=await draw({...row,observed_utc:'2000-01-01T00:00:00Z'});
  assert.equal(ui.elements.state.textContent,'Brak świeżych danych');
  assert.equal(ui.elements.bar.hidden,true);
  ui=await draw({...row,observer_alive:false});
  assert.equal(ui.elements.state.textContent,'Brak świeżych danych');
  ui=await draw({...row,error:true,operation_status:'CONTACT_JOB_FAILED_ROLLED_BACK'});
  assert.equal(ui.elements.state.textContent,'Zatrzymano');
  assert.equal(ui.elements.bar.hidden,true);
  ui=await draw({...row,operation_status:'CONTACT_JOB_COMPLETED_SAMPLED_ONLY',phase:'COMPLETED',placed:1});
  assert.equal(ui.elements.bar.value,100);
  assert.equal(ui.elements.state.textContent,'Gotowe');
  assert.match(ui.elements.detail.textContent,/podgląd do oceny/);
  ui=await draw({...row,triangles_read:null});
  assert.equal(ui.elements.bar.value,undefined);
  ui=await draw({...row,operation_status:'CONTACT_JOB_COMPLETED_CALLBACK_CLEANUP_REQUIRED'});
  assert.equal(ui.elements.state.textContent,'Zatrzymano');
  for (const phase of ['READ_CURRENT_NATIVE_GEOMETRY','MEASURE_LANDSCAPE_CONTACT','VERIFY_CURRENT_NATIVE_GEOMETRY']) {
    for (const [status,label,state] of [
      ['CONTACT_JOB_CANCELLED_ROLLED_BACK','Próba zatrzymana','Przerwano'],
      ['CONTACT_JOB_CLEARED','Grupa usunięta','Gotowe']
    ]) {
      ui=await draw({...row,phase,operation_status:status,placed:0,accepted:2,rejected:1});
      assert.equal(ui.elements.phase.textContent,label,'terminal status must override retained phase');
      assert.equal(ui.elements.state.textContent,state,'normal stop must not become a failure');
      assert.equal(ui.elements.bar.hidden,true);
      assert.equal(ui.elements.bar.value,undefined);
      assert.equal(ui.elements.detail.textContent,'','inactive attempt must not retain triangle or contact detail');
      assert.match(ui.elements.counts.textContent,/Posadzone: 0/);
      assert.match(ui.elements.counts.textContent,/Historia kontaktu — OK: 2 · Odrzucone: 1/);
    }
  }
  ui=await draw({...row,operation_status:'CONTACT_JOB_CANCELLED_ROLLED_BACK',observed_utc:'2000-01-01T00:00:00Z'});
  assert.equal(ui.elements.state.textContent,'Brak świeżych danych','terminal status must preserve freshness warning');
  assert.equal(ui.elements.phase.textContent,'Próba zatrzymana');
  console.log('Remote progress HUD: 15 scenarios PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
