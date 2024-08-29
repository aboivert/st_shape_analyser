import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point, Polygon
from streamlit_folium import st_folium
import numpy as np

st.set_page_config(
    page_title="shapes.txt analyser",
    page_icon=":bar_chart:",
    layout="wide"
)

st.subheader("Analyseur de fichier **shapes.txt**")
st.caption("Cet outil permet d'analyser les fichiers **shapes.txt**, notamment de vérifier si les tracés de circulation sont bons (passent bien sur les routes, pas de ligne droite à traver un immeuble, etc...).")

def plot_shape(data_to_plot, number_comp):
    points = []
    for index, row in data_to_plot.iterrows():
        points.append(tuple([row.shape_pt_lat, row.shape_pt_lon]))
    m = folium.Map([sum(p[0] for p in points)/len(points), sum(p[1] for p in points)/len(points)], zoom_start=14)
    for p in points:  
        folium.Circle(p, radius=3, color="red").add_to(m)
    folium.PolyLine(points, color="blue", weight=2.5, opacity=1).add_to(m)
    st_folium(m, width=700, height=500, key = number_comp)

def distance_analysis(data, distance, data_to_omit):
    data_reduced = data[~data['shape_id'].isin(data_to_omit)]
    list_shape_id = data_reduced.shape_id.unique()
    data_dist = pd.DataFrame(columns=['shape_id','distance_moyenne'])
    for s in list_shape_id:
        data_temp = data_reduced[data_reduced.shape_id == s]
        dist_moy = data_temp.shape_dist_traveled.max()/data_temp.shape[0]
        data_dist = data_dist._append({'shape_id':s,'distance_moyenne':dist_moy},ignore_index=True)
    shape_id_with_higher_mean_dist = data_dist[data_dist.distance_moyenne > distance]
    return shape_id_with_higher_mean_dist, data_dist

