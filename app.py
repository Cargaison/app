from flask import Flask, render_template, request, jsonify
import requests
import sqlite3
import os
from bs4 import BeautifulSoup  # Importé pour le scraping CDP
import time  # Pour le profilage des performances

app = Flask(__name__)

# Configuration du chemin de la base de données
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'mnt', 'data', 'tax_evasion.db')

# Définir un User-Agent personnalisé
headers = {
    'User-Agent': 'Mozilla/5.0'
}

# Fonction auxiliaire pour interroger la base de données SQLite avec des pragmas optimisés
def query_database(query, args=(), one=False):
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        # Activer les pragmas pour la performance
        conn.execute('PRAGMA synchronous = OFF;')
        conn.execute('PRAGMA journal_mode = MEMORY;')
        cur = conn.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

# Fonction pour obtenir les détails d'un nœud par son node_id
def get_node_details(node_id):
    tables = {
        'Entities': 'nodes_entities',
        'Officers': 'nodes_officers',
        'Intermediaries': 'nodes_intermediaries',
        'Addresses': 'nodes_addresses',
        'Others': 'nodes_others'
    }
    for node_type, table in tables.items():
        query = f"SELECT name FROM {table} WHERE node_id = ?"
        result = query_database(query, [node_id], one=True)
        if result:
            name = result['name'] if result['name'] else 'No Name'
            print(f"Nœud trouvé dans la table {table} : {name}")
            return {
                'id': node_id,
                'name': name,
                'type': node_type
            }
    print(f"Aucun détail trouvé pour le nœud ID {node_id}")
    return None

