"""Shopify par l'app privée de chaque boutique (installation sur un Mac) : remplace le connecteur Shopify de claude.ai.
Le jeton de chaque boutique est dans ~/.config/shopify/<boutique>.env (SHOPIFY_NOM, SHOPIFY_DOMAINE, SHOPIFY_JETON),
lisible par l'utilisateur seul. Ne jamais afficher, recopier ni écrire le jeton ailleurs.

Usage :
  python3 atlas/scripts/shopify.py boutiques
      liste les boutiques disponibles et les droits de leur app (écriture produits / thèmes / fichiers…)
  python3 atlas/scripts/shopify.py <boutique> <requete.graphql> [variables.json]
      envoie une requête ou une mutation GraphQL Admin et affiche la réponse JSON
      (<requete.graphql> peut être « - » pour lire la requête sur l'entrée standard)
Les mutations (écriture) ne se lancent qu'avec l'accord de l'utilisateur, comme avec le connecteur."""
import json, os, sys, urllib.error, urllib.request

DOSSIER = os.path.expanduser("~/.config/shopify")
API = "2026-10"


def lire(slug):
    f = os.path.join(DOSSIER, f"{slug}.env")
    if not os.path.exists(f):
        raise SystemExit(f"Boutique inconnue : {slug} (boutiques : {', '.join(liste()) or 'aucune'})")
    v = {}
    for l in open(f):
        if "=" in l:
            k, x = l.rstrip("\n").split("=", 1)
            v[k] = x
    return v


def liste():
    return sorted(f[:-4] for f in os.listdir(DOSSIER) if f.endswith(".env")) if os.path.isdir(DOSSIER) else []


def graphql(slug, requete, variables=None):
    b = lire(slug)
    corps = json.dumps({"query": requete, "variables": variables or {}}).encode()
    req = urllib.request.Request(f"https://{b['SHOPIFY_DOMAINE']}/admin/api/{API}/graphql.json", corps,
                                 {"Content-Type": "application/json", "X-Shopify-Access-Token": b["SHOPIFY_JETON"]})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        return {"errors": [{"message": f"HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:300]}"}]}


def droits(slug):
    b = lire(slug)
    req = urllib.request.Request(f"https://{b['SHOPIFY_DOMAINE']}/admin/oauth/access_scopes.json", headers={"X-Shopify-Access-Token": b["SHOPIFY_JETON"]})
    try:
        return [s["handle"] for s in json.load(urllib.request.urlopen(req, timeout=30))["access_scopes"]]
    except Exception as e:
        return [f"illisible ({str(e)[:80]})"]


BESOINS = ["write_products", "write_files", "write_themes", "write_content", "write_publications"]

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "boutiques":
        for s in liste():
            d = droits(s)
            manque = [x for x in BESOINS if x not in d]
            print(f"{s} · {lire(s).get('SHOPIFY_NOM', s)} · " + ("prête pour Atlas" if not manque else f"lecture seule : il manque {', '.join(manque)}"))
        sys.exit(0)
    if len(a) < 2:
        raise SystemExit(__doc__)
    requete = sys.stdin.read() if a[1] == "-" else open(a[1]).read()
    variables = json.load(open(a[2])) if len(a) > 2 else None
    print(json.dumps(graphql(a[0], requete, variables), ensure_ascii=False, indent=1))
