from flask import Flask, render_template, request, jsonify
import requests
import sqlite3
import os
import time

app = Flask(__name__)

# Configuration du chemin de la base de données
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'mnt', 'data', 'tax_evasion.db')

# Définir un User-Agent personnalisé
headers = {
    'User-Agent': 'Mozilla/5.0'
}

# Fonction auxiliaire pour interroger la base de données SQLite
def query_database(query, args=(), one=False):
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
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
        query = f"SELECT * FROM {table} WHERE node_id = ?"
        result = query_database(query, [node_id], one=True)
        if result:
            name = result['name'] if result['name'] else 'No Name'
            print(f"Nœud trouvé dans la table {table} : {name}")
            return {
                'id': result['node_id'],
                'name': name,
                'type': node_type
            }
    print(f"Aucun détail trouvé pour le nœud ID {node_id}")
    return None

# Route pour le diagnostic d'évasion fiscale
@app.route('/tax_evasion', methods=['POST'])
def tax_evasion():
    company_name = request.form.get('company_name', '').lower()
    print(f"Recherche pour l'entreprise : {company_name}")
    results = {
        'nodes': [],
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

    # Récupérer les nœuds correspondant au nom de l'entreprise
    for node_type, table in tables.items():
        query = f"SELECT * FROM {table} WHERE LOWER(name) LIKE ?"
        matches = query_database(query, [f"%{company_name}%"])
        print(f"Table {table}, {len(matches)} correspondances trouvées.")
        if matches:
            for row in matches:
                node_id = f"{node_type.lower()}-{row['node_id']}"  # Unique ID
                if node_id not in added_node_ids:
                    node = {
                        'id': node_id,
                        'name': row['name'] if row['name'] else 'No Name',
                        'type': node_type
                    }
                    results['nodes'].append(node)
                    added_node_ids.add(node_id)
                node_ids.add(row['node_id'])

    # Vérifier si des nœuds ont été trouvés
    if not node_ids:
        print("Aucun nœud trouvé pour le nom de l'entreprise fourni.")
        return jsonify(results)

    # Récupérer les relations pour les nœuds trouvés
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

    if relationships:
        for rel in relationships:
            # Récupérer les détails des nœuds de départ et de fin
            source = get_node_details(rel['node_id_start'])
            target = get_node_details(rel['node_id_end'])

            if source and target:
                # Construire les IDs uniques
                source_id = f"{source['type'].lower()}-{source['id']}"
                target_id = f"{target['type'].lower()}-{target['id']}"

                # Ajouter les nœuds s'ils ne sont pas déjà présents
                if source_id not in added_node_ids:
                    results['nodes'].append({
                        'id': source_id,
                        'name': source['name'],
                        'type': source['type']
                    })
                    added_node_ids.add(source_id)

                if target_id not in added_node_ids:
                    results['nodes'].append({
                        'id': target_id,
                        'name': target['name'],
                        'type': target['type']
                    })
                    added_node_ids.add(target_id)

                # Ajouter l'arête
                edge = {
                    'source': source_id,
                    'target': target_id,
                    'rel_type': rel['rel_type']
                }
                results['edges'].append(edge)

    print(f"Nombre total de nœuds : {len(results['nodes'])}")
    print(f"Nombre total d'arêtes : {len(results['edges'])}")

    return jsonify(results)

# Route pour la page d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Route pour le diagnostic juridique (API Justice) avec pagination
@app.route('/search', methods=['POST'])
def search():
    entreprise = request.form.get('entreprise', '')
    page = int(request.form.get('page', 1))
    resultats_par_page = 10

    url = f"https://api-justice.pappers.fr/v1/recherche?q={entreprise}&tri=date&page={page}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        resultats = data.get('resultats', [])
        total_results = data.get('total_results', len(resultats))

        return jsonify({
            "resultats": resultats,
            "total_results": total_results,
            "page": page,
            "resultats_par_page": resultats_par_page
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
