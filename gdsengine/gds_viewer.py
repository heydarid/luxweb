import streamlit as st
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
import streamlit.components.v1 as components

_LAYER_COLORS = [
    "#4e9af1", "#f14e4e", "#4ef18a", "#f1c44e", "#ae4ef1",
    "#4ef1e8", "#f18a4e", "#8af14e", "#f14eae", "#e8f14e",
    "#f14e8a", "#4e8af1",
]

def _unit_label(lib_unit):
    if abs(lib_unit - 1e-6) < 1e-9:  return "µm"
    if abs(lib_unit - 1e-9) < 1e-12: return "nm"
    if abs(lib_unit - 1e-3) < 1e-6:  return "mm"
    return "u"

def _parse_lyp(lyp_bytes):
    """Parse a KLayout .lyp XML file.
    Returns {layer_number: hex_color} for visible layers only.
    source format: 'layer/datatype@cellview'  e.g. '1/0@1'
    """
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

def _build_svg(top_cells, layer_colors=None):
    """Returns (svg_str, vb_x, vb_y, vb_w, vb_h).
    layer_colors: optional {layer_number: hex_color} from a .lyp file.
    Falls back to _LAYER_COLORS palette for unmapped layers."""
    layer_paths = defaultdict(list)
    all_x, all_y = [], []

    for cell in top_cells:
        for poly in cell.get_polygons():
            pts = poly.points
            if len(pts) < 2:
                continue
            xs = pts[:, 0]
            ys = -pts[:, 1]   # flip Y: GDS y-up → SVG y-down
            all_x.extend(xs)
            all_y.extend(ys)
            coords = " L".join(f"{x:.3f},{y:.3f}" for x, y in zip(xs, ys))
            layer_paths[poly.layer].append(f"M{coords}Z")

    if not all_x:
        return None, 0, 0, 1, 1

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    pad = max(max_x - min_x, max_y - min_y) * 0.02 or 1
    vb_x = min_x - pad
    vb_y = min_y - pad
    vb_w = max_x - min_x + 2 * pad
    vb_h = max_y - min_y + 2 * pad

    paths_html = ""
    for i, layer in enumerate(sorted(layer_paths)):
        if layer_colors and layer in layer_colors:
            color = layer_colors[layer]
        else:
            color = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        d = " ".join(layer_paths[layer])
        paths_html += (
            f'<path d="{d}" fill="{color}" fill-opacity="0.75" stroke="none"/>\n'
        )

    # preserveAspectRatio="none" — SVG fills container; viewBox manipulation
    # keeps proportions because we always scale vw/vh by the same factor.
    svg = (
        f'<svg id="gds" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb_x:.3f} {vb_y:.3f} {vb_w:.3f} {vb_h:.3f}" '
        f'preserveAspectRatio="none" '
        f'style="width:100%;height:100%;display:block">'
        f'{paths_html}</svg>'
    )
    return svg, vb_x, vb_y, vb_w, vb_h


