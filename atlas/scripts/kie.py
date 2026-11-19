"""Images IA de Atlas, sans rien installer : Kie (GPT Image 2.5) ou ArgoLink (Nano Banana Pro).
Fournisseur : variable IMAGES_FOURNISSEUR = « kie » (défaut) ou « argolink ». Mêmes commandes, mêmes fichiers dans les deux cas.

  python3 kie.py lancer <travail/images.json>
      images.json : [{"nom": "g1", "prompt": "...", "ref": "https://cdn.shopify.com/...", "ratio": "1:1", "taille": "1K"}, ...]
      Lance toutes les images en parallèle, écrit les numéros de tâche dans <travail/taches.json>.
  python3 kie.py recuperer <travail/>
      Attend la fin, télécharge <travail/images/<nom>.png>, écrit <travail/urls.json> (URL Kie de chaque image,
      à donner à Shopify fileCreate le jour même), affiche les crédits consommés.
  python3 kie.py planche <travail/>
      Fait <travail/planche.jpg> : toutes les images avec leur nom, à regarder une fois.

Clés : KIE_API_KEY (Kie) ou ARGOLINK_API_KEY (ArgoLink) ; sur un Mac, sinon ~/.config/kie/.env. Si elle vaut « cloud », le vrai secret est ajouté par claude.ai
(« secrets réseau ») : on n'envoie alors aucun en-tête d'autorisation. Ne jamais afficher la clé.
Coût indicatif : 6 crédits par image en 1K, 10 en 2K. Un échec ne coûte rien."""
import json, os, sys, time, urllib.error, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor

API = "https://api.kie.ai/api/v1"
def _cle():
    k = os.environ.get("KIE_API_KEY", "")
    if k:
        return k
    f = os.path.expanduser("~/.config/kie/.env")  # installation sur un Mac (fichier lisible par toi seul)
    if os.path.exists(f):
        for l in open(f):
            if l.strip().startswith("KIE_API_KEY="):
                return l.split("=", 1)[1].strip().strip('"\'')
    return ""


CLE = _cle()
FOURNISSEUR = os.environ.get("IMAGES_FOURNISSEUR", "kie").strip().lower()
ARGO = "https://argolink.io/v1"
CLE_ARGO = os.environ.get("ARGOLINK_API_KEY", "")
if FOURNISSEUR not in ("kie", "argolink"):
    raise SystemExit("IMAGES_FOURNISSEUR doit valoir « kie » ou « argolink »")


def appel(chemin, donnees=None):
    h = {"Content-Type": "application/json"}
    if CLE and CLE != "cloud":
        h["Authorization"] = "Bearer " + CLE
    req = urllib.request.Request(API + chemin, data=json.dumps(donnees).encode() if donnees is not None else None,
                                 headers=h, method="POST" if donnees is not None else "GET")
    return json.load(urllib.request.urlopen(req, timeout=60))


def telecharger(u, f):
    """Téléchargement avec un User-Agent de navigateur (files.argolink.io refuse celui de Python : HTTP 403)."""
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=120) as r, open(f, "wb") as h:
        h.write(r.read())


