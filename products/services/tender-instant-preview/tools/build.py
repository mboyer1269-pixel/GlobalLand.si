# Builds preview.html and the minimal index.html link change. Made by autonomous AI agents (GlobalLand BUILDER).
import pathlib, difflib, hashlib, json
D = pathlib.Path('products/services/tender-instant-preview'); S = pathlib.Path('products/sites/open-software-tenders')
core = (D / 'src/core.js').read_text(encoding='utf-8')
base = (S / 'index.html').read_text(encoding='utf-8')
(D / 'baseline-index.html').write_text(base, encoding='utf-8')
UI = '''
(function(){var $=function(i){return document.getElementById(i);};
function cnt(){var n=new TextEncoder().encode($('paste').value).length;$('bytes').textContent=n+' / '+LIMIT+' bytes / octets';}
$('paste').addEventListener('input',cnt);
$('run').addEventListener('click',async function(){var o=$('out');o.textContent='...';
 if(!(window.crypto&&crypto.subtle)){o.textContent='This browser does not provide Web Crypto SHA-256 here; the preview cannot run. / Ce navigateur ne fournit pas SHA-256 (Web Crypto) ici.';return;}
 try{var r=await analyse($('paste').value,$('nid').value,new Date());o.textContent=r.text;}catch(e){o.textContent='Error / Erreur: '+String(e&&e.message||e);}});cnt();})();
'''
html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Free local preview: one-notice OCDS source check / Aperçu local gratuit</title>
<style>body{font-family:sans-serif;max-width:60rem;margin:1rem auto;padding:0 1rem}textarea{width:100%;height:14rem;font-family:monospace}pre{white-space:pre-wrap;background:#f4f4f4;padding:.5rem;border:1px solid #ccc}</style></head><body>
<p><strong>Made by autonomous AI agents (GlobalLand). / Fait par des agents d'IA autonomes (GlobalLand).</strong> Not legal or procurement advice. / Ce n'est pas un avis juridique ni en marchés publics.</p>
<h1>Free local preview: check one Find a Tender OCDS notice</h1>
<p>Paste the text of an official Find a Tender OCDS release package (JSON, under 20,000 bytes) and type its notice ID. The same checks as our proposed paid brief run <strong>entirely in your browser</strong>: nothing is uploaded, no link or portal is fetched, and this page makes no network requests (its Content-Security-Policy forbids them). The result quotes <strong>your pasted text</strong>: it is user-supplied, not authenticated official data. Compare the SHA-256 values and fields with the official notice yourself.</p>
<p>Limits: the raw SHA-256 covers the text as your browser holds it (line endings normalised to LF), so it can differ from a downloaded file's hash; the canonical hash is formatting-independent but proves nothing about authenticity. Tested for byte-identical output with our Python script under Node.js on synthetic and saved official inputs; not yet tested in a real browser. Free preview only: it is not an order. The CAD 49 brief described on the <a href="./">main page</a> is an unvalidated price hypothesis; any paid order would need separate administrative acceptance by a human operator.</p>
<h2>Aperçu local gratuit (français)</h2>
<p>Collez le texte d'un paquet de publication OCDS officiel Find a Tender (JSON, moins de 20 000 octets) et saisissez le numéro d'avis. Les vérifications s'exécutent entièrement dans votre navigateur : rien n'est envoyé, aucun lien n'est consulté. Le résultat cite votre texte collé, qui n'est pas une donnée officielle authentifiée. Aperçu gratuit, pas une commande ; le prix de 49 CAD reste une hypothèse non validée. Les sections détaillées du résultat sont en anglais, avec un résumé en français.</p>
<p><label for="nid">Notice ID / Numéro d'avis</label> <input id="nid" list="known" value="" size="16"><datalist id="known"><option value="105246-2026"><option value="105838-2026"></datalist> <span id="bytes"></span></p>
<p><label for="paste">OCDS JSON (pasted text / texte collé)</label><br><textarea id="paste" spellcheck="false"></textarea></p>
<p><button id="run" type="button">Check locally / Vérifier localement</button></p>
<pre id="out" aria-live="polite"></pre>
<script>
''' + core + UI + '''</script>
</body></html>
'''
EN = '<!--/offer-test-en-->'; FR = '<!--/offer-test-fr-->'
assert base.count(EN) == 1 and base.count(FR) == 1, (base.count(EN), base.count(FR))
LE = '<p><!--preview-en--><strong>Free local preview:</strong> <a href="preview.html">check a pasted OCDS notice in your browser</a> with the same checks, without uploading anything. Free, not an order.<!--/preview-en--></p>'
LF = '<p><!--preview-fr--><strong>Aperçu local gratuit :</strong> <a href="preview.html">vérifiez un avis OCDS collé dans votre navigateur</a>, avec les mêmes vérifications et sans rien envoyer. Gratuit, ce n’est pas une commande.<!--/preview-fr--></p>'
new = base.replace(EN, EN + LE).replace(FR, FR + LF)
(S / 'index.html').write_text(new, encoding='utf-8'); (S / 'preview.html').write_text(html, encoding='utf-8')
(D / 'candidate-index.html').write_text(new, encoding='utf-8'); (D / 'preview.html').write_text(html, encoding='utf-8')
(D / 'index.diff').write_text(''.join(difflib.unified_diff(base.replace('><', '>\n<').splitlines(True), new.replace('><', '>\n<').splitlines(True), 'a/index.html', 'b/index.html')), encoding='utf-8')
rev = new.replace(LE, '').replace(LF, '')
print(json.dumps({'reverse_restores_baseline': rev == base, 'index_sha256': hashlib.sha256(new.encode()).hexdigest(), 'baseline_sha256': hashlib.sha256(base.encode()).hexdigest(), 'preview_sha256': hashlib.sha256(html.encode()).hexdigest(), 'preview_bytes': len(html.encode())}))
