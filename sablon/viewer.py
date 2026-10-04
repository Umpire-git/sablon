"""İnteraktif 3B görüntüleyici (tek HTML dosyası, three.js).

Fareyle döndürülür, kaydırıcıyla açınım ↔ bitmiş ürün arasında katlama animasyonu oynatılır,
adım düğmeleri montaj sırasını gösterir. Dönüşümler engine.Built ile birebir aynıdır;
katlar yuvarlak kıvrım olarak çizilir, deri prosedürel doku ve kenar boyası tonuyla gösterilir.
"""
from __future__ import annotations

import json

from .checks import pull_fold, pull_strip_data
from .engine import Built
from .geometry import seg_lines


def scene_json(b: Built) -> dict:
    nodes = []
    for pid in b.order:
        p = b.panels[pid]
        node = {
            "id": pid, "ad": p.spec.ad or pid, "parent": p.parent, "o": list(p.hinge_o), "d": list(p.hinge_d),
            "angle": p.angle, "t": p.t, "r": p.bend_r, "hx": list(p.hinge_x), "through": p.through,
            "order": p.spec.kat_sirasi, "poly": [[round(x, 3), round(y, 3)] for x, y in p.poly],
            "mount": None, "offset": 0.0, "color": getattr(b.parts.get(p.part), "renk", "") or "",
            "slits": [list(ln) for m in p.marks if m.kind.value == "slit" for ln in seg_lines(m.prim)],
        }
        if p.parent is None:
            if p.mount is not None and p.mount.ana_panel:
                node["mount"] = {"host": p.mount.ana_panel, "x": b.env_num(p.mount.x), "y": b.env_num(p.mount.y), "z": p.mount_z}
            else:
                node["offset"] = b._part_offset(p.part)
        nodes.append(node)
    hw = []
    for s in b.snaps:
        r = {"L20": 6.25, "L24": 7.5, "mini": 5.0}.get(s.size, 6.25)
        hw.append({"panel": s.src, "xy": list(map(float, s.src_xy)), "r": r, "side": s.src_side, "h": 2.0})
    for f in b.fasteners:
        r = 5.0 if f["tip"] == "vida" else 4.0
        hw.append({"panel": f["panel"], "xy": list(map(float, f["xy"])), "r": r, "side": -1, "h": 1.4})
        last = b.panels[f["layers"][-1]]
        loc = b.to_local(last.id, b.world(f["panel"], f["xy"]))
        hw.append({"panel": last.id, "xy": [float(loc[0]), float(loc[1])], "r": r, "side": -1 if loc[2] > 0 else 1, "h": 1.4})
    contents = [{"panel": c.panel, "x": c.x, "y": c.y, "w": c.w, "h": c.h, "s": c.s, "under": c.under, "z0": c.z0,
                 "zr": list(c.zrange(b.panels[c.panel].t)), "card": c.is_card}
                for c in b.contents]
    return {"title": b.design.ad, "color": b.design.renk or "#9a5a2e", "crazy": b.design.malzeme == "crazy_horse",
            "nodes": nodes, "hw": hw, "contents": contents,
            "steps": sorted({n["order"] for n in nodes if n["order"]}),
            "open_on_pull": sorted(k for k, v in pull_fold(b).items() if v == 0.0),
            "pulls": [{k: d[k] for k in ("child", "base", "content", "lift", "pass", "arm_len")} for d in pull_strip_data(b)]}


HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — 3B</title>
<style>
 :root{--bg:#efe9e1;--fg:#2b2118;--muted:#7a6a5a;--accent:#8b5a2b;--panel:rgba(255,255,255,.72)}
 @media (prefers-color-scheme: dark){:root{--bg:#1d1a17;--fg:#efe6da;--muted:#a8998a;--accent:#d49a5f;--panel:rgba(30,26,22,.72)}}
 html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;overflow:hidden}
 #c{position:fixed;inset:0;width:100%;height:100%}
 .ui{position:fixed;left:16px;right:16px;bottom:16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;
     background:var(--panel);padding:10px 14px;border-radius:14px;backdrop-filter:blur(8px)}
 h1{position:fixed;left:16px;top:12px;margin:0;font-size:18px;font-weight:650}
 input[type=range]{flex:1;min-width:140px;accent-color:var(--accent)}
 button{border:1px solid var(--muted);background:transparent;color:var(--fg);border-radius:9px;padding:6px 11px;cursor:pointer;font:inherit}
 button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
 .hint{color:var(--muted);font-size:12px;width:100%}
</style></head><body>
<h1>__TITLE__</h1><canvas id="c"></canvas>
<div class="ui"><span>Açık</span><input id="f" type="range" min="0" max="1" step="0.001" value="1"><span>Bitmiş</span>
<button id="play">▶ Katla</button><span id="steps"></span>
<span id="pullui" style="display:none"><span>Şeridi çek</span><input id="pull" type="range" min="0" max="1" step="0.001" value="0"><button id="pullplay">▶ Çek</button></span>
<label><input id="cards" type="checkbox" checked> kartlar</label>
<div class="hint">Sürükle: döndür · tekerlek: yakınlaştır · sağ tık: kaydır · adımlar montaj sırasını oynatır.</div></div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const S = __SCENE__;
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true});
renderer.setPixelRatio(Math.min(2, devicePixelRatio));
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.9;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
const cam = new THREE.PerspectiveCamera(30, 1, 1, 5000);
const ctl = new OrbitControls(cam, canvas); ctl.enableDamping = true;
const sun = new THREE.DirectionalLight(0xfff4e6, 2.2); sun.position.set(-120, 260, 160); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0004;
scene.add(sun); scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7560, 0.5));
const world = new THREE.Group(); world.rotation.x = -Math.PI/2; scene.add(world);

// --- deri dokusu (prosedürel)
function leatherTex(hex, crazy){
  const n = 512, cv = document.createElement('canvas'); cv.width = cv.height = n; const g = cv.getContext('2d');
  g.fillStyle = hex; g.fillRect(0,0,n,n);
  for (let i=0;i<(crazy?900:400);i++){ const x=Math.random()*n, y=Math.random()*n, r=20+Math.random()*90;
    const gr=g.createRadialGradient(x,y,0,x,y,r); const a=(crazy?0.10:0.05)*Math.random();
    gr.addColorStop(0, Math.random()<0.5?`rgba(255,235,210,${a})`:`rgba(30,15,5,${a})`); gr.addColorStop(1,'rgba(0,0,0,0)');
    g.fillStyle=gr; g.fillRect(x-r,y-r,2*r,2*r); }
  const id = g.getImageData(0,0,n,n); for (let i=0;i<id.data.length;i+=4){ const v=(Math.random()-0.5)*14; id.data[i]+=v; id.data[i+1]+=v; id.data[i+2]+=v; }
  g.putImageData(id,0,0);
  const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1/90, 1/90); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function bumpTex(){ const n=256, cv=document.createElement('canvas'); cv.width=cv.height=n; const g=cv.getContext('2d');
  const id=g.createImageData(n,n); for(let i=0;i<id.data.length;i+=4){const v=128+(Math.random()-0.5)*60; id.data[i]=id.data[i+1]=id.data[i+2]=v; id.data[i+3]=255;}
  g.putImageData(id,0,0); const t=new THREE.CanvasTexture(cv); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(1/6,1/6); return t; }
const base = new THREE.Color(S.color);
const leather = new THREE.MeshPhysicalMaterial({map:leatherTex(S.color, S.crazy), bumpMap:bumpTex(), bumpScale:0.15,
  roughness:S.crazy?0.55:0.7, clearcoat:S.crazy?0.3:0.08, clearcoatRoughness:0.6, sheen:0.12, sheenColor:new THREE.Color(0xffe2c4), envMapIntensity:0.45, side:THREE.DoubleSide});
const edge = new THREE.MeshStandardMaterial({color:base.clone().multiplyScalar(0.45), roughness:0.45});
const bendMat = leather.clone(); if (S.crazy){ bendMat.color = new THREE.Color(1.45,1.35,1.25); }
const metal = new THREE.MeshStandardMaterial({color:0xd9d2c4, roughness:0.28, metalness:1.0, envMapIntensity:1.2});
const cardTop = new THREE.MeshPhysicalMaterial({color:0x2f4f86, roughness:0.25, clearcoat:0.8});
const billTop = new THREE.MeshStandardMaterial({color:0xd3d6b4, roughness:0.85});
const cardSide = new THREE.MeshStandardMaterial({color:0xf2f1ec, roughness:0.6});
const slitMat = new THREE.MeshBasicMaterial({color:0x140c06});
const partMats = {};
function partMat(c){ if (!partMats[c]){ const m = leather.clone(); m.map = leatherTex(c, S.crazy);
  partMats[c] = [m, new THREE.MeshStandardMaterial({color:new THREE.Color(c).multiplyScalar(0.45), roughness:0.45})]; } return partMats[c]; }
