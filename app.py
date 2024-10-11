from flask import Flask, render_template, request, jsonify
import requests
import time

app = Flask(__name__)

# Définir un User-Agent personnalisé
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
}

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    entreprise = request.form['entreprise']
    page = 1
    resultats_par_page = 10
    max_resultats = 200  # Limiter à 200 résultats
    tous_les_resultats = []

    # Boucle pour paginer à travers les résultats
    while len(tous_les_resultats) < max_resultats:
        # Construire l'URL avec la pagination
        url = f"https://api-justice.pappers.fr/v1/recherche?q={entreprise}&tri=date&page={page}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            resultats = data.get('resultats', [])
            tous_les_resultats.extend(resultats)

            # Calcul du nombre de pages restantes
            if len(resultats) < resultats_par_page or len(tous_les_resultats) >= max_resultats:
                break

            page += 1
            time.sleep(1)  # Pause entre les requêtes pour éviter l'erreur 429
        else:
            return f"Erreur {response.status_code} lors de la requête à l'API", 500

    return jsonify(tous_les_resultats[:max_resultats])


@app.route('/details/<id_affaire>')
def details(id_affaire):
    url_detail = f"https://api-justice.pappers.fr/v1/decision/{id_affaire}"
    response = requests.get(url_detail, headers=headers)

    if response.status_code == 200:
        detail = response.json()
        resume_genere = detail.get('texte', 'Résumé non disponible')
        return jsonify({'resume': resume_genere})
    else:
        return f"Erreur {response.status_code} lors de la récupération du détail de l'affaire", 500


if __name__ == '__main__':
    app.run(debug=True)
