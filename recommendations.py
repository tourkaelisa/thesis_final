"""Service προτάσεων: κρατά τα μοντέλα ομοιότητας και εξυπηρετεί προτάσεις
όμοιων προϊόντων (item-to-item) και εξατομικευμένες προτάσεις."""
import recommendation_engine as engine
from graphdb import query_graphdb, bval

# Προϋπολογισμένα μοντέλα ομοιότητας ανά κατηγορία (γεμίζουν στο startup)
models = {}


def build_models(rdf_graph):
    """Χτίζει τα μοντέλα ομοιότητας από τον in-memory γράφο (μία φορά, στο startup)."""
    models["laptops"] = engine.build_laptop_recommendation_model(rdf_graph)
    models["mobiles"] = engine.build_mobile_recommendation_model(rdf_graph)
    models["tablets"] = engine.build_tablet_recommendation_model(rdf_graph)
    models["tvs"] = engine.build_tv_recommendation_model(rdf_graph)
    models["smartwatches"] = engine.build_smartwatch_recommendation_model(rdf_graph)


def get_similar_products(product_uri):
    """Προτάσεις όμοιων προϊόντων για ένα προϊόν. Επιστρέφει λίστα, ή None αν το
    προϊόν δεν ανήκει σε κανένα μοντέλο."""
    for _cat, (sim, names) in models.items():
        if product_uri in sim.index:
            recs = engine.get_recommendations(product_uri, sim, names)
            formatted = []
            for r in recs:
                rec_uri = r["URI"]
                img_query = f"""
                PREFIX schema1: <http://schema.org/>
                SELECT ?img WHERE {{ <{rec_uri}> schema1:image ?img . }}
                """
                img_res = query_graphdb(img_query)
                img_url = bval(img_res[0], "img") if img_res else ""
                formatted.append({"id": rec_uri, "name": r["Name"], "image": img_url})
            return formatted
    return None


def get_personalized_products(wishlist_uris):
    """Εξατομικευμένες προτάσεις βάσει της wishlist· επιστρέφει λίστα προϊόντων."""
    top_uris = engine.get_personalized_recommendations(wishlist_uris, models)
    products = []
    for rec_uri in top_uris:
        q = f"""
        PREFIX gr: <http://purl.org/goodrelations/v1#>
        PREFIX schema1: <http://schema.org/>
        SELECT ?name ?price ?image WHERE {{
            <{rec_uri}> gr:name ?name ;
                        schema1:price ?price ;
                        schema1:image ?image .
        }}
        """
        res = query_graphdb(q)
        if res:
            r = res[0]
            products.append({
                "id": rec_uri,
                "name": bval(r, "name"),
                "price": float(bval(r, "price")),
                "image": bval(r, "image"),
            })
    return products
