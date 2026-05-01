import geopandas as gpd
import osmnx as ox
import numpy as np

def carregar_dados():
    hospitais = gpd.read_file("dados/hospitais.shp")
    populacao = gpd.read_file("dados/pop.shp")
    estradas = gpd.read_file("dados/estradas.shp")
    return hospitais, populacao, estradas


def processar_gis():

    hospitais, populacao, estradas = carregar_dados()

    crs = 32736

    hospitais = hospitais.to_crs(crs)
    populacao = populacao.to_crs(crs)
    estradas = estradas.to_crs(crs)

    # 🔥 buffers
    hosp_buffer = hospitais.buffer(2000)
    road_buffer = estradas.buffer(500)

    # 🔥 zonas
    nao_cobertas = gpd.overlay(
        populacao,
        gpd.GeoDataFrame(geometry=hosp_buffer),
        how="difference"
    )

    acessiveis = gpd.overlay(
        nao_cobertas,
        gpd.GeoDataFrame(geometry=road_buffer),
        how="intersection"
    )

    acessiveis.columns = acessiveis.columns.str.strip()

    # 🔥 densidade
    pop_col = next((c for c in acessiveis.columns if "pop" in c.lower()), None)

    if pop_col:
        acessiveis["densidade"] = acessiveis[pop_col] / (acessiveis.geometry.area / 1_000_000)
    else:
        acessiveis["densidade"] = 0

    return hospitais, estradas, acessiveis


def grafo_osm():
    # 🔥 rede real (ArcGIS-level upgrade)
    G = ox.graph_from_place("Maputo, Mozambique", network_type="drive")
    return G