def _argo(im):
    """Une image ArgoLink (Nano Banana Pro). Avec ref : /images/edits (images envoyées en pièces jointes), sinon /images/generations."""
    h = {"User-Agent": "atlas/1.0"}
    if CLE_ARGO and CLE_ARGO != "cloud":
        h["Authorization"] = "Bearer " + CLE_ARGO
    champs = {"model": "nano-banana-pro", "prompt": im["prompt"], "aspect_ratio": im.get("ratio", "1:1"),
              "resolution": im.get("taille", "1K").lower(), "n": "1", "response_format": "url"}
    refs = im["ref"] if isinstance(im.get("ref"), list) else ([im["ref"]] if im.get("ref") else [])
    if refs:
        b = "----atlas" + uuid.uuid4().hex
        corps = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in champs.items())
        for i, u in enumerate(refs[:4]):
            data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124 Safari/537.36"}), timeout=60).read()
            corps += f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + data + b"\r\n"
        corps += f"--{b}--\r\n".encode()
        req = urllib.request.Request(ARGO + "/images/edits", corps, {**h, "Content-Type": "multipart/form-data; boundary=" + b})
    else:
        req = urllib.request.Request(ARGO + "/images/generations", json.dumps({**champs, "n": 1}).encode(), {**h, "Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))["data"][0]
    except urllib.error.HTTPError as e:
        return im["nom"], None, f"HTTP {e.code} {e.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as e:
        return im["nom"], None, str(e)[:200]
    return im["nom"], d.get("url"), None if d.get("url") else "pas de lien dans la réponse"


def lancer_argo(fichier):
    images = json.load(open(fichier, encoding="utf-8"))
    dossier = os.path.dirname(os.path.abspath(fichier))
    urls_f = os.path.join(dossier, "urls.json")
    urls = json.load(open(urls_f)) if os.path.exists(urls_f) else {}
    os.makedirs(os.path.join(dossier, "images"), exist_ok=True)
    a_faire = [im for im in images if im["nom"] not in urls]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for nom, u, err in ex.map(_argo, a_faire):
            if err:
                print(nom, "ÉCHEC :", err)
                continue
            urls[nom] = u
            telecharger(u, os.path.join(dossier, "images", nom + ".png"))
            print(nom, "ok")
    json.dump(urls, open(urls_f, "w"), indent=1)
    # taches.json garde la liste des images faites, pour que « recuperer » fonctionne pareil qu'avec Kie
    json.dump({n: "argolink" for n in urls}, open(os.path.join(dossier, "taches.json"), "w"), indent=1)
    print(f"{len(urls)} image(s) prêtes (ArgoLink). Liens publics dans {urls_f}")


def lancer(fichier):
    if FOURNISSEUR == "argolink":
        return lancer_argo(fichier)
    images = json.load(open(fichier, encoding="utf-8"))
    dossier = os.path.dirname(os.path.abspath(fichier))
    taches_f = os.path.join(dossier, "taches.json")
    taches = json.load(open(taches_f)) if os.path.exists(taches_f) else {}
    for im in images:
        if im["nom"] in taches:
            continue
        entree = {"prompt": im["prompt"], "aspect_ratio": im.get("ratio", "1:1"), "resolution": im.get("taille", "1K")}
        mode = "text-to-image"
        if im.get("ref"):
            entree["input_urls"] = im["ref"] if isinstance(im["ref"], list) else [im["ref"]]
            mode = "image-to-image"
        r = appel("/jobs/createTask", {"model": f"gpt-image-2-5-flare-{mode}", "input": entree})
        if r.get("code") != 200:
            print(im["nom"], "REFUS :", r.get("msg"))
            continue
        taches[im["nom"]] = r["data"]["taskId"]
        print(im["nom"], "lancée")
    json.dump(taches, open(taches_f, "w"), indent=1)
    print(f"{len(taches)} tâche(s) dans {taches_f}")


def recuperer(dossier):
    if FOURNISSEUR == "argolink":
        urls = json.load(open(os.path.join(dossier, "urls.json"))) if os.path.exists(os.path.join(dossier, "urls.json")) else {}
        print(f"ArgoLink : les images sont faites dès « lancer » ({len(urls)} prêtes). Relance « lancer » pour refaire celles en échec.")
        return
    taches = json.load(open(os.path.join(dossier, "taches.json")))
    urls_f = os.path.join(dossier, "urls.json")
    urls = json.load(open(urls_f)) if os.path.exists(urls_f) else {}
    os.makedirs(os.path.join(dossier, "images"), exist_ok=True)
    restantes = {n: t for n, t in taches.items() if n not in urls}
    credits = 0
    for _ in range(60):
        for nom, tid in list(restantes.items()):
            d = appel(f"/jobs/recordInfo?taskId={tid}")["data"]
            if d["state"] == "success":
                u = json.loads(d["resultJson"])["resultUrls"][0]
                urls[nom] = u
                urllib.request.urlretrieve(u, os.path.join(dossier, "images", nom + ".png"))
                credits += d.get("creditsConsumed") or 0
                print(nom, "ok")
                restantes.pop(nom)
            elif d["state"] == "fail":
                print(nom, "ÉCHEC :", d.get("failMsg"))
                restantes.pop(nom)
        if not restantes:
            break
        time.sleep(10)
    json.dump(urls, open(urls_f, "w"), indent=1)
    print("crédits consommés :", credits, "| encore en cours :", list(restantes))


def planche(dossier):
    from PIL import Image, ImageDraw
    d = os.path.join(dossier, "images")
    noms = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    if not noms:
        raise SystemExit("aucune image")
    L, col = 360, 4
    lignes = (len(noms) + col - 1) // col
    out = Image.new("RGB", (col * L, lignes * (L + 28)), "white")
    for i, n in enumerate(noms):
        im = Image.open(os.path.join(d, n)).convert("RGB")
        im.thumbnail((L - 8, L - 8))
        x, y = (i % col) * L, (i // col) * (L + 28)
        out.paste(im, (x + 4, y + 4))
        ImageDraw.Draw(out).text((x + 6, y + L + 6), n[:-4], fill="black")
    out.save(os.path.join(dossier, "planche.jpg"), quality=85)
    print("planche :", os.path.join(dossier, "planche.jpg"))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("lancer", "recuperer", "planche"):
        raise SystemExit(__doc__)
    {"lancer": lancer, "recuperer": recuperer, "planche": planche}[sys.argv[1]](sys.argv[2])
