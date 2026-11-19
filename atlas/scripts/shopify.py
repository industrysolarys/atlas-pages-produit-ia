"""Shopify par l'app privée « Claude » de chaque boutique (remplace le connecteur Shopify de claude.ai).

Les apps « Claude <pays> » (Dev Dashboard) donnent des jetons valables 24 h : le script les fabrique lui-même
(client_credentials) avec l'identifiant et le secret de l'app, et les garde en cache jusqu'à 5 min avant expiration.

Configuration, dans les variables d'environnement (environnement « Atlas » sur claude.ai/code) :
  SHOPIFY_BOUTIQUES=silibella-fr,silibella-us,decantic-it
  et pour chaque boutique (slug en majuscules, tirets → _) :
  SHOPIFY_SILIBELLA_FR_DOMAINE=xxxx.myshopify.com
  SHOPIFY_SILIBELLA_FR_CLIENT_ID=...
  SHOPIFY_SILIBELLA_FR_CLIENT_SECRET=...
  (optionnel) SHOPIFY_SILIBELLA_FR_NOM=Silibella FR
Ne jamais afficher, recopier ni écrire un secret ou un jeton ailleurs que dans le cache privé du script.

Usage :
  python3 atlas/scripts/shopify.py boutiques
      liste les boutiques configurées, vérifie la connexion et les droits d'écriture utiles à Atlas
  python3 atlas/scripts/shopify.py <boutique> <requete.graphql> [variables.json]
      envoie une requête ou une mutation GraphQL Admin et affiche la réponse JSON
      (<requete.graphql> peut être « - » pour lire la requête sur l'entrée standard)
Les mutations (écriture) ne se lancent qu'avec l'accord de l'utilisateur."""
import json, os, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

API = "2026-10"
CACHE = os.path.join(tempfile.gettempdir(), "atlas-shopify-jetons")
BESOINS = ["write_products", "write_files", "write_themes", "write_content", "write_publications"]


def cle(slug, champ):
    return os.environ.get(f"SHOPIFY_{slug.upper().replace('-', '_')}_{champ}", "").strip()


def liste():
    return [s.strip() for s in os.environ.get("SHOPIFY_BOUTIQUES", "").split(",") if s.strip()]


def config(slug):
    if slug not in liste():
        raise SystemExit(f"Boutique inconnue : {slug} (boutiques configurées : {', '.join(liste()) or 'aucune, voir SHOPIFY_BOUTIQUES'})")
    c = {k: cle(slug, k) for k in ("DOMAINE", "CLIENT_ID", "CLIENT_SECRET", "NOM")}
    manque = [k for k in ("DOMAINE", "CLIENT_ID", "CLIENT_SECRET") if not c[k] or c[k].startswith("COLLE_ICI")]
    if manque:
        raise SystemExit(f"{slug} : variable(s) manquante(s) {', '.join('SHOPIFY_' + slug.upper().replace('-', '_') + '_' + m for m in manque)}")
    return c


def jeton(slug):
    c = config(slug)
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    f = os.path.join(CACHE, f"{slug}.json")
    try:
        with open(f) as h:
            j = json.load(h)
        if j["expires_at"] > time.time() + 300 and j.get("client_id") == c["CLIENT_ID"]:
            return j["access_token"]
    except (OSError, KeyError, ValueError):
        pass
    corps = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": c["CLIENT_ID"], "client_secret": c["CLIENT_SECRET"]}).encode()
    req = urllib.request.Request(f"https://{c['DOMAINE']}/admin/oauth/access_token", corps, {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{slug} : Shopify refuse l'identifiant ou le secret de l'app (HTTP {e.code}). Vérifie les variables de cette boutique.")
    r = {"access_token": r["access_token"], "expires_at": time.time() + r.get("expires_in", 86399), "client_id": c["CLIENT_ID"]}
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as h:
        json.dump(r, h)
    return r["access_token"]


def graphql(slug, requete, variables=None):
    c = config(slug)
    corps = json.dumps({"query": requete, "variables": variables or {}}).encode()
    req = urllib.request.Request(f"https://{c['DOMAINE']}/admin/api/{API}/graphql.json", corps,
                                 {"Content-Type": "application/json", "X-Shopify-Access-Token": jeton(slug)})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:300]}"}]}


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "boutiques":
        if not liste():
            raise SystemExit("Aucune boutique configurée : ajoute SHOPIFY_BOUTIQUES et les variables de chaque boutique à l'environnement.")
        for s in liste():
            try:
                r = graphql(s, "{ shop { name } currentAppInstallation { accessScopes { handle } } }")
                if r.get("errors"):
                    print(f"{s} · erreur : {str(r['errors'])[:160]}")
                    continue
                d = [x["handle"] for x in r["data"]["currentAppInstallation"]["accessScopes"]]
                manque = [x for x in BESOINS if x not in d]
                print(f"{s} · {r['data']['shop']['name']} · " + ("prête pour Atlas" if not manque else f"il manque les droits {', '.join(manque)}"))
            except SystemExit as e:
                print(e)
        sys.exit(0)
    if len(a) < 2:
        raise SystemExit(__doc__)
    requete = sys.stdin.read() if a[1] == "-" else open(a[1]).read()
    variables = json.load(open(a[2])) if len(a) > 2 else None
    print(json.dumps(graphql(a[0], requete, variables), ensure_ascii=False, indent=1))
