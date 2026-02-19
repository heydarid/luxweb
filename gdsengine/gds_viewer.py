import streamlit as st
import os

def show_interactive_viewer():
    st.header("🔗 KLayout-Powered Interactive Viewer")
    uploaded_file = st.file_uploader("Upload GDSII", type=["gds"], key="kweb_uploader")

    if uploaded_file:
        gds_path = "temp_view.gds"
        with open(gds_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            import gdstk
            import plotly.graph_objects as go

            with st.spinner("Rendering layout..."):
                lib = gdstk.read_gds(gds_path)
                top_cells = lib.top_level()
                if not top_cells:
                    st.error("No top-level cell found in GDS file.")
                    return

                fig = go.Figure()
                for cell in top_cells:
                    for polygon in cell.get_polygons():
                        pts = polygon.points
                        xs = list(pts[:, 0]) + [pts[0, 0]]
                        ys = list(pts[:, 1]) + [pts[0, 1]]
                        layer = polygon.layer
                        fig.add_trace(go.Scatter(
                            x=xs, y=ys,
                            fill="toself",
                            mode="lines",
                            name=f"Layer {layer}",
                            legendgroup=f"layer_{layer}",
                            showlegend=True,
                        ))

                fig.update_layout(
                    yaxis=dict(scaleanchor="x", scaleratio=1),
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=600,
                )
                st.plotly_chart(fig, use_container_width=True)
                st.success("Interactive viewer loaded! Drag to pan, scroll to zoom.")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
