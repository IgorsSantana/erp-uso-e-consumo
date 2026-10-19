'use strict';
window.Helpers = {
  escape(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); },
  money(value) { return Number(value || 0).toLocaleString('pt-BR', {style:'currency',currency:'BRL'}); },
  unitMoney(value) { return Number(value || 0).toLocaleString('pt-BR', {style:'currency',currency:'BRL',minimumFractionDigits:2,maximumFractionDigits:4}); },
  number(value) { return Number(value || 0).toLocaleString('pt-BR', {maximumFractionDigits:3}); },
  date(value, withTime = false) { if (!value) return '—'; const raw=String(value);const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw)?raw+'T12:00:00':raw.replace(' ', 'T')); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR', withTime ? {dateStyle:'short',timeStyle:'short'} : {dateStyle:'short'}); },
  toast(message, type = 'success') { const el=document.createElement('div');el.className=`toast toast-${type}`;el.textContent=message;const region=document.getElementById('toast-region');while(region?.children.length>=3)region.firstElementChild.remove();region?.append(el);setTimeout(()=>el.remove(),5500); },
  csv(filename, headers, rows) { const cell=v=>'"'+String(v??'').replace(/"/g,'""').replace(/^[=+@\-]/,'\t$&')+'"';const text='\uFEFF'+[headers,...rows].map(r=>r.map(cell).join(';')).join('\r\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8;'}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); },
  icons: {
    dashboard:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="11" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="18" width="7" height="3" rx="1"/>',
    estoque:'<path d="m3 7 9-4 9 4-9 4-9-4Zm0 0v10l9 4 9-4V7M12 11v10M7 5l10 4"/>',
    pedidos:'<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3"/>',
    contagem:'<path d="M8 4H5a2 2 0 0 0-2 2v3M16 4h3a2 2 0 0 1 2 2v3M21 15v3a2 2 0 0 1-2 2h-3M8 20H5a2 2 0 0 1-2-2v-3M7 12l3 3 7-7"/>',
    cotacoes:'<path d="M12 3v17M4 20h16M5 5h14M5 5 2 12h6L5 5Zm14 0-3 7h6l-3-7Z"/>',
    produtos:'<path d="M20 13 11 22 2 13V3h10l8 8a2 2 0 0 1 0 2Z"/><circle cx="7" cy="8" r="1.5"/>',
    fornecedores:'<path d="M3 7h11v12H3zM14 11h4l3 4v4h-7M3 12h7"/><circle cx="7" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
    cadastros:'<path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h1M14 10h1M9 14h1M14 14h1M10 21v-3h4v3"/>',
    usuarios:'<circle cx="9" cy="8" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2M18 4a4 4 0 0 1 0 8M20 15a6 6 0 0 1 2 4v2"/>'
  },
  icon(name) { return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${this.icons[name]||this.icons.estoque}</svg>`; }
};
