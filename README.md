# Bot Discord — pixelvers (déploiement Railway)

## 1. Créer le projet sur Railway

1. Va sur [railway.app](https://railway.app) et connecte-toi (avec GitHub, c'est le plus simple).
2. **New Project** → **Deploy from GitHub repo** (pousse d'abord ces fichiers dans un repo GitHub),
   ou **Empty Project** puis glisse/dépose les fichiers si Railway te le permet dans ton cas.
3. Railway détecte automatiquement que c'est un projet Python grâce au `Procfile` et au
   `requirements.txt`.

## 2. Créer l'application Discord

1. Va sur https://discord.com/developers/applications → **New Application**.
2. Onglet **Bot** → **Add Bot** → copie le **Token**.
3. Toujours dans l'onglet **Bot**, active les 3 **Privileged Gateway Intents** :
   `Presence Intent`, `Server Members Intent`, `Message Content Intent`.
4. Onglet **OAuth2 → URL Generator** : scopes `bot` + `applications.commands`, permission
   `Administrator` → copie l'URL générée et ouvre-la pour inviter le bot sur ton serveur.

## 3. Générer un domaine public Railway

1. Dans ton projet Railway → clique sur ton service → onglet **Settings**.
2. Section **Networking** → **Generate Domain**. Railway te donne une URL du type
   `https://tonprojet-production.up.railway.app`.
3. Garde cette URL, tu en as besoin à l'étape suivante.

## 4. Variables d'environnement (équivalent des "Secrets" de Replit)

Dans ton service Railway → onglet **Variables** → ajoute :

| Variable | Valeur |
|---|---|
| `DISCORD_TOKEN` | Le token du bot (étape 2) |
| `DISCORD_CLIENT_ID` | Onglet **OAuth2 → General** de ton appli Discord → "Client ID" |
| `DISCORD_CLIENT_SECRET` | Même page → "Client Secret" |
| `DISCORD_REDIRECT_URI` | `https://tonprojet-production.up.railway.app/callback` |
| `SESSION_SECRET` | Une chaîne aléatoire longue (ex: générée sur randomkeygen.com) |

Railway fournit déjà automatiquement la variable `PORT` — tu n'as rien à faire pour ça, le code
(`webapp/api_server.py`) la lit tout seul.

## 5. Autoriser l'URL de redirection côté Discord

1. Retourne sur https://discord.com/developers/applications → ton appli → **OAuth2 → General**.
2. Dans **Redirects**, ajoute exactement : `https://tonprojet-production.up.railway.app/callback`
   (avec `/callback`, et la même URL que dans `DISCORD_REDIRECT_URI`).

## 6. Déployer

Railway redéploie automatiquement à chaque changement de variable ou de code (si connecté à GitHub).
Sinon, un simple redémarrage du service suffit. Dans les **Logs** du service, tu dois voir :

```
📦 Module chargé : cogs.moderation
...
✅ Connecté en tant que TonBot#1234
🔄 X commande(s) slash synchronisée(s)
```

Railway ne met pas le service en veille comme le fait Replit gratuit — pas besoin d'UptimeRobot ici
(sauf si tu es sur un plan gratuit avec des limites d'heures, auquel cas vérifie ton usage dans
**Usage** sur Railway).

## 7. Comment le site et le bot communiquent

- Le bot (discord.py) démarre dans `main.py`.
- Le site (Flask, dossier `webapp/`) démarre dans un thread à côté, sur le port fourni par Railway.
- Le site lit directement `bot.guilds`, `guild.text_channels`, `guild.roles`, etc. pour afficher les
  **vrais** salons/rôles de tes serveurs.
- Les réglages changés sur le site (notifications sociales, modération) sont sauvegardés dans des
  fichiers JSON (`social_alerts.json`, `moderation_config.json`) que les cogs du bot relisent pour agir.

⚠️ Sur Railway (comme sur beaucoup d'hébergeurs), le système de fichiers n'est pas forcément persistant
entre les redéploiements selon le plan. Si tes `social_alerts.json` / `badges.json` disparaissent après
un redéploiement, il faudra migrer vers une vraie base de données (ex: Railway propose PostgreSQL en
un clic) plutôt que des fichiers JSON — dis-le moi si tu en as besoin.

## 8. Commandes du bot

| Commande | Module | Description |
|---|---|---|
| `/serveur-setup` | Setup | Crée d'un coup les rôles, catégories, salons et le règlement |
| `/kick`, `/ban`, `/mute`, `/unmute`, `/clear` | Modération | Sanctions manuelles |
| `/ticket-setup` | Tickets | Bouton d'ouverture de ticket |
| `/badge set`, `/badge remove`, `/badge list` | Badges | Gère les badges des membres |
| `/play`, `/skip`, `/stop`, `/queue` | Musique | Lecture audio YouTube |
| `/stats`, `/userinfo` | Stats | Statistiques serveur / membre |
| `/social add`, `/social list`, `/social remove` | Notifications sociales | Alertes YouTube / TikTok / Twitch |

## 9. Twitch (optionnel)

YouTube et TikTok fonctionnent sans rien configurer. Pour Twitch : crée une app sur
https://dev.twitch.tv/console/apps, puis ajoute `TWITCH_CLIENT_ID` et `TWITCH_CLIENT_SECRET` dans les
Variables Railway.
