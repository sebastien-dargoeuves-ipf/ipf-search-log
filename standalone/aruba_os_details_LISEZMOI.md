# Aruba OS Details — Mode d'emploi

Petit script autonome qui récupère, depuis les logs IP Fabric, la version du firmware
des équipements HPE Aruba (commande `show version`) :

- famille `arubacx` (AOS-CX) → **BIOS Version**
- famille `arubasw` (AOS-Switch) → **Boot ROM Version**

## 1. Récupérer les fichiers

Vous avez seulement besoin de **deux fichiers** dans un même dossier :

- `aruba_os_details.py` (le script)
- `.env` (vos paramètres de connexion à IP Fabric)

## 2. Installer les dépendances

Une seule fois, dans un terminal :

```bash
pip install ipfabric python-dotenv
```

> ⚠️ La version du module `ipfabric` doit correspondre à votre version d'IP Fabric.

## 3. Configurer l'accès à IP Fabric

Créez un fichier nommé `.env` dans le même dossier que le script, avec ce contenu
(adaptez les valeurs) :

```env
IPF_URL = "https://mon-serveur-ipfabric/"
IPF_TOKEN = "votre_token_api"
IPF_VERIFY = "False"
IPF_SNAPSHOT = "$last"
PROMPT_DELIMITER = "#|>"
```

- `IPF_URL` : l'adresse de votre serveur IP Fabric
- `IPF_TOKEN` : votre jeton d'API
- `IPF_VERIFY` : `"False"` si vous utilisez un certificat auto-signé, sinon `"True"`
- `IPF_SNAPSHOT` : laissez `"$last"` pour utiliser le dernier snapshot
- `PROMPT_DELIMITER` : à laisser tel quel
- (optionnel) `DEVICES_FILTER` : pour limiter à certains équipements, ex :
  `DEVICES_FILTER = '{"hostname": ["like", "SW-PARIS"]}'`

## 4. Lancer le script

```bash
python aruba_os_details.py
```

## Résultat

Le script affiche les résultats à l'écran et crée un fichier **`os_details.csv`**
avec une ligne par équipement :

| device     | family   | detail           | value         |
|------------|----------|------------------|---------------|
| switch-01  | arubacx  | BIOS Version     | FL.01.0007    |
| switch-02  | arubasw  | Boot ROM Version | WC.17.02.0007 |