# Route pour le diagnostic d'évasion fiscale (Optimisée avec pagination et séparation des données)
@app.route('/tax_evasion', methods=['POST'])
def tax_evasion():
    start_time = time.time()  # Début du profilage

    company_name = request.form.get('company_name', '').lower()
    page = int(request.form.get('page', 1))
    per_page = int(request.form.get('per_page', 10))  # Valeur par défaut de 10 éléments par page
    print(f"Recherche pour l'entreprise : {company_name}, Page : {page}, Per Page : {per_page}")

    paginated_results = {
        'paginated_nodes': [],
        'total_results': 0,
        'page': page
    }

    visualization_results = {
        'all_nodes': [],
        'edges': []
    }

    # Définir les tables et les types correspondants
    tables = {
        'Entities': 'nodes_entities',
        'Officers': 'nodes_officers',
        'Intermediaries': 'nodes_intermediaries',
        'Addresses': 'nodes_addresses',
        'Others': 'nodes_others'
    }

    node_ids = set()
    added_node_ids = set()
    node_details = {}

    # Préparer les requêtes pour toutes les tables
    for node_type, table in tables.items():
        query = f"SELECT node_id, name FROM {table} WHERE LOWER(name) LIKE ?"
        matches = query_database(query, [f"%{company_name}%"])
        print(f"Table {table}, {len(matches)} correspondances trouvées.")
        if matches:
            for row in matches:
                node_id = row['node_id']
                unique_node_id = f"{node_type.lower()}-{node_id}"  # ID Unique
                if unique_node_id not in added_node_ids:
                    node = {
                        'id': unique_node_id,
                        'name': row['name'] if row['name'] else 'No Name',
                        'type': node_type
                    }
                    paginated_results['paginated_nodes'].append(node)
                    visualization_results['all_nodes'].append(node)
                    added_node_ids.add(unique_node_id)
                node_ids.add(node_id)
                # Stocker les détails du nœud
                node_details[node_id] = {
                    'id': node_id,
                    'name': row['name'] if row['name'] else 'No Name',
                    'type': node_type
                }

    # Vérifier si des nœuds ont été trouvés
    if not node_ids:
        print("Aucun nœud trouvé pour le nom de l'entreprise fourni.")
        paginated_results['total_results'] = 0
        end_time = time.time()
        print(f"Temps total pour /tax_evasion: {end_time - start_time} secondes")
        return jsonify({**paginated_results, **visualization_results})

    # Récupérer les relations pour les nœuds trouvés avec une seule requête
    placeholders = ','.join(['?'] * len(node_ids))
    query = f"""
        SELECT * FROM relationships 
        WHERE node_id_start IN ({placeholders}) 
        OR node_id_end IN ({placeholders})
    """
    params = list(node_ids)
    params.extend(node_ids)
    relationships = query_database(query, params)
    print(f"{len(relationships)} relations trouvées.")

    # Précharger les détails des nœuds impliqués dans les relations
    related_node_ids = set()
    for rel in relationships:
        related_node_ids.add(rel['node_id_start'])
        related_node_ids.add(rel['node_id_end'])

    # Récupérer les détails des nœuds manquants en une seule requête par table
    missing_node_ids = related_node_ids - node_ids
    if missing_node_ids:
        for node_type, table in tables.items():
            placeholders_missing = ','.join(['?'] * len(missing_node_ids))
            query_missing = f"SELECT node_id, name FROM {table} WHERE node_id IN ({placeholders_missing})"
            matches_missing = query_database(query_missing, list(missing_node_ids))
            for row in matches_missing:
                node_id = row['node_id']
                unique_node_id = f"{node_type.lower()}-{node_id}"
                if unique_node_id not in added_node_ids:
                    node = {
                        'id': unique_node_id,
                        'name': row['name'] if row['name'] else 'No Name',
                        'type': node_type
                    }
                    visualization_results['all_nodes'].append(node)
                    added_node_ids.add(unique_node_id)
                # Stocker les détails du nœud
                node_details[node_id] = {
                    'id': node_id,
                    'name': row['name'] if row['name'] else 'No Name',
                    'type': node_type
                }

    # Ajouter les arêtes et les nœuds associés pour la visualisation
    for rel in relationships:
        start_id = rel['node_id_start']
        end_id = rel['node_id_end']

        # Détails du nœud de départ
        source = node_details.get(start_id)
        if source:
            source_id = f"{source['type'].lower()}-{source['id']}"
            if source_id not in added_node_ids:
                node = {
                    'id': source_id,
                    'name': source['name'],
                    'type': source['type']
                }
                visualization_results['all_nodes'].append(node)
                added_node_ids.add(source_id)
        else:
            print(f"Détails manquants pour le nœud de départ ID {start_id}")
            continue  # Passer à la relation suivante si les détails sont manquants

        # Détails du nœud de fin
        target = node_details.get(end_id)
        if target:
            target_id = f"{target['type'].lower()}-{target['id']}"
            if target_id not in added_node_ids:
                node = {
                    'id': target_id,
                    'name': target['name'],
                    'type': target['type']
                }
                visualization_results['all_nodes'].append(node)
                added_node_ids.add(target_id)
        else:
            print(f"Détails manquants pour le nœud de fin ID {end_id}")
            continue  # Passer à la relation suivante si les détails sont manquants

        # Ajouter l'arête
        edge = {
            'source': source_id,
            'target': target_id,
            'rel_type': rel['rel_type']
        }
        visualization_results['edges'].append(edge)

    # Calculer le nombre total de nœuds pour la pagination
    total_nodes = len(paginated_results['paginated_nodes'])
    paginated_results['total_results'] = total_nodes

    # Appliquer la pagination sur les nœuds paginés
    start = (page - 1) * per_page
    end = start + per_page
    paginated_nodes = paginated_results['paginated_nodes'][start:end]
    paginated_results['paginated_nodes'] = paginated_nodes

    print(f"Nombre total de nœuds pour la pagination : {total_nodes}")
    print(f"Nœuds renvoyés pour la page {page} : {len(paginated_nodes)}")

    end_time = time.time()  # Fin du profilage
    print(f"Temps total pour /tax_evasion: {end_time - start_time} secondes")

    # S'assurer que 'edges' est toujours présent
    if 'edges' not in visualization_results:
        visualization_results['edges'] = []

    # Retourner les résultats paginés et les données pour la visualisation
    response_data = {**paginated_results, **visualization_results}
    print(f"Réponse JSON renvoyée : {response_data}")
    return jsonify(response_data)

