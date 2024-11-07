import requests
from bs4 import BeautifulSoup
import json

# URL de la page pour les réponses CDP de Carrefour
url = "https://www.cdp.net/en/responses?queries%5Bname%5D=Carrefour"

# Effectuer la requête vers l'URL
response = requests.get(url)
if response.status_code != 200:
    print("Erreur lors de la requête vers l'URL :", response.status_code)
    exit()

# Analyser le contenu HTML de la réponse
soup = BeautifulSoup(response.content, "html.parser")

# Trouver le tableau des résultats
table = soup.find("table", {"class": "sortable_table"})

# Initialiser la liste pour stocker les données
data = []

# Extraire les données de chaque ligne du tableau
for row in table.find_all("tr")[1:]:  # Sauter l'en-tête
    cells = row.find_all("td")

    if len(cells) >= 5:
        # Extraire le nom et le lien de l'entreprise
        name_tag = cells[0].find("a")
        name = name_tag.get_text(strip=True)
        link = name_tag["href"]
        full_link = f"https://www.cdp.net{link}"  # Ajouter le domaine pour un lien complet

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

# Convertir les données en JSON
json_data = json.dumps(data, indent=4, ensure_ascii=False)

# Afficher le JSON
print(json_data)
