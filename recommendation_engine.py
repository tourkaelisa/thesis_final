import rdflib
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import warnings

warnings.filterwarnings('ignore')

def build_laptop_recommendation_model(rdf_graph):
    query = """
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX pto: <http://www.productontology.org/id/>
    PREFIX prop: <http://www.myeshop.gr/property/>

    SELECT ?uri ?name ?price ?brand ?os ?cpu ?color ?releaseDate ?ram ?refresh_rate ?res_height ?res_width ?screen_size ?storage ?weight
    WHERE {
        ?uri a pto:Laptop ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:manufacturer ?brandURI ;
             schema1:operatingSystem ?os ;
             prop:cpu_model ?cpu ;
             schema1:color ?color ;
             schema1:releaseDate ?releaseDate .
             
        BIND(REPLACE(STR(?brandURI), "^.*Brand_", "") AS ?brand)

        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ramNode . FILTER(CONTAINS(STR(?ramNode), "_ram")) ?ramNode gr:hasValueFloat ?ram . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?rrNode . FILTER(CONTAINS(STR(?rrNode), "_refresh_rate")) ?rrNode gr:hasValueFloat ?refresh_rate . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?hNode . FILTER(CONTAINS(STR(?hNode), "_resolution_height")) ?hNode gr:hasValueFloat ?res_height . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wNode . FILTER(CONTAINS(STR(?wNode), "_resolution_width")) ?wNode gr:hasValueFloat ?res_width . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ssNode . FILTER(CONTAINS(STR(?ssNode), "_screen_size")) ?ssNode gr:hasValueFloat ?screen_size . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?stNode . FILTER(CONTAINS(STR(?stNode), "_storage")) ?stNode gr:hasValueFloat ?storage . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wtNode . FILTER(CONTAINS(STR(?wtNode), "_weight")) ?wtNode gr:hasValueFloat ?weight . }
    }
    """
    results = rdf_graph.query(query)

    laptops_data = []
    for row in results:
        laptops_data.append({
            "URI": str(row.uri),
            "Name": str(row.name),
            "Brand": str(row.brand),
            "OS": str(row.os),
            "CPU": str(row.cpu),
            "Color": str(row.color),
            "Release_Date": int(row.releaseDate) if row.releaseDate else 0,
            "Price": float(row.price) if row.price else 0.0,
            "RAM_GB": float(row.ram) if row.ram else 0.0,
            "Storage_GB": float(row.storage) if row.storage else 0.0,
            "Screen_Size_inch": float(row.screen_size) if row.screen_size else 0.0,
            "Refresh_Rate_Hz": float(row.refresh_rate) if row.refresh_rate else 0.0,
            "Res_Height": float(row.res_height) if row.res_height else 0.0,
            "Res_Width": float(row.res_width) if row.res_width else 0.0,
            "Weight_kg": float(row.weight) if row.weight else 0.0
        })

    df_laptops = pd.DataFrame(laptops_data)
    df_laptops.set_index('URI', inplace=True)
    
    laptop_names_dict = df_laptops['Name'].to_dict()
    df_features = df_laptops.drop(columns=['Name'])

    categorical_cols = ['Brand', 'OS', 'CPU', 'Color']
    numerical_cols = ['Release_Date', 'Price', 'RAM_GB', 'Storage_GB', 'Screen_Size_inch', 'Refresh_Rate_Hz', 'Res_Height', 'Res_Width', 'Weight_kg']

    df_categorical = pd.get_dummies(df_features[categorical_cols], dtype=float)
    scaler = MinMaxScaler()
    df_numerical = pd.DataFrame(
        scaler.fit_transform(df_features[numerical_cols]), 
        columns=numerical_cols, 
        index=df_features.index
    )
    df_final = pd.concat([df_numerical, df_categorical], axis=1)

    weights_numerical = {
        'RAM_GB': 3.0, 'Price': 2.5, 'Storage_GB': 2.0, 
        'Screen_Size_inch': 1.5, 'Refresh_Rate_Hz': 1.5, 
        'Res_Height': 1.0, 'Res_Width': 1.0, 
        'Release_Date': 1.0, 'Weight_kg': 0.5
    }

    for col in df_final.columns:
        if col in weights_numerical:
            df_final[col] = df_final[col] * weights_numerical[col]
        elif col.startswith('CPU_'):
            df_final[col] = df_final[col] * 3.0  
        elif col.startswith('OS_'):
            df_final[col] = df_final[col] * 2.0  
        elif col.startswith('Brand_'):
            df_final[col] = df_final[col] * 1.5
        elif col.startswith('Color_'):
            df_final[col] = df_final[col] * 0.2  

    similarity_matrix = cosine_similarity(df_final)
    df_similarity = pd.DataFrame(similarity_matrix, index=df_final.index, columns=df_final.index)

    return df_similarity, laptop_names_dict

