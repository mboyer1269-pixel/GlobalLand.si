// SYNTHETIC: runs preview.html inline script under a Node vm DOM stub (not a browser). Made by autonomous AI agents (GlobalLand BUILDER).
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(process.argv[2],'utf8');const src=html.split('<script>')[1].split('</script>')[0];
const els={};const mk=id=>({id,value:'',textContent:'',h:{},addEventListener(t,f){this.h[t]=f;}});
['paste','nid','run','out','bytes','ex'].forEach(i=>els[i]=mk(i));
const net=[];const ctx={document:{getElementById:i=>els[i]},window:{},TextEncoder,crypto:globalThis.crypto,Date,console,fetch:()=>{net.push('fetch')},XMLHttpRequest:function(){net.push('xhr')},setTimeout};ctx.window.crypto=globalThis.crypto;ctx.window.fetch=ctx.fetch;
vm.createContext(ctx);vm.runInContext(src,ctx);
(async()=>{const r={};els.ex.h.click();r.load={paste:els.paste.value,nid:els.nid.value,out:els.out.textContent,bytes:els.bytes.textContent};
await els.run.h.click();r.run1=els.out.textContent;
els.paste.value=els.paste.value.replace('2030-03-29T12:00:00Z','2030-04-30T12:00:00Z');els.paste.h.input();await els.run.h.click();r.run2=els.out.textContent;
els.nid.value='OTHER-1';await els.run.h.click();r.run3=els.out.textContent;r.net=net;process.stdout.write(JSON.stringify(r));})();
