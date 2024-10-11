from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import urllib.parse

# Demander le terme de recherche à l'utilisateur
search_term = input("Entrez le nom que vous voulez rechercher : ").strip()

# Encoder le terme de recherche pour l'URL (remplacement des espaces par des +)
encoded_search_term = urllib.parse.quote_plus(search_term)

# Construire l'URL de recherche en utilisant le terme encodé
url = f'https://justice.pappers.fr/recherche?q={encoded_search_term}&tri=date'

options = Options()
options.add_argument('--disable-gpu')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

try:
    print(f"Accès au site de recherche pour '{search_term}'...")
    driver.get(url)

    wait = WebDriverWait(driver, 20)
    try:
        print("Attente de la fenêtre contextuelle...")
        close_popup = wait.until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[13]/div/div/header/span/span[2]')))
        close_popup.click()
        print("Fenêtre contextuelle fermée avec succès.")
        time.sleep(3)
    except Exception as e:
        print("Pas de fenêtre contextuelle à fermer ou erreur lors de la fermeture :", e)

    data = []
    current_page = 1
    total_results = 0
    decision_links = []  # Liste pour stocker les liens vers les décisions

    while True:
        # Vérification pour savoir si des résultats existent
        try:
            print(f"Scraping des extraits de la page {current_page} avec Selenium...")
            excerpts = wait.until(EC.presence_of_all_elements_located((By.XPATH,
                                                                       "//div[contains(@class, 'relative rounded-lg transition-all shadow p-6 bg-white md:p-6 text-left')]")))

            if len(excerpts) == 0:
                print("Aucun résultat trouvé.")
                driver.quit()
                exit()

            # Scraping des extraits sur la page actuelle
            for index, excerpt in enumerate(excerpts, start=1):
                try:
                    title_element = excerpt.find_element(By.XPATH,
                                                         ".//div[contains(@class, 'inline-block flex-shrink')]")
                    content_element = excerpt.find_element(By.XPATH,
                                                           ".//div[contains(@class, 'text-sm text-gray-600 highlights overflow-hidden')]")
                    link_element = excerpt.find_element(By.XPATH,
                                                        ".//a[contains(@class, 'flex flex-shrink-0 items-center gap-2 outline-none transition-colors')]")

                    # Scraping des mots-clés associés dans les éléments span
                    keywords_elements = excerpt.find_elements(By.XPATH,
                                                              ".//span[contains(@class, 'inline-flex flex-shrink-0')]")
                    keywords = ', '.join([kw.text.strip() for kw in keywords_elements])

                    title = title_element.text.strip() if title_element else "Titre non trouvé"
                    content = content_element.text.strip() if content_element else "Contenu non trouvé"
                    link = link_element.get_attribute('href') if link_element else "Lien non trouvé"
                    keywords = keywords if keywords else "Aucun mot-clé"

                    data.append({'Titre': title, 'Contenu': content, 'Mots-clés': keywords, 'Lien': link})
                    decision_links.append(link)
                    print(f"Extrait {index + total_results}: {title} - {content} - Mots-clés : {keywords}")
                    print(f"Lien vers la décision : {link}")
                except Exception as e:
                    print(f"Erreur lors de la récupération de l'extrait {index + total_results} :", e)

            total_results += len(excerpts)
            print(f"Nombre total d'extraits scrapés jusqu'à présent : {total_results}")

            # Vérifier s'il y a une page suivante en vérifiant si le bouton est désactivé
            try:
                next_button = driver.find_element(By.XPATH, "//button[contains(@class, 'btn-next')]")
                is_disabled = next_button.get_attribute("aria-disabled")

                if is_disabled == "true":
                    print("Aucune page suivante. Fin du scraping.")
                    break
                else:
                    # Cliquer sur le bouton suivant
                    next_button.click()
                    time.sleep(3)  # Attendre que la page charge
                    current_page += 1
            except Exception as e:
                print(f"Erreur lors de la vérification du bouton suivant : {e}")
                break

        except Exception as e:
            print("Erreur lors du scraping :", e)
            break

    # Créer un DataFrame à partir des données extraites
    df = pd.DataFrame(data)
    print(f"Total des extraits scrapés : {len(df)}")
    print(df)

    # Afficher les résultats avec index de 1 à N pour l'utilisateur
    for i, row in df.iterrows():
        print(f"{i + 1}: {row['Titre']} - {row['Contenu']} - \n Mots-clés : {row['Mots-clés']}")

    # Demander à l'utilisateur de choisir un numéro pour aller sur une décision spécifique
    choice = int(input(
        f"Entrez le numéro de l'extrait pour lequel vous voulez voir la décision (1-{len(decision_links)}): ")) - 1

    # Aller sur la page de la décision choisie
    decision_url = decision_links[choice]
    print(f"Accès à la décision {choice + 1} : {decision_url}")
    driver.get(decision_url)

    # Scrapper les informations de la décision avec Selenium
    try:
        print(f"Scraping de la décision : {decision_url}...")
        decision_title = wait.until(EC.presence_of_element_located((By.XPATH, "//h1"))).text
        decision_content = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@class='highlights break-words font-text text-black whitespace-pre-wrap']"))).text

        print(f"Titre de la décision : {decision_title}")
        print(f"Contenu de la décision :\n{decision_content}")

    except Exception as e:
        print("Erreur lors du scraping de la décision :", e)

finally:
    driver.quit()