def build_mobile_recommendation_model(rdf_graph):
    query = """
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX pto: <http://www.productontology.org/id/>

    SELECT ?uri ?name ?price ?brand ?os ?color ?releaseDate ?battery ?camera_main ?camera_selfie ?refresh_rate ?res_height ?res_width ?screen_size ?storage ?weight
    WHERE {
        ?uri a pto:Smartphone ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:manufacturer ?brandURI ;
             schema1:operatingSystem ?os ;
             schema1:color ?color ;
             schema1:releaseDate ?releaseDate .
             
        BIND(REPLACE(STR(?brandURI), "^.*Brand_", "") AS ?brand)

        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?batNode . FILTER(CONTAINS(STR(?batNode), "_battery")) ?batNode gr:hasValueFloat ?battery . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?cmNode . FILTER(CONTAINS(STR(?cmNode), "_camera_main_mp")) ?cmNode gr:hasValueFloat ?camera_main . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?csNode . FILTER(CONTAINS(STR(?csNode), "_camera_selfie_mp")) ?csNode gr:hasValueFloat ?camera_selfie . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?rrNode . FILTER(CONTAINS(STR(?rrNode), "_refresh_rate")) ?rrNode gr:hasValueFloat ?refresh_rate . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?hNode . FILTER(CONTAINS(STR(?hNode), "_resolution_height")) ?hNode gr:hasValueFloat ?res_height . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wNode . FILTER(CONTAINS(STR(?wNode), "_resolution_width")) ?wNode gr:hasValueFloat ?res_width . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ssNode . FILTER(CONTAINS(STR(?ssNode), "_screen_size")) ?ssNode gr:hasValueFloat ?screen_size . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?stNode . FILTER(CONTAINS(STR(?stNode), "_storage")) ?stNode gr:hasValueFloat ?storage . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wtNode . FILTER(CONTAINS(STR(?wtNode), "_weight")) ?wtNode gr:hasValueFloat ?weight . }
    }
    """
    results = rdf_graph.query(query)

    mobiles_data = []
    for row in results:
        mobiles_data.append({
            "URI": str(row.uri),
            "Name": str(row.name),
            "Brand": str(row.brand),
            "OS": str(row.os),
            "Color": str(row.color),
            "Release_Date": int(row.releaseDate) if row.releaseDate else 0,
            "Price": float(row.price) if row.price else 0.0,
            "Battery_mAh": float(row.battery) if row.battery else 0.0,
            "Camera_Main_MP": float(row.camera_main) if row.camera_main else 0.0,
            "Camera_Selfie_MP": float(row.camera_selfie) if row.camera_selfie else 0.0,
            "Storage_GB": float(row.storage) if row.storage else 0.0,
            "Screen_Size_inch": float(row.screen_size) if row.screen_size else 0.0,
            "Refresh_Rate_Hz": float(row.refresh_rate) if row.refresh_rate else 0.0,
            "Res_Height": float(row.res_height) if row.res_height else 0.0,
            "Res_Width": float(row.res_width) if row.res_width else 0.0,
            "Weight_g": float(row.weight) if row.weight else 0.0
        })

    df_mobiles = pd.DataFrame(mobiles_data)
    df_mobiles.set_index('URI', inplace=True)
    
    mobile_names_dict = df_mobiles['Name'].to_dict()
    df_features = df_mobiles.drop(columns=['Name'])

    categorical_cols = ['Brand', 'OS', 'Color']
    numerical_cols = ['Release_Date', 'Price', 'Battery_mAh', 'Camera_Main_MP', 'Camera_Selfie_MP', 'Storage_GB', 'Screen_Size_inch', 'Refresh_Rate_Hz', 'Res_Height', 'Res_Width', 'Weight_g']

    df_categorical = pd.get_dummies(df_features[categorical_cols], dtype=float)
    scaler = MinMaxScaler()
    df_numerical = pd.DataFrame(
        scaler.fit_transform(df_features[numerical_cols]), 
        columns=numerical_cols, 
        index=df_features.index
    )
    df_final = pd.concat([df_numerical, df_categorical], axis=1)

    weights_numerical = {
        'Battery_mAh': 3.0,     
        'Camera_Main_MP': 3.0,   
        'Price': 2.5,            
        'Storage_GB': 2.5,       
        'Camera_Selfie_MP': 2.0, 
        'Screen_Size_inch': 1.5, 
        'Refresh_Rate_Hz': 1.5, 
        'Res_Height': 1.0, 
        'Res_Width': 1.0, 
        'Release_Date': 1.0, 
        'Weight_g': 0.5
    }

    for col in df_final.columns:
        if col in weights_numerical:
            df_final[col] = df_final[col] * weights_numerical[col]
        elif col.startswith('OS_'):
            df_final[col] = df_final[col] * 2.5 
        elif col.startswith('Brand_'):
            df_final[col] = df_final[col] * 2.0  
        elif col.startswith('Color_'):
            df_final[col] = df_final[col] * 0.2  

    similarity_matrix = cosine_similarity(df_final)
    df_similarity = pd.DataFrame(similarity_matrix, index=df_final.index, columns=df_final.index)

    return df_similarity, mobile_names_dict

