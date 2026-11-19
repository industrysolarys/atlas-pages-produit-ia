#!/bin/bash
# Installe Atlas dans la session cloud, que le dossier du dépôt soit branché ou non.
# Appelé par le « Script de configuration » de l'atelier Atlas (voir le guide).
pip install -q pillow 2>/dev/null || true

D="$HOME/atlas-methode"
if [ -d "$D/.git" ]; then
  git -C "$D" pull -q 2>/dev/null || true
else
  git clone -q --depth 1 https://github.com/industrysolarys/atlas-pages-produit-ia "$D" 2>/dev/null || true
fi
[ -f "$D/atlas/SKILL.md" ] || { echo "Atlas : téléchargement impossible"; exit 0; }

mkdir -p "$HOME/.claude/skills"
ln -sfn "$D/atlas" "$HOME/.claude/skills/atlas"

cat > "$HOME/.claude/CLAUDE.md" <<'EOF'
# Atlas
Tu es **Atlas**, le créateur de pages produit IA de l'élève (skill `atlas`).
Ta méthode complète est dans `~/atlas-methode`. Si le dossier `atlas-pages-produit-ia` n'est pas branché
sur cette session, lis `~/atlas-methode/CLAUDE.md` et suis-le à la lettre, en lançant tes commandes depuis
`~/atlas-methode` (les chemins `atlas/scripts/…` et `travail/` partent de là).
Quand l'élève envoie un lien de page produit concurrente, c'est toujours une demande de page produit :
applique le skill `atlas`, n'utilise aucun autre skill de création de boutique.
EOF
echo "Atlas installé"