const byId = {}; const groups = {}; const bends = {};
for (const n of S.nodes) byId[n.id] = n;
function slab(poly, z0, z1, faceMat, sideMat){
  const sh = new THREE.Shape(poly.map(p=>new THREE.Vector2(p[0],p[1])));
  const g = new THREE.ExtrudeGeometry(sh, {depth:z1-z0, bevelEnabled:true, bevelThickness:0.12, bevelSize:0.12, bevelSegments:2, curveSegments:24});
  g.translate(0,0,z0); g.computeVertexNormals();
  const m = new THREE.Mesh(g, [faceMat, sideMat]); m.castShadow = m.receiveShadow = true; return m;
}
for (const n of S.nodes){
  const g = new THREE.Group(); g.matrixAutoUpdate = false; groups[n.id] = g; world.add(g);
  const lm = n.color ? partMat(n.color) : [leather, edge];
  g.add(slab(n.poly, -n.t+0.12, -0.12, lm[0], lm[1]));
  for (const s of n.slits){ const dx=s[2]-s[0], dy=s[3]-s[1], L=Math.hypot(dx,dy);
    for (const z of [0.02, -n.t-0.02]){ const m=new THREE.Mesh(new THREE.PlaneGeometry(L,0.7), slitMat);
      m.position.set((s[0]+s[2])/2,(s[1]+s[3])/2,z); m.rotation.z=Math.atan2(dy,dx); if(z<0) m.rotation.x=Math.PI; g.add(m);} }
  if (n.parent && Math.abs(n.angle) > 0.01){
    const segs = 16; const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array((segs+1)*4*3), 3));
    const idx=[]; for(let k=0;k<segs;k++){ const a=k*4, b=(k+1)*4; idx.push(a,a+1,b+1, a,b+1,b, a+2,b+3,a+3, a+2,b+2,b+3, a,b,b+2, a,b+2,a+2, a+1,a+3,b+3, a+1,b+3,b+1); }
    geo.setIndex(idx);
    const m = new THREE.Mesh(geo, n.color ? partMat(n.color)[0] : bendMat); m.castShadow = m.receiveShadow = true; m.matrixAutoUpdate = false;
    world.add(m); bends[n.id] = {mesh:m, segs};
  }
}
function dome(r, h){ const pts=[]; for(let i=0;i<=12;i++){ const a=i/12*Math.PI/2; pts.push(new THREE.Vector2(r*Math.cos(a)+0.001, h*0.35+h*0.65*Math.sin(a))); }
  pts.unshift(new THREE.Vector2(r,0)); const g=new THREE.LatheGeometry(pts, 40); g.rotateX(Math.PI/2); return g; }
for (const s of S.hw){ const m = new THREE.Mesh(dome(s.r, s.h), metal); m.castShadow = true; const t = byId[s.panel].t;
  m.position.set(s.xy[0], s.xy[1], s.side>0 ? 0 : -t); if (s.side<0) m.scale.z = -1; groups[s.panel].add(m); }
const contentMeshes = [];
const fillers = {};
for (const pl of S.pulls) for (const id of (pl.pass.length ? pl.pass : [pl.child])){ const n = byId[id]; const w = n.hx[1]-n.hx[0];
  const g = new THREE.BoxGeometry(w, 1, n.t); g.translate((n.hx[0]+n.hx[1])/2, 0.5, -n.t/2);
  const m = new THREE.Mesh(g, n.color ? partMat(n.color)[0] : leather); m.castShadow = m.receiveShadow = true; m.visible = false; groups[id].add(m); fillers[id] = m; }