def build_tablet_recommendation_model(rdf_graph):
    query = """
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX pto: <http://www.productontology.org/id/>
    PREFIX prop: <http://www.myeshop.gr/property/>

    SELECT ?uri ?name ?price ?brand ?os ?color ?releaseDate ?definition ?camera_main ?camera_selfie ?ram ?refresh_rate ?res_height ?res_width ?screen_size ?storage ?weight
    WHERE {
        ?uri a pto:Tablet_computer ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:manufacturer ?brandURI ;
             schema1:operatingSystem ?os ;
             schema1:color ?color ;
             schema1:releaseDate ?releaseDate ;
             prop:definition ?definition .
             
        BIND(REPLACE(STR(?brandURI), "^.*Brand_", "") AS ?brand)

        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?cmNode . FILTER(CONTAINS(STR(?cmNode), "_camera_main_mp")) ?cmNode gr:hasValueFloat ?camera_main . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?csNode . FILTER(CONTAINS(STR(?csNode), "_camera_selfie_mp")) ?csNode gr:hasValueFloat ?camera_selfie . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ramNode . FILTER(CONTAINS(STR(?ramNode), "_ram")) ?ramNode gr:hasValueFloat ?ram . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?rrNode . FILTER(CONTAINS(STR(?rrNode), "_refresh_rate")) ?rrNode gr:hasValueFloat ?refresh_rate . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?hNode . FILTER(CONTAINS(STR(?hNode), "_resolution_height")) ?hNode gr:hasValueFloat ?res_height . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wNode . FILTER(CONTAINS(STR(?wNode), "_resolution_width")) ?wNode gr:hasValueFloat ?res_width . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ssNode . FILTER(CONTAINS(STR(?ssNode), "_screen_size")) ?ssNode gr:hasValueFloat ?screen_size . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?stNode . FILTER(CONTAINS(STR(?stNode), "_storage")) ?stNode gr:hasValueFloat ?storage . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wtNode . FILTER(CONTAINS(STR(?wtNode), "_weight")) ?wtNode gr:hasValueFloat ?weight . }
    }
    """
    results = rdf_graph.query(query)

    tablets_data = []
    for row in results:
        tablets_data.append({
            "URI": str(row.uri),
            "Name": str(row.name),
            "Brand": str(row.brand),
            "OS": str(row.os),
            "Color": str(row.color),
            "Definition": str(row.definition),
            "Release_Date": int(row.releaseDate) if row.releaseDate else 0,
            "Price": float(row.price) if row.price else 0.0,
            "Camera_Main_MP": float(row.camera_main) if row.camera_main else 0.0,
            "Camera_Selfie_MP": float(row.camera_selfie) if row.camera_selfie else 0.0,
            "RAM_GB": float(row.ram) if row.ram else 0.0,
            "Refresh_Rate_Hz": float(row.refresh_rate) if row.refresh_rate else 0.0,
            "Screen_Size_inch": float(row.screen_size) if row.screen_size else 0.0,
            "Storage_GB": float(row.storage) if row.storage else 0.0,
            "Res_Height": float(row.res_height) if row.res_height else 0.0,
            "Res_Width": float(row.res_width) if row.res_width else 0.0,
            "Weight_g": float(row.weight) if row.weight else 0.0
        })

    df_tablets = pd.DataFrame(tablets_data)
    df_tablets.set_index('URI', inplace=True)
    
    tablet_names_dict = df_tablets['Name'].to_dict()
    df_features = df_tablets.drop(columns=['Name'])

    # 3. Preprocessing
    categorical_cols = ['Brand', 'OS', 'Color', 'Definition']
    numerical_cols = ['Release_Date', 'Price', 'Camera_Main_MP', 'Camera_Selfie_MP', 'RAM_GB', 'Refresh_Rate_Hz', 'Screen_Size_inch', 'Storage_GB', 'Res_Height', 'Res_Width', 'Weight_g']

    df_categorical = pd.get_dummies(df_features[categorical_cols], dtype=float)
    scaler = MinMaxScaler()
    df_numerical = pd.DataFrame(
        scaler.fit_transform(df_features[numerical_cols]), 
        columns=numerical_cols, 
        index=df_features.index
    )
    df_final = pd.concat([df_numerical, df_categorical], axis=1)

    weights_numerical = {
        'Screen_Size_inch': 3.0, 
        'RAM_GB': 2.5,
        'Storage_GB': 2.5,
        'Price': 2.0,            
        'Refresh_Rate_Hz': 1.5,
        'Camera_Main_MP': 1.0,
        'Camera_Selfie_MP': 1.0,
        'Res_Height': 1.0, 
        'Res_Width': 1.0, 
        'Release_Date': 1.0, 
        'Weight_g': 0.5          
    }

    for col in df_final.columns:
        if col in weights_numerical:
            df_final[col] = df_final[col] * weights_numerical[col]
        elif col.startswith('OS_'):
            df_final[col] = df_final[col] * 3.0  
        elif col.startswith('Brand_'):
            df_final[col] = df_final[col] * 2.0  
        elif col.startswith('Definition_'):
            df_final[col] = df_final[col] * 1.5
        elif col.startswith('Color_'):
            df_final[col] = df_final[col] * 0.2  

    similarity_matrix = cosine_similarity(df_final)
    df_similarity = pd.DataFrame(similarity_matrix, index=df_final.index, columns=df_final.index)

    return df_similarity, tablet_names_dict

