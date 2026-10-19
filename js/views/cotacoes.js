'use strict';
(() => {
 let itemSequence=0;
 const active=rows=>rows.filter(row=>row.ativo!==false&&row.ativo!==0);
 const portalLink=token=>new URL('/portal_fornecedor.html?token='+encodeURIComponent(token),location.origin).href;
 const hasPrice=r=>!!r&&!r.indisponivel&&Number.isFinite(Number(r.preco))&&Number(r.preco)>0;
 const itemRow=()=>{
  const key=++itemSequence;
  return `<div class="item-row" data-quote-item><div class="form-field"><label for="quote-product-${key}">Produto <span aria-hidden="true">*</span></label><select class="field-control" id="quote-product-${key}" data-quote-product required>${App.options(active(Store.produtos).map(p=>({...p,label:p.id+' · '+p.nome})),'id','label')}</select></div><div class="form-field"><label for="quote-quantity-${key}">Quantidade</label><input class="field-control" id="quote-quantity-${key}" data-quote-quantity type="number" min="0.001" max="999999999" step="0.001" value="1" required></div><div class="form-field"><label for="quote-unit-${key}">Unidade</label><input class="field-control" id="quote-unit-${key}" data-quote-unit value="—" readonly tabindex="-1"></div>${App.button('Remover','remove-quote-item','type="button" aria-label="Remover produto da cotação"','danger')}</div>`;
 };
 App.views.cotacoes=async()=>{
  const list=await Store.request('/cotacoes');App.data.cotacoes=list;
  const rows=list.map(c=>App.row([`<span class="cell-title">${E(c.titulo)}</span><span class="cell-subtitle">#${E(c.id)} · Criada em ${H.date(c.criado_em)}</span>`,App.badge(c.status),H.date(c.data_limite),H.number(c.qtd_itens),`<span class="cell-title">${H.number(c.qtd_respostas)} / ${H.number(c.qtd_fornecedores)}</span><span class="cell-subtitle">fornecedores responderam</span>`,App.canManage?App.button('Comparar ofertas','view-quote',`data-id="${E(c.id)}"`,'secondary'):'<span class="muted">Detalhes restritos à gestão</span>'],c.id+' '+c.titulo+' '+c.status));
  return App.heading('Melhores compras começam aqui.','Convide fornecedores, compare condições e escolha o menor preço por produto.',App.button('Exportar CSV','export-table','','secondary')+(App.canManage?App.button('+ Nova cotação','new-quote'):''))+App.panel(list.length+' cotações',list.filter(c=>c.status==='Aberta').length+' abertas para receber propostas',App.toolbar('Buscar por título, número ou situação…')+App.table(['Cotação','Situação','Prazo das propostas','Itens','Participação','Ações'],rows));
 };
 App.actions['new-quote']=()=>{
  if(!App.canManage)return;
  const products=active(Store.produtos),suppliers=active(Store.fornecedores);
  if(!products.length||!suppliers.length){
   App.modal('Prepare sua primeira cotação','<p>Para criar uma cotação, cadastre pelo menos um produto ativo e um fornecedor ativo.</p><div class="row-actions"><a class="button button-secondary" href="#produtos" data-action="close-dialog">Ver produtos</a><a class="button button-secondary" href="#fornecedores" data-action="close-dialog">Ver fornecedores</a></div>',null,{readOnly:true});return;
  }
  const body=`<div class="form-grid">${App.field('titulo','Título da cotação','text','',{required:true,maxlength:150,full:true})}${App.field('data_limite','Receber propostas até','date','',{hint:'Opcional. O portal informa o prazo aos fornecedores.'})}${App.field('observacoes','Orientações aos fornecedores','textarea','',{maxlength:2000,full:true,hint:'Informe condições de entrega, marcas desejadas ou outras orientações.'})}</div><div class="panel-header"><div><h3 class="panel-title">Produtos e quantidades</h3><p class="panel-subtitle">Cada produto deve aparecer uma única vez.</p></div>${App.button('+ Adicionar produto','add-quote-item','type="button"','secondary')}</div><div class="line-items" id="quote-items">${itemRow()}</div><div class="panel-header"><div><h3 class="panel-title">Fornecedores convidados</h3><p class="panel-subtitle">Cada fornecedor terá um link exclusivo do portal.</p></div>${App.button('Marcar / desmarcar','toggle-quote-suppliers','type="button"','secondary')}</div><div class="form-field"><label for="quote-supplier-search">Buscar fornecedor</label><input class="field-control" id="quote-supplier-search" type="search" placeholder="Nome do fornecedor…" autocomplete="off"></div><div class="form-grid" id="quote-suppliers">${suppliers.map(f=>`<label class="checkbox-field" data-quote-supplier data-name="${E(f.nome_fantasia.toLocaleLowerCase('pt-BR'))}"><input type="checkbox" name="quote_supplier" value="${E(f.id)}">${E(f.nome_fantasia)}</label>`).join('')}</div>`;
  const form=App.modal('Nova cotação de compra',body,async(data,form)=>{
   const itens=Array.from(form.querySelectorAll('[data-quote-item]')).map(row=>({produto_id:row.querySelector('[data-quote-product]').value,quantidade:Number(row.querySelector('[data-quote-quantity]').value)}));
   const fornecedores=Array.from(form.querySelectorAll('input[name="quote_supplier"]:checked')).map(input=>Number(input.value));
   if(!data.titulo.trim())throw new Error('Informe um título para a cotação.');
   if(!itens.length||itens.length>500)throw new Error('Informe de 1 a 500 produtos.');
   if(itens.some(item=>!item.produto_id||!Number.isFinite(item.quantidade)||item.quantidade<=0))throw new Error('Selecione os produtos e informe quantidades maiores que zero.');
   if(new Set(itens.map(item=>item.produto_id)).size!==itens.length)throw new Error('Há um produto repetido. Consolide sua quantidade em uma única linha.');
   if(!fornecedores.length||fornecedores.length>100)throw new Error('Selecione de 1 a 100 fornecedores para participar.');
   await Store.request('/cotacoes',{method:'POST',body:{titulo:data.titulo.trim(),data_limite:data.data_limite||null,observacoes:data.observacoes.trim(),itens,fornecedores}});
   await App.navigate('cotacoes');H.toast('Cotação criada. Abra a comparação para copiar os links dos fornecedores.');
  },{wide:true,submit:'Criar cotação'});
  form.addEventListener('change',event=>{if(event.target.matches('[data-quote-product]')){const product=Store.produtos.find(p=>String(p.id)===event.target.value);event.target.closest('[data-quote-item]').querySelector('[data-quote-unit]').value=product?.unidade||'—';}});
  form.querySelector('#quote-supplier-search').addEventListener('input',event=>{const query=event.target.value.toLocaleLowerCase('pt-BR').trim();form.querySelectorAll('[data-quote-supplier]').forEach(label=>label.hidden=!label.dataset.name.includes(query));});
 };
 App.actions['add-quote-item']=()=>{const container=document.getElementById('quote-items');if(!container)return;if(container.children.length>=500)throw new Error('A cotação aceita no máximo 500 produtos.');container.insertAdjacentHTML('beforeend',itemRow());};
 App.actions['remove-quote-item']=(_,button)=>{
  const container=button.closest('#quote-items');if(!container)return;
  if(container.querySelectorAll('[data-quote-item]').length===1)throw new Error('Mantenha pelo menos um produto na cotação.');
  button.closest('[data-quote-item]').remove();
 };
 App.actions['toggle-quote-suppliers']=()=>{
  const boxes=Array.from(document.querySelectorAll('#quote-suppliers [data-quote-supplier]:not([hidden]) input')),check=boxes.some(box=>!box.checked);
  boxes.forEach(box=>box.checked=check);
 };
 App.actions['view-quote']=async({id})=>{
  if(!App.canManage)throw new Error('A comparação de ofertas está disponível para gestores e administradores.');
  const quote=await Store.request('/cotacoes/'+encodeURIComponent(id));App.data.quote=quote;
  const items=quote.itens||[],suppliers=quote.fornecedores||[],responses=quote.respostas||[];
  const priced=items.filter(item=>responses.some(r=>String(r.produto_id)===String(item.produto_id)&&hasPrice(r)));
  const total=items.reduce((sum,item)=>{const offers=responses.filter(r=>String(r.produto_id)===String(item.produto_id)&&hasPrice(r)),winner=offers.find(r=>r.vencedor);return sum+(offers.length?Number(winner?.preco??Math.min(...offers.map(r=>Number(r.preco))))*Number(item.quantidade):0);},0);
  const rows=items.map(item=>{
   const offers=responses.filter(r=>String(r.produto_id)===String(item.produto_id)&&hasPrice(r)),minimum=offers.length?Math.min(...offers.map(r=>Number(r.preco))):null;
   return App.row([`<span class="cell-title">${E(item.produto_nome)}</span><span class="cell-subtitle">${E(item.produto_id)} · ${H.number(item.quantidade)} ${E(item.unidade||'UN')}</span>`,...suppliers.map(supplier=>{
    const response=responses.find(r=>String(r.produto_id)===String(item.produto_id)&&String(r.fornecedor_id)===String(supplier.id));
    if(!response)return '<span class="muted">Aguardando proposta</span>';
    if(response.indisponivel)return '<span class="badge badge-neutral">Indisponível</span>';
    if(!hasPrice(response))return '<span class="muted">Sem oferta válida</span>';
    return `<span class="cell-title numeric">${H.unitMoney(response.preco)}</span><span class="cell-subtitle">Total: ${H.money(Number(response.preco)*Number(item.quantidade))}</span>${response.vencedor?'<span class="badge badge-success">Vencedor</span>':Number(response.preco)===minimum?'<span class="badge badge-success">Menor preço</span>':''}${response.prazo_entrega!==null&&response.prazo_entrega!==undefined?`<span class="cell-subtitle">Entrega: ${H.number(response.prazo_entrega)} ${Number(response.prazo_entrega)===1?'dia':'dias'}</span>`:''}${response.observacoes?`<span class="cell-subtitle">${E(response.observacoes)}</span>`:''}`;
   })],item.produto_nome);
  });
  const links=suppliers.map(supplier=>{
   const link=portalLink(supplier.token);
   return `<article class="quote-card"><h3>${E(supplier.nome_fantasia)}</h3>${App.badge(supplier.preencheu?'Proposta enviada':'Aguardando proposta')}${supplier.observacoes?`<p>${E(supplier.observacoes)}</p>`:''}<label class="field-hint" for="quote-link-${E(supplier.id)}">Link exclusivo do fornecedor</label><input class="field-control" id="quote-link-${E(supplier.id)}" value="${E(link)}" readonly><div class="row-actions">${App.button('Copiar link','copy-quote-link',`type="button" data-id="${E(supplier.id)}"`,'secondary')}<a class="button button-secondary" href="${E(link)}" target="_blank" rel="noopener noreferrer">Abrir portal ↗</a></div></article>`;
  }).join('');
  const actions=App.canManage&&quote.status==='Aberta'?`<div class="row-actions">${App.button('Encerrar e escolher vencedores','close-quote',`type="button" data-id="${E(quote.id)}" ${priced.length!==items.length?'disabled':''}`)}${App.button('Cancelar cotação','cancel-quote',`type="button" data-id="${E(quote.id)}"`,'danger')}</div><p class="field-hint">Para encerrar, todos os produtos precisam de uma proposta válida. O menor preço por produto determina o vencedor; o encerramento não movimenta o estoque.</p>`:App.canManage&&quote.status==='Encerrada'?`<div class="row-actions">${App.button('Gerar ordens de compra','purchase-from-quote',`type="button" data-id="${E(quote.id)}"`)}<a class="button button-secondary" href="#compras" data-action="close-dialog">Ver compras</a></div><p class="field-hint">Gere uma ordem por fornecedor vencedor e escolha a loja de destino. A entrada no estoque acontece ao confirmar o recebimento da compra.</p>`:'';
  const body=`<div class="panel-header"><div>${App.badge(quote.status)}<p class="panel-subtitle">Prazo: ${H.date(quote.data_limite)} · ${priced.length} de ${items.length} produtos com proposta válida</p></div>${App.button('Exportar comparação','export-quote','type="button"','secondary')}</div>${quote.observacoes?`<p class="page-description">${E(quote.observacoes)}</p>`:''}<div class="stats-grid"><article class="stat-card"><span class="stat-label">${quote.status==='Encerrada'?'Total das ofertas vencedoras':'Total dos menores preços'}</span><strong class="stat-value">${H.money(total)}</strong><span class="stat-caption">${priced.length<items.length?'Valor parcial: faltam propostas para alguns produtos.':'Considera as quantidades solicitadas.'}</span></article></div>${App.table(['Produto / quantidade',...suppliers.map(f=>f.nome_fantasia)],rows,'quote-comparison')}${actions}<div class="panel-header"><div><h3 class="panel-title">Portais dos fornecedores</h3><p class="panel-subtitle">Compartilhe cada link apenas com o fornecedor correspondente. O link dá acesso à proposta.</p></div></div><div class="quote-grid">${links}</div>`;
  App.modal(quote.titulo,body,null,{wide:true,readOnly:true,eyebrow:'COTAÇÃO #'+quote.id});
 };
 App.actions['copy-quote-link']=async({id})=>{
  const input=document.getElementById('quote-link-'+id);if(!input)return;
  try{await navigator.clipboard.writeText(input.value);H.toast('Link do fornecedor copiado.');}
  catch{input.focus();input.select();if(document.execCommand('copy'))H.toast('Link do fornecedor copiado.');else H.toast('Selecione o link e copie com Ctrl+C.','error');}
 };
 App.actions['close-quote']=({id})=>{
  if(!App.canManage)return;
  return App.confirm('Encerrar esta cotação?','O sistema escolherá o menor preço válido de cada produto e impedirá novas propostas. O encerramento não movimenta o estoque.',async()=>{await Store.request('/cotacoes/'+encodeURIComponent(id)+'/encerrar',{method:'POST'});await Store.loadCatalogs();await App.navigate('cotacoes');H.toast('Cotação encerrada. Abra a comparação para consultar os vencedores.');});
 };
 App.actions['cancel-quote']=({id})=>{
  if(!App.canManage)return;
  return App.confirm('Cancelar esta cotação?','Os fornecedores não poderão enviar novas propostas. O histórico será preservado.',async()=>{await Store.request('/cotacoes/'+encodeURIComponent(id)+'/cancelar',{method:'POST'});await App.navigate('cotacoes');H.toast('Cotação cancelada.');});
 };
 App.actions['purchase-from-quote']=({id})=>{
  if(!App.canManage)throw new Error('Somente gestores e administradores podem gerar ordens de compra.');
  if(!Store.lojas.length){App.modal('Cadastre uma loja de destino','<p>É necessário cadastrar uma loja para gerar as ordens desta cotação.</p><a class="button button-secondary" href="#cadastros" data-action="close-dialog">Cadastrar loja</a>',null,{readOnly:true});return;}
  App.modal('Gerar compras da cotação #'+id,`<p>Será gerada uma ordem de compra por fornecedor vencedor, com os preços e quantidades desta cotação. As ordens ficam pendentes até a conferência e o recebimento dos materiais.</p><div class="form-grid">${App.field('loja_id','Loja que receberá os materiais','select','',{items:Store.lojas,required:true,full:true})}</div><p class="field-hint">A geração pode ser realizada uma vez por cotação. Ordens existentes podem ser acompanhadas em Compras.</p>`,async(data)=>{if(!data.loja_id)throw new Error('Selecione a loja de destino.');const result=await Store.request('/cotacoes/'+encodeURIComponent(id)+'/compras',{method:'POST',body:{loja_id:Number(data.loja_id)}});await App.navigate('compras');H.toast(result.message||'Ordens de compra geradas com sucesso.');},{submit:'Gerar ordens de compra'});
 };
 App.actions['export-quote']=()=>{
  const quote=App.data.quote;if(!quote)return;const rows=[];
  for(const item of quote.itens||[])for(const supplier of quote.fornecedores||[]){
   const response=(quote.respostas||[]).find(r=>String(r.produto_id)===String(item.produto_id)&&String(r.fornecedor_id)===String(supplier.id));
   rows.push([item.produto_id,item.produto_nome,item.quantidade,item.unidade,supplier.nome_fantasia,response?.indisponivel?'Indisponível':hasPrice(response)?'Proposta enviada':'Aguardando',response?.indisponivel?'':response?.preco??'',hasPrice(response)?Number(response.preco)*Number(item.quantidade):'',response?.prazo_entrega||'',response?.observacoes||'',response?.vencedor?'Sim':'']);
  }
  H.csv('cotacao-'+quote.id+'.csv',['Código','Produto','Quantidade','Unidade','Fornecedor','Situação','Preço unitário','Total','Prazo de entrega','Observações','Vencedor'],rows);
 };
})();