# Nouvelle Route pour le Score Environnemental CDP
@app.route('/environmental_score', methods=['POST'])
def environmental_score():
    company_name = request.form.get('company_name', '').strip()
    if not company_name:
        return jsonify({"error": "Nom de l'entreprise non fourni."}), 400

    print(f"Recherche du score environnemental pour : {company_name}")

    # Construire l'URL CDP
    query_param = requests.utils.quote(company_name)
    url = f"https://www.cdp.net/en/responses?queries%5Bname%5D={query_param}"

    # Définir les headers pour imiter un navigateur
    cdp_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    # Effectuer la requête vers CDP
    response = requests.get(url, headers=cdp_headers)
    if response.status_code != 200:
        print(f"Erreur lors de la requête vers CDP : {response.status_code}")
        return jsonify({"error": f"Erreur lors de la requête vers CDP : {response.status_code}"}), 500

    # Analyser le contenu HTML de la réponse
    soup = BeautifulSoup(response.content, "html.parser")

    # Trouver le tableau des résultats
    table = soup.find("table", {"class": "sortable_table"})
    if not table:
        print("Table des résultats CDP non trouvée.")
        return jsonify({"error": "Table des résultats CDP non trouvée."}), 404

    # Initialiser la liste pour stocker les données
    data = []

    # Extraire les données de chaque ligne du tableau
    for row in table.find_all("tr")[1:]:  # Sauter l'en-tête
        cells = row.find_all("td")

        if len(cells) >= 5:
            # Extraire le nom et le lien de l'entreprise
            name_tag = cells[0].find("a")
            if name_tag:
                name = name_tag.get_text(strip=True)
                link = name_tag["href"]
                full_link = f"https://www.cdp.net{link}"  # Ajouter le domaine pour un lien complet
            else:
                name = cells[0].get_text(strip=True)
                full_link = ""

            # Extraire les autres informations
            response_type = cells[1].get_text(strip=True)
            year = cells[2].get_text(strip=True)
            status = cells[3].get_text(strip=True)

            # Extraire uniquement la première lettre du score (et + ou - si présent)
            score_text = cells[4].get_text(strip=True)
            score = score_text[0] + (score_text[1] if len(score_text) > 1 and score_text[1] in ['+', '-'] else '')

            # Ajouter les données dans un dictionnaire avec le thème de la réponse
            data.append({
                "Name": name,
                "Link": full_link,  # Lien vers la page de l'entreprise
                "Theme": response_type,  # Thème basé sur la colonne Response
                "Year": year,
                "Status": status,
                "Score": score  # Note formatée
            })

    if not data:
        print("Aucune donnée CDP trouvée pour l'entreprise.")
        return jsonify({"message": "Aucune donnée CDP trouvée pour l'entreprise."}), 404

    # Retourner les données JSON
    return jsonify(data)

# Route pour la page d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Route pour le diagnostic juridique (API Justice) avec pagination
@app.route('/search', methods=['POST'])
def search():
    entreprise = request.form.get('entreprise', '')
    page = int(request.form.get('page', 1))
    resultats_par_page = int(request.form.get('per_page', 10))  # Assurez-vous de recevoir per_page

    # Encodage de l'entreprise pour l'URL
    entreprise_encoded = requests.utils.quote(entreprise)
    url = f"https://api-justice.pappers.fr/v1/recherche?q={entreprise_encoded}&tri=date&page={page}&per_page={resultats_par_page}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        resultats = data.get('resultats', [])
        total_results = data.get('total_results', len(resultats))

        return jsonify({
            "resultats": resultats,
            "total_results": total_results,
            "page": page,
            "per_page": resultats_par_page
        })
    else:
        return jsonify({"error": f"Erreur {response.status_code} lors de la requête à l'API"}), 500

# Route pour obtenir les détails d'une décision
@app.route('/details/<id_affaire>')
def details(id_affaire):
    url_detail = f"https://api-justice.pappers.fr/v1/decision/{id_affaire}"
    response = requests.get(url_detail, headers=headers)

    if response.status_code == 200:
        detail = response.json()
        resume_genere = detail.get('texte', 'Résumé non disponible')
        return jsonify({'resume': resume_genere})
    else:
        return jsonify({"error": f"Erreur {response.status_code} lors de la récupération du détail de l'affaire"}), 500

if __name__ == '__main__':
    app.run(debug=True)
