// SYNTHETIC: runs the actual inline script of preview.html under a Node vm DOM stub (not a browser). Made by autonomous AI agents (GlobalLand BUILDER).
const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(process.argv[2],'utf8');const m=html.match(/<script>([\s\S]*?)<\/script>/g);
const src=html.split('<script>')[1].split('</script>')[0];
const els={};const mk=id=>({id,value:'',textContent:'',h:{},addEventListener(t,f){this.h[t]=f;}});
['paste','nid','run','out','bytes'].forEach(i=>els[i]=mk(i));
const net=[];const ctx={document:{getElementById:i=>els[i]},window:{},TextEncoder,crypto:globalThis.crypto,Date,console,
 fetch:()=>{net.push('fetch')},XMLHttpRequest:function(){net.push('xhr')},setTimeout};ctx.window.crypto=globalThis.crypto;ctx.window.fetch=ctx.fetch;
vm.createContext(ctx);vm.runInContext(src,ctx);
els.paste.value=fs.readFileSync(process.argv[3],'utf8');els.nid.value=process.argv[4];els.paste.h.input();
Promise.resolve(els.run.h.click()).then(()=>{process.stdout.write(JSON.stringify({scripts:m.length,out:els.out.textContent,bytes:els.bytes.textContent,net}));});
