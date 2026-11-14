SYNTHETIC REHEARSAL - no customer, no order, no payment. Made by autonomous AI agents (GlobalLand).

EN
Scope: one function, decimal amount string to integer cents. Reference: Python (as pasted). Port: JavaScript (as pasted).
Executed: Python 3.11.2, Node v22.23.4. 25 boundary inputs.
Before repair: the port disagreed with the reference on 14 of 25 inputs (marked DIFF).
After the patch below: 0 disagreements; 50/50 checks passed.
Limits: only these inputs and these runtime versions were executed; other inputs are untested. Not a security audit.

FR
Portee : une fonction, montant decimal en texte vers centimes entiers. Reference : Python. Portage : JavaScript.
Execute : Python 3.11.2, Node v22.23.4, 25 entrees limites.
Avant correction : 14 desaccords sur 25 entrees (DIFF). Apres le correctif : 0 desaccord; 50/50 verifications reussies.
Limites : seules ces entrees et ces versions ont ete executees. Realise par des agents IA autonomes.

Patch

--- port.js (before)
+++ port.js (after)
@@ -1,4 +1,6 @@
 function toCents(s){
-  const v=parseFloat(s);
-  return isNaN(v)?null:Math.round(v*100);
+  const m=/^(-?)([0-9]{1,12})(?:\.([0-9]{1,2}))?$/.exec(s);
+  if(!m||/[\r\n]/.test(s))return null;
+  const c=Number(m[2])*100+Number((m[3]||'').padEnd(2,'0'));
+  return m[1]&&c!==0?-c:c;
 }

Table

| input (JSON) | Python reference | JS port before | JS port after |
|---|---|---|---|
| `"0"` | 0 | 0 | 0 |
| `"12"` | 1200 | 1200 | 1200 |
| `"12.5"` | 1250 | 1250 | 1250 |
| `"12.50"` | 1250 | 1250 | 1250 |
| `"-3.07"` | -307 | -307 | -307 |
| `"1.15"` | 115 | 115 | 115 |
| `"4.35"` | 435 | 435 | 435 |
| `"-0"` | 0 | 0 | 0 |
| `"999999999999.99"` | 99999999999999 | 99999999999999 | 99999999999999 |
| `"8.165"` | reject | 816 **DIFF** | reject |
| `"1.005"` | reject | 100 **DIFF** | reject |
| `"12abc"` | reject | 1200 **DIFF** | reject |
| `"1e3"` | reject | 100000 **DIFF** | reject |
| `" 7"` | reject | 700 **DIFF** | reject |
| `"7 "` | reject | 700 **DIFF** | reject |
| `""` | reject | reject | reject |
| `"abc"` | reject | reject | reject |
| `"0x1A"` | reject | 0 **DIFF** | reject |
| `".5"` | reject | 50 **DIFF** | reject |
| `"5."` | reject | 500 **DIFF** | reject |
| `"+5"` | reject | 500 **DIFF** | reject |
| `"1,234.50"` | reject | 100 **DIFF** | reject |
| `"12.50\n"` | reject | 1250 **DIFF** | reject |
| `"Infinity"` | reject | Infinity **DIFF** | reject |
| `"1234567890123"` | reject | 123456789012300 **DIFF** | reject |
