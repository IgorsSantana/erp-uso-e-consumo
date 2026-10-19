'use strict';
window.Store = {
  user: null, csrfToken: null, produtos: [], lojas: [], secoes: [], fornecedores: [],
  async request(path, options = {}) {
    const method=options.method || 'GET';
    const headers={Accept:'application/json',...(options.body?{'Content-Type':'application/json'}:{}),...(this.csrfToken&&method!=='GET'?{'X-CSRF-Token':this.csrfToken}:{}),...options.headers};
    let response;
    try { response=await fetch(`/api${path}`,{...options,method,headers,credentials:'same-origin',body:options.body?JSON.stringify(options.body):undefined}); }
    catch { throw new Error('Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.'); }
    let data;try { data=await response.json(); } catch { data={}; }
    if (data.csrf_token) this.csrfToken=data.csrf_token;
    if (!response.ok) { if(response.status===401&&!['/login','/session'].includes(path)) location.replace('/login.html'); throw new Error(data.error||data.message||`Não foi possível concluir a operação (${response.status}).`); }
    return data;
  },
  async loadCatalogs() { const paths=['lojas','secoes','produtos','fornecedores'];const result=await Promise.all(paths.map(p=>this.request(`/${p}`)));paths.forEach((p,i)=>this[p]=Array.isArray(result[i])?result[i]:result[i].items||[]); },
  async session() { const result=await this.request('/session');this.user=result.user;return result; },
  async save(resource, data, id) { return this.request(`/${resource}${id!==undefined?`/${encodeURIComponent(id)}`:''}`,{method:id!==undefined?'PUT':'POST',body:data}); },
  async remove(resource,id) { return this.request(`/${resource}/${encodeURIComponent(id)}`,{method:'DELETE'}); }
};
