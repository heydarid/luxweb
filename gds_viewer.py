import streamlit as st
import gdstk
import plotly.graph_objects as go
import os

def show_gds_viewer():
    st.header("🔬 GDSII Layout Viewer")
    uploaded_file = st.file_uploader("Upload a .gds file", type=["gds"])

    if uploaded_file:
        # Save temp file because gdstk needs a file path to read
        temp_path = "temp_layout.gds"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            with st.spinner("Processing GDS geometry..."):
                # Load the GDSII file
                library = gdstk.read_gds(temp_path)
                top_cells = library.top_level()
                
                if not top_cells:
                    st.error("No top-level cells found in GDS.")
                    return

                # For simplicity, we take the first top-level cell
                main_cell = top_cells[0]
                fig = go.Figure()

                # Extract and draw polygons
                polygons = main_cell.get_polygons()
                for poly in polygons:
                    # poly is a Nx2 array of (x, y)
                    fig.add_trace(go.Scatter(
                        x=poly[:, 0], 
                        y=poly[:, 1],
                        fill="toself",
                        mode='lines',
                        line=dict(color='royalblue', width=1),
                        hoverinfo='none'
                    ))

                fig.update_layout(
                    yaxis=dict(scaleanchor="x", scaleratio=1),
                    showlegend=False,
                    plot_bgcolor='white',
                    height=600
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error rendering GDS: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path) # Clean up the temp file