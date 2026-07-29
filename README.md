# Pickle Match Kanto

関東1都6県のピックルボール団体、練習会、参加者募集を検索・比較・掲載申請できるWebアプリです。対象は東京都、神奈川県、埼玉県、千葉県、茨城県、栃木県、群馬県で、島しょ部は扱いません。

## Local Run

```powershell
python outputs\pickle_match_tokyo\picklematch_tokyo_app.py
```

Open `http://127.0.0.1:8791/`.

Initialize without starting the server:

```powershell
python outputs\pickle_match_tokyo\picklematch_tokyo_app.py --init-only
```

## Production on Render

`render.yaml` is a Circle Match-compatible Blueprint. It starts the app with a persistent 1 GB disk mounted at `/var/data` and checks `/healthz`.

1. Connect `yuumaokamori015710-droid/picklematch_tokyo` in Render and create the Blueprint service.
2. Set `PICKLEMATCH_CONTACT_EMAIL` to the real operations address.
3. Set `PICKLEMATCH_SITE_BASE_URL` to the Render URL first, then replace it with the HTTPS custom domain once DNS is active.
4. In Render, add the chosen custom domain. Configure the exact DNS record Render displays at the domain provider and wait for HTTPS to become active.

The service name requests the default Render URL `https://pickle-match-kanto.onrender.com`. Render creates this URL only after the first successful deployment; it is not claimed by this repository alone.

## Data and Privacy

- SQLite files, representative applications, inquiry messages, logs, and secrets are excluded by `.gitignore`.
- Public endpoints exclude representative names, representative emails, and internal notes.
- A public contact address is displayed only where the organization has consented to publication.
- Initial public records require an official website or directly verifiable official social account. Unconfirmed records remain in the non-public candidate database.
