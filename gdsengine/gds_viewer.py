import streamlit as st
import os
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
import streamlit.components.v1 as components

# (fill_color, stroke_color, hatch_pattern)
_LAYER_STYLES = [
    ("#3a7fd5", "#1a4080", "hlines"),
    ("#d53a3a", "#801a1a", "diag45"),
    ("#2db870", "#0a6030", "vlines"),
    ("#d5a020", "#806000", "xcross"),
    ("#9b3ad5", "#501080", "diag135"),
    ("#20c5be", "#0a6560", "cross"),
    ("#d5701a", "#803000", "dots"),
    ("#70d51a", "#308000", "hlines"),
    ("#d51a8a", "#800050", "diag45"),
    ("#c5c020", "#706000", "vlines"),
    ("#d51a55", "#800020", "xcross"),
    ("#1a70d5", "#004080", "diag135"),
]


def _unit_label(lib_unit):
    if abs(lib_unit - 1e-6) < 1e-9:  return "µm"
    if abs(lib_unit - 1e-9) < 1e-12: return "nm"
    if abs(lib_unit - 1e-3) < 1e-6:  return "mm"
    return "u"


def _parse_lyp(lyp_bytes):
    """Parse a KLayout .lyp file.
    Returns ({layer: hex_color}, {layer: name}) for visible layers."""
    layer_colors = {}
    layer_names  = {}
    try:
        root = ET.fromstring(lyp_bytes)
        for props in root.findall(".//properties"):
            if props.findtext("visible", "true").strip().lower() == "false":
                continue
            source = props.findtext("source", "").strip()
            color  = props.findtext("fill-color", "").strip()
            name   = props.findtext("name",       "").strip()
            if not source or not color:
                continue
            try:
                layer = int(source.split("/")[0])
                layer_colors[layer] = color
                if name:
                    layer_names[layer] = name
            except (ValueError, IndexError):
                continue
    except ET.ParseError:
        pass
    return layer_colors, layer_names


def _build_cell_data(cell, layer_colors=None, layer_names=None):
    """Build canvas render data for a single gdstk Cell (polygons flattened).

    Returns (layers_list, vb_x, vb_y, vb_w, vb_h) or (None, 0,0,1,1).

    Each entry in layers_list:
        [layer_num, display_name, fill, stroke, ptype, polys, bounds]
    """
    layer_polys = defaultdict(list)
    all_x, all_y = [], []

    for poly in cell.get_polygons():
        pts = poly.points
        if len(pts) < 3:
            continue
        xs = pts[:, 0]
        ys = -pts[:, 1]
        all_x.extend(xs.tolist())
        all_y.extend(ys.tolist())

        flat = []
        for x, y in zip(xs.tolist(), ys.tolist()):
            flat.append(round(x, 2))
            flat.append(round(y, 2))

        bx0, bx1 = float(xs.min()), float(xs.max())
        by0, by1 = float(ys.min()), float(ys.max())
        layer_polys[poly.layer].append((flat, bx0, by0, bx1, by1))

    if not all_x:
        return None, 0, 0, 1, 1

    mn_x, mx_x = min(all_x), max(all_x)
    mn_y, mx_y = min(all_y), max(all_y)
    pad  = max(mx_x - mn_x, mx_y - mn_y) * 0.02 or 1
    vb_x = float(mn_x - pad)
    vb_y = float(mn_y - pad)
    vb_w = float(mx_x - mn_x + 2 * pad)
    vb_h = float(mx_y - mn_y + 2 * pad)

    layers_list = []
    for i, layer_num in enumerate(sorted(layer_polys)):
        style        = _LAYER_STYLES[i % len(_LAYER_STYLES)]
        fill_color   = (layer_colors or {}).get(layer_num, style[0])
        stroke_color = style[1]
        ptype        = style[2]
        lname        = (layer_names or {}).get(layer_num, f"Layer {layer_num}")

        polys  = []
        bounds = []
        for (flat, bx0, by0, bx1, by1) in layer_polys[layer_num]:
            polys.append(flat)
            bounds.append([round(bx0,2), round(by0,2),
                           round(bx1,2), round(by1,2)])

        layers_list.append([layer_num, lname, fill_color,
                            stroke_color, ptype, polys, bounds])

    return layers_list, vb_x, vb_y, vb_w, vb_h