for (const c of S.contents){
  const t = byId[c.panel].t; const z0 = c.under ? c.zr[0] : c.z0 + 0.05, z1 = c.under ? c.zr[1] : c.z0 + c.s;
  const r=3.18, x=c.x, y=c.y, w=c.w, h=c.h; const sh=new THREE.Shape();
  sh.moveTo(x+r,y); sh.lineTo(x+w-r,y); sh.quadraticCurveTo(x+w,y,x+w,y+r); sh.lineTo(x+w,y+h-r); sh.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  sh.lineTo(x+r,y+h); sh.quadraticCurveTo(x,y+h,x,y+h-r); sh.lineTo(x,y+r); sh.quadraticCurveTo(x,y,x+r,y);
  const g = new THREE.ExtrudeGeometry(sh,{depth:z1-z0, bevelEnabled:false}); g.translate(0,0,z0);
  const m = new THREE.Mesh(g,[c.card ? cardTop : billTop, cardSide]); m.castShadow = true; groups[c.panel].add(m); contentMeshes.push(m);
}
const M4 = THREE.Matrix4, T = (x,y,z)=>new M4().makeTranslation(x,y,z);
function compute(fold, pullv){
  const mats = {}, hinge = {};
  const get = (id)=>{
    if (mats[id]) return mats[id];
    const n = byId[id]; let m;
    if (!n.parent){ m = n.mount ? get(n.mount.host).clone().multiply(T(n.mount.x, n.mount.y, n.mount.z)) : T(n.offset,0,0); }
    else {
      const f = fold(n), a = n.angle*f*Math.PI/180, zh = n.angle>=0 ? n.r : -n.t - n.r;
      const B = new M4().set(n.d[0],-n.d[1],0,0, n.d[1],n.d[0],0,0, 0,0,1,0, 0,0,0,1);
      const H = get(n.parent).clone().multiply(T(n.o[0],n.o[1],0)).multiply(B); hinge[id] = {H, a, zh};
      m = H.clone().multiply(T(0,0,zh)).multiply(new M4().makeRotationX(a)).multiply(T(0,0,-zh));
      if (n.through) m.multiply(T(0,0,n.through*f));
    }
    return mats[id] = m;
  };
  const p = pullv ?? +document.getElementById('pull').value, moves = {}, bshift = {};
  contentMeshes.forEach(m=>m.position.y=0); Object.values(fillers).forEach(m=>m.visible=false);
  const fill = (id, L)=>{ const fm = fillers[id]; fm.visible = L > 0.01; fm.position.y = -L; fm.scale.y = Math.max(L, 1e-3); };
  for (const pl of S.pulls){ const dl = pl.lift*p, v = new THREE.Vector3(0,1,0).transformDirection(get(pl.base));
    const Tv = (k)=>T(v.x*k, v.y*k, v.z*k);
    if (pl.pass.length){ moves[pl.child] = [Tv(dl), new M4().makeScale(1, Math.max(1e-3, (pl.arm_len-dl)/pl.arm_len), 1)];
      for (const id of pl.pass){ moves[id] = [Tv(2*dl), new M4()]; fill(id, 2*dl); } }
    else { moves[pl.child] = [Tv(2*dl), new M4()]; fill(pl.child, dl); }
    bshift[pl.child] = v.clone().multiplyScalar(dl);
    if (contentMeshes[pl.content]) contentMeshes[pl.content].position.y = dl; }
  for (const n of S.nodes){ const g = groups[n.id]; g.matrix.copy(get(n.id));
    if (moves[n.id]){ g.matrix.premultiply(moves[n.id][0]); g.matrix.multiply(moves[n.id][1]); } g.matrixWorldNeedsUpdate = true; }
  for (const id in bends){
    const n = byId[id], {mesh, segs} = bends[id], h = hinge[id]; const pos = mesh.geometry.attributes.position;
    for (let k=0;k<=segs;k++){ const a = h.a*k/segs, s=Math.sin(a), c=Math.cos(a);
      const pts = [[n.hx[0],0],[n.hx[1],0],[n.hx[0],-n.t],[n.hx[1],-n.t]];
      pts.forEach((p,j)=>{ const z0=p[1]; pos.setXYZ(k*4+j, p[0], -(z0-h.zh)*s, h.zh+(z0-h.zh)*c); }); }
    pos.needsUpdate = true; mesh.geometry.computeVertexNormals(); mesh.geometry.computeBoundingSphere();
    mesh.matrix.copy(h.H); if (bshift[id]) mesh.matrix.premultiply(T(bshift[id].x, bshift[id].y, bshift[id].z)); mesh.matrixWorldNeedsUpdate = true; mesh.visible = Math.abs(h.a) > 1e-3;
  }
}
const slider = document.getElementById('f'); let stepMode = null;
function foldFn(){ const v = +slider.value; if (stepMode === null) return ()=>v;
  return (n)=> n.order && n.order < stepMode ? 1 : (n.order === stepMode ? v : 0); }
