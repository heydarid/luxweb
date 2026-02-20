import streamlit as st
import os
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
import streamlit.components.v1 as components

# KLayout-style layer defaults: (fill_color, frame_color, stipple_index)
# Stipple indices reference built-in KLayout patterns defined in JS.
_LAYER_STYLES = [
    ("#ff0000", "#ff0000",  2),   # dotted
    ("#00ff00", "#00ff00",  4),   # left-hatched
    ("#0000ff", "#0000ff",  5),   # lightly left-hatched
    ("#ffff00", "#ffff00",  8),   # right-hatched
    ("#ff00ff", "#ff00ff",  9),   # lightly right-hatched
    ("#00ffff", "#00ffff", 12),   # cross-hatched
    ("#ff8000", "#ff8000",  3),   # coarsely dotted
    ("#80ff00", "#80ff00",  6),   # strongly left-hatched dense
    ("#0080ff", "#0080ff", 10),   # strongly right-hatched dense
    ("#ff0080", "#ff0080", 13),   # lightly cross-hatched
    ("#80ff80", "#80ff80", 14),   # checkerboard 2px
    ("#8080ff", "#8080ff", 23),   # 22.5 degree down
    ("#ff8080", "#ff8080", 33),   # vertical
    ("#80ffff", "#80ffff", 38),   # horizontal
    ("#ffff80", "#ffff80", 28),   # zig zag
    ("#ff80ff", "#ff80ff", 29),   # sine
]


def _unit_label(lib_unit):
    if abs(lib_unit - 1e-6) < 1e-9:  return "µm"
    if abs(lib_unit - 1e-9) < 1e-12: return "nm"
    if abs(lib_unit - 1e-3) < 1e-6:  return "mm"
    return "u"


def _parse_lyp(lyp_bytes):
    """Parse a KLayout .lyp file.
    Returns ({layer: hex_color}, {layer: frame_color}, {layer: name})."""
    layer_fills  = {}
    layer_frames = {}
    layer_names  = {}
    try:
        root = ET.fromstring(lyp_bytes)
        for props in root.findall(".//properties"):
            if props.findtext("visible", "true").strip().lower() == "false":
                continue
            source      = props.findtext("source",      "").strip()
            fill_color  = props.findtext("fill-color",  "").strip()
            frame_color = props.findtext("frame-color", "").strip()
            name        = props.findtext("name",        "").strip()
            if not source or not fill_color:
                continue
            try:
                layer = int(source.split("/")[0])
                layer_fills[layer]  = fill_color
                layer_frames[layer] = frame_color or fill_color
                if name:
                    layer_names[layer] = name
            except (ValueError, IndexError):
                continue
    except ET.ParseError:
        pass
    return layer_fills, layer_frames, layer_names