def compute_distance(lat1, lon1, lat2, lon2):
    earth_radius = 6371e3
    phi_point = lat1 * np.pi/180
    phi_area = lat2 * np.pi/180
    delta_phi = (lat2 - lat1) * np.pi/180
    delta_lambda = (lon2 - lon1) * np.pi/180
    a = np.sin(delta_phi/2) * np.sin(delta_phi/2) + np.cos(phi_point) * np.cos(phi_area) * np.sin(delta_lambda/2) * np.sin(delta_lambda/2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return earth_radius*c

def compute_shape_dist_traveled(data):
    data_sdt = data.copy(deep=True)
    data_sdt = data_sdt.sort_values(by=['shape_id', 'shape_pt_sequence'])
    data_sdt['shape_dist_traveled'] = 0.0
    for shape_id, group in data_sdt.groupby('shape_id'):
        cumulative_distance = 0.0
        previous_point = None
        for index, row in group.iterrows():
            if previous_point is not None:
                dist = compute_distance(previous_point['shape_pt_lat'], previous_point['shape_pt_lon'],row['shape_pt_lat'], row['shape_pt_lon'])
                cumulative_distance += dist
                data_sdt.at[index, 'shape_dist_traveled'] = cumulative_distance
            previous_point = row
    return data_sdt

uploaded_shapes = st.file_uploader("Choisir un fichier **shapes.txt**")
#uploaded_shapes = r"C:\Users\aboivert\OneDrive - Keolis\Bureau\shapes.txt"
if uploaded_shapes is not None:
    data = pd.read_csv(uploaded_shapes)
    with st.expander("Afficher un tracé"):
        selected_shape_id = st.selectbox("Choisir un tracé à afficher", data.shape_id.unique())
        data_to_plot = data[data.shape_id == selected_shape_id]
        plot_shape(data_to_plot, 0)
    with st.expander ("Afficher plusieurs tracés"):
        data_plus = data.copy(deep=True)
        data_plus['shape_id_str'] = data_plus['shape_id'].astype(str)
        with st.popover("Pourquoi ?"):
            st.markdown('''Permet d'entrer la liste récupérée directement dans les audits pour vérifier directement tous les tracés remontés.''')
        st.warning("Veuillez entrer une liste au format suivant: id_1 id_2 .... Les *shape_id* doivent être séparés d'un espace.")
        list_shape_id = st.text_input('Entrer la liste des *shape_id* correspondant aux tracés à vérifier.')
        valid_list = st.toggle("Valider la liste", False)
        if valid_list: #a reprendre
            if list_shape_id is not None:
                for s in list(list_shape_id.split(" ")):
                    data_to_plot = data_plus[data_plus.shape_id_str == s]
                    st.write("Tracé correspondant à la *shape_id* " + s)# + "     (key_comp:" + str(s) + ")") #debug, do not uncomment
                    plot_shape(data_to_plot, s)
    with st.expander("Afficher tous les tracés"):
        st.warning("Attention, peut générer une surcharge de la page.", icon="⚠️")
        print_all = st.checkbox("Afficher tous les tracés", False)
        if print_all:
            for s in data.shape_id.unique():
                data_to_plot = data[data.shape_id == s]
                st.write("Tracé correspondant à la *shape_id* " + str(s))# + "     (key_comp:" + str(s) + ")") #debug, do not uncomment
                plot_shape(data_to_plot, s)
    with st.expander("Analyse par la distance moyenne"):
        #st.warning('Cette fonctionnalité est disponible uniquement si la variable *shape_dist_traveled* est disponible dans le fichier **shapes.txt**.', icon="⚠️")
        data_analyse_dist = data.copy(deep=True)
        if 'shape_dist_traveled' in data.columns:
            if data_analyse_dist.shape_dist_traveled.isnull().all():
                st.warning('La colonne *shape_dist_traveled* est vide. Les distances vont être calculées approximativement, pouvant altérer la qualité du rapport.', icon="⚠️")
                data_analyse_dist = compute_shape_dist_traveled(data_analyse_dist)
            else:
                st.success('*shape_dist_traveled* disponible dans le fichier **shapes.txt**. Analyse par distance possible.', icon="✅")
        else:
            st.warning('La colonne *shape_dist_traveled* est absente du fichier **shapes.txt**. Les distances vont être calculées approximativement, pouvant altérer la qualité du rapport.', icon="⚠️")
            data_analyse_dist = compute_shape_dist_traveled(data_analyse_dist)
        missing_counts = data_analyse_dist['shape_dist_traveled'].isna().groupby(data_analyse_dist['shape_id']).sum()
        total_points = data_analyse_dist.groupby('shape_id').size()
        missing_sdt = pd.DataFrame({'missing_shape_dist_traveled': missing_counts, 'total_points': total_points}).reset_index()
        if missing_sdt[missing_sdt['missing_shape_dist_traveled'] != 0].empty:
            list_shape_id_no_shape_dist = []
        else:
            st.warning("Certaines valeurs de *shape_dist_traveled* ne sont pas définies, la procédure omettra les *shape_id* suivants.", icon="⚠️")
            list_shape_id_no_shape_dist = missing_sdt[missing_sdt['missing_shape_dist_traveled'] != 0]['shape_id'].tolist()
            st.dataframe(missing_sdt[missing_sdt['missing_shape_dist_traveled'] != 0], hide_index=True)
        col1, col2 = st.columns(2)
        with col1:
            with st.popover("Principe"):
                st.markdown('''On calcule pour tous les *shape_id* la distance moyenne parcourue entre chaque point permettant le tracé. Si cette dernière est plus grande que le seuil choisi, les *shape_id* concernés par le problème sont remontés, et il est posible de les afficher.''')
        with col2:
            with st.popover("Choix de l'unité de mesure"):
                st.markdown('''Certains fichiers ont *shape_dist_traveled* en mètres, d'autres en kilomètres. On affiche ici la valeur moyenne basée sur la totalité du fichier. Le choix de l'unité de mesure se fait donc en conséquence.''')
        shape_dist_traveled_mean = data_analyse_dist.shape_dist_traveled.mean()
        st.write("Valeur moyenne de *shape_dist_traveled*: " + str(shape_dist_traveled_mean))
        if shape_dist_traveled_mean > 50:
            st.info("*shape_dist_traveled* est probablement définie en **mètres**.")
            unite_mesure = st.selectbox("Choisir une unité de mesure", ('m','km'))
        else:
            st.info("*shape_dist_traveled* est probablement définie en **kilomètres**.")
            unite_mesure = st.selectbox("Choisir une unité de mesure", ('km','m'))
        if unite_mesure == 'm':
            distance_seuil = st.slider("Distance seuil *(en mètres)*",0,2000,100)
        elif unite_mesure =='km':
            distance_seuil = st.slider("Distance seuil *(en kilomètres)*",0,20,1)
        id_after_analysis, df_distance_moy = distance_analysis(data_analyse_dist,distance_seuil,list_shape_id_no_shape_dist)
        if id_after_analysis.empty:
            st.success("Aucun tracé remonté")
        else:
            st.dataframe(id_after_analysis, hide_index=True)
            plot_analysis_dist = st.checkbox("Afficher les tracés des *shape_id* remontés", False)
            if plot_analysis_dist:
                for s in id_after_analysis.shape_id.unique():
                    data_to_plot = data[data.shape_id == s]
                    st.write("Tracé correspondant à la *shape_id* " + str(s))# + "     (key_comp:" + str(s) + ")") #debug, do not uncomment
                    plot_shape(data_to_plot, s)
        if missing_sdt[missing_sdt['missing_shape_dist_traveled'] != 0].empty:
            st.success("Aucun tracé omis dans l'analyse")
        else:
            plot_analysis_dist = st.checkbox("Afficher les tracés des *shape_id* omis", False)
            if plot_analysis_dist:
                for s in list_shape_id_no_shape_dist:
                    data_to_plot = data[data.shape_id == s]
                    st.write("Tracé correspondant à la *shape_id* " + str(s))# + "     (key_comp:" + str(s) + ")") #debug, do not uncomment
                    plot_shape(data_to_plot, s)
    #with st.expander("Afficher les tracés ayant moins de X points de tracé en moyenne entre 2 arrêts"):
    with st.expander("Futures implémentations"):
        st.markdown(
            """
            A implémenter:
            - Procédure de vérification par les arrêts ?
            - Meilleur texte
            - Voir comment la donner
            - Rejeter mauvais fichier
            - Menu déroulant de tous les fichiers disponibles ? pas possible das le zip, créer une nouvelle option: menu déroulant de choix de réseau, puis avec ça on pointe sur un dossier ou y'a tous les fichiers shapes extraits, pour choisir
            """
            )
else:
    st.error("Veuillez choisir un fichier **shapes.txt**.", icon="🚨")