def show_interactive_viewer():
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
                lib = gdstk.read_gds(gds_path)
                top_cells = lib.top_level()
                if not top_cells:
                    st.error("No top-level cell found in GDS file.")
                    return

                svg, vb_x, vb_y, vb_w, vb_h = _build_svg(top_cells)
                if not svg:
                    st.error("No geometry found in GDS file.")
                    return

                unit = _unit_label(lib.unit)

                html = f"""<!DOCTYPE html>
<html><head><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#d4d0c8;overflow:hidden;font-family:"MS Sans Serif",Arial,sans-serif;font-size:11px}}

  /* ── Windows 98 toolbar ── */
  #toolbar{{
    background:#d4d0c8;
    border-bottom:1px solid #808080;
    padding:4px 6px;
    display:flex;gap:4px;align-items:center;
    user-select:none;
  }}
  .btn{{
    background:#d4d0c8;color:#000;
    font:11px "MS Sans Serif",Arial,sans-serif;
    padding:3px 10px;cursor:pointer;
    border-top:2px solid #dfdfdf;border-left:2px solid #dfdfdf;
    border-bottom:2px solid #404040;border-right:2px solid #404040;
    outline:1px solid #000;
    white-space:nowrap;min-width:72px;text-align:center;
  }}
  .btn:active,.btn.on{{
    border-top:2px solid #404040;border-left:2px solid #404040;
    border-bottom:2px solid #dfdfdf;border-right:2px solid #dfdfdf;
    padding:4px 9px 2px 11px;
  }}
  .btn:focus{{outline:1px dotted #000;outline-offset:-4px}}
  .sep{{width:1px;height:20px;background:#808080;border-right:1px solid #fff;margin:0 2px}}

  /* ── Viewer canvas ── */
  #c{{
    width:100%;height:600px;overflow:hidden;
    cursor:crosshair;position:relative;background:#1e1e2e;
  }}

  /* ── Box-zoom selection rectangle ── */
  #selbox{{
    position:absolute;display:none;pointer-events:none;
    border:1px dashed #fff;background:rgba(100,160,255,.12);
  }}

  /* ── Ruler ── */
  #ruler{{
    position:absolute;bottom:16px;left:16px;z-index:10;
    color:#e0e0e0;font:11px/1.4 monospace;pointer-events:none;
  }}
  #rbar{{height:3px;background:#e0e0e0;border-radius:1px;margin-bottom:4px}}
  #rlabel{{text-align:center;text-shadow:0 0 4px #000}}
</style></head><body>

<div id="toolbar">
  <button class="btn on" id="bPan"  title="Pan – drag to move">&#128336; Pan</button>
  <button class="btn"    id="bBox"  title="Box Zoom – drag to select area">&#9974; Box Zoom</button>
  <div class="sep"></div>
  <button class="btn"    id="bReset" title="Fit whole layout (double-click also works)">&#8635; Reset</button>
</div>

<div id="c">
  {svg}
  <div id="selbox"></div>
  <div id="ruler"><div id="rbar"></div><div id="rlabel"></div></div>
</div>

<script>
  const c   = document.getElementById('c');
  const gds = document.getElementById('gds');
  const sel = document.getElementById('selbox');

  let mode = 'pan';   // 'pan' | 'zoombox'
  let vx={vb_x:.6f}, vy={vb_y:.6f}, vw={vb_w:.6f}, vh={vb_h:.6f};
  const UNIT = "{unit}";

  // ── Aspect-ratio correction on init ──────────────────────────────────────
  (function(){{
    const cw=c.offsetWidth||800, ch=c.offsetHeight||600;
    const cAR=cw/ch, gAR=vw/vh;
    if(gAR>cAR){{ const n=vw/cAR; vy-=(n-vh)/2; vh=n; }}
    else        {{ const n=vh*cAR; vx-=(n-vw)/2; vw=n; }}
  }})();
  const initVx=vx, initVy=vy, initVw=vw, initVh=vh;

  // ── Helpers ───────────────────────────────────────────────────────────────
  function niceNum(x){{
    const m=Math.pow(10,Math.floor(Math.log10(x))), f=x/m;
    return f<1.5?m : f<3.5?2*m : f<7.5?5*m : 10*m;
  }}
  function updateRuler(){{
    const gpx=vw/c.offsetWidth, gl=niceNum(gpx*120), bp=gl/gpx;
    document.getElementById('rbar').style.width=bp+'px';
    document.getElementById('rlabel').textContent=(gl%1===0?gl:gl.toPrecision(3))+' '+UNIT;
  }}
  function apply(){{
    gds.setAttribute('viewBox',`${{vx}} ${{vy}} ${{vw}} ${{vh}}`);
    updateRuler();
  }}
  function setMode(m){{
    mode=m;
    ['bPan','bBox'].forEach(id=>document.getElementById(id).classList.remove('on'));
    document.getElementById(m==='pan'?'bPan':'bBox').classList.add('on');
    c.style.cursor = m==='pan' ? 'crosshair' : 'crosshair';
  }}

  // ── Toolbar buttons ───────────────────────────────────────────────────────
  document.getElementById('bPan').addEventListener('click',()=>setMode('pan'));
  document.getElementById('bBox').addEventListener('click',()=>setMode('zoombox'));
  document.getElementById('bReset').addEventListener('click',()=>{{
    vx=initVx;vy=initVy;vw=initVw;vh=initVh;apply();
  }});

  // ── Scroll wheel → zoom toward cursor (works in both modes) ──────────────
  c.addEventListener('wheel',e=>{{
    e.preventDefault();
    const r=c.getBoundingClientRect();
    const mx=(e.clientX-r.left)/r.width, my=(e.clientY-r.top)/r.height;
    const d=e.deltaY<0?1/1.15:1.15;
    const nvw=vw*d, nvh=vh*d;
    vx+=mx*(vw-nvw); vy+=my*(vh-nvh); vw=nvw; vh=nvh;
    apply();
  }},{{passive:false}});

  // ── Mouse drag: pan or box-zoom ───────────────────────────────────────────
  let dragging=false, sx, sy, svx, svy, bx0, by0;

  c.addEventListener('mousedown',e=>{{
    if(e.button!==0 && e.button!==1) return;
    e.preventDefault();
    dragging=true;
    sx=e.clientX; sy=e.clientY; svx=vx; svy=vy;
    const r=c.getBoundingClientRect();
    bx0=e.clientX-r.left; by0=e.clientY-r.top;
    if(mode==='zoombox'){{
      sel.style.cssText=`left:${{bx0}}px;top:${{by0}}px;width:0;height:0;display:block`;
    }}
  }});

  window.addEventListener('mousemove',e=>{{
    if(!dragging) return;
    const r=c.getBoundingClientRect();
    if(mode==='pan'){{
      vx=svx-(e.clientX-sx)/r.width *vw;
      vy=svy-(e.clientY-sy)/r.height*vh;
      apply();
    }} else {{
      const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
      const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
      sel.style.left  =Math.min(bx0,cx)+'px';
      sel.style.top   =Math.min(by0,cy)+'px';
      sel.style.width =Math.abs(cx-bx0)+'px';
      sel.style.height=Math.abs(cy-by0)+'px';
    }}
  }});

  window.addEventListener('mouseup',e=>{{
    if(!dragging) return;
    dragging=false;
    if(mode==='zoombox'){{
      sel.style.display='none';
      const r=c.getBoundingClientRect();
      const cx=Math.max(0,Math.min(r.width, e.clientX-r.left));
      const cy=Math.max(0,Math.min(r.height,e.clientY-r.top));
      const pw=Math.abs(cx-bx0), ph=Math.abs(cy-by0);
      if(pw>6 && ph>6){{
        const x0=Math.min(bx0,cx)/r.width,  x1=Math.max(bx0,cx)/r.width;
        const y0=Math.min(by0,cy)/r.height, y1=Math.max(by0,cy)/r.height;
        let nvx=vx+x0*vw, nvy=vy+y0*vh, nvw=(x1-x0)*vw, nvh=(y1-y0)*vh;
        // expand shorter side to match container aspect ratio
        const cAR=r.width/r.height, sAR=nvw/nvh;
        if(sAR>cAR){{ const n=nvw/cAR; nvy-=(n-nvh)/2; nvh=n; }}
        else        {{ const n=nvh*cAR; nvx-=(n-nvw)/2; nvw=n; }}
        vx=nvx;vy=nvy;vw=nvw;vh=nvh;
        apply();
      }}
    }}
  }});

  // ── Double-click → reset ──────────────────────────────────────────────────
  c.addEventListener('dblclick',()=>{{vx=initVx;vy=initVy;vw=initVw;vh=initVh;apply();}});

  apply();
</script></body></html>"""

                components.html(html, height=645)
                st.caption("Scroll to zoom · Drag to pan/box-zoom · Double-click to reset")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