def _build_cell_data(cell, layer_fills=None, layer_frames=None, layer_names=None):
    """Build canvas render data for one gdstk Cell.

    Returns (layers_list, vb_x, vb_y, vb_w, vb_h) or (None, 0,0,1,1).

    Each entry:
        [layer_num, name, fill_color, frame_color, stipple_idx, polys, bounds]
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
        style      = _LAYER_STYLES[i % len(_LAYER_STYLES)]
        fill_c     = (layer_fills  or {}).get(layer_num, style[0])
        frame_c    = (layer_frames or {}).get(layer_num, style[1])
        stip_idx   = style[2]
        lname      = (layer_names  or {}).get(layer_num, f"{layer_num}/0")

        polys  = []
        bounds = []
        for (flat, bx0, by0, bx1, by1) in layer_polys[layer_num]:
            polys.append(flat)
            bounds.append([round(bx0,2), round(by0,2),
                           round(bx1,2), round(by1,2)])

        layers_list.append([layer_num, lname, fill_c,
                            frame_c, stip_idx, polys, bounds])

    return layers_list, vb_x, vb_y, vb_w, vb_h


def show_interactive_viewer():
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

                layer_fills, layer_frames, layer_names = (
                    _parse_lyp(uploaded_lyp.read()) if uploaded_lyp
                    else ({}, {}, {}))

                top_names = [c.name for c in top_cells]
                try:
                    all_lib_cells = list(lib.cells)
                except Exception:
                    all_lib_cells = list(top_cells)

                non_top = sorted(
                    [c for c in all_lib_cells if c.name not in top_names],
                    key=lambda c: c.name)
                ordered_cells = list(top_cells) + non_top

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

                all_cells_data: dict = {}
                for cell in ordered_cells:
                    layers_list, vb_x, vb_y, vb_w, vb_h = _build_cell_data(
                        cell, layer_fills, layer_frames, layer_names)
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
                all_cells_json   = json.dumps(all_cells_data, separators=(',',':'))
                top_names_json   = json.dumps(top_names,      separators=(',',':'))
                cell_tree_json   = json.dumps(cell_children,  separators=(',',':'))
                init_cell_json   = json.dumps(init_cell)

                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;overflow:hidden;background:#000;
  font-family:"MS Sans Serif",Arial,sans-serif;font-size:11px;color:#000}}

#shell{{display:flex;flex-direction:column;height:100%;}}

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

#body{{display:flex;flex:1;overflow:hidden;min-height:0}}

#wrap{{
  position:relative;flex:1;min-width:0;
  background:#000;overflow:hidden;cursor:crosshair;
}}
canvas{{display:block;}}
#selbox{{position:absolute;display:none;pointer-events:none;
  border:1px dashed #7af;background:rgba(80,140,255,.10);}}

#ruler{{position:absolute;bottom:28px;left:12px;z-index:10;
  color:#bbb;font:10px/1.4 monospace;pointer-events:none;}}
#rbar{{height:2px;background:#bbb;border-radius:1px;margin-bottom:3px}}
#rlabel{{text-align:center;text-shadow:0 0 3px #000}}

#status{{
  height:18px;background:#d4d0c8;
  border-top:1px solid #808080;padding:2px 6px;
  display:flex;align-items:center;gap:16px;flex-shrink:0;
  font:11px "MS Sans Serif",Arial,sans-serif;
}}
#coords{{color:#000;}}
#cellName{{color:#000080;font-weight:bold;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;max-width:240px}}

#sidebar{{
  width:195px;min-width:195px;background:#d4d0c8;
  border-left:2px solid #808080;
  display:flex;flex-direction:column;overflow:hidden;
}}
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

<div id="toolbar">
  <button class="btn on" id="bPan"  title="Pan (drag)">&#9995; Pan</button>
  <button class="btn"    id="bBox"  title="Box Zoom (drag rectangle)">&#9974; Zoom</button>
  <div class="sep"></div>
  <button class="btn"    id="bGrid" title="Toggle grid overlay">&#10166; Grid</button>
  <button class="btn"    id="bReset" title="Fit (double-click also works)">&#8635; Fit</button>
  <div class="sep"></div>
  <span id="zoomLbl" title="Current zoom level">100%</span>
</div>

<div id="body">
  <div id="wrap">
    <canvas id="cv"></canvas>
    <div id="selbox"></div>
    <div id="ruler"><div id="rbar"></div><div id="rlabel"></div></div>
  </div>
  <div id="sidebar">
    <div class="gb" style="flex:0 0 auto;max-height:42%">
      <div class="gb-title">&#128194; Cells</div>
      <div id="cellScroll"></div>
    </div>
    <div class="gb grow">
      <div class="gb-title">&#9632; Layers</div>
      <div class="lyr-ctrl">
        <button class="sbtn" id="bShowAll">Show All</button>
        <button class="sbtn" id="bHideAll">Hide All</button>
      </div>
      <div id="layerScroll"></div>
    </div>
  </div>
</div>

<div id="status">
  <span id="cellName">&mdash;</span>
  <span id="coords">x: &mdash;, y: &mdash;</span>
</div>

</div>

<script>
// ═══════════════════════════════════════════════════════════════════════════
// KLayout built-in stipple/dither patterns — transcribed from
// layDitherPattern.cc in the KLayout source.
// Each entry is an array of row strings ('*' = set, '.' = unset).
// ═══════════════════════════════════════════════════════════════════════════
const STIPPLES = [
  // 0: solid
  ['*'],
  // 1: hollow
  ['.'],
  // 2: dotted
  ['*.','.*'],
  // 3: coarsely dotted
  ['*...','....','..*.','....'],
  // 4: left-hatched
  ['*...','.*..','..*.',
   '...*'],
  // 5: lightly left-hatched
  ['*.......',
   '.*......',
   '..*.....',
   '...*....',
   '....*...',
   '.....*..',
   '......*.',
   '.......*'],
  // 6: strongly left-hatched dense
  ['**..','.**.','..**','*..*'],
  // 7: strongly left-hatched sparse
  ['**......','.**.....','..**....','...**...','....**..',
   '.....**.',  '......**','*......*'],
  // 8: right-hatched
  ['*...','...*','..*.','.*..'],
  // 9: lightly right-hatched
  ['*.......',
   '.......*',
   '......*.',
   '.....*..',
   '....*...',
   '...*....',
   '..*.....',
   '.*......'],
  // 10: strongly right-hatched dense
  ['**..','*..*','..**','.**.' ],
  // 11: strongly right-hatched sparse
  ['**......','*......*','......**','.....**.',
   '....**..',  '...**...', '..**....','.*......'],
  // 12: cross-hatched
  ['*...','.*.*','..*.',
   '.*.*'],
  // 13: lightly cross-hatched
  ['*.......',
   '.*.....*',
   '..*...*.',
   '...*.*..',
   '....*...',
   '...*.*..',
   '..*...*.',
   '.*.....*'],
  // 14: checkerboard 2px
  ['**..','**..', '..**','..**'],
  // 15: strongly cross-hatched sparse
  ['**......','***....*','..**..**','...****.',
   '....**..',  '...****.',  '..**..**','***....*'],
  // 16: heavy checkerboard
  ['****....','****....','****....','****....',
   '....****','....****','....****','....****'],
  // 17: hollow bubbles
  ['.*...*..','*.*.....',  '.*...*..','....*.*.',
   '.*...*..','*.*.....',  '.*...*..','....*.*.' ],
  // 18: solid bubbles
  ['.*...*..','***.....',  '.*...*..','....***.',
   '.*...*..','***.....',  '.*...*..','....***.' ],
  // 19: pyramids
  ['.*......','*.*.....',  '****...*','........',
   '....*...','...*.*..',  '..*****.',  '........'],
  // 20: turned pyramids
  ['****...*','*.*.....',  '.*......','........',
   '..*****.',  '...*.*..',  '....*...','........'],
  // 21: plus
  ['..*...*.','..*.....',  '*****...','..*.....',
   '..*...*.',  '......*.','*...****','......*.'],
  // 22: minus
  ['........','........',  '*****...','........',
   '........','........','*...****','........'],
  // 23: 22.5 degree down
  ['*......*','.**.....',  '...**...','.....**.',
   '*......*','.**.....',  '...**...','.....**.' ],
  // 24: 22.5 degree up
  ['*......*','.....**.',  '...**...','.**.....',
   '*......*','.....**.',  '...**...','.*......'],
  // 25: 67.5 degree down
  ['*...*...','.*...*..','.*...*..', '..*...*.',
   '..*...*.',  '...*...*','...*...*','*...*...'],
  // 26: 67.5 degree up
  ['...*...*','..*...*.','..*...*.',  '.*...*..',
   '.*...*..',  '*...*...','*...*...','...*...*'],
  // 27: 22.5 cross hatched
  ['*......*','.**..**.',  '...**...','.**..**.',
   '*......*','.**..**.',  '...**...','.**..**.' ],
  // 28: zig zag
  ['..*...*.',  '.*.*.*.*','*...*...',  '........',
   '..*...*.',  '.*.*.*.*','*...*...',  '........'],
  // 29: sine
  ['..***...',  '.*...*..','*.....**',  '........',
   '..***...',  '.*...*..','*.....**',  '........'],
  // 30: heavy unordered
  ['****.*.*','**.****.',  '*.**.***','*****.*.',
   '.**.****','**.***.*',  '.****.**','*.*.****'],
  // 31: light unordered
  ['....*.*.',  '..*....*','.*..*...',
   '.....*.*','*..*....','..*...*.',  '*....*..',  '.*.*....'],
  // 32: vertical dense
  ['*.','*.'],
  // 33: vertical
  ['.*..','.*..','.*..','.*..'],
  // 34: vertical thick
  ['.**.',  '.**.',  '.**.',  '.**.' ],
  // 35: vertical sparse
  ['...*....','...*....','...*....','...*....'],
  // 36: vertical sparse thick
  ['...**...','...**...','...**...','...**...'],
  // 37: horizontal dense
  ['**','..'],
  // 38: horizontal
  ['....','****','....','....'],
  // 39: horizontal thick
  ['....','****','****','....'],
  // 40: horizontal sparse
  ['........','........','........','********'],
  // 41: horizontal sparse thick
  ['........','........','********','********'],
];

// ═══════════════════════════════════════════════════════════════════════════
const ALL_CELLS = {all_cells_json};
const TOP_NAMES = {top_names_json};
const CELL_TREE = {cell_tree_json};
const INIT_CELL = {init_cell_json};
const UNIT      = "{unit}";

// ── State ─────────────────────────────────────────────────────────────────
let LAYERS = [], GX, GY, GW, GH;
let fillPatterns = [], frameColors = [];
const hiddenNums = new Set();
let showGrid = false;
let sc, tx, ty, iSc, iTx, iTy;
let activeCellName = '';

const wrap = document.getElementById('wrap');
const cv   = document.getElementById('cv');
const sel  = document.getElementById('selbox');
const ctx  = cv.getContext('2d');

function resizeCanvas(){{
  cv.width  = wrap.offsetWidth  || 800;
  cv.height = wrap.offsetHeight || 580;
}}

// ── Build a CanvasPattern from a KLayout stipple bitmap ───────────────────
// Key: the stipple is in SCREEN pixels, constant size regardless of zoom.
// Only pixels where bitmap='*' are drawn in fillColor; '.' stays transparent.
// This is exactly how KLayout renders — you see through the gaps.
function buildStipplePattern(fillColor, stipIdx){{
  const bmp = STIPPLES[stipIdx] || STIPPLES[0];
  const h = bmp.length, w = bmp[0].length;
  const oc = document.createElement('canvas');
  oc.width = w; oc.height = h;
  const p  = oc.getContext('2d');

  // Parse fillColor to get r,g,b
  let r=255,g=255,b=255;
  if (fillColor.startsWith('#')) {{
    const hex = fillColor.slice(1);
    if (hex.length===6) {{
      r=parseInt(hex.slice(0,2),16);
      g=parseInt(hex.slice(2,4),16);
      b=parseInt(hex.slice(4,6),16);
    }}
  }}

  const img = p.createImageData(w, h);
  for(let y=0;y<h;y++){{
    const row = bmp[y];
    for(let x=0;x<w;x++){{
      const idx = (y*w+x)*4;
      if(x < row.length && row[x]==='*'){{
        img.data[idx]   = r;
        img.data[idx+1] = g;
        img.data[idx+2] = b;
        img.data[idx+3] = 255;
      }} else {{
        img.data[idx+3] = 0;  // transparent
      }}
    }}
  }}
  p.putImageData(img, 0, 0);
  return ctx.createPattern(oc, 'repeat');
}}

// Sidebar swatch: fill a small canvas with the stipple pattern on dark bg
function drawSwatchOn(sw, fillColor, frameColor, stipIdx){{
  const sc2 = sw.getContext('2d');
  sc2.fillStyle = '#000';
  sc2.fillRect(0, 0, sw.width, sw.height);

  const pat = buildStipplePattern(fillColor, stipIdx);
  sc2.fillStyle = pat;
  sc2.fillRect(0, 0, sw.width, sw.height);

  sc2.strokeStyle = frameColor;
  sc2.lineWidth = 1;
  sc2.strokeRect(0.5, 0.5, sw.width-1, sw.height-1);
}}

// ── Layer panel ───────────────────────────────────────────────────────────
function buildLayerPanel(){{
  const list = document.getElementById('layerScroll');
  list.innerHTML = '';
  LAYERS.forEach(([lnum, lname, fill, frame, stipIdx], i) => {{
    const row = document.createElement('div');
    row.className = 'lr' + (hiddenNums.has(lnum) ? ' hidden' : '');

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
    drawSwatchOn(sw, fill, frame, stipIdx);

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
  document.querySelectorAll('#layerScroll .lr').forEach(r => {{
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
  const wrap2    = document.createElement('div');

  const row = document.createElement('div');
  row.className = 'tnode' + (name===activeCellName ? ' active' : '');
  row.style.paddingLeft = (4 + depth*14) + 'px';

  const tog = document.createElement('span');
  tog.className = 'tn-tog';
  tog.textContent = children.length ? '▶' : ' ';

  const lbl = document.createElement('span');
  lbl.className = 'tn-lbl' + (isTop ? ' toplevel' : '');
  lbl.textContent = name; lbl.title = name;

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
  }} else {{ lbl.style.color = '#888'; }}
  return wrap2;
}}

function buildCellTree(){{
  const container = document.getElementById('cellScroll');
  container.innerHTML = '';
  TOP_NAMES.forEach(name => container.appendChild(makeTreeNode(name, 0)));
  const reachable = new Set();
  function mark(n){{ (CELL_TREE[n]||[]).forEach(c=>{{ if(!reachable.has(c)){{ reachable.add(c); mark(c); }} }}); }}
  TOP_NAMES.forEach(n=>{{ reachable.add(n); mark(n); }});
  Object.keys(ALL_CELLS).forEach(n => {{
    if(!reachable.has(n)) container.appendChild(makeTreeNode(n, 0));
  }});
}}

// ── Load cell ─────────────────────────────────────────────────────────────
function loadCell(name){{
  const cd = ALL_CELLS[name]; if(!cd) return;
  activeCellName = name;
  LAYERS = cd.l;
  [GX,GY,GW,GH] = cd.b;

  fillPatterns = LAYERS.map(([,,fill,,stipIdx]) => buildStipplePattern(fill, stipIdx));
  frameColors  = LAYERS.map(([,,,frame]) => frame);

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
  document.getElementById('zoomLbl').textContent = Math.round(sc/iSc*100)+'%';
}}

// ── Grid ──────────────────────────────────────────────────────────────────
function drawGrid(){{
  const W=cv.width, H=cv.height, uPx=1/sc;
  let minor=niceNum(uPx*60), major=minor*5;
  ctx.save();
  ctx.strokeStyle='rgba(255,255,255,0.08)'; ctx.lineWidth=1;
  drawGridLines(W,H,minor);
  ctx.strokeStyle='rgba(255,255,255,0.18)'; ctx.lineWidth=1;
  drawGridLines(W,H,major);
  ctx.fillStyle='rgba(180,200,255,0.5)'; ctx.font='9px monospace';
  let x0=Math.ceil(-tx/sc/major)*major;
  for(let gx=x0; gx*sc+tx<W; gx+=major) ctx.fillText(fmtCoord(gx), gx*sc+tx+2, H-4);
  let y0=Math.ceil(-ty/sc/major)*major;
  for(let gy=y0; gy*sc+ty<H; gy+=major) ctx.fillText(fmtCoord(-gy), 4, gy*sc+ty-2);
  ctx.restore();
}}
function drawGridLines(W,H,step){{
  ctx.beginPath();
  let x0=Math.ceil(-tx/sc/step)*step;
  for(let gx=x0; gx*sc+tx<W+1; gx+=step){{ let sx=gx*sc+tx; ctx.moveTo(sx,0); ctx.lineTo(sx,H); }}
  let y0=Math.ceil(-ty/sc/step)*step;
  for(let gy=y0; gy*sc+ty<H+1; gy+=step){{ let sy=gy*sc+ty; ctx.moveTo(0,sy); ctx.lineTo(W,sy); }}
  ctx.stroke();
}}
function fmtCoord(v){{ return (Math.abs(v)<1000?+v.toPrecision(4):Math.round(v))+''; }}

function niceNum(x){{
  if(x<=0) return 1;
  const m=Math.pow(10,Math.floor(Math.log10(x))), f=x/m;
  return f<1.5?m : f<3.5?2*m : f<7.5?5*m : 10*m;
}}
function updateRuler(){{
  const gpx=1/sc, gl=niceNum(gpx*120), bp=gl*sc;
  document.getElementById('rbar').style.width=bp+'px';
  document.getElementById('rlabel').textContent=
    (gl%1===0?gl:gl.toPrecision(3))+' '+UNIT;
}}

// ══════════════════════════════════════════════════════════════════════════
// RENDER — KLayout-style:
//   1. Black background
//   2. For each visible layer, for each polygon:
//      a. Fill with stipple pattern (opaque at '*' pixels, transparent at '.')
//      b. Stroke outline in frame_color (1px)
//   3. Because stipple has transparent gaps, you see through to layers below
//      and the black background — same visual as KLayout/kwasm.
// ══════════════════════════════════════════════════════════════════════════
function render(){{
  const W=cv.width, H=cv.height;
  ctx.fillStyle='#000';
  ctx.fillRect(0,0,W,H);
  if(showGrid) drawGrid();

  const wxMin=-tx/sc, wyMin=-ty/sc;
  const wxMax=(W-tx)/sc, wyMax=(H-ty)/sc;

  for(let li=0; li<LAYERS.length; li++){{
    const [lnum,,,,, polys, bounds] = LAYERS[li];
    if(hiddenNums.has(lnum)) continue;

    const pat   = fillPatterns[li];
    const frc   = frameColors[li];

    // Anchor stipple to screen origin (fixed pixel grid)
    pat.setTransform(new DOMMatrix([1,0,0,1, tx%1, ty%1]));

    for(let pi=0; pi<polys.length; pi++){{
      const [bx0,by0,bx1,by1] = bounds[pi];
      if(bx1<wxMin||bx0>wxMax||by1<wyMin||by0>wyMax) continue;

      const poly = polys[pi];
      ctx.beginPath();
      ctx.moveTo(poly[0]*sc+tx, poly[1]*sc+ty);
      for(let k=2; k<poly.length; k+=2)
        ctx.lineTo(poly[k]*sc+tx, poly[k+1]*sc+ty);
      ctx.closePath();

      // Stipple fill
      ctx.fillStyle = pat;
      ctx.fill();

      // Frame outline (1px, KLayout style)
      ctx.strokeStyle = frc;
      ctx.lineWidth = 1;
      ctx.stroke();
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
document.getElementById('bPan').onclick   = ()=>setMode('pan');
document.getElementById('bBox').onclick   = ()=>setMode('zoombox');
document.getElementById('bReset').onclick = ()=>{{sc=iSc;tx=iTx;ty=iTy;updateZoom();render();}};
document.getElementById('bGrid').onclick  = ()=>{{
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

// ── Mouse drag ────────────────────────────────────────────────────────────
// Middle button (1) always pans regardless of mode.
// In zoombox mode, dragging top-left→bottom-right zooms IN to the rect;
// dragging bottom-right→top-left (reverse) zooms OUT to fit the layout.
let drag=false, dragBtn=-1, dsx,dsy,dtx,dty,bx0,by0;
wrap.addEventListener('mousedown',e=>{{
  if(e.button!==0&&e.button!==1) return;
  e.preventDefault(); drag=true; dragBtn=e.button;
  dsx=e.clientX; dsy=e.clientY; dtx=tx; dty=ty;
  const r=wrap.getBoundingClientRect();
  bx0=e.clientX-r.left; by0=e.clientY-r.top;
  if(mode==='zoombox'&&dragBtn===0)
    sel.style.cssText=`left:${{bx0}}px;top:${{by0}}px;width:0;height:0;display:block`;
}});
window.addEventListener('mousemove',e=>{{
  if(!drag) return;
  if(mode==='pan'||dragBtn===1){{
    tx=dtx+(e.clientX-dsx); ty=dty+(e.clientY-dsy); render();
  }}else{{
    const r=wrap.getBoundingClientRect();
    const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
    const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
    sel.style.left=Math.min(bx0,cx)+'px'; sel.style.top=Math.min(by0,cy)+'px';
    sel.style.width=Math.abs(cx-bx0)+'px'; sel.style.height=Math.abs(cy-by0)+'px';
  }}
}});
window.addEventListener('mouseup',e=>{{
  if(!drag) return; drag=false;
  if(mode==='zoombox'&&dragBtn===0){{
    sel.style.display='none';
    const r=wrap.getBoundingClientRect();
    const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
    const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
    let nw=Math.abs(cx-bx0), nh=Math.abs(cy-by0);
    if(nw<6||nh<6){{ dragBtn=-1; return; }}

    // Detect drag direction: end is up-left of start → zoom out (fit)
    const endRight = (e.clientX-r.left) >= bx0;
    const endBelow = (e.clientY-r.top)  >= by0;
    if(!endRight && !endBelow){{
      sc=iSc; tx=iTx; ty=iTy; updateZoom(); render();
      dragBtn=-1; return;
    }}

    let nx0=Math.min(bx0,cx), ny0=Math.min(by0,cy);
    const cAR=cv.width/cv.height, sAR=nw/nh;
    if(sAR>cAR){{const n=nw/cAR;ny0-=(n-nh)/2;nh=n;}}
    else       {{const n=nh*cAR;nx0-=(n-nw)/2;nw=n;}}
    const wx0=(nx0-tx)/sc, wy0=(ny0-ty)/sc;
    sc=sc*cv.width/nw; tx=-wx0*sc; ty=-wy0*sc;
    updateZoom(); render();
  }}
  dragBtn=-1;
}});

wrap.addEventListener('mousemove',e=>{{
  const r=wrap.getBoundingClientRect();
  const wx= ((e.clientX-r.left)-tx)/sc;
  const wy=-((e.clientY-r.top) -ty)/sc;
  const fmt=v=>(Math.abs(v)<1e4?+v.toPrecision(5):Math.round(v));
  document.getElementById('coords').textContent=
    'x: '+fmt(wx)+' '+UNIT+',  y: '+fmt(wy)+' '+UNIT;
}});
wrap.addEventListener('mouseleave',()=>{{
  document.getElementById('coords').textContent='x: \\u2014, y: \\u2014';
}});

wrap.addEventListener('dblclick',()=>{{sc=iSc;tx=iTx;ty=iTy;updateZoom();render();}});
wrap.addEventListener('auxclick',e=>e.preventDefault());   // suppress middle-click auto-scroll
</script></body></html>"""

                components.html(html, height=700)
                st.caption(
                    "Scroll to zoom \u00b7 Middle-click drag to pan \u00b7 "
                    "Box zoom: drag \u2198 to zoom in, drag \u2196 to zoom out \u00b7 "
                    "Double-click to fit")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