def build_tv_recommendation_model(rdf_graph):
    query = """
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX pto: <http://www.productontology.org/id/>
    PREFIX prop: <http://www.myeshop.gr/property/>

    SELECT ?uri ?name ?price ?brand ?os ?definition ?releaseDate ?refresh_rate ?screen_size ?weight
    WHERE {
        ?uri a pto:Television_set ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:manufacturer ?brandURI ;
             schema1:operatingSystem ?os ;
             schema1:releaseDate ?releaseDate ;
             prop:definition ?definition .
             
        BIND(REPLACE(STR(?brandURI), "^.*Brand_", "") AS ?brand)

        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?rrNode . FILTER(CONTAINS(STR(?rrNode), "_refresh_rate")) ?rrNode gr:hasValueFloat ?refresh_rate . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ssNode . FILTER(CONTAINS(STR(?ssNode), "_screen_size")) ?ssNode gr:hasValueFloat ?screen_size . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wtNode . FILTER(CONTAINS(STR(?wtNode), "_weight")) ?wtNode gr:hasValueFloat ?weight . }
    }
    """
    results = rdf_graph.query(query)

    tvs_data = []
    for row in results:
        tvs_data.append({
            "URI": str(row.uri),
            "Name": str(row.name),
            "Brand": str(row.brand),
            "OS": str(row.os),
            "Definition": str(row.definition), # π.χ. 4K Ultra HD, Full HD
            "Release_Date": int(row.releaseDate) if row.releaseDate else 0,
            "Price": float(row.price) if row.price else 0.0,
            "Screen_Size_inch": float(row.screen_size) if row.screen_size else 0.0,
            "Refresh_Rate_Hz": float(row.refresh_rate) if row.refresh_rate else 0.0,
            "Weight_kg": float(row.weight) if row.weight else 0.0
        })

    df_tvs = pd.DataFrame(tvs_data)
    df_tvs.set_index('URI', inplace=True)
    
    tv_names_dict = df_tvs['Name'].to_dict()
    df_features = df_tvs.drop(columns=['Name'])

    categorical_cols = ['Brand', 'OS', 'Definition']
    numerical_cols = ['Release_Date', 'Price', 'Screen_Size_inch', 'Refresh_Rate_Hz', 'Weight_kg']

    df_categorical = pd.get_dummies(df_features[categorical_cols], dtype=float)
    scaler = MinMaxScaler()
    df_numerical = pd.DataFrame(
        scaler.fit_transform(df_features[numerical_cols]), 
        columns=numerical_cols, 
        index=df_features.index
    )
    df_final = pd.concat([df_numerical, df_categorical], axis=1)

    weights_numerical = {
        'Screen_Size_inch': 3.5, 
        'Price': 2.5,            
        'Refresh_Rate_Hz': 2.0,  
        'Release_Date': 1.0, 
        'Weight_kg': 0.2        
    }

    for col in df_final.columns:
        if col in weights_numerical:
            df_final[col] = df_final[col] * weights_numerical[col]
        elif col.startswith('Definition_'):
            df_final[col] = df_final[col] * 3.0  
        elif col.startswith('OS_'):
            df_final[col] = df_final[col] * 1.5  
        elif col.startswith('Brand_'):
            df_final[col] = df_final[col] * 1.5  

    # 5. Υπολογισμός Cosine Similarity
    similarity_matrix = cosine_similarity(df_final)
    df_similarity = pd.DataFrame(similarity_matrix, index=df_final.index, columns=df_final.index)

    return df_similarity, tv_names_dict

