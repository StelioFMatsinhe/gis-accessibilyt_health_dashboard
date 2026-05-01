from flask import Flask, render_template, request
import geopandas as gpd
import folium

app = Flask(__name__)


# -------------------------
# POPUP HOSPITAL
# -------------------------
def popup_hospital(row):
    html = "<div style='font-size:13px'>"
    for col in row.index:
        if col != "geometry":
            html += f"<b>{col}:</b> {row[col]}<br>"
    html += "</div>"
    return html


# -------------------------
# CALCULAR POPULAÇÃO
# -------------------------
def calcular_pop(buffer_geom, populacao, pop_index, pop_col):

    possible = list(pop_index.intersection(buffer_geom.bounds))

    if not possible:
        return 0

    subset = populacao.iloc[possible]
    subset = subset[subset.intersects(buffer_geom)]

    if subset.empty or pop_col not in subset.columns:
        return 0

    return subset[pop_col].sum()


# -------------------------
# APP
# -------------------------
@app.route("/")
def index():

    buffer_dist = request.args.get("buffer", 2000, type=int)

    # -------------------------
    # 1. DADOS
    # -------------------------
    hospitais = gpd.read_file("dados/hospitais.shp")
    populacao = gpd.read_file("dados/PopMaputoCidade.shp")
    estradas = gpd.read_file("dados/estradas.shp")

    crs = 32736

    hospitais = hospitais.to_crs(crs)
    populacao = populacao.to_crs(crs)
    estradas = estradas.to_crs(crs)

    pop_col = next((c for c in populacao.columns if "pop" in c.lower()), None)
    pop_index = populacao.sindex

    # -------------------------
    # 2. VARIÁVEIS GLOBAIS
    # -------------------------
    buffer_geoms = []
    pop_coberta_total = 0

    hospitais_4326 = hospitais.to_crs(4326)

    fg_hosp = folium.FeatureGroup(name="Hospitais", show=True)
    fg_buffer = folium.FeatureGroup(name="Cobertura", show=True)

    # -------------------------
    # 3. BUFFERS + POPULAÇÃO
    # -------------------------
    for i, h in hospitais.iterrows():

        buffer_geom = h.geometry.buffer(buffer_dist)

        if not buffer_geom.is_valid:
            continue

        pop_val = calcular_pop(buffer_geom, populacao, pop_index, pop_col)
        pop_coberta_total += pop_val

        buffer_geoms.append(buffer_geom)

        h_wgs = hospitais_4326.iloc[i]

        popup = f"""
        <div style="width:250px">
            <b>Hospital</b><br>
            {popup_hospital(h_wgs)}
            <hr>
            <b>População abrangida:</b> {int(pop_val)}
        </div>
        """

        folium.Marker(
            location=[h_wgs.geometry.y, h_wgs.geometry.x],
            popup=popup,
            icon=folium.Icon(color="red")
        ).add_to(fg_hosp)

    buffer_gdf = gpd.GeoDataFrame(geometry=buffer_geoms, crs=crs)

    # -------------------------
    # 4. POPULAÇÃO NÃO ABRANGIDA
    # -------------------------
    try:
        pop_nao_coberta = gpd.overlay(populacao, buffer_gdf, how="difference")
    except:
        pop_nao_coberta = populacao.copy()

    pop_nao_coberta_total = pop_nao_coberta[pop_col].sum()

    # -------------------------
    # 5. ÁREAS PRIORITÁRIAS
    # -------------------------
    areas_prioritarias = pop_nao_coberta.copy()

    if "densidade" in areas_prioritarias.columns:
        areas_prioritarias = areas_prioritarias[areas_prioritarias["densidade"] > 1000]

    # -------------------------
    # 6. MAPA
    # -------------------------
    m = folium.Map(location=[-25.96, 32.58], zoom_start=12)
    
    folium.TileLayer("OpenStreetMap").add_to(m)
    folium.TileLayer("CartoDB positron").add_to(m)
    folium.TileLayer("CartoDB dark_matter").add_to(m)

    fg_pop = folium.FeatureGroup(name="População", show=False)
    fg_gap = folium.FeatureGroup(name="População NÃO Abrangida", show=True)
    fg_prior = folium.FeatureGroup(name="Áreas Prioritárias", show=True)

    # buffers
    folium.GeoJson(
        buffer_gdf.to_crs(4326).to_json(),
        style_function=lambda x: {
            "fillColor": "#22c55e",
            "color": "#16a34a",
            "fillOpacity": 0.3
        }
    ).add_to(fg_buffer)

    # população não coberta
    folium.GeoJson(
        pop_nao_coberta.to_crs(4326).to_json(),
        style_function=lambda x: {
            "fillColor": "#ef4444",
            "color": "#b91c1c",
            "fillOpacity": 0.6
        }
    ).add_to(fg_gap)

    # áreas prioritárias
    folium.GeoJson(
        areas_prioritarias.to_crs(4326).to_json(),
        style_function=lambda x: {
            "fillColor": "#f59e0b",
            "color": "#b45309",
            "fillOpacity": 0.7
        }
    ).add_to(fg_prior)

    # hospitais
    fg_hosp.add_to(m)
    fg_buffer.add_to(m)
    fg_gap.add_to(m)
    fg_prior.add_to(m)

    folium.LayerControl().add_to(m)

    # -------------------------
    # OUTPUT
    # -------------------------
    return render_template(
        "dashboard.html",
        mapa=m._repr_html_(),
        buffer=buffer_dist,
        pop_coberta=int(pop_coberta_total),
        pop_nao_coberta=int(pop_nao_coberta_total)
    )


if __name__ == "__main__":
    app.run(debug=True)