const openSet = new Set(S.open_on_pull);
function update(){ const f = foldFn(), pv = +document.getElementById('pull').value;
  // şerit çekilirken kartların üstünü örten kapak önce açılır, kartlar sonra yükselir
  const k = Math.max(0, 1 - pv*4);
  compute(openSet.size ? (n)=> openSet.has(n.id) ? f(n)*k : f(n) : f, Math.max(0, (pv - (openSet.size ? 0.25 : 0)) / (openSet.size ? 0.75 : 1))); }
slider.oninput = update;
const stepsEl = document.getElementById('steps'); const btns=[];
const allBtn = document.createElement('button'); allBtn.textContent='Tümü'; allBtn.className='on'; stepsEl.append(allBtn); btns.push(allBtn);
allBtn.onclick=()=>{stepMode=null; btns.forEach(b=>b.classList.remove('on')); allBtn.classList.add('on'); slider.value=0; update(); play();};
S.steps.forEach((k,i)=>{ const b=document.createElement('button'); b.textContent='Adım '+(i+1); stepsEl.append(b); btns.push(b);
  b.onclick=()=>{stepMode=k; btns.forEach(x=>x.classList.remove('on')); b.classList.add('on'); slider.value=0; update(); play();}; });
let anim=null;
function play(){ cancelAnimationFrame(anim); const t0=performance.now(); const from=+slider.value>0.99?0:+slider.value;
  const tick=(t)=>{ const v=Math.min(1, from+(t-t0)/2400); slider.value=v; update(); if(v<1) anim=requestAnimationFrame(tick); }; anim=requestAnimationFrame(tick); }
document.getElementById('play').onclick=play;
const pullEl = document.getElementById('pull');
if (S.pulls.length){ document.getElementById('pullui').style.display=''; }
pullEl.oninput = update;
let panim=null;
document.getElementById('pullplay').onclick=()=>{ cancelAnimationFrame(panim); const t0=performance.now(), back=+pullEl.value>0.5;
  const tick=(t)=>{ const k=Math.min(1,(t-t0)/1400); pullEl.value = back ? 1-k : k; update(); if(k<1) panim=requestAnimationFrame(tick); }; panim=requestAnimationFrame(tick); };
document.getElementById('cards').onchange=(e)=>contentMeshes.forEach(m=>m.visible=e.target.checked);
update();
const box = new THREE.Box3().setFromObject(world); const ctr = box.getCenter(new THREE.Vector3()); const sz = box.getSize(new THREE.Vector3()).length();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(sz*8, sz*8), new THREE.ShadowMaterial({opacity:0.22}));
ground.rotation.x = -Math.PI/2; ground.position.y = box.min.y - 0.05; ground.receiveShadow = true; scene.add(ground);
const sc = sun.shadow.camera; sc.left=sc.bottom=-sz; sc.right=sc.top=sz; sc.near=1; sc.far=2000; sun.target.position.copy(ctr); scene.add(sun.target);
ctl.target.copy(ctr); cam.position.copy(ctr).add(new THREE.Vector3(sz*0.75, sz*1.05, sz*1.35));
function resize(){ renderer.setSize(innerWidth, innerHeight, false); cam.aspect=innerWidth/innerHeight; cam.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
renderer.setAnimationLoop(()=>{ ctl.update(); renderer.render(scene, cam); });
</script></body></html>
"""


def write_viewer(b: Built, path: str) -> None:
    title = (b.design.ad or "Tasarım").replace("<", "").replace(">", "")
    html = HTML.replace("__TITLE__", title).replace("__SCENE__", json.dumps(scene_json(b), ensure_ascii=False))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
