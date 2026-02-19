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
    """Parse a KLayout .lyp XML file.
    Returns {layer_number: hex_color} for visible layers only."""
    layer_colors = {}
    try:
        root = ET.fromstring(lyp_bytes)
        for props in root.findall(".//properties"):
            if props.findtext("visible", "true").strip().lower() == "false":
                continue
            source = props.findtext("source", "").strip()
            color  = props.findtext("fill-color", "").strip()
            if not source or not color:
                continue
            try:
                layer = int(source.split("/")[0])
                layer_colors[layer] = color
            except (ValueError, IndexError):
                continue
    except ET.ParseError:
        pass
    return layer_colors


def _build_canvas_data(top_cells, layer_colors=None):
    """Collect polygon data as compact JSON for the Canvas renderer.

    Returns (layers_json_str, vb_x, vb_y, vb_w, vb_h) or
            (None, ...) when no geometry is found.

    layers_json is a list of layer entries:
        [fill, stroke, ptype, polys, bounds]
    where polys[i] = [x0,y0,x1,y1,...] (flat, 2 dp)
    and   bounds[i] = [minX,minY,maxX,maxY] (for viewport culling).
    """
    layer_polys = defaultdict(list)
    all_x, all_y = [], []

    for cell in top_cells:
        for poly in cell.get_polygons():
            pts = poly.points
            if len(pts) < 3:
                continue
            xs = pts[:, 0]
            ys = -pts[:, 1]          # flip Y: GDS y-up → canvas y-down
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

    layers_data = []
    for i, layer in enumerate(sorted(layer_polys)):
        style        = _LAYER_STYLES[i % len(_LAYER_STYLES)]
        fill_color   = (layer_colors or {}).get(layer, style[0])
        stroke_color = style[1]
        ptype        = style[2]

        polys  = []
        bounds = []
        for (flat, bx0, by0, bx1, by1) in layer_polys[layer]:
            polys.append(flat)
            bounds.append([round(bx0, 2), round(by0, 2),
                           round(bx1, 2), round(by1, 2)])

        layers_data.append([fill_color, stroke_color, ptype, polys, bounds])

    return json.dumps(layers_data, separators=(',', ':')), vb_x, vb_y, vb_w, vb_h


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

                layer_colors = _parse_lyp(uploaded_lyp.read()) if uploaded_lyp else None

                layers_json, vb_x, vb_y, vb_w, vb_h = _build_canvas_data(
                    top_cells, layer_colors)
                if layers_json is None:
                    st.error("No geometry found in GDS file.")
                    return

                unit = _unit_label(lib.unit)

                # ------------------------------------------------------------------
                # HTML: Canvas-based viewer modelled after KLayout's rendering loop.
                #
                # Key design decisions (why it's fast):
                #  1. <canvas> immediate-mode — no DOM node per polygon, no retained
                #     scene graph, no SVG pattern recomputation on every pan/zoom.
                #  2. Viewport culling — each polygon's pre-computed AABB is tested
                #     against the world-space viewport; off-screen polys are skipped.
                #  3. Constant-pixel hatch tiles — CanvasPattern tiles are 14 px
                #     offscreen canvases; they never rescale with zoom.
                #  4. Simple state: (sc, tx, ty). Pan = tx/ty +=, zoom = sc *= factor.
                #     No DOM attribute writes, no layout invalidation.
                # ------------------------------------------------------------------
                html = f"""<!DOCTYPE html>
<html><head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#d4d0c8;overflow:hidden;
     font-family:"MS Sans Serif",Arial,sans-serif;font-size:11px}}

#toolbar{{
  background:#d4d0c8;border-bottom:1px solid #808080;
  padding:4px 6px;display:flex;gap:4px;align-items:center;user-select:none;
}}
.btn{{
  background:#d4d0c8;color:#000;
  font:11px "MS Sans Serif",Arial,sans-serif;
  padding:3px 10px;cursor:pointer;
  border-top:2px solid #dfdfdf;border-left:2px solid #dfdfdf;
  border-bottom:2px solid #404040;border-right:2px solid #404040;
  outline:1px solid #000;white-space:nowrap;min-width:72px;text-align:center;
}}
.btn:active,.btn.on{{
  border-top:2px solid #404040;border-left:2px solid #404040;
  border-bottom:2px solid #dfdfdf;border-right:2px solid #dfdfdf;
  padding:4px 9px 2px 11px;
}}
.btn:focus{{outline:1px dotted #000;outline-offset:-4px}}
.sep{{width:1px;height:20px;background:#808080;border-right:1px solid #fff;margin:0 2px}}

#wrap{{
  position:relative;width:100%;height:600px;
  background:#1e1e2e;overflow:hidden;cursor:crosshair;
}}
canvas{{display:block;}}

#selbox{{
  position:absolute;display:none;pointer-events:none;
  border:1px dashed #fff;background:rgba(100,160,255,.12);
}}
#ruler{{
  position:absolute;bottom:16px;left:16px;z-index:10;
  color:#e0e0e0;font:11px/1.4 monospace;pointer-events:none;
}}
#rbar{{height:3px;background:#e0e0e0;border-radius:1px;margin-bottom:4px}}
#rlabel{{text-align:center;text-shadow:0 0 4px #000}}
</style></head><body>

<div id="toolbar">
  <button class="btn on" id="bPan"  title="Pan – drag to move">&#128336; Pan</button>
  <button class="btn"    id="bBox"  title="Box Zoom – drag rectangle">&#9974; Box Zoom</button>
  <div class="sep"></div>
  <button class="btn"    id="bReset" title="Fit layout (double-click also works)">&#8635; Reset</button>
</div>

<div id="wrap">
  <canvas id="cv"></canvas>
  <div id="selbox"></div>
  <div id="ruler"><div id="rbar"></div><div id="rlabel"></div></div>
</div>

<script>
// ── Data from Python ─────────────────────────────────────────────────────
const LAYERS = {layers_json};
const UNIT   = "{unit}";
const GX={vb_x:.6f}, GY={vb_y:.6f}, GW={vb_w:.6f}, GH={vb_h:.6f};
const PSIZE  = 14;   // hatch tile size in screen pixels (constant)

// ── Canvas setup ─────────────────────────────────────────────────────────
const wrap = document.getElementById('wrap');
const cv   = document.getElementById('cv');
const sel  = document.getElementById('selbox');
const ctx  = cv.getContext('2d');

function resizeCanvas(){{
  cv.width  = wrap.offsetWidth;
  cv.height = wrap.offsetHeight;
}}

// ── Build hatch CanvasPatterns (offscreen canvas, fixed px size) ──────────
// Patterns are constant-pixel-size regardless of zoom: no recomputation needed.
function buildPattern(fill, stroke, ptype){{
  const oc = document.createElement('canvas');
  oc.width = oc.height = PSIZE;
  const p = oc.getContext('2d');
  const s = PSIZE, h = s / 2, lw = Math.max(1, s * 0.11);

  // semi-transparent fill background
  p.fillStyle = fill;
  p.globalAlpha = 0.50;
  p.fillRect(0, 0, s, s);
  p.globalAlpha = 0.85;

  p.strokeStyle = stroke;
  p.lineWidth   = lw;
  p.lineCap     = 'butt';

  if (ptype === 'dots') {{
    p.fillStyle = stroke;
    p.beginPath();
    p.arc(h, h, s * 0.15, 0, Math.PI * 2);
    p.fill();
  }} else {{
    p.beginPath();
    switch (ptype) {{
      case 'hlines':  p.moveTo(0,h);  p.lineTo(s,h); break;
      case 'vlines':  p.moveTo(h,0);  p.lineTo(h,s); break;
      case 'diag45':  p.moveTo(0,0);  p.lineTo(s,s); break;
      case 'diag135': p.moveTo(s,0);  p.lineTo(0,s); break;
      case 'cross':
        p.moveTo(0,h); p.lineTo(s,h);
        p.moveTo(h,0); p.lineTo(h,s); break;
      case 'xcross':
        p.moveTo(0,0); p.lineTo(s,s);
        p.moveTo(s,0); p.lineTo(0,s); break;
    }}
    p.stroke();
  }}
  return ctx.createPattern(oc, 'repeat');
}}

const patterns = LAYERS.map(([fill, stroke, ptype]) => buildPattern(fill, stroke, ptype));

// ── View state ────────────────────────────────────────────────────────────
// sc  = pixels per GDS unit
// tx  = screen x of GDS origin
// ty  = screen y of GDS origin
let sc, tx, ty, iSc, iTx, iTy;

function fitView(){{
  const W = cv.width, H = cv.height;
  sc = Math.min(W / GW, H / GH) * 0.97;
  tx = (W - GW * sc) / 2 - GX * sc;
  ty = (H - GH * sc) / 2 - GY * sc;
  iSc = sc; iTx = tx; iTy = ty;
}}

// ── Ruler ─────────────────────────────────────────────────────────────────
function niceNum(x){{
  const m = Math.pow(10, Math.floor(Math.log10(x))), f = x / m;
  return f < 1.5 ? m : f < 3.5 ? 2*m : f < 7.5 ? 5*m : 10*m;
}}
function updateRuler(){{
  const gpx = 1 / sc, gl = niceNum(gpx * 120), bp = gl * sc;
  document.getElementById('rbar').style.width = bp + 'px';
  document.getElementById('rlabel').textContent =
    (gl % 1 === 0 ? gl : gl.toPrecision(3)) + ' ' + UNIT;
}}

// ── Render loop ───────────────────────────────────────────────────────────
// KLayout-style: clear canvas, iterate layers → polygons, cull off-screen,
// draw screen-space paths with constant-pixel hatch pattern fill.
function render(){{
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);

  // World bounds of the current viewport (for AABB culling)
  const wxMin = -tx / sc,       wyMin = -ty / sc;
  const wxMax = (W - tx) / sc,  wyMax = (H - ty) / sc;

  for (let li = 0; li < LAYERS.length; li++) {{
    const [fill, stroke, ptype, polys, bounds] = LAYERS[li];
    const pat = patterns[li];

    // Anchor pattern to world origin so it stays fixed during pan/zoom
    // (tx%PSIZE keeps translation in [0,PSIZE) without affecting repeat phase)
    pat.setTransform(new DOMMatrix([1,0,0,1, tx % PSIZE, ty % PSIZE]));
    ctx.fillStyle = pat;

    for (let pi = 0; pi < polys.length; pi++) {{
      // Viewport cull — cheap AABB test using pre-computed bounding boxes
      const [bx0, by0, bx1, by1] = bounds[pi];
      if (bx1 < wxMin || bx0 > wxMax || by1 < wyMin || by0 > wyMax) continue;

      // Draw polygon in screen space
      const poly = polys[pi];
      ctx.beginPath();
      ctx.moveTo(poly[0] * sc + tx, poly[1] * sc + ty);
      for (let k = 2; k < poly.length; k += 2)
        ctx.lineTo(poly[k] * sc + tx, poly[k+1] * sc + ty);
      ctx.closePath();
      ctx.fill();
    }}
  }}
  updateRuler();
}}

// ── Init: wait for layout, then fit & render ─────────────────────────────
function init(){{
  if (!wrap.offsetWidth) {{ requestAnimationFrame(init); return; }}
  resizeCanvas();
  fitView();
  render();
}}
requestAnimationFrame(init);

// ── Mode ─────────────────────────────────────────────────────────────────
let mode = 'pan';
function setMode(m){{
  mode = m;
  ['bPan','bBox'].forEach(id => document.getElementById(id).classList.remove('on'));
  document.getElementById(m === 'pan' ? 'bPan' : 'bBox').classList.add('on');
}}
document.getElementById('bPan').addEventListener('click', () => setMode('pan'));
document.getElementById('bBox').addEventListener('click', () => setMode('zoombox'));
document.getElementById('bReset').addEventListener('click', () => {{
  sc=iSc; tx=iTx; ty=iTy; render();
}});

// ── Scroll-wheel zoom toward cursor ───────────────────────────────────────
wrap.addEventListener('wheel', e => {{
  e.preventDefault();
  const r  = wrap.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  const d  = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  tx = (tx - mx) * d + mx;
  ty = (ty - my) * d + my;
  sc *= d;
  render();
}}, {{passive: false}});

// ── Mouse drag ────────────────────────────────────────────────────────────
let drag = false, dsx, dsy, dtx, dty, bx0, by0;

wrap.addEventListener('mousedown', e => {{
  if (e.button !== 0 && e.button !== 1) return;
  e.preventDefault();
  drag = true;
  dsx = e.clientX; dsy = e.clientY; dtx = tx; dty = ty;
  const r = wrap.getBoundingClientRect();
  bx0 = e.clientX - r.left; by0 = e.clientY - r.top;
  if (mode === 'zoombox')
    sel.style.cssText = `left:${{bx0}}px;top:${{by0}}px;width:0;height:0;display:block`;
}});

window.addEventListener('mousemove', e => {{
  if (!drag) return;
  if (mode === 'pan') {{
    tx = dtx + (e.clientX - dsx);
    ty = dty + (e.clientY - dsy);
    render();
  }} else {{
    const r  = wrap.getBoundingClientRect();
    const cx = Math.max(0, Math.min(r.width,  e.clientX - r.left));
    const cy = Math.max(0, Math.min(r.height, e.clientY - r.top));
    sel.style.left   = Math.min(bx0, cx) + 'px';
    sel.style.top    = Math.min(by0, cy) + 'px';
    sel.style.width  = Math.abs(cx - bx0) + 'px';
    sel.style.height = Math.abs(cy - by0) + 'px';
  }}
}});

window.addEventListener('mouseup', e => {{
  if (!drag) return;
  drag = false;
  if (mode === 'zoombox') {{
    sel.style.display = 'none';
    const r  = wrap.getBoundingClientRect();
    const cx = Math.max(0, Math.min(r.width,  e.clientX - r.left));
    const cy = Math.max(0, Math.min(r.height, e.clientY - r.top));
    let nx0 = Math.min(bx0, cx), ny0 = Math.min(by0, cy);
    let nw  = Math.abs(cx - bx0), nh  = Math.abs(cy - by0);
    if (nw < 6 || nh < 6) return;

    // Aspect-ratio correct the selection box
    const cAR = cv.width / cv.height, sAR = nw / nh;
    if (sAR > cAR) {{ const n = nw / cAR; ny0 -= (n - nh) / 2; nh = n; }}
    else           {{ const n = nh * cAR; nx0 -= (n - nw) / 2; nw = n; }}

    // Zoom: map selection rectangle to full viewport
    const wx0 = (nx0 - tx) / sc, wy0 = (ny0 - ty) / sc;
    sc = sc * cv.width / nw;
    tx = -wx0 * sc;
    ty = -wy0 * sc;
    render();
  }}
}});

wrap.addEventListener('dblclick', () => {{ sc=iSc; tx=iTx; ty=iTy; render(); }});
</script></body></html>"""

                components.html(html, height=645)
                st.caption("Scroll to zoom · Drag to pan/box-zoom · Double-click to reset")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