def show_interactive_viewer():
    # ── Win98 styling for Streamlit file uploaders ────────────────────────────
    st.markdown("""<style>
[data-testid="stFileUploaderDropzone"]{
  background:#d4d0c8!important;border:1px solid!important;
  border-color:#404040 #dfdfdf #dfdfdf #404040!important;
  border-radius:0!important;padding:6px 10px!important;
}
[data-testid="stFileUploaderDropzone"] button{
  background:#d4d0c8!important;color:#000!important;
  font:11px "MS Sans Serif",Arial,sans-serif!important;
  border-top:2px solid #dfdfdf!important;border-left:2px solid #dfdfdf!important;
  border-bottom:2px solid #404040!important;border-right:2px solid #404040!important;
  outline:1px solid #000!important;border-radius:0!important;
  box-shadow:none!important;padding:3px 12px!important;
}
[data-testid="stFileUploaderDropzone"] button:hover{background:#d4d0c8!important;color:#000!important;}
[data-testid="stFileUploaderDropzone"] button:active{
  border-top:2px solid #404040!important;border-left:2px solid #404040!important;
  border-bottom:2px solid #dfdfdf!important;border-right:2px solid #dfdfdf!important;
  padding:4px 11px 2px 13px!important;
}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span{
  font-family:"MS Sans Serif",Arial,sans-serif!important;font-size:10px!important;color:#000!important;
}
</style>""", unsafe_allow_html=True)

    st.header("🔗 KLayout-Powered Interactive Viewer")
    col1, col2 = st.columns([3, 2])
    with col1:
        uploaded_file = st.file_uploader("Upload GDSII", type=["gds"], key="kweb_uploader")
    with col2:
        uploaded_lyp = st.file_uploader("Layer Properties (optional)", type=["lyp"], key="lyp_uploader")

    if uploaded_file:
        gds_path = "temp_view.gds"
        with open(gds_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            import gdstk

            with st.spinner("Rendering layout..."):
                lib       = gdstk.read_gds(gds_path)
                top_cells = lib.top_level()
                if not top_cells:
                    st.error("No top-level cell found in GDS file.")
                    return

                layer_colors, layer_names = (
                    _parse_lyp(uploaded_lyp.read()) if uploaded_lyp else ({}, {}))

                # ── collect all library cells ──────────────────────────────
                top_names = [c.name for c in top_cells]
                try:
                    all_lib_cells = list(lib.cells)
                except Exception:
                    all_lib_cells = list(top_cells)

                non_top = sorted(
                    [c for c in all_lib_cells if c.name not in top_names],
                    key=lambda c: c.name)
                ordered_cells = list(top_cells) + non_top

                # ── cell hierarchy (parent → [child names]) ───────────────
                cell_children: dict = {}
                for cell in ordered_cells:
                    children = []
                    for ref in getattr(cell, "references", []):
                        try:
                            cname = ref.cell.name if ref.cell else ref.cell_name
                            if cname not in children:
                                children.append(cname)
                        except Exception:
                            pass
                    cell_children[cell.name] = children

                # ── per-cell render data ──────────────────────────────────
                all_cells_data: dict = {}
                for cell in ordered_cells:
                    layers_list, vb_x, vb_y, vb_w, vb_h = _build_cell_data(
                        cell, layer_colors, layer_names)
                    if layers_list is not None:
                        all_cells_data[cell.name] = {
                            "b": [vb_x, vb_y, vb_w, vb_h],
                            "l": layers_list,
                        }

                if not all_cells_data:
                    st.error("No geometry found in GDS file.")
                    return

                init_cell = next(
                    (n for n in top_names if n in all_cells_data),
                    next(iter(all_cells_data)))

                unit             = _unit_label(lib.unit)
                all_cells_json   = json.dumps(all_cells_data,  separators=(',', ':'))
                top_names_json   = json.dumps(top_names,        separators=(',', ':'))
                cell_tree_json   = json.dumps(cell_children,    separators=(',', ':'))
                init_cell_json   = json.dumps(init_cell)

                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
/* ── reset ── */
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;overflow:hidden;background:#d4d0c8;
  font-family:"MS Sans Serif",Arial,sans-serif;font-size:11px;color:#000}}

/* ── shell ── */
#shell{{display:flex;flex-direction:column;height:100%;}}

/* ── Win98 toolbar ── */
#toolbar{{
  background:#d4d0c8;border-bottom:2px solid #808080;
  padding:3px 5px;display:flex;gap:3px;align-items:center;
  flex-shrink:0;user-select:none;flex-wrap:wrap;
}}
.btn{{
  background:#d4d0c8;color:#000;
  font:11px "MS Sans Serif",Arial,sans-serif;
  padding:2px 8px;cursor:pointer;
  border-top:2px solid #dfdfdf;border-left:2px solid #dfdfdf;
  border-bottom:2px solid #404040;border-right:2px solid #404040;
  outline:1px solid #000;white-space:nowrap;text-align:center;
}}
.btn:active,.btn.on{{
  border-top:2px solid #404040;border-left:2px solid #404040;
  border-bottom:2px solid #dfdfdf;border-right:2px solid #dfdfdf;
  padding:3px 7px 1px 9px;
}}
.btn:focus{{outline:1px dotted #000;outline-offset:-3px}}
.sep{{width:1px;height:18px;background:#808080;border-right:1px solid #fff;margin:0 2px;flex-shrink:0}}
#zoomLbl{{font:11px "MS Sans Serif",Arial,sans-serif;color:#000;padding:0 4px;min-width:48px}}

/* ── body row ── */
#body{{display:flex;flex:1;overflow:hidden;min-height:0}}

/* ── canvas wrapper ── */
#wrap{{
  position:relative;flex:1;min-width:0;
  background:#1a1a2e;overflow:hidden;cursor:crosshair;
}}
canvas{{display:block;}}
#selbox{{position:absolute;display:none;pointer-events:none;
  border:1px dashed #7af;background:rgba(80,140,255,.10);}}

/* ── ruler overlay ── */
#ruler{{position:absolute;bottom:28px;left:12px;z-index:10;
  color:#ccc;font:10px/1.4 monospace;pointer-events:none;}}
#rbar{{height:2px;background:#ccc;border-radius:1px;margin-bottom:3px}}
#rlabel{{text-align:center;text-shadow:0 0 3px #000}}

/* ── status bar ── */
#status{{
  height:18px;background:#d4d0c8;
  border-top:1px solid #808080;padding:2px 6px;
  display:flex;align-items:center;gap:16px;flex-shrink:0;
  font:11px "MS Sans Serif",Arial,sans-serif;
}}
#coords{{color:#000;}}
#cellName{{color:#000080;font-weight:bold;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;max-width:240px}}

