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
  console.log('Remote progress HUD: 8 scenarios PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
