/* Shared feature destinations drive both Help and the guided tour. Inlined by build_web.py. */
const mobileUI=matchMedia("(max-width:880px)");
const app=document.querySelector(".app"),stageWrap=document.querySelector(".stagewrap");
app.classList.add("explorer");
const rail=document.querySelector(".rail"),scenePanel=rail.children[0],viewsPanel=rail.children[1],sectionPanel=rail.children[2];
const layersPanel=document.querySelector(".modules"),specsPanel=document.querySelector(".sheets"),storyPanel=document.querySelector(".story");
const notePanel=document.getElementById("note");
specsPanel.appendChild(notePanel);
sectionPanel.appendChild(document.getElementById("reset"));
const bar=document.createElement("div");bar.className="explorer-bar";
bar.innerHTML='<strong>FET Lab</strong><button class="btn" id="choose-scene" aria-expanded="false" aria-controls="scene-chooser">Choose device ▾</button><button class="btn" id="help-open" aria-label="Help, features and guided tour">Help</button><div id="scene-chooser" class="scene-chooser" hidden></div>';
app.before(bar);
const chooser=document.getElementById("scene-chooser"),chooseButton=document.getElementById("choose-scene");
chooser.appendChild(scenePanel);
const sheet=document.createElement("section");sheet.className="tool-sheet";sheet.dataset.level="0";sheet.setAttribute("aria-label","Model controls");
sheet.innerHTML='<div class="sheet-handle"><button id="sheet-toggle" aria-expanded="false" aria-controls="sheet-body">Open controls</button><button id="sheet-expand">Expand</button></div><div class="sheet-tabs" role="tablist" aria-label="Model tools"></div><div class="sheet-body" id="sheet-body"></div>';
app.appendChild(sheet);
const body=sheet.querySelector(".sheet-body"),tabs=sheet.querySelector(".sheet-tabs");
const panels={views:viewsPanel,section:sectionPanel,layers:layersPanel,specs:specsPanel,story:storyPanel};
let toolTab="views",sheetLevel=0,tourStep=-1,tourSnapshot=null,guideTimer=0;
for(const [key,panel] of Object.entries(panels)){
  const b=document.createElement("button");b.textContent=key[0].toUpperCase()+key.slice(1);b.id="tab-"+key;b.setAttribute("role","tab");b.setAttribute("aria-controls","panel-"+key);
  b.onclick=()=>openTool(key);tabs.appendChild(b);
  panel.id="panel-"+key;panel.setAttribute("role","tabpanel");panel.setAttribute("aria-labelledby",b.id);panel.tabIndex=0;
  body.appendChild(panel);
}
rail.remove();
function setChooser(open){chooser.hidden=!open;chooseButton.setAttribute("aria-expanded",String(open));}
chooseButton.onclick=()=>setChooser(chooser.hidden);
chooser.addEventListener("click",e=>{if(e.target.closest("#devs button,#cfetseg button"))setChooser(false);});
document.addEventListener("pointerdown",e=>{if(!bar.contains(e.target))setChooser(false);});
function setSheet(level){
  sheetLevel=Math.max(0,Math.min(2,level));sheet.dataset.level=String(sheetLevel);
  document.getElementById("sheet-toggle").textContent=sheetLevel?"Hide controls":"Open controls";
  document.getElementById("sheet-toggle").setAttribute("aria-expanded",String(sheetLevel>0));
  document.getElementById("sheet-expand").textContent=sheetLevel===2?"Half":"Expand";
  syncInsets();
}
function openTool(key,level){
  toolTab=key;
  for(const [k,p] of Object.entries(panels)){p.hidden=k!==key;const t=document.getElementById("tab-"+k);t.setAttribute("aria-selected",String(k===key));t.tabIndex=k===key?0:-1;}
  sheet.dataset.reading=String(key==="story");body.scrollTop=0;
  setSheet(level===undefined?(key==="story"?2:1):level);
}
tabs.addEventListener("keydown",e=>{
  const keys=Object.keys(panels),i=keys.indexOf(toolTab);
  if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key))return;
  e.preventDefault();const next=e.key==="Home"?0:e.key==="End"?keys.length-1:(i+(e.key==="ArrowRight"?1:-1)+keys.length)%keys.length;
  openTool(keys[next]);document.getElementById("tab-"+keys[next]).focus();
});
document.getElementById("sheet-toggle").onclick=()=>setSheet(sheetLevel?0:1);
document.getElementById("sheet-expand").onclick=()=>setSheet(sheetLevel===2?1:2);
let sheetDrag=null;
sheet.querySelector(".sheet-handle").addEventListener("pointerdown",e=>{if(e.target.closest("button"))return;sheetDrag={y:e.clientY,id:e.pointerId};e.currentTarget.setPointerCapture(e.pointerId);});
sheet.querySelector(".sheet-handle").addEventListener("pointerup",e=>{if(sheetDrag){const dy=e.clientY-sheetDrag.y;if(Math.abs(dy)>28){setSheet(sheetLevel+(dy<0?1:-1));e.preventDefault();}sheetDrag=null;}});
sheet.querySelector(".sheet-handle").addEventListener("pointercancel",()=>{sheetDrag=null;});

