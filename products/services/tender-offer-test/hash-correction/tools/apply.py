# Made by autonomous AI agents (GlobalLand BUILDER). Applies G1/G3 corrections.
import pathlib, difflib, hashlib, json
NL = chr(10); BS = chr(92)
B = pathlib.Path('products/services/tender-offer-test')
HC = B / 'hash-correction'
HC.mkdir(parents=True, exist_ok=True)
old = (B / 'fulfillment/reconcile.py').read_text(encoding='utf-8')
OUT_DEF = 'def out(s):' + NL + '    sys.stdout.buffer.write((s + "' + BS + 'n").encode("utf-8"))' + NL + '    sys.stdout.buffer.flush()' + NL + 'def red(s):'
P = [
 ('ni en marches publics.', 'ni en marchés publics.'),
 ('REFUSED / REFUSE' + BS + 'nEN', 'REFUSED / REFUSÉ' + BS + 'nEN'),
 ('    print("REFUSED', '    out("REFUSED'),
 ('    print(txt)', '    out(txt)'),
 ('def red(s):', OUT_DEF),
 ('le texte colle fait', 'le texte collé fait'),
 ("le texte colle n'est pas", "le texte collé n'est pas"),
 ('dans le texte colle (identifiants', 'dans le texte collé (identifiants'),
 ('empreinte du texte verifie:', 'empreinte du texte vérifié :'),
 ('Whitespace-independent SHA-256 of this release (canonical JSON, sorted keys) / empreinte canonique:', "Formatting-independent SHA-256 of the selected release (canonical JSON: sorted keys, no spaces between elements; spaces inside text values still count; not proof of authenticity) / empreinte canonique (clés triées ; tolère la mise en forme, pas les espaces dans les valeurs ; ne prouve pas l'authenticité):"),
 ("Nous n'avons consulte aucun lien ni portail ; comparez vous-meme", "Nous n'avons consulté aucun lien ni portail ; comparez vous-même"),
 ('== Resume en francais ==', '== Résumé en français =='),
 ('publication collee', 'publication collée'),
 ('Voie de depot (citee)', 'Voie de dépôt (citée)'),
 ('Contradictions signalees', 'Contradictions signalées'),
 ('exigences citees', 'exigences citées'),
 ('(les notres)', '(les nôtres)'),
 ('par la voie de depot ; verifier chaque exigence ; comparer les ponderations', 'par la voie de dépôt ; vérifier chaque exigence ; comparer les pondérations'),
 ('votre admissibilite et inscription', 'votre admissibilité et inscription'),
 ("Aucune admissibilite n'est affirmee.", "Aucune admissibilité n'est affirmée."),
]
src = old
for a, b in P:
    n = src.count(a)
    assert n == 1, (a, n)
    src = src.replace(a, b)
compile(src, 'reconcile.py', 'exec')
(HC / 'reconcile.py').write_text(src, encoding='utf-8')
(HC / 'reconcile.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), src.splitlines(True), 'fulfillment/reconcile.py', 'hash-correction/reconcile.py')), encoding='utf-8')
S = pathlib.Path('products/sites/open-software-tenders/index.html')
base = S.read_bytes()
(HC / 'baseline-index.html').write_bytes(base)
t = base.decode('utf-8')
EA = 'and gives the SHA-256 of the text we checked.'
EN = ' Because email clients can reformat pasted text, the reply also gives a canonical SHA-256 of the selected release (JSON re-serialized with sorted keys and no spaces between elements): it stays the same if indentation or line breaks between elements change, but changes if any value changes, including spaces inside text values, and neither hash proves that the text is authentic or official.'
FA = 'et donne l’empreinte SHA-256 du texte vérifié.'
FR = ' Comme les logiciels de courriel peuvent reformater le texte collé, la réponse donne aussi une empreinte SHA-256 canonique de la publication choisie (JSON resérialisé avec clés triées et sans espaces entre les éléments) : elle reste identique si l’indentation ou les retours à la ligne entre éléments changent, mais change si une valeur change, y compris les espaces dans un texte, et aucune empreinte ne prouve que le texte est authentique ou officiel.'
assert t.count(EA) == 1 and t.count(FA) == 1
c = t.replace(EA, EA + EN).replace(FA, FA + FR)
S.write_text(c, encoding='utf-8')
(HC / 'candidate-index.html').write_text(c, encoding='utf-8')
(HC / 'index.diff').write_text(''.join(difflib.unified_diff(t.splitlines(True), c.splitlines(True), 'live/index.html', 'candidate/index.html')), encoding='utf-8')
(HC / 'inserted-sentences.json').write_text(json.dumps({'en_anchor': EA, 'en': EN, 'fr_anchor': FA, 'fr': FR}, indent=1, ensure_ascii=False), encoding='utf-8')
print('applied', hashlib.sha256(src.encode()).hexdigest(), hashlib.sha256(c.encode()).hexdigest())
