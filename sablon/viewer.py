"""İnteraktif 3B görüntüleyici (tek HTML dosyası, three.js).

Fareyle döndürülür, kaydırıcıyla açınım ↔ bitmiş ürün arasında katlama animasyonu
oynatılır, adım düğmeleri montaj sırasını gösterir. Matris hesabı engine.Built ile
birebir aynıdır.
"""
from __future__ import annotations

import json

from .engine import Built
from .pattern import Kind


def scene_json(b: Built) -> dict:
    nodes = []
    for pid in b.order:
        p = b.panels[pid]
        node = {
            "id": pid, "ad": p.spec.ad or pid, "parent": p.parent, "o": list(p.hinge_o), "d": list(p.hinge_d),
            "angle": p.angle, "t": p.t, "bulge": p.bulge, "order": p.spec.kat_sirasi,
            "poly": [[round(x, 3), round(y, 3)] for x, y in p.poly],
            "mount": None, "offset": 0.0,
            "stitch": [[round(m.prim.cx, 2), round(m.prim.cy, 2)] for m in p.marks if m.kind == Kind.STITCH],
        }
        if p.parent is None:
            if p.mount is not None and p.mount.ana_panel:
                node["mount"] = {"host": p.mount.ana_panel, "x": b.env_num(p.mount.x), "y": b.env_num(p.mount.y), "z": p.mount_z}
            else:
                node["offset"] = b._part_offset(p.part)
        nodes.append(node)
    snaps = []
    for s in b.snaps:
        if s.kind != "citcit":
            continue
        r = {"L20": 6.25, "L24": 7.5, "mini": 5.0}.get(s.size, 6.25)
        snaps.append({"panel": s.src, "xy": list(map(float, s.src_xy)), "r": r, "side": s.src_side, "h": 1.6})
        if s.dst:
            snaps.append({"panel": s.dst, "xy": list(map(float, s.dst_xy)), "r": r * 0.55, "side": s.dst_side, "h": 1.2})
    contents = [{"panel": c.panel, "x": c.x, "y": c.y, "w": c.w, "h": c.h, "s": c.s, "under": c.under} for c in b.contents]
    return {"title": b.design.ad, "color": b.design.renk or "#b07a45", "nodes": nodes, "snaps": snaps,
            "contents": contents, "steps": sorted({n["order"] for n in nodes if n["order"]})}


HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — 3B</title>
<style>
 :root{--bg:#f6f2ec;--fg:#2b2118;--muted:#7a6a5a;--accent:#8b5a2b}
 @media (prefers-color-scheme: dark){:root{--bg:#1d1a17;--fg:#efe6da;--muted:#a8998a;--accent:#d49a5f}}
 html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
 #c{position:fixed;inset:0}
 .ui{position:fixed;left:16px;right:16px;bottom:16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;
     background:color-mix(in srgb,var(--bg) 85%,transparent);padding:10px 14px;border-radius:12px;backdrop-filter:blur(6px)}
 h1{position:fixed;left:16px;top:10px;margin:0;font-size:18px}
 input[type=range]{flex:1;min-width:160px;accent-color:var(--accent)}
 button{border:1px solid var(--muted);background:transparent;color:var(--fg);border-radius:8px;padding:6px 10px;cursor:pointer}
 button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
 .hint{color:var(--muted);font-size:12px;width:100%}
</style></head><body>
<h1>__TITLE__</h1><canvas id="c"></canvas>
<div class="ui"><span>Açık</span><input id="f" type="range" min="0" max="1" step="0.001" value="1"><span>Bitmiş</span>
<button id="play">▶ Katla</button><span id="steps"></span>
<label><input id="cards" type="checkbox" checked> içerik</label>
<div class="hint">Sürükle: döndür · tekerlek: yakınlaştır · sağ tık: kaydır. Kesikli adımlar montaj sırasıdır.</div></div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const S = __SCENE__;
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true});
renderer.setPixelRatio(devicePixelRatio);
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(35, 1, 1, 5000);
const ctl = new OrbitControls(cam, canvas); ctl.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a6a, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.8); sun.position.set(120, -160, 260); scene.add(sun);
const world = new THREE.Group(); world.rotation.x = -Math.PI/2; scene.add(world);
const leather = new THREE.MeshStandardMaterial({color:S.color, roughness:0.75, metalness:0.0, side:THREE.DoubleSide});
const edgeMat = new THREE.LineBasicMaterial({color:0x2a1a0e, transparent:true, opacity:0.55});
const thread = new THREE.MeshStandardMaterial({color:0xefe6d2, roughness:0.6});
const metal = new THREE.MeshStandardMaterial({color:0xd6d1c4, roughness:0.35, metalness:0.45});
const paper = new THREE.MeshStandardMaterial({color:0xe3e8ef, roughness:0.9});
const byId = {}; const groups = {};
for (const n of S.nodes) byId[n.id] = n;
function slab(poly, z0, z1, mat){
  const sh = new THREE.Shape(poly.map(p=>new THREE.Vector2(p[0],p[1])));
  const g = new THREE.ExtrudeGeometry(sh, {depth:z1-z0, bevelEnabled:false, curveSegments:24});
  g.translate(0,0,z0); const m = new THREE.Mesh(g, mat);
  m.add(new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), edgeMat)); return m;
}
for (const n of S.nodes){
  const g = new THREE.Group(); g.matrixAutoUpdate = false; groups[n.id] = g; world.add(g);
  g.add(slab(n.poly, -n.t, 0, leather));
  const dot = new THREE.CylinderGeometry(0.5,0.5,0.12,8); dot.rotateX(Math.PI/2);
  for (const [x,y] of n.stitch){ for (const z of [0.06, -n.t-0.06]){ const m=new THREE.Mesh(dot,thread); m.position.set(x,y,z); g.add(m);} }
}
for (const s of S.snaps){
  const geo = new THREE.CylinderGeometry(s.r, s.r, s.h, 28); geo.rotateX(Math.PI/2);
  const m = new THREE.Mesh(geo, metal); const t = byId[s.panel].t;
  m.position.set(s.xy[0], s.xy[1], s.side>0 ? s.h/2 : -t - s.h/2); groups[s.panel].add(m);
}
const contentMeshes = [];
for (const c of S.contents){
  const t = byId[c.panel].t; const z0 = c.under ? -t - c.s : 0.02, z1 = c.under ? -t : c.s;
  const m = slab([[c.x,c.y],[c.x+c.w,c.y],[c.x+c.w,c.y+c.h],[c.x,c.y+c.h]], z0, z1, paper);
  groups[c.panel].add(m); contentMeshes.push(m);
}
const M4 = THREE.Matrix4;
const T = (x,y,z)=>new M4().makeTranslation(x,y,z);
function compute(fold){
  const mats = {};
  const get = (id)=>{
    if (mats[id]) return mats[id];
    const n = byId[id]; let m;
    if (!n.parent){
      if (n.mount) m = get(n.mount.host).clone().multiply(T(n.mount.x, n.mount.y, n.mount.z));
      else m = T(n.offset,0,0);
    } else {
      const f = fold(n); const a = n.angle*f*Math.PI/180; const zh = n.angle>=0 ? 0 : -n.t;
      const B = new M4().set(n.d[0],-n.d[1],0,0, n.d[1],n.d[0],0,0, 0,0,1,0, 0,0,0,1);
      m = get(n.parent).clone().multiply(T(0,0,n.bulge*f)).multiply(T(n.o[0],n.o[1],0)).multiply(B)
          .multiply(T(0,0,zh)).multiply(new M4().makeRotationX(a)).multiply(T(0,0,-zh));
    }
    return mats[id] = m;
  };
  for (const n of S.nodes){ const g = groups[n.id]; g.matrix.copy(get(n.id)); g.matrixWorldNeedsUpdate = true; }
}
const slider = document.getElementById('f');
let stepMode = null;
function foldFn(){
  const v = +slider.value;
  if (stepMode === null) return ()=>v;
  return (n)=> n.order && n.order < stepMode ? 1 : (n.order === stepMode ? v : 0);
}
function update(){ compute(foldFn()); }
slider.oninput = update;
const stepsEl = document.getElementById('steps');
const allBtn = document.createElement('button'); allBtn.textContent='Tümü'; allBtn.className='on'; stepsEl.append(allBtn);
const btns=[allBtn];
allBtn.onclick=()=>{stepMode=null; btns.forEach(b=>b.classList.remove('on')); allBtn.classList.add('on'); update();};
for (const k of S.steps){ const b=document.createElement('button'); b.textContent='Adım '+k; stepsEl.append(b); btns.push(b);
  b.onclick=()=>{stepMode=k; btns.forEach(x=>x.classList.remove('on')); b.classList.add('on'); slider.value=0; update(); play();}; }
let anim=null;
function play(){ cancelAnimationFrame(anim); const t0=performance.now(); const from=+slider.value>0.99?0:+slider.value;
  const tick=(t)=>{ const v=Math.min(1, from+(t-t0)/2200); slider.value=v; update(); if(v<1) anim=requestAnimationFrame(tick); }; anim=requestAnimationFrame(tick); }
document.getElementById('play').onclick=play;
document.getElementById('cards').onchange=(e)=>contentMeshes.forEach(m=>m.visible=e.target.checked);
update();
const box = new THREE.Box3().setFromObject(world); const ctr = box.getCenter(new THREE.Vector3()); const sz = box.getSize(new THREE.Vector3()).length();
ctl.target.copy(ctr); cam.position.copy(ctr).add(new THREE.Vector3(sz*0.8, sz*0.9, sz*1.2));
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