const stageTools=document.createElement("div");stageTools.className="stage-tools";
stageTools.innerHTML='<button aria-label="Zoom in">+</button><button aria-label="Zoom out">−</button><button aria-label="Reset camera">Fit</button>';
stageWrap.appendChild(stageTools);
stageTools.children[0].onclick=()=>{S.r=Math.max(40,S.r/1.2);render();};
stageTools.children[1].onclick=()=>{S.r=Math.min(3000,S.r*1.2);render();};
stageTools.children[2].onclick=()=>applyView(Object.keys(DEV.views)[0]);

const card=document.createElement("section");card.className="tour-card";card.hidden=true;card.setAttribute("aria-label","Guided tour");
card.innerHTML='<div aria-live="polite" aria-atomic="true"><strong id="tour-title"></strong><p id="tour-description"></p></div><div class="tour-actions"><button class="btn" id="tour-exit">Skip tour</button><button class="btn" id="tour-back">Back</button><button class="btn" id="tour-next">Next</button></div>';
stageWrap.appendChild(card);
function syncInsets(){
  bottomInset=mobileUI.matches?sheet.getBoundingClientRect().height:0;
  topInset=card.hidden?0:card.getBoundingClientRect().height+20;
  document.getElementById("logicbar").style.bottom=(bottomInset+12)+"px";
  stageTools.style.top=(topInset+32)+"px";
  render();
}
new ResizeObserver(syncInsets).observe(sheet);
new ResizeObserver(syncInsets).observe(card);
new ResizeObserver(()=>{W=cv.clientWidth;H=cv.clientHeight;if(S.view&&DEV.views[S.view])S.r=viewR(DEV.views[S.view]);syncInsets();}).observe(stageWrap);
mobileUI.addEventListener("change",()=>{syncInsets();body.style.visibility="";});

const targetFor=id=>({stage:cv,architecture:chooseButton,views:viewsPanel,section:sectionPanel,layers:layersPanel,specs:specsPanel,story:storyPanel,
  parasitics:document.getElementById("parpanel"),logic:document.getElementById("logicbar"),explode:document.getElementById("ex").closest(".ctl"),
  dimensions:document.getElementById("dims").parentElement,ghost:document.getElementById("ghost").parentElement,display:document.getElementById("edges").parentElement}[id]);
function clearHighlight(){document.querySelectorAll(".guide-highlight").forEach(el=>el.classList.remove("guide-highlight"));}
function highlight(id){
  clearTimeout(guideTimer);clearHighlight();
  const el=targetFor(id);if(!el)return;
  el.classList.add("guide-highlight");
  // Scroll the tool body only; the canvas and page stay in place.
  requestAnimationFrame(()=>{if(body.contains(el))body.scrollTop+=el.getBoundingClientRect().top-body.getBoundingClientRect().top-10;});
  if(tourStep<0)guideTimer=setTimeout(clearHighlight,6500);
}
function navigateTo(feature,touring=false){
  S.spin=false;document.getElementById("spin").checked=false;
  setDevice(feature.scene);S.ex=0;exr.value=0;document.getElementById("vex").textContent="0 nm";
  S.ghost=false;document.getElementById("ghost").checked=false;
  S.dims=feature.id==="dimensions";document.getElementById("dims").checked=S.dims;
  S.inp=0;lbar.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.v==="0")));
  logicText();applyView(feature.view);
  openTool(feature.tab,feature.peek?0:feature.tab==="story"&&!touring?2:1);
  setChooser(feature.target==="architecture");highlight(feature.target);syncInsets();
}

const help=document.createElement("dialog");help.className="help-dialog";help.setAttribute("aria-labelledby","help-title");
help.innerHTML='<div class="help-heading"><h2 id="help-title">Help & features</h2><button class="btn" id="help-close">Close</button></div><button class="btn" id="help-tour">Guided tour</button><label for="feature-search" class="sr-label">Find a feature</label><input id="feature-search" type="search" placeholder="Find views, layers, logic…"><div id="feature-list"></div><details><summary>About FET Lab</summary><p>Explore FinFET, nanosheet, forksheet and CFET structures. Dimensions are teaching approximations. Your tour preference stays on this device.</p><p><a href="https://github.com/ehsanul-karim-pappu/fet-lab">Source</a> · <a href="https://github.com/ehsanul-karim-pappu/fet-lab/issues">Report an issue</a> · <a href="https://github.com/ehsanul-karim-pappu/fet-lab/blob/main/PRIVACY.md">Privacy</a></p></details>';
document.body.appendChild(help);
function populateFeatures(){
  const query=document.getElementById("feature-search").value.toLowerCase(),list=document.getElementById("feature-list");list.replaceChildren();
  for(const f of GUIDE.features){if(!(f.title+" "+f.category+" "+f.description).toLowerCase().includes(query))continue;
    const b=document.createElement("button");b.className="feature-entry";b.dataset.feature=f.id;
    const category=document.createElement("small"),title=document.createElement("strong"),desc=document.createElement("p");
    category.textContent=f.category;title.textContent=f.title;desc.textContent=f.description;b.append(category,title,desc);
    b.onclick=()=>{help.close();if(tourStep>=0)endTour();navigateTo(f);requestAnimationFrame(()=>{const target=targetFor(f.target);(target.querySelector("button,input")||target).focus({preventScroll:true});});};list.appendChild(b);
  }
  if(!list.children.length)list.textContent="No matching features. Try views, layers or logic.";
}
document.getElementById("feature-search").oninput=populateFeatures;
document.getElementById("help-open").onclick=()=>{populateFeatures();help.showModal();};
document.getElementById("help-close").onclick=()=>help.close();
document.getElementById("help-tour").onclick=()=>{help.close();startTour();};