/* ── Win98 sidebar ── */
#sidebar{{
  width:195px;min-width:195px;background:#d4d0c8;
  border-left:2px solid #808080;
  display:flex;flex-direction:column;overflow:hidden;
}}

/* Win98 group-box panels */
.gb{{
  margin:4px 4px 0 4px;flex-shrink:0;
  border-top:1px solid #808080;border-left:1px solid #808080;
  border-bottom:1px solid #dfdfdf;border-right:1px solid #dfdfdf;
}}
.gb.grow{{flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:60px}}
.gb-title{{
  background:#d4d0c8;
  font:bold 11px "MS Sans Serif",Arial,sans-serif;
  padding:2px 5px;border-bottom:1px solid #808080;user-select:none;
  display:flex;align-items:center;gap:3px;
}}

/* ── cell tree ── */
#cellScroll{{overflow-y:auto;flex:1;padding:1px 0}}
.tnode{{display:flex;align-items:center;padding:1px 2px 1px 4px;cursor:pointer;white-space:nowrap}}
.tnode:hover{{background:#b8c8e0}}
.tnode.active{{background:#000080;color:#fff}}
.tnode.active .tn-lbl{{color:#fff}}
.tn-tog{{width:12px;text-align:center;flex-shrink:0;font-size:9px;color:#555;cursor:pointer;user-select:none}}
.tnode.active .tn-tog{{color:#ccc}}
.tn-lbl{{font:11px "MS Sans Serif",Arial,sans-serif;overflow:hidden;text-overflow:ellipsis}}
.tn-lbl.toplevel{{font-weight:bold}}
.tn-children{{display:none;}}

/* ── layer panel ── */
.lyr-ctrl{{display:flex;gap:2px;padding:2px 3px;border-bottom:1px solid #b0b0b0}}
.sbtn{{
  background:#d4d0c8;color:#000;font:10px "MS Sans Serif",Arial,sans-serif;
  padding:1px 4px;cursor:pointer;border-radius:0;
  border-top:1px solid #dfdfdf;border-left:1px solid #dfdfdf;
  border-bottom:1px solid #808080;border-right:1px solid #808080;
}}
.sbtn:active{{border-color:#808080 #dfdfdf #dfdfdf #808080;padding:2px 3px 0 5px}}
#layerScroll{{overflow-y:auto;flex:1;padding:1px 1px}}
.lr{{display:flex;align-items:center;gap:3px;padding:1px 3px;cursor:pointer;user-select:none;}}
.lr:hover{{background:#b0b8c8}}
.lr input[type=checkbox]{{width:11px;height:11px;margin:0;flex-shrink:0;cursor:pointer;}}
.swatch{{flex-shrink:0;
  border-top:1px solid #808080;border-left:1px solid #808080;
  border-bottom:1px solid #dfdfdf;border-right:1px solid #dfdfdf;}}
.lr label{{font:11px "MS Sans Serif",Arial,sans-serif;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:108px;cursor:pointer}}
.lr.hidden label,.lr.hidden .lr-lnum{{color:#909090;text-decoration:line-through}}
.lr-lnum{{font:9px monospace;color:#606060;flex-shrink:0}}
</style></head><body><div id="shell">

<!-- toolbar -->
<div id="toolbar">
  <button class="btn on" id="bPan"  title="Pan (drag)">&#9995; Pan</button>
  <button class="btn"    id="bBox"  title="Box Zoom (drag rectangle)">&#9974; Zoom</button>
  <div class="sep"></div>
  <button class="btn"    id="bGrid" title="Toggle grid overlay">&#10166; Grid</button>
  <button class="btn"    id="bReset" title="Fit entire layout (double-click also works)">&#8635; Fit</button>
  <div class="sep"></div>
  <span id="zoomLbl" title="Current zoom level">100%</span>
</div>

<!-- body: canvas + sidebar -->
<div id="body">

  <!-- canvas -->
  <div id="wrap">
    <canvas id="cv"></canvas>
    <div id="selbox"></div>
    <div id="ruler"><div id="rbar"></div><div id="rlabel"></div></div>
  </div>

  <!-- sidebar -->
  <div id="sidebar">

    <!-- Cells group-box -->
    <div class="gb" style="flex:0 0 auto;max-height:42%">
      <div class="gb-title">&#128194; Cells</div>
      <div id="cellScroll"></div>
    </div>

    <!-- Layers group-box -->
    <div class="gb grow">
      <div class="gb-title">
        &#9632; Layers
      </div>
      <div class="lyr-ctrl">
        <button class="sbtn" id="bShowAll">Show All</button>
        <button class="sbtn" id="bHideAll">Hide All</button>
      </div>
      <div id="layerScroll"></div>
    </div>

  </div><!-- sidebar -->

</div><!-- body -->

<!-- status bar -->
<div id="status">
  <span id="cellName">—</span>
  <span id="coords">x: —, y: —</span>
</div>

</div><!-- shell -->

<script>
// ── Data injected by Python ───────────────────────────────────────────────
const ALL_CELLS = {all_cells_json};
const TOP_NAMES = {top_names_json};
const CELL_TREE = {cell_tree_json};
const INIT_CELL = {init_cell_json};
const UNIT      = "{unit}";
const PSIZE     = 14;

// ── Runtime state ─────────────────────────────────────────────────────────
let LAYERS   = [];
let GX, GY, GW, GH;
let patterns = [];
const hiddenNums = new Set();
let showGrid = false;
let sc, tx, ty, iSc, iTx, iTy;
let activeCellName = '';

// ── DOM refs ──────────────────────────────────────────────────────────────
const wrap = document.getElementById('wrap');
const cv   = document.getElementById('cv');
const sel  = document.getElementById('selbox');
const ctx  = cv.getContext('2d');

function resizeCanvas(){{
  cv.width  = wrap.offsetWidth  || 800;
  cv.height = wrap.offsetHeight || 580;
}}

// ── Hatch pattern builder ─────────────────────────────────────────────────
function buildPattern(fill, stroke, ptype){{
  const oc = document.createElement('canvas');
  oc.width = oc.height = PSIZE;
  const p = oc.getContext('2d');
  const s = PSIZE, h = s/2, lw = Math.max(1, s*0.11);
  p.fillStyle = fill; p.globalAlpha = 0.50; p.fillRect(0,0,s,s);
  p.globalAlpha = 0.85; p.strokeStyle = stroke; p.lineWidth = lw; p.lineCap = 'butt';
  if (ptype === 'dots') {{
    p.fillStyle = stroke; p.beginPath(); p.arc(h,h,s*0.15,0,Math.PI*2); p.fill();
  }} else {{
    p.beginPath();
    switch(ptype){{
      case 'hlines':  p.moveTo(0,h);  p.lineTo(s,h); break;
      case 'vlines':  p.moveTo(h,0);  p.lineTo(h,s); break;
      case 'diag45':  p.moveTo(0,0);  p.lineTo(s,s); break;
      case 'diag135': p.moveTo(s,0);  p.lineTo(0,s); break;
      case 'cross':   p.moveTo(0,h);  p.lineTo(s,h); p.moveTo(h,0); p.lineTo(h,s); break;
      case 'xcross':  p.moveTo(0,0);  p.lineTo(s,s); p.moveTo(s,0); p.lineTo(0,s); break;
    }}
    p.stroke();
  }}
  return ctx.createPattern(oc,'repeat');
}}

function drawSwatchOn(sw, fill, stroke, ptype){{
  const sc2 = sw.getContext('2d');
  const ps2 = 7;
  const oc  = document.createElement('canvas'); oc.width = oc.height = ps2;
  const p   = oc.getContext('2d');
  const s=ps2, h=s/2;
  p.fillStyle=fill; p.globalAlpha=0.50; p.fillRect(0,0,s,s);
  p.globalAlpha=0.85; p.strokeStyle=stroke; p.lineWidth=Math.max(1,s*0.11); p.lineCap='butt';
  if(ptype==='dots'){{ p.fillStyle=stroke; p.beginPath(); p.arc(h,h,s*0.15,0,Math.PI*2); p.fill(); }}
  else {{
    p.beginPath();
    switch(ptype){{
      case 'hlines':  p.moveTo(0,h); p.lineTo(s,h); break;
      case 'vlines':  p.moveTo(h,0); p.lineTo(h,s); break;
      case 'diag45':  p.moveTo(0,0); p.lineTo(s,s); break;
      case 'diag135': p.moveTo(s,0); p.lineTo(0,s); break;
      case 'cross':   p.moveTo(0,h); p.lineTo(s,h); p.moveTo(h,0); p.lineTo(h,s); break;
      case 'xcross':  p.moveTo(0,0); p.lineTo(s,s); p.moveTo(s,0); p.lineTo(0,s); break;
    }}
    p.stroke();
  }}
  const pat = sc2.createPattern(oc,'repeat');
  sc2.fillStyle = pat; sc2.fillRect(0,0,sw.width,sw.height);
  sc2.strokeStyle='#555'; sc2.lineWidth=1; sc2.strokeRect(0.5,0.5,sw.width-1,sw.height-1);
}}

// ── Layer panel ───────────────────────────────────────────────────────────
function buildLayerPanel(){{
  const list = document.getElementById('layerScroll');
  list.innerHTML = '';
  LAYERS.forEach(([lnum, lname, fill, stroke, ptype], i) => {{
    const row = document.createElement('div');
    row.className = 'lr' + (hiddenNums.has(lnum) ? ' hidden' : '');
    row.id = 'lr' + i;

    const cb = document.createElement('input');
    cb.type='checkbox'; cb.id='lc'+i; cb.checked=!hiddenNums.has(lnum);

    const sw = document.createElement('canvas');
    sw.className='swatch'; sw.width=22; sw.height=14;

    const lnum_span = document.createElement('span');
    lnum_span.className = 'lr-lnum';
    lnum_span.textContent = lnum;

    const lbl = document.createElement('label');
    lbl.htmlFor = 'lc'+i;
    lbl.textContent = lname;
    lbl.title = lname + ' (layer ' + lnum + ')';

    row.append(cb, sw, lnum_span, lbl);
    list.appendChild(row);
    drawSwatchOn(sw, fill, stroke, ptype);

    const toggle = () => {{
      if(cb.checked) hiddenNums.delete(lnum); else hiddenNums.add(lnum);
      row.className = 'lr' + (hiddenNums.has(lnum) ? ' hidden' : '');
      render();
    }};
    cb.addEventListener('change', toggle);
    row.addEventListener('click', e => {{ if(e.target!==cb && e.target!==lbl){{ cb.checked=!cb.checked; toggle(); }} }});
  }});
}}

document.getElementById('bShowAll').onclick = () => {{
  hiddenNums.clear();
  document.querySelectorAll('#layerScroll .lr').forEach((r,i) => {{
    r.className='lr'; r.querySelector('input').checked=true; }});
  render();
}};
document.getElementById('bHideAll').onclick = () => {{
  LAYERS.forEach(([lnum]) => hiddenNums.add(lnum));
  document.querySelectorAll('#layerScroll .lr').forEach(r => {{
    r.className='lr hidden'; r.querySelector('input').checked=false; }});
  render();
}};

// ── Cell hierarchy tree ───────────────────────────────────────────────────
function makeTreeNode(name, depth){{
  const children = (CELL_TREE[name] || []).filter(c => ALL_CELLS[c]);
  const hasData  = !!ALL_CELLS[name];
  const isTop    = TOP_NAMES.includes(name);

  const wrap2 = document.createElement('div');

  const row = document.createElement('div');
  row.className = 'tnode' + (name===activeCellName ? ' active' : '');
  row.id = 'tn_' + CSS.escape(name);
  row.style.paddingLeft = (4 + depth*14) + 'px';

  const tog = document.createElement('span');
  tog.className = 'tn-tog';
  tog.textContent = children.length ? '▶' : ' ';

  const lbl = document.createElement('span');
  lbl.className = 'tn-lbl' + (isTop ? ' toplevel' : '');
  lbl.textContent = name;
  lbl.title = name;

  row.append(tog, lbl);
  wrap2.appendChild(row);

  const childBox = document.createElement('div');
  childBox.className = 'tn-children';
  wrap2.appendChild(childBox);

  let expanded = false;
  if(children.length){{
    tog.onclick = e => {{
      e.stopPropagation();
      expanded = !expanded;
      tog.textContent = expanded ? '▼' : '▶';
      childBox.style.display = expanded ? 'block' : 'none';
      if(expanded && !childBox.children.length)
        children.forEach(c => childBox.appendChild(makeTreeNode(c, depth+1)));
    }};
  }}

  if(hasData){{
    row.onclick = () => {{
      document.querySelectorAll('.tnode.active').forEach(el => el.classList.remove('active'));
      row.classList.add('active');
      loadCell(name);
    }};
  }} else {{
    lbl.style.color = '#888';
  }}
  return wrap2;
}}

function buildCellTree(){{
  const container = document.getElementById('cellScroll');
  container.innerHTML = '';
  TOP_NAMES.forEach(name => container.appendChild(makeTreeNode(name, 0)));
  // cells that exist but aren't top-level and aren't reachable (orphans)
  const reachable = new Set();
  function mark(n){{ (CELL_TREE[n]||[]).forEach(c=>{{ if(!reachable.has(c)){{ reachable.add(c); mark(c); }} }}); }}
  TOP_NAMES.forEach(n=>{{ reachable.add(n); mark(n); }});
  Object.keys(ALL_CELLS).forEach(n => {{
    if(!reachable.has(n)) container.appendChild(makeTreeNode(n, 0));
  }});
}}

// ── Load a cell ───────────────────────────────────────────────────────────
function loadCell(name){{
  const cd = ALL_CELLS[name]; if(!cd) return;
  activeCellName = name;
  LAYERS   = cd.l;
  [GX,GY,GW,GH] = cd.b;
  patterns = LAYERS.map(([,, fill,stroke,ptype]) => buildPattern(fill,stroke,ptype));
  buildLayerPanel();
  document.getElementById('cellName').textContent = name;
  if(cv.width){{ fitView(); render(); }}
}}

// ── View ──────────────────────────────────────────────────────────────────
function fitView(){{
  const W=cv.width, H=cv.height;
  sc = Math.min(W/GW, H/GH)*0.97;
  tx = (W-GW*sc)/2 - GX*sc;
  ty = (H-GH*sc)/2 - GY*sc;
  iSc=sc; iTx=tx; iTy=ty;
  updateZoom();
}}

function updateZoom(){{
  // Compute zoom relative to "fit" scale
  const pct = Math.round(sc/iSc*100);
  document.getElementById('zoomLbl').textContent = pct+'%';
}}

// ── Grid overlay ──────────────────────────────────────────────────────────
function drawGrid(){{
  const W=cv.width, H=cv.height;
  // How many GDS units per pixel
  const uPx = 1/sc;
  // Target ~60 px between minor lines, ~300 px between major lines
  let minor = niceNum(uPx*60);
  let major = minor*5;

  ctx.save();
  // minor grid
  ctx.strokeStyle='rgba(255,255,255,0.06)';
  ctx.lineWidth=1;
  drawGridLines(W,H,minor);
  // major grid
  ctx.strokeStyle='rgba(255,255,255,0.14)';
  ctx.lineWidth=1;
  drawGridLines(W,H,major);
  // major labels
  ctx.fillStyle='rgba(200,220,255,0.55)';
  ctx.font='9px monospace';
  const x0=Math.ceil(-tx/sc/major)*major;
  for(let gx=x0; gx*sc+tx<W; gx+=major){{
    const sx=gx*sc+tx;
    ctx.fillText(fmtCoord(gx), sx+2, H-4);
  }}
  const y0=Math.ceil(-ty/sc/major)*major;
  for(let gy=y0; gy*sc+ty<H; gy+=major){{
    const sy=gy*sc+ty;
    ctx.fillText(fmtCoord(-gy), 4, sy-2);  // negate: canvas y is flipped
  }}
  ctx.restore();
}}
function drawGridLines(W,H,step){{
  ctx.beginPath();
  const x0=Math.ceil(-tx/sc/step)*step;
  for(let gx=x0; gx*sc+tx<W+1; gx+=step){{ const sx=gx*sc+tx; ctx.moveTo(sx,0); ctx.lineTo(sx,H); }}
  const y0=Math.ceil(-ty/sc/step)*step;
  for(let gy=y0; gy*sc+ty<H+1; gy+=step){{ const sy=gy*sc+ty; ctx.moveTo(0,sy); ctx.lineTo(W,sy); }}
  ctx.stroke();
}}
function fmtCoord(v){{ return (Math.abs(v)<1000?+v.toPrecision(4):Math.round(v))+''; }}

// ── Ruler ─────────────────────────────────────────────────────────────────
function niceNum(x){{
  if(x<=0)return 1;
  const m=Math.pow(10,Math.floor(Math.log10(x))), f=x/m;
  return f<1.5?m : f<3.5?2*m : f<7.5?5*m : 10*m;
}}
function updateRuler(){{
  const gpx=1/sc, gl=niceNum(gpx*120), bp=gl*sc;
  document.getElementById('rbar').style.width=bp+'px';
  document.getElementById('rlabel').textContent=
    (gl%1===0?gl:gl.toPrecision(3))+' '+UNIT;
}}

// ── Main render ───────────────────────────────────────────────────────────
function render(){{
  const W=cv.width, H=cv.height;
  ctx.clearRect(0,0,W,H);
  if(showGrid) drawGrid();

  const wxMin=-tx/sc, wyMin=-ty/sc;
  const wxMax=(W-tx)/sc, wyMax=(H-ty)/sc;

  for(let li=0;li<LAYERS.length;li++){{
    const [lnum,,fill,stroke,ptype,polys,bounds]=LAYERS[li];
    if(hiddenNums.has(lnum)) continue;
    const pat=patterns[li];
    pat.setTransform(new DOMMatrix([1,0,0,1, tx%PSIZE, ty%PSIZE]));
    ctx.fillStyle=pat;
    for(let pi=0;pi<polys.length;pi++){{
      const [bx0,by0,bx1,by1]=bounds[pi];
      if(bx1<wxMin||bx0>wxMax||by1<wyMin||by0>wyMax) continue;
      const poly=polys[pi];
      ctx.beginPath();
      ctx.moveTo(poly[0]*sc+tx, poly[1]*sc+ty);
      for(let k=2;k<poly.length;k+=2)
        ctx.lineTo(poly[k]*sc+tx, poly[k+1]*sc+ty);
      ctx.closePath(); ctx.fill();
    }}
  }}
  updateRuler();
}}

// ── Init ──────────────────────────────────────────────────────────────────
function init(){{
  if(!wrap.offsetWidth){{ requestAnimationFrame(init); return; }}
  resizeCanvas();
  buildCellTree();
  loadCell(INIT_CELL);
}}
requestAnimationFrame(init);

// ── Toolbar ───────────────────────────────────────────────────────────────
let mode='pan';
function setMode(m){{
  mode=m;
  ['bPan','bBox'].forEach(id=>document.getElementById(id).classList.remove('on'));
  document.getElementById(m==='pan'?'bPan':'bBox').classList.add('on');
}}
document.getElementById('bPan').onclick  = ()=>setMode('pan');
document.getElementById('bBox').onclick  = ()=>setMode('zoombox');
document.getElementById('bReset').onclick= ()=>{{sc=iSc;tx=iTx;ty=iTy;updateZoom();render();}};
document.getElementById('bGrid').onclick = ()=>{{
  showGrid=!showGrid;
  document.getElementById('bGrid').classList.toggle('on',showGrid);
  render();
}};

// ── Scroll-wheel zoom ─────────────────────────────────────────────────────
wrap.addEventListener('wheel',e=>{{
  e.preventDefault();
  const r=wrap.getBoundingClientRect();
  const mx=e.clientX-r.left, my=e.clientY-r.top;
  const d=e.deltaY<0?1.15:1/1.15;
  tx=(tx-mx)*d+mx; ty=(ty-my)*d+my; sc*=d;
  updateZoom(); render();
}},{{passive:false}});

// ── Mouse drag (pan / box-zoom) ───────────────────────────────────────────
let drag=false, dsx,dsy,dtx,dty,bx0,by0;
wrap.addEventListener('mousedown',e=>{{
  if(e.button!==0&&e.button!==1) return;
  e.preventDefault(); drag=true;
  dsx=e.clientX; dsy=e.clientY; dtx=tx; dty=ty;
  const r=wrap.getBoundingClientRect();
  bx0=e.clientX-r.left; by0=e.clientY-r.top;
  if(mode==='zoombox')
    sel.style.cssText=`left:${{bx0}}px;top:${{by0}}px;width:0;height:0;display:block`;
}});
window.addEventListener('mousemove',e=>{{
  if(!drag) return;
  if(mode==='pan'){{
    tx=dtx+(e.clientX-dsx); ty=dty+(e.clientY-dsy); render();
  }}else{{
    const r=wrap.getBoundingClientRect();
    const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
    const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
    sel.style.left  =Math.min(bx0,cx)+'px'; sel.style.top   =Math.min(by0,cy)+'px';
    sel.style.width =Math.abs(cx-bx0)+'px'; sel.style.height=Math.abs(cy-by0)+'px';
  }}
}});
window.addEventListener('mouseup',e=>{{
  if(!drag) return; drag=false;
  if(mode==='zoombox'){{
    sel.style.display='none';
    const r=wrap.getBoundingClientRect();
    const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
    const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
    let nx0=Math.min(bx0,cx), ny0=Math.min(by0,cy);
    let nw=Math.abs(cx-bx0), nh=Math.abs(cy-by0);
    if(nw<6||nh<6) return;
    const cAR=cv.width/cv.height, sAR=nw/nh;
    if(sAR>cAR){{const n=nw/cAR;ny0-=(n-nh)/2;nh=n;}}
    else       {{const n=nh*cAR;nx0-=(n-nw)/2;nw=n;}}
    const wx0=(nx0-tx)/sc, wy0=(ny0-ty)/sc;
    sc=sc*cv.width/nw; tx=-wx0*sc; ty=-wy0*sc;
    updateZoom(); render();
  }}
}});

// ── Cursor coordinates ────────────────────────────────────────────────────
wrap.addEventListener('mousemove',e=>{{
  const r=wrap.getBoundingClientRect();
  const wx= ((e.clientX-r.left)-tx)/sc;
  const wy=-((e.clientY-r.top) -ty)/sc;  // negate: canvas y is flipped
  const fmt=v=>(Math.abs(v)<1e4?+v.toPrecision(5):Math.round(v));
  document.getElementById('coords').textContent=
    'x: '+fmt(wx)+' '+UNIT+',  y: '+fmt(wy)+' '+UNIT;
}});
wrap.addEventListener('mouseleave',()=>{{
  document.getElementById('coords').textContent='x: —, y: —';
}});

// ── Double-click → reset ──────────────────────────────────────────────────
wrap.addEventListener('dblclick',()=>{{sc=iSc;tx=iTx;ty=iTy;updateZoom();render();}});
</script></body></html>"""

                components.html(html, height=700)
                st.caption(
                    "Scroll to zoom · Drag to pan/box-zoom · Double-click to fit · "
                    "Grid button toggles overlay · Click any cell in the tree to switch view")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
