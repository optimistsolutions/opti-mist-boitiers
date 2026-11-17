# OPTI-MIST SOLUTIONS — code des boîtiers de supervision

Dépôt **public** contenant uniquement les programmes des boîtiers de supervision posés chez les clients.
- **Aucun secret** : jetons, mots de passe, adresses de service, listes de sites et noms de clients restent dans la configuration de chaque boîtier, jamais ici.
- **Lecture seule** : les programmes lisent les équipements, ils n'écrivent aucun réglage.
- **Mise à jour automatique** : un boîtier n'installe un fichier de ce dépôt que si son empreinte sha256 a été approuvée par la gérance d'OPTI-MIST SOLUTIONS sur un second canal indépendant. Un fichier modifié ici sans approbation n'est jamais installé.

Source de référence et historique complet : dépôt privé interne. Ce dépôt en est une copie publiée.

| Dossier | Rôle |
|---|---|
| sma/ | Collecteur pour centrales à onduleurs SMA (lecture Speedwire, journal d'événements, compteur en écoute passive) |
| sa_relais/ | Relais en lecture seule de sites équipés d'une plateforme de supervision tierce |
| felicity/ | Collecteur pour convertisseurs à batterie |
| maj_auto/ | Mise à jour automatique à double canal (approbation + fichiers), avec retour arrière |
| reseau/ | Bascule Wi-Fi principal / secours selon l'accès internet réel (v1.0) |