def build_smartwatch_recommendation_model(rdf_graph):
    query = """
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX pto: <http://www.productontology.org/id/>

    SELECT ?uri 
           (SAMPLE(?name) AS ?name_val) 
           (SAMPLE(?price) AS ?price_val) 
           (SAMPLE(?brandURI) AS ?brand_val) 
           (SAMPLE(?color) AS ?color_val) 
           (SAMPLE(?releaseDate) AS ?releaseDate_val) 
           (SAMPLE(?res_height) AS ?res_height_val) 
           (SAMPLE(?res_width) AS ?res_width_val) 
           (SAMPLE(?screen_size) AS ?screen_size_val) 
           (GROUP_CONCAT(?os; separator=",") AS ?os_list)
    WHERE {
        ?uri a pto:Smartwatch ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:manufacturer ?brandURI ;
             schema1:color ?color ;
             schema1:releaseDate ?releaseDate .
             
        OPTIONAL { ?uri schema1:operatingSystem ?os . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?hNode . FILTER(CONTAINS(STR(?hNode), "_resolution_height")) ?hNode gr:hasValueFloat ?res_height . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?wNode . FILTER(CONTAINS(STR(?wNode), "_resolution_width")) ?wNode gr:hasValueFloat ?res_width . }
        OPTIONAL { ?uri gr:quantitativeProductOrServiceProperty ?ssNode . FILTER(CONTAINS(STR(?ssNode), "_screen_size")) ?ssNode gr:hasValueFloat ?screen_size . }
    }
    GROUP BY ?uri
    """
    results = rdf_graph.query(query)

    smartwatches_data = []
    for row in results:
        brand_raw = str(row.brand_val)
        brand_clean = brand_raw.replace("http://www.myeshop.gr/resource/Brand_", "")
        
        smartwatches_data.append({
            "URI": str(row.uri),
            "Name": str(row.name_val),
            "Brand": brand_clean,
            "OS_list": str(row.os_list), 
            "Color": str(row.color_val),
            "Release_Date": int(row.releaseDate_val) if row.releaseDate_val else 0,
            "Price": float(row.price_val) if row.price_val else 0.0,
            "Screen_Size_inch": float(row.screen_size_val) if row.screen_size_val else 0.0,
            "Res_Height": float(row.res_height_val) if row.res_height_val else 0.0,
            "Res_Width": float(row.res_width_val) if row.res_width_val else 0.0
        })

    df_sw = pd.DataFrame(smartwatches_data)
    df_sw.set_index('URI', inplace=True)
    
    sw_names_dict = df_sw['Name'].to_dict()
    df_features = df_sw.drop(columns=['Name'])

    df_os = df_features['OS_list'].str.get_dummies(sep=',')
    df_os = df_os.add_prefix('OS_') 
    
    df_categorical = pd.get_dummies(df_features[['Brand', 'Color']], dtype=float)
    
    numerical_cols = ['Release_Date', 'Price', 'Screen_Size_inch', 'Res_Height', 'Res_Width']
    scaler = MinMaxScaler()
    df_numerical = pd.DataFrame(
        scaler.fit_transform(df_features[numerical_cols]), 
        columns=numerical_cols, 
        index=df_features.index
    )
    
    df_final = pd.concat([df_numerical, df_categorical, df_os], axis=1)

    weights = {
        'Screen_Size_inch': 3.0, 
        'Price': 2.5,            
        'Res_Height': 1.5, 
        'Res_Width': 1.5, 
        'Release_Date': 1.0
    }

    for col in df_final.columns:
        if col in weights:
            df_final[col] = df_final[col] * weights[col]
        elif col.startswith('OS_'):
            df_final[col] = df_final[col] * 3.5  
        elif col.startswith('Brand_'):
            df_final[col] = df_final[col] * 2.0  
        elif col.startswith('Color_'):
            df_final[col] = df_final[col] * 0.5  
    similarity_matrix = cosine_similarity(df_final)
    df_similarity = pd.DataFrame(similarity_matrix, index=df_final.index, columns=df_final.index)

    return df_similarity, sw_names_dict