const storageKey="fetlab.tourVersion";
function rememberTour(){try{localStorage.setItem(storageKey,String(GUIDE.version));}catch(_){/* Private or unavailable storage: replay still works. */}}
function startTour(){
  if(tourStep>=0)endTour();rememberTour();
  tourSnapshot={state:{...S,tgt:S.tgt.slice(),clip:S.clip.slice()},tab:toolTab,level:sheetLevel,chooser:!chooser.hidden,
    visibility:DEVS.map(d=>d.parts.map(p=>p.on)),last:JSON.parse(JSON.stringify(LAST)),hot:HOT};
  tourStep=0;card.hidden=false;showTourStep();document.getElementById("tour-next").focus({preventScroll:true});
}
function showTourStep(){
  const f=GUIDE.features.find(f=>f.id===GUIDE.tour[tourStep]);
  document.getElementById("tour-title").textContent=`${tourStep+1} / ${GUIDE.tour.length} · ${f.title}`;
  document.getElementById("tour-description").textContent=f.description;
  document.getElementById("tour-back").disabled=tourStep===0;
  document.getElementById("tour-next").textContent=tourStep===GUIDE.tour.length-1?"Finish":"Next";
  navigateTo(f,true);
}
function endTour(){
  const saved=tourSnapshot;tourStep=-1;tourSnapshot=null;card.hidden=true;clearHighlight();
  if(saved){
    setDevice(saved.state.key);Object.assign(S,saved.state);HOT=saved.hot;
    Object.keys(LAST).forEach(k=>LAST[k]=saved.last[k]);
    DEVS.forEach((d,i)=>d.parts.forEach((p,j)=>{p.on=saved.visibility[i][j];if(p._ck){p._ck.querySelector("input").checked=p.on;p._ck.classList.toggle("off",!p.on);}}));
    for(const [id,key] of Object.entries({ghost:"ghost",dims:"dims",tex:"tex",edges:"edges",spin:"spin",lightbg:"lightBg"}))document.getElementById(id).checked=S[key];
    stageWrap.classList.toggle("light",S.lightBg);exr.value=S.ex/16*100;document.getElementById("vex").textContent=S.ex.toFixed(1)+" nm";
    lbar.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(+b.dataset.v===S.inp)));
    if(S.par){const rows=document.querySelectorAll("#partable tr");DEV.parasitics.terms.forEach((t,i)=>rows[i].setAttribute("aria-pressed",String(t.id===S.par.id)));document.getElementById("parsel").innerHTML=S.par.desc;}
    logicText();syncClip();setView(S.view);rebuildCaps();openTool(saved.tab,saved.level);setChooser(saved.chooser);if(S.spin)loop();
  }
  syncInsets();document.getElementById("help-open").focus({preventScroll:true});
}
document.getElementById("tour-exit").onclick=endTour;
document.getElementById("tour-back").onclick=()=>{if(tourStep>0){tourStep--;showTourStep();}};
document.getElementById("tour-next").onclick=()=>{if(tourStep===GUIDE.tour.length-1)endTour();else{tourStep++;showTourStep();}};
document.addEventListener("keydown",e=>{if(e.key!=="Escape"||help.open)return;if(tourStep>=0)endTour();else if(!chooser.hidden)setChooser(false);else setSheet(0);});

const welcome=document.createElement("dialog");welcome.className="help-dialog";welcome.setAttribute("aria-labelledby","welcome-title");
welcome.innerHTML='<h2 id="welcome-title">Explore logic devices in 3D</h2><p>Take a short guided tour, or explore at your own pace. You can replay it anytime from Help & features.</p><button class="btn" id="welcome-tour">Start tour</button> <button class="btn" id="welcome-skip">Explore myself</button>';
document.body.appendChild(welcome);
document.getElementById("welcome-tour").onclick=()=>{welcome.close();startTour();};
document.getElementById("welcome-skip").onclick=()=>{rememberTour();welcome.close();document.getElementById("help-open").focus();};
welcome.addEventListener("cancel",rememberTour);
openTool("views",0);syncInsets();
let seenVersion=0;try{seenVersion=Number(localStorage.getItem(storageKey))||0;}catch(_){}
if(seenVersion<GUIDE.version)welcome.showModal();