def get_recommendations(target_uri, df_similarity, names_dict, top_n=3):
    if target_uri not in df_similarity.index:
        return {"error": "Το προϊόν δεν βρέθηκε στη βάση."}

    scores = df_similarity[target_uri]
    sorted_scores = scores.sort_values(ascending=False).drop(target_uri)
    top_results = sorted_scores.head(top_n)
    
    recommendations = []
    for uri, score in top_results.items():
        recommendations.append({
            "URI": uri,
            "Name": names_dict[uri],
            "Similarity": round(score * 100, 2)
        })
        
    return recommendations


def get_personalized_recommendations(wishlist_uris, models, per_item=3):
    """Εξατομικευμένες προτάσεις από τη λίστα αγαπημένων ενός χρήστη (καθαρή λογική).

    Για ΚΑΘΕ αγαπημένο επιστρέφει τα top-`per_item` όμοιά του (προεπιλογή 3).
    Δηλαδή N αγαπημένα -> έως N*per_item προτάσεις (π.χ. 2 αγαπημένα -> 6, 3 για
    το καθένα). Οι προτάσεις εναλλάσσονται (round-robin) ώστε οι κατηγορίες να
    μην εμφανίζονται σε μπλοκ. Αποκλείει ό,τι είναι ήδη στη wishlist και αποφεύγει
    διπλότυπα. Επιστρέφει λίστα από URIs — χωρίς πρόσβαση σε βάση/GraphDB.
    """
    wishlist_set = set(wishlist_uris)
    seen = set()
    per_favorite = []  # μία λίστα προτάσεων για κάθε αγαπημένο

    for w_uri in wishlist_uris:
        # Βρες το μοντέλο της κατηγορίας στην οποία ανήκει το αγαπημένο
        model = None
        for sim, names in models.values():
            if w_uri in sim.index:
                model = (sim, names)
                break
        if model is None:
            continue
        sim, names = model

        # Κράτα τα top-`per_item` όμοια που δεν είναι ήδη στη wishlist ούτε
        # έχουν προταθεί από άλλο αγαπημένο.
        recs = get_recommendations(w_uri, sim, names, top_n=len(sim))
        picks = []
        for r in recs:
            rec_uri = r["URI"]
            if rec_uri in wishlist_set or rec_uri in seen:
                continue
            picks.append(rec_uri)
            seen.add(rec_uri)
            if len(picks) >= per_item:
                break
        per_favorite.append(picks)

    # Ανακάτεμα (round-robin): 1η πρόταση κάθε αγαπημένου, μετά 2η κάθε αγαπημένου...
    recommended = []
    for i in range(per_item):
        for picks in per_favorite:
            if i < len(picks):
                recommended.append(picks[i])
    return recommended
